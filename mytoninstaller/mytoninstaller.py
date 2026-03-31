#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import sys
import inspect
import random
import json
import subprocess

import requests

from mypylib.mypylib import MyPyClass, run_as_root, color_print
from mypyconsole.mypyconsole import MyPyConsole
from mytoncore.utils import get_package_resource_path
from mytonctrl.utils import get_current_user, pop_user_from_args

from mytoninstaller.config import GetLiteServerConfig, get_ls_proxy_config
from mytoninstaller.node_args import get_node_args
from mytoninstaller.utils import GetInitBlock, get_ton_storage_port
from mytoncore.utils import dict2b64, str2bool, b642dict, b642hex

from mytoninstaller.settings import (
	FirstNodeSettings,
	FirstMytoncoreSettings,
	EnableValidatorConsole,
	EnableLiteServer,
	EnableDhtServer,
	EnableJsonRpc,
	enable_ton_http_api,
	DangerousRecoveryValidatorConfigFile,
	CreateSymlinks,
	enable_ls_proxy,
	enable_ton_storage,
	EnableMode, ConfigureFromBackup, ConfigureOnlyNode, SetInitialSync, SetupCollator
)
from mytoninstaller.config import (
	CreateLocalConfig,
	BackupMconfig,
)

from functools import partial


def init_envs(local):
	local.buffer.cport = int(os.getenv('VALIDATOR_CONSOLE_PORT') if os.getenv('VALIDATOR_CONSOLE_PORT') else random.randint(2000, 65000))
	local.buffer.lport = int(os.getenv('LITESERVER_PORT') if os.getenv('LITESERVER_PORT') else random.randint(2000, 65000))
	local.buffer.vport = int(os.getenv('VALIDATOR_PORT') if os.getenv('VALIDATOR_PORT') else random.randint(2000, 65000))
	local.buffer.archive_ttl = os.getenv('ARCHIVE_TTL')
	local.buffer.state_ttl = os.getenv('STATE_TTL')
	local.buffer.public_ip = os.getenv('PUBLIC_IP')
	local.buffer.add_shard = os.getenv('ADD_SHARD')
	local.buffer.archive_blocks = os.getenv('ARCHIVE_BLOCKS')
	local.buffer.collate_shard = os.getenv('COLLATE_SHARD', '')


def Init(local, console):
	local.db.config.isStartOnlyOneProcess = False
	local.db.config.logLevel = "debug"
	local.db.config.isIgnorLogWarning = True # disable warning
	local.run()
	local.db.config.isIgnorLogWarning = False # enable warning


	# create variables
	local.buffer.user = get_current_user()
	local.buffer.vuser = "validator"
	init_envs(local)

	# this funciton injects MyPyClass instance
	def inject_globals(func):
		args = []
		for arg_name in inspect.getfullargspec(func)[0]:
			if arg_name == 'local':
				args.append(local)
		return partial(func, *args)

	# Create user console
	console.name = "MyTonInstaller"
	console.color = console.RED
	console.add_item("status", inject_globals(Status), "Print TON component status")
	console.add_item("set_node_argument", inject_globals(set_node_argument), "Set node argument", "<arg_name> [arg_value1] [arg_value2] [-d (to delete)]")
	console.add_item("enable", inject_globals(Enable), "Enable some function", "<mode_name>")
	console.add_item("update", inject_globals(Enable), "Update some function: 'JR' - jsonrpc.  Example: 'update JR'", "<mode_name>")
	console.add_item("plsc", inject_globals(PrintLiteServerConfig), "Print lite-server config")
	console.add_item("clcf", inject_globals(CreateLocalConfigFile), "Create lite-server config file", "[-u <user>]")
	console.add_item("print_ls_proxy_config", inject_globals(print_ls_proxy_config), "Print ls-proxy config")
	console.add_item("create_ls_proxy_config_file", inject_globals(create_ls_proxy_config_file), "Create ls-proxy config file")
	console.add_item("drvcf", inject_globals(DRVCF), "Dangerous recovery validator config file")
	console.add_item("setwebpass", inject_globals(SetWebPassword), "Set a password for the web admin interface")
	console.add_item("ton_storage_list", inject_globals(ton_storage_list), "Print result of /list method at Ton Storage API")

	Refresh(local)
#end define


