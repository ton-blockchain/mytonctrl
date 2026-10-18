from __future__ import annotations

import os
import os.path
import base64
import hashlib
import logging
import re
import pwd
import shlex
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import psutil
import subprocess
import requests
import json

from mypylib import MyPyClass
from mypylib.mypylib import (
	ip2int,
	Dict, int2ip
)
from mytoncore.models import Paths
from mytoncore.clients import ValidatorConsole
from mytonctrl.utils import is_hex, is_container
from mytoninstaller.archive_blocks import run_process_hardforks, parse_block_value, download_bag, update_init_block, \
	download_blocks_bag, download_master_blocks_bag
from mytoninstaller.context import InstallerContext, InstallerPaths
from mytoninstaller.utils import StartValidator, StartMytoncore, stop_service, \
	is_testnet, disable_service, add2systemd, get_ed25519_pubkey
from mytoninstaller.config import SetConfig, GetConfig, get_own_ip
from mytoninstaller.dump import download_dump


def _get_dir_from_path(path: str) -> str:
	return path[:path.rfind('/') + 1]


def _run_as_installer_user(user: str, args: list[str]):
	if not is_container():
		return subprocess.run(["su", "-l", user, "-c", ' '.join(args)])
	if user == "root":
		return subprocess.run(args, check=True)
	env = os.environ.copy()
	home = pwd.getpwnam(user).pw_dir
	env.update(HOME=home, USER=user, LOGNAME=user, XDG_DATA_HOME=os.path.join(home, ".local", "share"))
	return subprocess.run(["su", "-p", "-s", "/bin/sh", user, "-c", shlex.join(args)], env=env, check=True)


