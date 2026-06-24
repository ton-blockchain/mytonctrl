from __future__ import annotations

import os
import os.path
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
from mytonctrl.utils import is_hex
from mytoninstaller.archive_blocks import run_process_hardforks, parse_block_value, download_bag, update_init_block, \
	download_blocks_bag, download_master_blocks_bag
from mytoninstaller.context import InstallerContext, InstallerPaths
from mytoninstaller.utils import StartValidator, StartMytoncore, start_service, stop_service, \
	is_testnet, disable_service, add2systemd
from mytoninstaller.config import SetConfig, GetConfig, get_own_ip


def _get_dir_from_path(path: str) -> str:
	return path[:path.rfind('/') + 1]


def FirstNodeSettings(local: MyPyClass, ctx: InstallerContext):
	if ctx.only_mtc:
		return

	local.add_log("start FirstNodeSettings fuction", "debug")

	# Создать переменные
	vuser = ctx.validator_user
	ton_work_dir = ctx.paths.ton_work_dir
	ton_db_dir = ctx.paths.ton_db_dir
	keys_dir = ctx.paths.keys_dir
	tonLogPath = ctx.paths.ton_log_path
	validatorAppPath = ctx.paths.validator_app_path
	globalConfigPath = ctx.paths.global_config_path
	vconfig_path = ctx.paths.vconfig_path
	vport = ctx.ports.validator

	if ctx.archive_ttl is not None:
		archive_ttl = int(ctx.archive_ttl)
	else:
		archive_ttl = 2592000 if ctx.mode == 'liteserver' else 86400
	state_ttl = None
	if ctx.state_ttl is not None:
		state_ttl = int(ctx.state_ttl)
		archive_ttl -= state_ttl
	if archive_ttl == 0:
		archive_ttl = 1  # todo: remove this when archive_ttl==0 will be allowed in node

	# Проверить конфигурацию
	if os.path.isfile(vconfig_path):
		local.add_log(f"Validators config '{vconfig_path}' already exist. Break FirstNodeSettings fuction", "warning")
		return

	# Создать пользователя
	file = open("/etc/passwd", 'rt')
	text = file.read()
	file.close()
	if vuser not in text:
		local.add_log("Creating new user: " + vuser, "debug")
		args = ["/usr/sbin/useradd", "-d", "/dev/null", "-s", "/dev/null", vuser]
		subprocess.run(args)

	# Подготовить папки валидатора
	os.makedirs(ton_db_dir, exist_ok=True)
	os.makedirs(keys_dir, exist_ok=True)

	# Прописать автозагрузку
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
		add_shard = ctx.add_shard
		cmd += ' -M'
		for shard in add_shard.split():
			cmd += f' --add-shard {shard}'

	add2systemd(name="validator", user=vuser, start=cmd, pre='/bin/sleep 2')

	if ctx.public_ip is not None:
		ip = ctx.public_ip
	else:
		ip = get_own_ip()
	addr = "{ip}:{vport}".format(ip=ip, vport=vport)
	local.add_log("Use addr: " + addr, "debug")

	# Первый запуск
	local.add_log("First start validator - create config.json", "debug")
	args = [validatorAppPath, "--global-config", globalConfigPath, "--db", ton_db_dir, "--ip", addr, "--logname", tonLogPath]
	subprocess.run(args)

	if ctx.dump:
		if DownloadDump(local, ctx) is False:
			local.add_log("Dump download or extraction failed. Aborting node setup", "error")
			sys.exit(1)
	if ctx.archive_blocks:
		download_archive_from_ts(local, ctx)

	# chown 1
	local.add_log("Chown ton-work dir", "debug")
	args = ["chown", "-R", vuser + ':' + vuser, ton_work_dir]
	subprocess.run(args)

	# start validator
	StartValidator(local)


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
		return

	local.add_log(f"Downloading blockchain state for block {state_bag['at_block']}", "info")
	if not download_bag(local, state_bag['bag'], downloads_path, api_port):
		local.add_log("Error downloading state bag", "error")
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