def Refresh(local):
	user = local.buffer.user
	local.buffer.mconfig_path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	if user == 'root':
		local.buffer.mconfig_path = "/usr/local/bin/mytoncore/mytoncore.db"
	#end if

	# create variables
	bin_dir = "/usr/bin/"
	src_dir = "/usr/src/"
	ton_work_dir = "/var/ton-work/"
	ton_bin_dir = bin_dir + "ton/"
	ton_src_dir = src_dir + "ton/"
	mtc_src_dir = src_dir + "mytonctrl/"
	local.buffer.bin_dir = bin_dir
	local.buffer.src_dir = src_dir
	local.buffer.ton_work_dir = ton_work_dir
	local.buffer.ton_bin_dir = ton_bin_dir
	local.buffer.ton_src_dir = ton_src_dir
	local.buffer.mtc_src_dir = mtc_src_dir
	ton_db_dir = ton_work_dir + "db/"
	keys_dir = ton_work_dir + "keys/"
	local.buffer.ton_db_dir = ton_db_dir
	local.buffer.keys_dir = keys_dir
	local.buffer.ton_log_path = ton_work_dir + "log"
	local.buffer.validator_app_path = ton_bin_dir + "validator-engine/validator-engine"
	local.buffer.global_config_path = ton_bin_dir + "global.config.json"
	local.buffer.vconfig_path = ton_db_dir + "config.json"
#end define


def Status(local, args):
	keys_dir = local.buffer.keys_dir
	server_key = keys_dir + "server"
	client_key = keys_dir + "client"
	liteserver_key = keys_dir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"

	statuses = {
		'Full node status': os.path.isfile(local.buffer.vconfig_path),
		'Mytoncore status': os.path.isfile(local.buffer.mconfig_path),
		'V.console status': os.path.isfile(server_key) or os.path.isfile(client_key),
		'Liteserver status': os.path.isfile(liteserver_pubkey)
	}

	color_print("{cyan}===[ Services status ]==={endc}")
	for item in statuses.items():
		status = '{green}enabled{endc}' if item[1] else '{red}disabled{endc}'
		color_print(f"{item[0]}: {status}")

	node_args = get_node_args()
	color_print("{cyan}===[ Node arguments ]==={endc}")
	for key, value in node_args.items():
		if len(value) == 0:
			print(f"{key}")
		for v in value:
			print(f"{key}: {v}")
#end define


def set_node_argument(local, args):
	if len(args) < 1:
		color_print("{red}Bad args. Usage:{endc} set_node_argument <arg-name> [arg-value] [-d (to delete)].\n"
					"Examples: 'set_node_argument --archive-ttl 86400' or 'set_node_argument --archive-ttl -d' or 'set_node_argument -M' or 'set_node_argument --add-shard 0:2000000000000000 0:a000000000000000'")
		return
	arg_name = args[0]
	args = [arg_name, " ".join(args[1:])]
	with get_package_resource_path('mytoninstaller.scripts', 'set_node_argument.py') as script_path:
		run_as_root(['python3', script_path] + args)
	color_print("set_node_argument - {green}OK{endc}")
#end define


def Enable(local, args: list):
	if len(args) < 1:
		color_print("{red}Bad args. Usage:{endc} enable <mode-name>")
		print("'FN' - Full node")
		print("'VC' - Validator console")
		print("'LS' - Lite-Server")
		print("'DS' - DHT-Server")
		print("'JR' - jsonrpc")
		print("'THA' - ton-http-api")
		print("'LSP' - ls-proxy")
		print("'TS' - ton-storage")
		print("Example: 'enable FN'")
		return
	name = args[0]
	if name == "THA":
		CreateLocalConfigFile(local, args)
	args = ["python3", "-m", "mytoninstaller", "-u", local.buffer.user, "-e", f"enable{name}"]
	run_as_root(args)
#end define


def DRVCF(local, args):
	args = ["python3", "-m", "mytoninstaller", "-u", local.buffer.user, "-e", "drvcf"]
	run_as_root(args)
#end define


def SetWebPassword(args):
	args = ["python3", "/usr/src/mtc-jsonrpc/mtc-jsonrpc.py", "-p"]
	subprocess.run(args)
#end define


def ton_storage_list(local, args: list):
	if len(args) > 0:
		api_port = int(args[0])
	else:
		api_port = get_ton_storage_port(local)
		if api_port is None:
			raise Exception('Failed to get Ton Storage API port and port was not provided. Use ton_storage_list [api_port]')
	data = requests.get(f"http://127.0.0.1:{api_port}" + '/api/v1/list', timeout=3)
	if data.status_code != 200:
		raise Exception(f'Failed to get Ton Storage list: {data.text}')
	print(json.dumps(data.json(), indent=4))


