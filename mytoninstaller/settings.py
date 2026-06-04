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
	add2systemd,
	get_dir_from_path,
	ip2int,
	Dict, int2ip
)
from mytonctrl.utils import is_hex
from mytoninstaller.archive_blocks import run_process_hardforks, parse_block_value, download_bag, update_init_block, \
	download_blocks_bag, download_master_blocks_bag
from mytoninstaller.context import InstallerContext
from mytoninstaller.utils import StartValidator, StartMytoncore, start_service, stop_service, \
	is_testnet, disable_service
from mytoninstaller.config import SetConfig, GetConfig, get_own_ip


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
	#end if

	# Создать пользователя
	file = open("/etc/passwd", 'rt')
	text = file.read()
	file.close()
	if vuser not in text:
		local.add_log("Creating new user: " + vuser, "debug")
		args = ["/usr/sbin/useradd", "-d", "/dev/null", "-s", "/dev/null", vuser]
		subprocess.run(args)
	#end if

	# Подготовить папки валидатора
	os.makedirs(ton_db_dir, exist_ok=True)
	os.makedirs(keys_dir, exist_ok=True)

	# Прописать автозагрузку
	cpus = psutil.cpu_count() - 1

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
		DownloadDump(local, ctx)
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
	block_from = max(1, block_from - 100)  # to download previous package as node may require some blocks from it

	from mytoninstaller.scripts.ton_storage import enable_ton_storage
	api_port = enable_ton_storage(ctx.user, ctx.mconfig_path)
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
    url = "https://dump.ton.org/dumps/latest"
    if is_testnet(ctx.paths.global_config_path):
        url += '_testnet'
    dumpSize = requests.get(url + ".tar.size.archive.txt", timeout=3).text
    print("dumpSize:", dumpSize)
    needSpace = int(dumpSize) * 3
    diskSpace = psutil.disk_usage("/var")
    if needSpace > diskSpace.free:
        return
    #end if

    # apt install
    cmd = "apt install plzip pv aria2 curl -y"
    os.system(cmd)

    # download dump using aria2c to a temporary file
    temp_file = "/tmp/latest.tar.lz"
    cmd = f"aria2c -x 8 -s 8 -c {url}.tar.lz -d / -o {temp_file}"
    os.system(cmd)

    # process the downloaded file
    cmd = f"pv {temp_file} | plzip -d -n8 | tar -xC {ctx.paths.ton_db_dir}"
    os.system(cmd)

    # clean up the temporary file after processing
    if os.path.exists(temp_file):
        os.remove(temp_file)
        local.add_log(f"Temporary file {temp_file} removed", "debug")
    #end if
#end define

def FirstMytoncoreSettings(local: MyPyClass, ctx: InstallerContext):
	local.add_log("start FirstMytoncoreSettings fuction", "debug")
	user = ctx.user

	# Прописать mytoncore.py в автозагрузку
	# add2systemd(name="mytoncore", user=user, start="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py")  # TODO: fix path
	add2systemd(name="mytoncore", user=user, start="/usr/bin/python3 -m mytoncore")

	# Проверить конфигурацию
	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	if os.path.isfile(path):
		local.add_log(f"{path} already exist. Break FirstMytoncoreSettings fuction", "warning")
		return
	#end if

	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path2):
		local.add_log(f"{path2}.db already exist. Break FirstMytoncoreSettings fuction", "warning")
		return
	#end if

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
	mconfigDir = get_dir_from_path(mconfig_path)
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

	# Telemetry
	mconfig.sendTelemetry = ctx.telemetry

	# Записать настройки в файл
	SetConfig(path=mconfig_path, data=mconfig)

	# chown 1
	args = ["chown", user + ':' + user, mconfigDir, mconfig_path]
	subprocess.run(args)

	# start mytoncore
	StartMytoncore(local)