def DownloadDump(local: MyPyClass, ctx: InstallerContext):
    local.add_log("start DownloadDump function", "debug")
    base_url = "https://dump.ton.org/dumps"
    dump_name = "latest"
    if is_testnet(ctx.paths.global_config_path):
        dump_name += '_testnet'
    #end if
    dump_dir = ctx.paths.ton_db_dir
    dump_cache_dir = GetDumpCacheDir(ctx.paths.ton_work_dir)
    os.makedirs(dump_dir, exist_ok=True)
    os.makedirs(dump_cache_dir, exist_ok=True)
    CleanupDumpTempFiles(local, os.path.join(dump_dir, "latest.tar.lz"))
    CleanupDumpTempFiles(local, os.path.join(dump_cache_dir, "latest.tar.lz"))

    try:
        dump_metadata = GetDumpMetadata(base_url, dump_name)
    except Exception as e:
        local.add_log(f"Failed to get dump metadata: {e}", "error")
        return False
    #end try

    archive_name = dump_metadata["archive_name"]
    temp_file = os.path.join(dump_cache_dir, archive_name)
    CleanupDumpTempFiles(local, os.path.join(dump_dir, archive_name))
    CleanupDumpTempFiles(local, temp_file)
    dumpSize = dump_metadata["archive_size"]
    print("dumpName:", archive_name)
    print("dumpSize:", dumpSize)
    print("dumpDiskSize:", dump_metadata["disk_size"])
    print("dumpCacheDir:", dump_cache_dir)
    if not CheckDumpSpace(local, dump_dir, dump_cache_dir, dump_metadata):
        return False
    #end if

    # apt install
    apt_result = subprocess.run(["apt", "install", "plzip", "aria2", "curl", "-y"]).returncode
    if apt_result != 0:
        local.add_log(f"Failed to install dump tools with exit code {apt_result}", "error")
        return False
    #end if

    # download dump using aria2c to a temporary file
    cmd = [
        "aria2c",
        "-x", "8",
        "-s", "8",
        "--enable-http-keep-alive=false",
        "--retry-wait=5",
        "--max-tries=20",
        "--connect-timeout=60",
        "--timeout=120",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--check-integrity=true",
        f"--checksum=sha-256={dump_metadata['sha256']}",
        "-c",
        f"{base_url}/{archive_name}",
        "-d", dump_cache_dir,
        "-o", archive_name,
    ]
    download_started_at = time.monotonic()
    download_result = subprocess.run(cmd).returncode
    download_elapsed = FormatElapsedTime(time.monotonic() - download_started_at)
    if download_result != 0 or not os.path.exists(temp_file):
        local.add_log(f"Dump download failed after {download_elapsed}: {temp_file}", "error")
        CleanupDumpTempFiles(local, temp_file)
        return False
    #end if
    if os.path.getsize(temp_file) != dump_metadata["archive_size"]:
        local.add_log(f"Dump download size mismatch after {download_elapsed}: {temp_file}", "error")
        CleanupDumpTempFiles(local, temp_file)
        return False
    #end if
    checksum_started_at = time.monotonic()
    checksum_result = VerifyDumpChecksum(local, dump_cache_dir, archive_name, dump_metadata["sha256"])
    checksum_elapsed = FormatElapsedTime(time.monotonic() - checksum_started_at)
    if checksum_result is False:
        local.add_log(f"Dump checksum verification failed after {checksum_elapsed}: {temp_file}", "error")
        CleanupDumpTempFiles(local, temp_file)
        return False
    #end if
    local.add_log(f"Dump checksum verified in {checksum_elapsed}: {temp_file}", "info")

    if DumpBoolEnv("DUMP_VALIDATE_BEFORE_EXTRACT", False):
        validation_started_at = time.monotonic()
        validation_result = ValidateDumpArchive(local, temp_file)
        validation_elapsed = FormatElapsedTime(time.monotonic() - validation_started_at)
        if validation_result != 0:
            local.add_log(f"Dump lzip validation failed after {validation_elapsed}: {temp_file}", "error")
            CleanupDumpTempFiles(local, temp_file)
            return False
        #end if
        local.add_log(f"Dump lzip validation succeeded in {validation_elapsed}: {temp_file}", "info")
    #end if

    # process the downloaded file
    archive_size = os.path.getsize(temp_file)
    msg = f"Dump downloaded to {temp_file} in {download_elapsed}. Starting extraction to {dump_dir}"
    print(msg, flush=True)
    local.add_log(msg, "info")
    extraction_started_at = time.monotonic()
    extraction_result = ExtractDump(local, archive_size, temp_file, dump_dir)
    extraction_elapsed = FormatElapsedTime(time.monotonic() - extraction_started_at)
    if extraction_result != 0:
        local.add_log(f"Dump extraction failed after {extraction_elapsed}", "error")
        CleanupDumpTempFiles(local, temp_file)
        return False
    #end if
    msg = f"Dump extracted to {dump_dir} in {extraction_elapsed}"
    print(msg, flush=True)
    local.add_log(msg, "info")

    # clean up the temporary file after processing
    CleanupDumpTempFiles(local, temp_file)
    return True