def PrintLiteServerConfig(local, args):
	liteServerConfig = GetLiteServerConfig(local)
	text = json.dumps(liteServerConfig, indent=4)
	print(text)
#end define


def CreateLocalConfigFile(local, args):
	init_block = GetInitBlock()
	if init_block['rootHash'] is None:
		local.add_log("Failed to get recent init block. Using init block from global config.", "warning")
		with open('/usr/bin/ton/global.config.json', 'r') as f:
			config = json.load(f)
		config_init_block = config['validator']['init_block']
		init_block = dict()
		init_block["seqno"] = config_init_block['seqno']
		init_block["rootHash"] = b642hex(config_init_block['root_hash'])
		init_block["fileHash"] = b642hex(config_init_block['file_hash'])
	init_block_b64 = dict2b64(init_block)
	user = pop_user_from_args(args)
	if user is None:
		user = local.buffer.user or get_current_user()
	args = ["python3", "-m", "mytoninstaller", "-u", user, "-e", "clc", "-i", init_block_b64]
	run_as_root(args)
#end define

def print_ls_proxy_config(local, args):
	ls_proxy_config = get_ls_proxy_config(local)
	text = json.dumps(ls_proxy_config, indent=4)
	print(text)
#end define

def create_ls_proxy_config_file(local, args):
	print("TODO")
#end define

def Event(local, name):
	if name == "enableFN":
		FirstNodeSettings(local)
	if name == "enableVC":
		EnableValidatorConsole(local)
	if name == "enableLS":
		EnableLiteServer(local)
	if name == "enableDS":
		EnableDhtServer(local)
	if name == "drvcf":
		DangerousRecoveryValidatorConfigFile(local)
	if name == "enableJR":
		EnableJsonRpc(local)
	if name == "enableTHA":
		enable_ton_http_api(local)
	if name == "enableLSP":
		enable_ls_proxy(local)
	if name == "enableTS":
		enable_ton_storage(local)
	if name == "clc":
		ix = sys.argv.index("-i")
		initBlock_b64 = sys.argv[ix+1]
		initBlock = b642dict(initBlock_b64)
		CreateLocalConfig(local, initBlock)
	local.exit()
#end define


def Command(local, args, console):
	cmd = args[0]
	args = args[1:]
	for item in console.menu_items:
		if cmd == item.cmd:
			console._try(item.func, args)
			print()
			local.exit()
	print(console.unknown_cmd)
	local.exit()
#end define


def General(local, console):
	if "-u" in sys.argv:
		ux = sys.argv.index("-u")
		user = sys.argv[ux+1]
		local.buffer.user = user
		Refresh(local)
	if "-c" in sys.argv:
		cx = sys.argv.index("-c")
		args = sys.argv[cx+1].split()
		Command(local, args, console)
	if "-e" in sys.argv:
		ex = sys.argv.index("-e")
		name = sys.argv[ex+1]
		Event(local, name)
	if "-t" in sys.argv:
		mx = sys.argv.index("-t")
		telemetry = sys.argv[mx+1]
		local.buffer.telemetry = str2bool(telemetry)
	if "--dump" in sys.argv:
		mx = sys.argv.index("--dump")
		dump = sys.argv[mx+1]
		local.buffer.dump = str2bool(dump)
	if "-m" in sys.argv:
		mx = sys.argv.index("-m")
		mode = sys.argv[mx+1]
		local.buffer.mode = mode
	if "--only-mtc" in sys.argv:
		ox = sys.argv.index("--only-mtc")
		local.buffer.only_mtc = str2bool(sys.argv[ox+1])
	if "--only-node" in sys.argv:
		ox = sys.argv.index("--only-node")
		local.buffer.only_node = str2bool(sys.argv[ox+1])
	if "--backup" in sys.argv:
		bx = sys.argv.index("--backup")
		backup = sys.argv[bx+1]
		if backup != "none":
			local.buffer.backup = backup
	#end if

	FirstMytoncoreSettings(local)
	FirstNodeSettings(local)
	EnableValidatorConsole(local)
	EnableLiteServer(local)
	BackupMconfig(local)
	CreateSymlinks(local)
	EnableMode(local)
	ConfigureFromBackup(local)
	ConfigureOnlyNode(local)
	SetInitialSync(local)
	SetupCollator(local)
#end define


###
### Start of the program
###
def mytoninstaller():
	local = MyPyClass(__file__)
	console = MyPyConsole(local)

	Init(local, console)
	if len(sys.argv) > 1:
		General(local, console)
	else:
		console.Run()
	local.exit()