def _container_validator_threads() -> int:
	try:
		cpus = len(os.sched_getaffinity(0))
	except (AttributeError, OSError):
		cpus = psutil.cpu_count() or 1
	try:
		quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
		if quota != "max":
			cpus = min(cpus, max(1, int(quota) // int(period)))
	except (OSError, ValueError, ZeroDivisionError):
		pass
	return max(1, cpus - 1)


_VALIDATOR_CONSOLE_READY_TIMEOUT = 600
_VALIDATOR_CONSOLE_POLL_INTERVAL = 2
_VALIDATOR_CONSOLE_WAIT_LOG_INTERVAL = 30


def _validator_log_tail(path: Path) -> str:
	try:
		with path.open("rb") as source:
			source.seek(0, os.SEEK_END)
			offset = max(0, source.tell() - 8192)
			source.seek(offset)
			tail = source.read(8192).decode("utf-8", errors="replace")
		if offset:
			tail = tail.partition("\n")[2]
		return "\n".join(tail.splitlines()[-40:])
	except OSError:
		return ""


def _validator_failure(local: MyPyClass, message: str, log_path: Path) -> RuntimeError:
	tail = _validator_log_tail(log_path)
	logger = getattr(local, "logger", None)
	if tail and isinstance(logger, logging.Logger):
		# Preserve diagnostics in the existing installer file log without flooding stdout.
		record = logger.makeRecord(logger.name, logging.ERROR, __file__, 0,
								   f"Validator log tail ({log_path}):\n{tail}", (), None)
		while logger is not None:
			for handler in logger.handlers:
				if isinstance(handler, logging.FileHandler) and record.levelno >= handler.level:
					handler.handle(record)
			if not logger.propagate:
				break
			logger = logger.parent
	lines = [line.strip() for line in tail.splitlines() if line.strip()]
	reason = next((line for line in reversed(lines)
				   if re.search(r"fatal|error|failed|permission denied|assert|cannot|corrupt|unsupported", line, re.IGNORECASE)), "")
	if reason:
		message += f". Validator log: {reason[:500]}"
	return RuntimeError(f"{message}. See {log_path}; node data and dump cache were retained")


def _wait_validator_console(local: MyPyClass, ctx: InstallerContext):
	if not is_container():
		return
	keys = Path(ctx.paths.keys_dir)
	mconfig = GetConfig(ctx.mconfig_path)
	console_config = mconfig.validatorConsole
	console = ValidatorConsole(local, console_config.appPath, str(keys / "client"), str(keys / "server.pub"), console_config.addr)
	log_path = Path(ctx.paths.ton_log_path)
	started = time.monotonic()
	deadline = started + _VALIDATOR_CONSOLE_READY_TIMEOUT
	next_log = started
	previous_pid = None
	restarts = 0
	last_error = "no getstats response"
	while time.monotonic() < deadline:
		try:
			process = subprocess.run(
				["systemctl", "show", "validator", "--property=SubState,MainPID,ExecMainStatus"],
				capture_output=True, text=True, timeout=5, check=True,
			)
		except (OSError, subprocess.SubprocessError) as error:
			raise _validator_failure(local, f"Cannot inspect validator startup state: {error}", log_path) from error
		state = dict(line.split("=", 1) for line in process.stdout.splitlines() if "=" in line)
		substate = state.get("SubState", "").upper()
		if substate in ("FATAL", "EXITED", "STOPPED"):
			raise _validator_failure(local, f"Validator stopped during initialization ({substate}, exit {state.get('ExecMainStatus', 'unknown')})", log_path)
		try:
			pid = int(state.get("MainPID", "0"))
		except ValueError:
			pid = 0
		if pid and pid != previous_pid:
			if previous_pid is not None:
				restarts += 1
			previous_pid = pid
		if restarts >= 3:
			raise _validator_failure(local, "Validator repeatedly restarted before its console became ready", log_path)
		if substate == "RUNNING":
			try:
				result = console.run("getstats", timeout=5)
				if re.search(r"(?:^|\n)\s*unixtime\s+[1-9]\d*(?:\s|$)", result):
					local.add_log("Validator console is ready", "info")
					return
				last_error = "getstats did not return validator statistics"
			except Exception as error:
				last_error = " ".join(str(error).splitlines())[:250]
		else:
			last_error = f"validator service is {substate or 'not running'}"
		now = time.monotonic()
		if now >= next_log:
			local.add_log(f"Waiting for validator console ({int(now - started)}s elapsed): {last_error}", "info")
			next_log = now + _VALIDATOR_CONSOLE_WAIT_LOG_INTERVAL
		time.sleep(min(_VALIDATOR_CONSOLE_POLL_INTERVAL, max(0, deadline - now)))
	raise _validator_failure(local, f"Validator console did not become ready within {_VALIDATOR_CONSOLE_READY_TIMEOUT}s: {last_error}", log_path)


def _start_validator(local: MyPyClass):
	if not is_container():
		return StartValidator(local)
	local.add_log("Start/restart validator service", "debug")
	try:
		subprocess.run(["systemctl", "restart", "validator"], check=True)
	except subprocess.CalledProcessError as error:
		log_path = Path(os.getenv("TON_WORK_DIR") or "/var/ton-work") / "log"
		raise _validator_failure(local, f"Validator service could not start (exit {error.returncode})", log_path) from error
	time.sleep(10)


def _start_mytoncore(local: MyPyClass):
	# The container entrypoint starts enabled services once all settings are ready.
	if not is_container():
		StartMytoncore(local)


def _repair_node_ownership(ctx: InstallerContext):
	owner = f"{ctx.validator_user}:{ctx.validator_user}"
	subprocess.run(["chown", owner, ctx.paths.ton_work_dir], check=True)
	log_path = Path(ctx.paths.ton_log_path)
	logs = [str(path) for path in log_path.parent.glob(log_path.name + "*") if path.is_file()]
	subprocess.run(["chown", "-R", owner, ctx.paths.ton_db_dir], check=True)
	subprocess.run(["chown", owner, ctx.paths.keys_dir, *logs], check=True)
	client_keys = [str(Path(ctx.paths.keys_dir) / name) for name in ("client", "client.pub", "server.pub", "liteserver.pub")
				   if (Path(ctx.paths.keys_dir) / name).is_file()]
	if client_keys:
		subprocess.run(["chown", f"{ctx.user}:{ctx.user}", *client_keys], check=True)


def FirstNodeSettings(local: MyPyClass, ctx: InstallerContext):
	if ctx.only_mtc:
		return

	local.add_log("start FirstNodeSettings fuction", "debug")
	container = is_container()
	vuser = ctx.validator_user
	ton_work_dir = ctx.paths.ton_work_dir
	ton_db_dir = ctx.paths.ton_db_dir
	keys_dir = ctx.paths.keys_dir
	tonLogPath = ctx.paths.ton_log_path
	validatorAppPath = ctx.paths.validator_app_path
	globalConfigPath = ctx.paths.global_config_path
	vconfig_path = ctx.paths.vconfig_path
	vport = ctx.ports.validator
	marker = Path(ton_work_dir) / "controller/node-initialized.json"

	existing_config = os.path.isfile(vconfig_path)
	if existing_config and container:
		vconfig = GetConfig(vconfig_path)
		if not vconfig.get("addrs") or not isinstance(vconfig.get("control"), list) or not isinstance(vconfig.get("liteservers"), list):
			raise RuntimeError(f"Existing validator configuration is incomplete: {vconfig_path}; retained node keys and data were not replaced")
		local.add_log("Resuming node setup with the existing validator configuration and keyring", "info")
	if container and marker.exists():
		if not existing_config or GetConfig(str(marker)).get("version") != 1:
			raise RuntimeError(f"Invalid node initialization checkpoint: {marker}")
		_repair_node_ownership(ctx)
		_start_validator(local)
		return

	if ctx.archive_ttl is not None:
		archive_ttl = int(ctx.archive_ttl)
	else:
		archive_ttl = 2592000 if ctx.mode == 'liteserver' else 86400
	state_ttl = None
	if ctx.state_ttl is not None:
		state_ttl = int(ctx.state_ttl)
		archive_ttl -= state_ttl
	if archive_ttl == 0:
		archive_ttl = 1
	if existing_config and not container:
		local.add_log(f"Validators config '{vconfig_path}' already exist. Break FirstNodeSettings fuction", "warning")
		return

	with open("/etc/passwd", 'rt') as file:
		text = file.read()
	if vuser not in text:
		local.add_log("Creating new user: " + vuser, "debug")
		args = ["/usr/sbin/useradd", "-d", "/dev/null", "-s", "/dev/null", vuser]
		subprocess.run(args, check=container)
	os.makedirs(ton_db_dir, exist_ok=True)
	os.makedirs(keys_dir, exist_ok=True)

	if container:
		cpus = _container_validator_threads()
	else:
		cpus = psutil.cpu_count()
		if cpus is None:
			raise ValueError("Failed to get CPU count")
		cpus -= 1

	ttl_cmd = ''
	if archive_ttl == -1:
		archive_ttl = 10**9
		state_ttl = 10**9
		ttl_cmd += ' --permanent-celldb'
	if state_ttl is not None:
		ttl_cmd += f' --state-ttl {state_ttl}'
	ttl_cmd += f' --archive-ttl {archive_ttl}'
	cmd = f"{validatorAppPath} --threads {cpus} --daemonize --global-config {globalConfigPath} --db {ton_db_dir} --logname {tonLogPath} --verbosity 1"
	cmd += ttl_cmd
	if ctx.add_shard is not None:
		cmd += ' -M'
		for shard in ctx.add_shard.split():
			cmd += f' --add-shard {shard}'
	add2systemd(name="validator", user=vuser, start=cmd, pre='/bin/sleep 2')

	if not existing_config:
		ip = ctx.public_ip if ctx.public_ip is not None else get_own_ip()
		addr = f"{ip}:{vport}"
		local.add_log("Use addr: " + addr, "debug")
		local.add_log("First start validator - create config.json", "debug")
		args = [validatorAppPath, "--global-config", globalConfigPath, "--db", ton_db_dir, "--ip", addr, "--logname", tonLogPath]
		subprocess.run(args, check=container)
		if container and not os.path.isfile(vconfig_path):
			raise RuntimeError("Validator initialization did not create config.json")

	if container and (ctx.dump or ctx.archive_blocks):
		# The importer needs exclusive access to the node database, including on retry.
		subprocess.run(["systemctl", "stop", "validator"], check=True)
	if ctx.dump:
		if download_dump(local, ctx) is False:
			local.add_log("Dump download or extraction failed. Aborting node setup", "error")
			sys.exit(1)
	if ctx.archive_blocks:
		download_archive_from_ts(local, ctx)

	local.add_log("Chown ton-work dir", "debug")
	if container:
		_repair_node_ownership(ctx)
	else:
		subprocess.run(["chown", "-R", vuser + ':' + vuser, ton_work_dir])
	_start_validator(local)
	if container:
		marker.parent.mkdir(parents=True, exist_ok=True)
		SetConfig(str(marker), Dict(version=1))


def download_archive_from_ts(local: MyPyClass, ctx: InstallerContext):
	archive_blocks = ctx.archive_blocks
	if archive_blocks is None:
		raise ValueError("archive_blocks is not specified")
	downloads_path = f'{ctx.paths.ton_work_dir}ts-downloads/'
	os.makedirs(downloads_path, exist_ok=True)
	subprocess.run(["chmod", "o+wx", downloads_path])

	block_from, block_to = archive_blocks, None
	if len(archive_blocks.split()) > 1:
		block_from, block_to = archive_blocks.split()
	block_from, block_to = parse_block_value(local, block_from, ctx.paths.global_config_path), parse_block_value(local, block_to, ctx.paths.global_config_path)
	if block_from is None:
		raise ValueError(f"Invalid block_from value: {block_from}")
	block_from = max(1, block_from - 100)  # to download previous package as node may require some blocks from it

	from mytoninstaller.scripts.ton_storage import enable_ton_storage
	api_port = enable_ton_storage(ctx.user, ctx.mconfig_path, ctx.paths.global_config_path, ctx.paths.src_dir)
	url = 'https://archival-dump.ton.org/index/mainnet.json'
	if is_testnet(ctx.paths.global_config_path,):
		url = 'https://archival-dump.ton.org/index/testnet.json'

	state_bag = {}
	block_bags = []
	master_block_bags = []

	blocks_config = None

	for _ in range(5):
		try:
			blocks_config = requests.get(url, timeout=3).json()
			break
		except Exception as e:
			local.add_log(f"Failed to get blocks config: {e}. Retrying", "error")
			time.sleep(10)

	if blocks_config is None:
		local.add_log(f"Failed to get blocks config: {url}. Aborting installation", "error")
		sys.exit(1)

	for state in blocks_config['states']:
		if state['at_block'] > block_from:
			break
		state_bag = state
	block_from = state_bag['at_block']
	completed = False
	for block in blocks_config['blocks']:
		if completed:
			master_block_bags.append(block)
			continue
		if block_to is not None and block['from'] > block_to:
			completed = True
			master_block_bags.append(block)
			continue
		if block['to'] >= block_from:
			block_bags.append(block)

	if not state_bag or not block_bags:
		local.add_log("Skip downloading archive blocks: No bags found for the specified block", "error")
		if is_container():
			raise RuntimeError("No archive bags found for the requested blocks")
		return

	local.add_log(f"Downloading blockchain state for block {state_bag['at_block']}", "info")
	if not download_bag(local, state_bag['bag'], downloads_path, api_port):
		local.add_log("Error downloading state bag", "error")
		if is_container():
			raise RuntimeError("Archive state download failed; downloaded files were retained for retry")
		return


	update_init_block(local, state_bag['at_block'], ctx.paths.global_config_path)
	estimated_size = len(block_bags) * 4 * 2**30 + len(master_block_bags) * 4 * 2**30 * 0.2  # 4 GB per bag, 20% for master blocks

	local.add_log(f"Downloading archive blocks. Rough estimate total blocks size is {int(estimated_size / 2**30)} GB", "info")
	with ThreadPoolExecutor(max_workers=4) as executor:
		futures = [executor.submit(download_blocks_bag, local, bag, downloads_path, api_port) for bag in block_bags]
		futures += [executor.submit(download_master_blocks_bag, local, bag, downloads_path, api_port) for bag in master_block_bags]
		for future in as_completed(futures):
			try:
				future.result()
			except Exception as e:
				local.add_log(f"Error while downloading blocks: {e}", "error")
				if is_container():
					raise
				return

	local.add_log("Downloading blocks is completed, moving files", "info")

	archive_dir = ctx.paths.ton_db_dir + 'archive/'
	import_dir = ctx.paths.ton_db_dir + 'import/'
	os.makedirs(import_dir, exist_ok=True)
	states_dir = archive_dir + '/states'

	os.makedirs(states_dir, exist_ok=True)
	os.makedirs(import_dir, exist_ok=True)

	if not is_hex(state_bag['bag']):
		raise ValueError(f"Invalid bag {state_bag}")

	def _move_archive_item(src: Path, destination_dir: str):
		destination = Path(destination_dir) / src.name
		if destination.exists() or destination.is_symlink():
			if src.is_dir() or destination.is_dir():
				raise shutil.Error(f"Destination path '{destination}' already exists")
			destination.unlink()
		shutil.move(src, destination)

	source = Path(downloads_path) / state_bag["bag"]
	for state_dir in source.glob("state-*"):
		for item in state_dir.iterdir():
			_move_archive_item(item, states_dir)

	for bag in block_bags + master_block_bags:
		if not is_hex(bag['bag']):
			raise ValueError(f"Invalid bag {bag}")
		source = Path(downloads_path) / bag["bag"]
		for item in source.glob("*/*/*"):
			_move_archive_item(item, import_dir)
	subprocess.run(['rm', '-rf', downloads_path])

	stop_service(local, "ton_storage")  # stop TS
	disable_service(local, "ton_storage")

	from mytoninstaller.node_args import set_node_argument

	set_node_argument(['--skip-key-sync'])
	if block_to is not None:
		set_node_argument(['--sync-shards-upto', str(block_to)])

	with open(ctx.paths.global_config_path, 'r') as f:
		c = json.loads(f.read())
	if c['validator']['hardforks'] and c['validator']['hardforks'][-1]['seqno'] > block_from:
		run_process_hardforks(local, block_from, ctx.paths.mtc_src_dir, ctx.paths.global_config_path)

	local.add_log("Changing permissions on imported files", "info")
	subprocess.run(["chmod", "o+w", import_dir])
	mconfig_path = ctx.mconfig_path
	mconfig = GetConfig(path=mconfig_path)
	mconfig.importGc = True
	SetConfig(path=mconfig_path, data=mconfig)


def _public_key_from_private(path: Path) -> bytes:
	data = path.read_bytes()
	if len(data) != 36 or data[:4] != bytes.fromhex("17236849"):
		raise RuntimeError(f"Invalid existing Ed25519 private key: {path}; the key was not replaced")
	return bytes.fromhex("c6b41348") + get_ed25519_pubkey(data[4:])


def _write_missing_public_key(path: Path, data: bytes):
	temporary = path.with_name(path.name + ".tmp")
	temporary.write_bytes(data)
	temporary.replace(path)


def _read_public_key(path: Path) -> bytes:
	data = path.read_bytes()
	if len(data) != 36 or data[:4] != bytes.fromhex("c6b41348"):
		raise RuntimeError(f"Invalid existing Ed25519 public key: {path}; the key was not replaced")
	return data


def _keyring_key(keyring: Path, key_hash: bytes) -> Path:
	matches = [path for path in keyring.iterdir() if path.name.upper() == key_hash.hex().upper()]
	if len(matches) > 1:
		raise RuntimeError(f"Multiple keyring files have the same key ID in {keyring}")
	return matches[0] if matches else keyring / key_hash.hex().upper()


def _ensure_node_key(ctx: InstallerContext, name: str, records: list, port: int) -> tuple[str, Path]:
	private = Path(ctx.paths.keys_dir) / name
	public = private.with_name(name + ".pub")
	keyring = Path(ctx.paths.keyring_dir)
	keyring.mkdir(parents=True, exist_ok=True)
	if not public.exists():
		if private.exists():
			_write_missing_public_key(public, _public_key_from_private(private))
		elif records:
			candidates = [record for record in records if record.get("port") == port]
			if not candidates and len(records) == 1:
				candidates = records
			if len(candidates) != 1:
				raise RuntimeError(f"Cannot identify the existing {name} key; restore {public} without replacing node keys")
			key_hash = base64.b64decode(candidates[0]["id"], validate=True)
			if len(key_hash) != 32:
				raise RuntimeError(f"Invalid existing {name} key ID")
			data = _public_key_from_private(_keyring_key(keyring, key_hash))
			if hashlib.sha256(data).digest() != key_hash:
				raise RuntimeError(f"Existing {name} key does not match validator configuration")
			_write_missing_public_key(public, data)
		else:
			generate = ctx.paths.ton_bin_dir + "utils/generate-random-id"
			subprocess.run([generate, "--mode", "keys", "--name", str(private)], check=True, stdout=subprocess.PIPE)
	data = _read_public_key(public)
	key_hash = hashlib.sha256(data).digest()
	target = _keyring_key(keyring, key_hash)
	if private.exists():
		if _public_key_from_private(private) != data:
			raise RuntimeError(f"Existing private/public {name} keys do not match")
		if target.exists():
			if private.read_bytes() != target.read_bytes():
				raise RuntimeError(f"Refusing to replace existing node key: {target}")
			private.unlink()
		else:
			private.rename(target)
	if not target.is_file() or _public_key_from_private(target) != data:
		raise RuntimeError(f"Missing or mismatched existing node key: {target}")
	return base64.b64encode(key_hash).decode(), target


def _ensure_client_key(ctx: InstallerContext) -> str:
	private = Path(ctx.paths.keys_dir) / "client"
	public = private.with_name("client.pub")
	if not public.exists():
		if private.exists():
			_write_missing_public_key(public, _public_key_from_private(private))
		else:
			generate = ctx.paths.ton_bin_dir + "utils/generate-random-id"
			subprocess.run([generate, "--mode", "keys", "--name", str(private)], check=True, stdout=subprocess.PIPE)
	data = _read_public_key(public)
	if not private.is_file() or _public_key_from_private(private) != data:
		raise RuntimeError(f"Missing or mismatched existing validator-console client key: {private}")
	return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _configure_container_validator_console(local: MyPyClass, ctx: InstallerContext):
	vconfig = GetConfig(ctx.paths.vconfig_path)
	controls = vconfig.get("control")
	if not isinstance(controls, list):
		raise RuntimeError("Validator configuration has no valid control interfaces")
	server_id, key = _ensure_node_key(ctx, "server", controls, ctx.ports.validator_console)
	client_id = _ensure_client_key(ctx)
	matches = [control for control in controls if control.get("id") == server_id]
	if len(matches) > 1:
		raise RuntimeError("Validator configuration has multiple interfaces for the same console key")
	if matches:
		control = matches[0]
		port = int(control["port"])
	else:
		port = ctx.ports.validator_console
		if any(control.get("port") == port for control in controls):
			raise RuntimeError(f"Validator-console port {port} is already assigned to another key")
		control = Dict(id=server_id, port=port, allowed=[])
		controls.append(control)
	allowed = control.get("allowed")
	if not isinstance(allowed, list):
		raise RuntimeError("Validator-console allowed clients are invalid")
	client = next((item for item in allowed if item.get("id") == client_id), None)
	if client is None:
		allowed.append(Dict(id=client_id, permissions=15))
	else:
		client["permissions"] = 15
	SetConfig(ctx.paths.vconfig_path, vconfig)
	keys = Path(ctx.paths.keys_dir)
	subprocess.run(["chown", f"{ctx.validator_user}:{ctx.validator_user}", str(key)], check=True)
	subprocess.run(["chown", f"{ctx.user}:{ctx.user}", str(keys / "server.pub"), str(keys / "client"), str(keys / "client.pub")], check=True)
	_start_validator(local)
	mconfig = GetConfig(ctx.mconfig_path)
	mconfig.validatorConsole = Dict(
		appPath=ctx.paths.ton_bin_dir + "validator-engine-console/validator-engine-console",
		privKeyPath=str(keys / "client"), pubKeyPath=str(keys / "server.pub"), addr=f"127.0.0.1:{port}",
	)
	SetConfig(ctx.mconfig_path, mconfig)
	_wait_validator_console(local, ctx)
	if mconfig.get("containerEnableVcComplete") and (not mconfig.get("validatorWalletName") or not mconfig.get("adnlAddr")):
		raise RuntimeError("Validator-console setup checkpoint is missing its wallet or ADNL identity")
	if not mconfig.get("containerEnableVcComplete"):
		event = "enableVC" + (f"_{ctx.ports.quic}" if ctx.ports.quic is not None else "")
		_run_as_installer_user(ctx.user, [sys.executable, "-m", "mytoncore", "-e", event])


def _configure_container_liteserver(local: MyPyClass, ctx: InstallerContext):
	vconfig = GetConfig(ctx.paths.vconfig_path)
	servers = vconfig.get("liteservers")
	if not isinstance(servers, list):
		raise RuntimeError("Validator configuration has no valid liteservers")
	server_id, key = _ensure_node_key(ctx, "liteserver", servers, ctx.ports.liteserver)
	matches = [server for server in servers if server.get("id") == server_id]
	if len(matches) > 1:
		raise RuntimeError("Validator configuration has multiple liteservers for the same key")
	if matches:
		port = int(matches[0]["port"])
	else:
		port = ctx.ports.liteserver
		if any(server.get("port") == port for server in servers):
			raise RuntimeError(f"Liteserver port {port} is already assigned to another key")
		servers.append(Dict(id=server_id, port=port))
	SetConfig(ctx.paths.vconfig_path, vconfig)
	public = str(Path(ctx.paths.keys_dir) / "liteserver.pub")
	subprocess.run(["chown", f"{ctx.validator_user}:{ctx.validator_user}", str(key)], check=True)
	subprocess.run(["chown", f"{ctx.user}:{ctx.user}", public], check=True)
	_start_validator(local)
	mconfig = GetConfig(ctx.mconfig_path)
	mconfig.liteClient.liteServer = Dict(pubkeyPath=public, ip="127.0.0.1", port=port)
	SetConfig(ctx.mconfig_path, mconfig)


def FirstMytoncoreSettings(local: MyPyClass, ctx: InstallerContext):
	local.add_log("start FirstMytoncoreSettings fuction", "debug")
	user = ctx.user

	add2systemd(name="mytoncore", user=user, start=f"{sys.executable} -m mytoncore", force=not is_container())

	# Проверить конфигурацию
	path = ctx.mconfig_path
	if os.path.isfile(path):
		local.add_log(f"{path} already exist. Break FirstMytoncoreSettings fuction", "warning")
		return

	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path2):
		local.add_log(f"{path2}.db already exist. Break FirstMytoncoreSettings fuction", "warning")
		return

	#amazon bugfix
	path1 = "/home/{user}/.local/".format(user=user)
	path2 = path1 + "share/"
	chownOwner = "{user}:{user}".format(user=user)
	os.makedirs(path1, exist_ok=True)
	os.makedirs(path2, exist_ok=True)
	args = ["chown", chownOwner, path1, path2]
	subprocess.run(args)

	# Подготовить папку mytoncore
	mconfig_path = ctx.mconfig_path
	mconfigDir = _get_dir_from_path(mconfig_path)
	os.makedirs(mconfigDir, exist_ok=True)

	# create variables
	ton_bin_dir = ctx.paths.ton_bin_dir
	ton_src_dir = ctx.paths.ton_src_dir

	# general config
	mconfig = Dict()
	mconfig.config = Dict()
	mconfig.config.logLevel = "debug"
	mconfig.config.isLocaldbSaving = True

	# fift
	fift = Dict()
	fift.appPath = ton_bin_dir + "crypto/fift"
	fift.libsPath = ton_src_dir + "crypto/fift/lib"
	fift.smartcontsPath = ton_src_dir + "crypto/smartcont"
	mconfig.fift = fift

	# lite-client
	liteClient = Dict()
	liteClient.appPath = ton_bin_dir + "lite-client/lite-client"
	liteClient.configPath = ton_bin_dir + "global.config.json"
	mconfig.liteClient = liteClient

	mconfig.sendTelemetry = ctx.telemetry
	mconfig.paths = get_paths_dict(ctx.paths)
	SetConfig(path=mconfig_path, data=mconfig)

	# chown 1
	args = ["chown", user + ':' + user, mconfigDir, mconfig_path]
	subprocess.run(args)

	# start mytoncore
	_start_mytoncore(local)

def EnableValidatorConsole(local: MyPyClass, ctx: InstallerContext):
	if ctx.only_mtc:
		return
	if is_container():
		return _configure_container_validator_console(local, ctx)
	local.add_log("start EnableValidatorConsole function", "debug")

	# Create variables
	user = ctx.user
	vuser = ctx.validator_user
	cport = ctx.ports.validator_console
	ton_db_dir = ctx.paths.ton_db_dir
	ton_bin_dir = ctx.paths.ton_bin_dir
	vconfig_path = ctx.paths.vconfig_path
	generate_random_id = ton_bin_dir + "utils/generate-random-id"
	keys_dir = ctx.paths.keys_dir
	client_key = keys_dir + "client"
	server_key = keys_dir + "server"
	client_pubkey = client_key + ".pub"
	server_pubkey = server_key + ".pub"

	# Check if key exist
	if os.path.isfile(server_key):
		local.add_log(f"Server key '{server_key}' already exist. Break EnableValidatorConsole fuction", "warning")
		return

	if os.path.isfile(client_key):
		local.add_log(f"Client key '{client_key}' already exist. Break EnableValidatorConsole fuction", "warning")
		return

	# generate server key
	args = [generate_random_id, "--mode", "keys", "--name", server_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	server_key_hex = output_arr[0]
	server_key_b64 = output_arr[1].replace('\n', '')

	# move key
	newKeyPath = ton_db_dir + "/keyring/" + server_key_hex
	args = ["mv", server_key, newKeyPath]
	subprocess.run(args)

	# generate client key
	args = [generate_random_id, "--mode", "keys", "--name", client_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	client_key_b64 = output_arr[1].replace('\n', '')

	# chown 1
	args = ["chown", vuser + ':' + vuser, newKeyPath]
	subprocess.run(args)

	# chown 2
	args = ["chown", user + ':' + user, server_pubkey, client_key, client_pubkey]
	subprocess.run(args)

	# read vconfig
	vconfig = GetConfig(path=vconfig_path)

	# prepare config
	control = Dict()
	control.id = server_key_b64
	control.port = cport
	allowed = Dict()
	allowed.id = client_key_b64
	allowed.permissions = 15
	control.allowed = [allowed] # fix me
	vconfig.control.append(control)

	# write vconfig
	SetConfig(path=vconfig_path, data=vconfig)

	# restart validator
	StartValidator(local)

	# read mconfig
	mconfig_path = ctx.mconfig_path
	mconfig = GetConfig(path=mconfig_path)

	# edit mytoncore config file
	validatorConsole = Dict()
	validatorConsole.appPath = ton_bin_dir + "validator-engine-console/validator-engine-console"
	validatorConsole.privKeyPath = client_key
	validatorConsole.pubKeyPath = server_pubkey
	validatorConsole.addr = "127.0.0.1:{cport}".format(cport=cport)
	mconfig.validatorConsole = validatorConsole

	# write mconfig
	SetConfig(path=mconfig_path, data=mconfig)

	event_name = "enableVC"
	if ctx.ports.quic is not None:
		event_name += f'_{ctx.ports.quic}'

	cmd = f'{sys.executable} -m mytoncore -e "{event_name}"'
	subprocess.run(["su", "-l", user, "-c", cmd])

	# restart mytoncore
	_start_mytoncore(local)

def EnableLiteServer(local: MyPyClass, ctx: InstallerContext):
	if is_container():
		return _configure_container_liteserver(local, ctx)
	local.add_log("start EnableLiteServer function", "debug")

	# Create variables
	user = ctx.user
	vuser = ctx.validator_user
	lport = ctx.ports.liteserver
	ton_db_dir = ctx.paths.ton_db_dir
	keys_dir = ctx.paths.keys_dir
	ton_bin_dir = ctx.paths.ton_bin_dir
	vconfig_path = ctx.paths.vconfig_path
	generate_random_id = ton_bin_dir + "utils/generate-random-id"
	liteserver_key = keys_dir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"

	# Check if key exist
	if os.path.isfile(liteserver_pubkey):
		local.add_log(f"Liteserver key '{liteserver_pubkey}' already exist. Break EnableLiteServer fuction", "warning")
		return

	# generate liteserver key
	local.add_log("generate liteserver key", "debug")
	args = [generate_random_id, "--mode", "keys", "--name", liteserver_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	liteserver_key_hex = output_arr[0]
	liteserver_key_b64 = output_arr[1].replace('\n', '')

	# move key
	local.add_log("move key", "debug")
	newKeyPath = ton_db_dir + "/keyring/" + liteserver_key_hex
	args = ["mv", liteserver_key, newKeyPath]
	subprocess.run(args)

	# chown 1
	local.add_log("chown 1", "debug")
	args = ["chown", vuser + ':' + vuser, newKeyPath]
	subprocess.run(args)

	# chown 2
	local.add_log("chown 2", "debug")
	args = ["chown", user + ':' + user, liteserver_pubkey]
	subprocess.run(args)

	# read vconfig
	local.add_log("read vconfig", "debug")
	vconfig = GetConfig(path=vconfig_path)

	# prepare vconfig
	local.add_log("prepare vconfig", "debug")
	liteserver = Dict()
	liteserver.id = liteserver_key_b64
	liteserver.port = lport
	vconfig.liteservers.append(liteserver)

	# write vconfig
	local.add_log("write vconfig", "debug")
	SetConfig(path=vconfig_path, data=vconfig)

	# restart validator
	StartValidator(local)

	# edit mytoncore config file
	# read mconfig
	local.add_log("read mconfig", "debug")
	mconfig_path = ctx.mconfig_path
	mconfig = GetConfig(path=mconfig_path)

	# edit mytoncore config file
	local.add_log("edit mytoncore config file", "debug")
	liteServer = Dict()
	liteServer.pubkeyPath = liteserver_pubkey
	liteServer.ip = "127.0.0.1"
	liteServer.port = lport
	mconfig.liteClient.liteServer = liteServer

	# write mconfig
	local.add_log("write mconfig", "debug")
	SetConfig(path=mconfig_path, data=mconfig)

	# restart mytoncore
	_start_mytoncore(local)

def CreateSymlinks(local: MyPyClass, ctx: InstallerContext):
	local.add_log("start CreateSymlinks fuction", "debug")
	cport = ctx.ports.validator_console

	mytonctrl_file = "/usr/bin/mytonctrl"
	fift_file = "/usr/bin/fift"
	liteclient_file = "/usr/bin/lite-client"
	validator_console_file = "/usr/bin/validator-console"
	env_file = "/etc/environment"
	file = open(mytonctrl_file, 'wt')
	file.write(f'{sys.executable} -m mytonctrl "$@"')
	file.close()
	file = open(fift_file, 'wt')
	file.write(ctx.paths.ton_bin_dir + 'crypto/fift "$@"')
	file.close()
	file = open(liteclient_file, 'wt')
	file.write(ctx.paths.ton_bin_dir + f'lite-client/lite-client -C {ctx.paths.global_config_path} "$@"')
	file.close()
	if cport:
		file = open(validator_console_file, 'wt')
		file.write(ctx.paths.ton_bin_dir + f'validator-engine-console/validator-engine-console -k {ctx.paths.keys_dir}client -p {ctx.paths.keys_dir}server.pub -a 127.0.0.1:' + str(cport) + ' "$@"')
		file.close()
		args = ["chmod", "+x", validator_console_file]
		subprocess.run(args)
	args = ["chmod", "+x", mytonctrl_file, fift_file, liteclient_file]
	subprocess.run(args)

	# env
	fiftpath = f"export FIFTPATH={ctx.paths.ton_src_dir}crypto/fift/lib/:{ctx.paths.ton_src_dir}crypto/smartcont/"
	file = open(env_file, 'rt+')
	text = file.read()
	if fiftpath not in text:
		file.write(fiftpath + '\n')
	file.close()


def EnableMode(local: MyPyClass, ctx: InstallerContext):
	args = [sys.executable, "-m", "mytoncore", "-e"]
	if ctx.mode and ctx.mode != "none" and not ctx.backup:
		args.append("enable_mode_" + ctx.mode)
	else:
		return
	_run_as_installer_user(ctx.user, args)


def set_external_ip(local: MyPyClass, ip: str, mconfig_path: str):
	mconfig = GetConfig(path=mconfig_path)

	mconfig.liteClient.liteServer.ip = ip
	mconfig.validatorConsole.addr = f'{ip}:{mconfig.validatorConsole.addr.split(":")[1]}'

	# write mconfig
	local.add_log("write mconfig", "debug")
	SetConfig(path=mconfig_path, data=mconfig)


def ConfigureFromBackup(local: MyPyClass, ctx: InstallerContext):
	if not ctx.backup:
		return
	from modules.backups import BackupModule
	mconfig_path = ctx.mconfig_path
	mconfig_dir = _get_dir_from_path(mconfig_path)
	local.add_log("start ConfigureFromBackup function", "info")
	backup_file = ctx.backup

	os.makedirs(ctx.paths.ton_work_dir, exist_ok=True)
	ton_work_dir = ctx.paths.ton_work_dir.rstrip('/')
	if not ctx.only_mtc:
		public_ip = ctx.public_ip if is_container() and ctx.public_ip else get_own_ip()
		ip = str(ip2int(public_ip))
		exit_code = BackupModule.run_restore_backup(["-m", mconfig_dir, "-n", backup_file, "-i", ip, "-t", ton_work_dir], user=ctx.user)
	else:
		exit_code = BackupModule.run_restore_backup(["-m", mconfig_dir, "-n", backup_file, "-t", ton_work_dir], user=ctx.user)
	if is_container() and exit_code != 0:
		raise RuntimeError(f"Backup restoration failed with exit code {exit_code}; persistent state was retained for inspection")

	# the restored mconfig may carry the donor's paths. re-write the target ones
	write_paths(local, ctx)
	mconfig = GetConfig(path=mconfig_path)
	update_client_path_settings(mconfig, Paths.from_dict(get_paths_dict(ctx.paths)))
	SetConfig(path=mconfig_path, data=mconfig)
	_start_mytoncore(local)

	if ctx.only_mtc:
		local.add_log("Installing only mtc", "info")
		vconfig_path = ctx.paths.vconfig_path
		vconfig = GetConfig(path=vconfig_path)
		try:
			node_ip = int2ip(vconfig['addrs'][0]['ip'])
		except Exception:
			local.add_log("Can't get ip from validator", "error")
			return
		set_external_ip(local, node_ip, ctx.mconfig_path)


def ConfigureOnlyNode(local: MyPyClass, ctx: InstallerContext):
	if not ctx.only_node:
		return
	from modules.backups import BackupModule
	mconfig_path = ctx.mconfig_path
	mconfig_dir = _get_dir_from_path(mconfig_path)
	local.add_log("start ConfigureOnlyNode function", "info")

	db_dir = ctx.paths.ton_db_dir.rstrip('/')
	keys_dir = ctx.paths.keys_dir.rstrip('/')
	exit_code = BackupModule.run_create_backup(["-m", mconfig_dir, "-b", db_dir, "-k", keys_dir], user=ctx.user)
	if exit_code != 0:
		local.add_log("Backup creation failed", "error")
		return
	local.add_log("Backup successfully created. Use this file on the controller server with `--only-mtc` flag on installation.", "info")

	mconfig = GetConfig(path=mconfig_path)
	mconfig.onlyNode = True
	SetConfig(path=mconfig_path, data=mconfig)

	_start_mytoncore(local)


def SetInitialSync(local: MyPyClass, ctx: InstallerContext):
	mconfig_path = ctx.mconfig_path

	mconfig = GetConfig(path=mconfig_path)
	mconfig.initialSync = True
	SetConfig(path=mconfig_path, data=mconfig)

	_start_mytoncore(local)


def SetupCollator(local: MyPyClass, ctx: InstallerContext):
	if ctx.mode != "collator":
		return
	local.add_log("Setting up collator", "info")
	args = [sys.executable, "-m", "mytoncore", "-e", "setup_collator"]
	_run_as_installer_user(ctx.user, args)


def get_paths_dict(paths: InstallerPaths) -> dict[str, str]:
	return {
		'ton_work': paths.ton_work_dir,
		'ton_db': paths.ton_db_dir,
		'ton_keys': paths.keys_dir,
		'ton_src': paths.ton_src_dir,
		'ton_bin': paths.ton_bin_dir,
		'mtc_src': paths.mtc_src_dir,
		'src_dir': paths.src_dir,
	}


def write_paths(local: MyPyClass, ctx: InstallerContext):
	local.add_log("start write_paths function", "debug")
	mconfig_path = ctx.mconfig_path
	if not os.path.isfile(mconfig_path):
		local.add_log(f"write_paths: {mconfig_path} does not exist, skipping", "warning")
		return
	mconfig = GetConfig(path=mconfig_path)
	mconfig['paths'] = get_paths_dict(ctx.paths)
	SetConfig(path=mconfig_path, data=mconfig)


def update_client_path_settings(db: Dict, paths: Paths):
	fift = db.get('fift')
	if fift is not None:
		fift['appPath'] = str(paths.ton_bin / 'crypto/fift')
		fift['libsPath'] = str(paths.ton_src / 'crypto/fift/lib')
		fift['smartcontsPath'] = str(paths.ton_src / 'crypto/smartcont')
	lite_client = db.get('liteClient')
	if lite_client is not None:
		lite_client['appPath'] = str(paths.ton_bin / 'lite-client/lite-client')
		lite_client['configPath'] = str(paths.global_config_path)
		lite_server = lite_client.get('liteServer')
		if lite_server is not None:
			lite_server['pubkeyPath'] = str(paths.ton_keys / 'liteserver.pub')
	validator_console = db.get('validatorConsole')
	if validator_console is not None:
		validator_console['appPath'] = str(paths.ton_bin / 'validator-engine-console/validator-engine-console')
		validator_console['privKeyPath'] = str(paths.ton_keys / 'client')
		validator_console['pubKeyPath'] = str(paths.ton_keys / 'server.pub')