#end define


def CleanupDumpTempFiles(local, temp_file):
    for path in [temp_file, temp_file + ".aria2"]:
        if os.path.exists(path):
            os.remove(path)
            local.add_log(f"Temporary file {path} removed", "debug")
        #end if
    #end for
#end define


def DumpBoolEnv(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")
#end define


def DumpExtractThreads():
    value = os.getenv("DUMP_EXTRACT_THREADS", "8")
    try:
        threads = int(value)
    except ValueError:
        return 8
    if threads < 1:
        return 8
    return threads
#end define


def GetDumpCacheDir(ton_work_dir):
    return os.getenv("DUMP_CACHE_DIR") or os.path.join(ton_work_dir, "dump-cache")
#end define


def CheckDumpSpace(local, dump_dir, dump_cache_dir, dump_metadata):
    archive_size = dump_metadata["archive_size"]
    disk_size = dump_metadata["disk_size"]

    dump_usage = psutil.disk_usage(dump_dir)
    cache_usage = psutil.disk_usage(dump_cache_dir)

    if os.stat(dump_dir).st_dev == os.stat(dump_cache_dir).st_dev:
        need_space = archive_size + disk_size
        if need_space > dump_usage.free:
            local.add_log(f"Not enough disk space in {dump_dir}: need {need_space}, free {dump_usage.free}", "error")
            return False
        #end if
        return True
    #end if

    if archive_size > cache_usage.free:
        local.add_log(f"Not enough disk space in {dump_cache_dir}: need {archive_size}, free {cache_usage.free}", "error")
        return False
    #end if
    if disk_size > dump_usage.free:
        local.add_log(f"Not enough disk space in {dump_dir}: need {disk_size}, free {dump_usage.free}", "error")
        return False
    #end if
    return True
#end define


def GetDumpMetadata(base_url, dump_name):
    latest_name = DumpFetchText(f"{base_url}/{dump_name}.tar.name.txt", timeout=10)
    if not latest_name:
        raise RuntimeError(f"empty dump name for {dump_name}")
    #end if

    metadata_name = os.path.basename(latest_name)
    archive_name = metadata_name
    if not archive_name.endswith(".lz"):
        archive_name += ".lz"
    else:
        metadata_name = archive_name[:-3]
    #end if

    sha_text = DumpFetchText(f"{base_url}/{metadata_name}.sha256sum.txt", timeout=10)
    sha_parts = sha_text.split()
    if not sha_parts:
        raise RuntimeError(f"empty dump sha256 for {metadata_name}")
    #end if
    sha256 = sha_parts[0]
    if len(sha256) != 64:
        raise RuntimeError(f"invalid dump sha256 for {metadata_name}: {sha256}")
    #end if
    if len(sha_parts) > 1 and os.path.basename(sha_parts[1]) != archive_name:
        raise RuntimeError(f"dump sha256 file does not match archive {archive_name}: {sha_parts[1]}")
    #end if

    archive_size = int(DumpFetchText(f"{base_url}/{metadata_name}.size.archive.txt", timeout=10))
    disk_size = int(DumpFetchText(f"{base_url}/{metadata_name}.size.disk.txt", timeout=10))
    return {
        "archive_name": archive_name,
        "sha256": sha256,
        "archive_size": archive_size,
        "disk_size": disk_size,
    }
#end define


def DumpFetchText(url, timeout=10):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text.strip()
#end define


def VerifyDumpChecksum(local, dump_dir, archive_name, sha256):
    checksum_line = f"{sha256}  {archive_name}\n"
    result = subprocess.run(
        ["sha256sum", "-c", "-"],
        input=checksum_line,
        text=True,
        cwd=dump_dir,
        capture_output=True,
    )
    output = "\n".join([result.stdout.strip(), result.stderr.strip()]).strip()
    if output:
        print(output, flush=True)
        local.add_log(output, "debug" if result.returncode == 0 else "error")
    #end if
    return result.returncode == 0
#end define


def ValidateDumpArchive(local, temp_file):
    threads = DumpExtractThreads()
    local.add_log(f"Validating lzip archive before extraction: file={temp_file} threads={threads}", "info")
    return subprocess.run(["plzip", "-tvv", f"-n{threads}", temp_file]).returncode
#end define


def FormatElapsedTime(elapsed):
    total_seconds = int(elapsed)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    #end if
    if minutes:
        return f"{minutes}m {seconds}s"
    #end if
    return f"{seconds}s"
#end define


def UseInteractiveExtractionProgress():
    if not sys.stderr.isatty():
        return False
    # Container log collectors usually need newline-delimited output, even if a TTY is allocated.
    if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
        return False
    if os.getenv("KUBERNETES_SERVICE_HOST") or os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
        return False
    return True
#end define


def ExtractDump(local, archive_size, temp_file, dump_dir):
    threads = DumpExtractThreads()
    local.add_log(f"Extracting dump with plzip regular-file input: file={temp_file} dir={dump_dir} threads={threads}", "info")
    extract_cmd = 'plzip -cd -n"$3" -- "$1" | tar -xf - -C "$2"'
    # Use bash for pipefail so decompressor and tar failures are both surfaced.
    result = subprocess.run([
        "bash", "-o", "pipefail", "-c", extract_cmd,
        "extract-dump", temp_file, dump_dir, str(threads)
    ])
    if result.returncode != 0:
        local.add_log(f"Dump extraction failed with exit code {result.returncode}", "error")
    return result.returncode
#end define

def FirstMytoncoreSettings(local: MyPyClass, ctx: InstallerContext):
	local.add_log("start FirstMytoncoreSettings fuction", "debug")
	user = ctx.user

	add2systemd(name="mytoncore", user=user, start=f"{sys.executable} -m mytoncore", force=True)

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
	StartMytoncore(local)

def EnableValidatorConsole(local: MyPyClass, ctx: InstallerContext):
	if ctx.only_mtc:
		return
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
	args = ["su", "-l", user, "-c", cmd]
	subprocess.run(args)

	# restart mytoncore
	StartMytoncore(local)

def EnableLiteServer(local: MyPyClass, ctx: InstallerContext):
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
	StartMytoncore(local)

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
	args = ["su", "-l", ctx.user, "-c", ' '.join(args)]
	subprocess.run(args)


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
		ip = str(ip2int(get_own_ip()))
		BackupModule.run_restore_backup(["-m", mconfig_dir, "-n", backup_file, "-i", ip, "-t", ton_work_dir], user=ctx.user)
	else:
		BackupModule.run_restore_backup(["-m", mconfig_dir, "-n", backup_file, "-t", ton_work_dir], user=ctx.user)

	# the restored mconfig may carry the donor's paths. re-write the target ones
	write_paths(local, ctx)
	mconfig = GetConfig(path=mconfig_path)
	update_client_path_settings(mconfig, Paths.from_dict(get_paths_dict(ctx.paths)))
	SetConfig(path=mconfig_path, data=mconfig)
	StartMytoncore(local)  # the restore script started mytoncore with the donor's settings

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

	args = [sys.executable, "-m", "mytoncore", "-e", "enable_btc_teleport"]
	args = ["su", "-l", ctx.user, "-c", ' '.join(args)]
	subprocess.run(args)


def ConfigureOnlyNode(local: MyPyClass, ctx: InstallerContext):
	if not ctx.only_node:
		return
	from modules.backups import BackupModule
	mconfig_path = ctx.mconfig_path
	mconfig_dir = _get_dir_from_path(mconfig_path)
	local.add_log("start ConfigureOnlyNode function", "info")

	ton_work_dir = ctx.paths.ton_work_dir.rstrip('/')
	keys_dir = ctx.paths.keys_dir.rstrip('/')
	process = BackupModule.run_create_backup(["-m", mconfig_dir, "-t", ton_work_dir, "-k", keys_dir], user=ctx.user)
	if process.returncode != 0:
		local.add_log("Backup creation failed", "error")
		return
	local.add_log("Backup successfully created. Use this file on the controller server with `--only-mtc` flag on installation.", "info")

	mconfig = GetConfig(path=mconfig_path)
	mconfig.onlyNode = True
	SetConfig(path=mconfig_path, data=mconfig)

	start_service(local, 'mytoncore')


def SetInitialSync(local: MyPyClass, ctx: InstallerContext):
	mconfig_path = ctx.mconfig_path

	mconfig = GetConfig(path=mconfig_path)
	mconfig.initialSync = True
	SetConfig(path=mconfig_path, data=mconfig)

	start_service(local, 'mytoncore')


def SetupCollator(local: MyPyClass, ctx: InstallerContext):
	if ctx.mode != "collator":
		return
	shards = ctx.collate_shard.split()
	if not shards:
		shards = ['0:8000000000000000']
	local.add_log(f"Setting up collator for shards: {shards}", "info")
	args = [sys.executable, "-m", "mytoncore", "-e", "setup_collator_" + '_'.join(shards)]
	args = ["su", "-l", ctx.user, "-c", ' '.join(args)]
	subprocess.run(args)


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