#end define

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
	#end if

	if os.path.isfile(client_key):
		local.add_log(f"Client key '{client_key}' already exist. Break EnableValidatorConsole fuction", "warning")
		return
	#end if

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

	cmd = f'python3 -m mytoncore -e "{event_name}"'
	args = ["su", "-l", user, "-c", cmd]
	subprocess.run(args)

	# restart mytoncore
	StartMytoncore(local)
#end define

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
	#end if

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
#end define

def CreateSymlinks(local: MyPyClass, ctx: InstallerContext):
	local.add_log("start CreateSymlinks fuction", "debug")
	cport = ctx.ports.validator_console

	mytonctrl_file = "/usr/bin/mytonctrl"
	fift_file = "/usr/bin/fift"
	liteclient_file = "/usr/bin/lite-client"
	validator_console_file = "/usr/bin/validator-console"
	env_file = "/etc/environment"
	file = open(mytonctrl_file, 'wt')
	# file.write("/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py $@")  # TODO: fix path
	file.write('/usr/bin/python3 -m mytonctrl "$@"')  # TODO: fix path
	file.close()
	file = open(fift_file, 'wt')
	file.write('/usr/bin/ton/crypto/fift "$@"')
	file.close()
	file = open(liteclient_file, 'wt')
	file.write('/usr/bin/ton/lite-client/lite-client -C /usr/bin/ton/global.config.json "$@"')
	file.close()
	if cport:
		file = open(validator_console_file, 'wt')
		file.write(f'/usr/bin/ton/validator-engine-console/validator-engine-console -k {ctx.paths.keys_dir}client -p {ctx.paths.keys_dir}server.pub -a 127.0.0.1:' + str(cport) + ' "$@"')
		file.close()
		args = ["chmod", "+x", validator_console_file]
		subprocess.run(args)
	args = ["chmod", "+x", mytonctrl_file, fift_file, liteclient_file]
	subprocess.run(args)

	# env
	fiftpath = "export FIFTPATH=/usr/src/ton/crypto/fift/lib/:/usr/src/ton/crypto/smartcont/"
	file = open(env_file, 'rt+')
	text = file.read()
	if fiftpath not in text:
		file.write(fiftpath + '\n')
	file.close()
#end define


def EnableMode(local: MyPyClass, ctx: InstallerContext):
	args = ["python3", "-m", "mytoncore", "-e"]
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
	mconfig_dir = get_dir_from_path(mconfig_path)
	local.add_log("start ConfigureFromBackup function", "info")
	backup_file = ctx.backup

	os.makedirs(ctx.paths.ton_work_dir, exist_ok=True)
	if not ctx.only_mtc:
		ip = str(ip2int(get_own_ip()))
		BackupModule.run_restore_backup(["-m", mconfig_dir, "-n", backup_file, "-i", ip], user=ctx.user)

	if ctx.only_mtc:
		BackupModule.run_restore_backup(["-m", mconfig_dir, "-n", backup_file], user=ctx.user)
		local.add_log("Installing only mtc", "info")
		vconfig_path = ctx.paths.vconfig_path
		vconfig = GetConfig(path=vconfig_path)
		try:
			node_ip = int2ip(vconfig['addrs'][0]['ip'])
		except Exception:
			local.add_log("Can't get ip from validator", "error")
			return
		set_external_ip(local, node_ip, ctx.mconfig_path)

	args = ["python3", "-m", "mytoncore", "-e", "enable_btc_teleport"]
	args = ["su", "-l", ctx.user, "-c", ' '.join(args)]
	subprocess.run(args)


def ConfigureOnlyNode(local: MyPyClass, ctx: InstallerContext):
	if not ctx.only_node:
		return
	from modules.backups import BackupModule
	mconfig_path = ctx.mconfig_path
	mconfig_dir = get_dir_from_path(mconfig_path)
	local.add_log("start ConfigureOnlyNode function", "info")

	process = BackupModule.run_create_backup(["-m", mconfig_dir], user=ctx.user)
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
	args = ["python3", "-m", "mytoncore", "-e", "setup_collator_" + '_'.join(shards)]
	args = ["su", "-l", ctx.user, "-c", ' '.join(args)]
	subprocess.run(args)
