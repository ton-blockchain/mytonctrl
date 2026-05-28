from __future__ import annotations

import argparse
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
from mytoninstaller.context import InstallerContext, InstallerPaths, InstallerPorts
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


def Init(local: MyPyClass):
	local.db.config.isStartOnlyOneProcess = False
	local.db.config.logLevel = "debug"
	local.db.config.isIgnorLogWarning = True # disable warning
	local.run()
	local.db.config.isIgnorLogWarning = False # enable warning

def add_commands(local: MyPyClass, console: MyPyConsole, ctx: InstallerContext):
	# this funciton injects MyPyClass instance
	def inject_globals(func):
		args = []
		for arg_name in inspect.getfullargspec(func)[0]:
			if arg_name == 'local':
				args.append(local)
			if arg_name == 'ctx':
				args.append(ctx)
		return partial(func, *args)

	# Create user console
	console.color = console.RED
	console.add_item("status", inject_globals(Status), "Print TON component status")
	console.add_item("set_node_argument", inject_globals(set_node_argument), "Set node argument", "<arg_name> [arg_value1] [arg_value2] [-d (to delete)]")
	console.add_item("enable", inject_globals(Enable), "Enable some function", "<mode_name>")
	console.add_item("update", inject_globals(Enable), "Update some function: 'JR' - jsonrpc.  Example: 'update JR'", "<mode_name>")
	console.add_item("plsc", inject_globals(PrintLiteServerConfig), "Print lite-server config")
	console.add_item("clcf", inject_globals(CreateLocalConfigFileCommand), "Create lite-server config file", "[-u <user>]")
	console.add_item("print_ls_proxy_config", inject_globals(print_ls_proxy_config), "Print ls-proxy config")
	console.add_item("create_ls_proxy_config_file", inject_globals(create_ls_proxy_config_file), "Create ls-proxy config file")
	console.add_item("drvcf", inject_globals(DRVCF), "Dangerous recovery validator config file")
	console.add_item("setwebpass", inject_globals(SetWebPassword), "Set a password for the web admin interface")
	console.add_item("ton_storage_list", inject_globals(ton_storage_list), "Print result of /list method at Ton Storage API")

def Status(ctx: InstallerContext, _):
	keys_dir = ctx.paths.keys_dir
	server_key = keys_dir + "server"
	client_key = keys_dir + "client"
	liteserver_key = keys_dir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"

	statuses = {
		'Full node status': os.path.isfile(ctx.paths.vconfig_path),
		'Mytoncore status': os.path.isfile(ctx.mconfig_path),
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
		run_as_root(['python3', str(script_path)] + args)
	color_print("set_node_argument - {green}OK{endc}")
#end define


def Enable(local: MyPyClass, ctx: InstallerContext, args: list):
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
		CreateLocalConfigFile(local, args, ctx.user)
	args = ["python3", "-m", "mytoninstaller", "-u", ctx.user, "-e", f"enable{name}"]
	run_as_root(args)
#end define


def DRVCF(ctx: InstallerContext, _):
	args = ["python3", "-m", "mytoninstaller", "-u", ctx.user, "-e", "drvcf"]
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


def PrintLiteServerConfig(local: MyPyClass, ctx: InstallerContext, _):
	liteServerConfig = GetLiteServerConfig(local, ctx)
	text = json.dumps(liteServerConfig, indent=4)
	print(text)
#end define


def CreateLocalConfigFileCommand(local: MyPyClass, ctx: InstallerContext, args):
	CreateLocalConfigFile(local, args, ctx.user)

def CreateLocalConfigFile(local: MyPyClass, args, user: str | None = None):
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
	user = pop_user_from_args(args) or user
	if user is None:
		user = get_current_user()
	args = ["python3", "-m", "mytoninstaller", "-u", user, "-e", "clc", "--init-block", init_block_b64]
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

def Event(local: MyPyClass, ctx: InstallerContext, name: str, initBlock_b64: str | None = None):
	if name == "enableFN":
		FirstNodeSettings(local, ctx)
	if name == "enableVC":
		EnableValidatorConsole(local, ctx)
	if name == "enableLS":
		EnableLiteServer(local, ctx)
	if name == "enableDS":
		EnableDhtServer(local, ctx)
	if name == "drvcf":
		DangerousRecoveryValidatorConfigFile(local, ctx)
	if name == "enableJR":
		EnableJsonRpc(local, ctx)
	if name == "enableTHA":
		enable_ton_http_api(local, user=ctx.user, update=True)
	if name == "enableLSP":
		enable_ls_proxy(local, ctx)
	if name == "enableTS":
		enable_ton_storage(local, ctx)
	if name == "clc":
		if initBlock_b64 is None:
			raise ValueError("init block is required for clc event")
		initBlock = b642dict(initBlock_b64)
		CreateLocalConfig(local, ctx, initBlock)
	local.exit()


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


def _build_general_arg_parser():
	parser = argparse.ArgumentParser(prog="mytoninstaller", allow_abbrev=False)
	parser.add_argument("-u", dest="user", help="user to be used for MyTonCtrl installation")
	parser.add_argument("-c", dest="command", help="run installer console command")
	parser.add_argument("-e", dest="event", help="run installer event")
	parser.add_argument("--init-block", help="base64 init block for clc event")
	parser.add_argument(
		"-t",
		dest="telemetry",
		nargs="?",
		const="false",
		type=str2bool,
		help="set telemetry boolean; without a value disables telemetry",
	)
	parser.add_argument(
		"--dump",
		nargs="?",
		const="true",
		type=str2bool,
		help="set whether to use pre-packaged dump",
	)
	parser.add_argument("-m", dest="mode", help="installation mode")
	parser.add_argument(
		"--only-mtc",
		nargs="?",
		const="true",
		type=str2bool,
		help="install only MyTonCtrl",
	)
	parser.add_argument(
		"--only-node",
		nargs="?",
		const="true",
		type=str2bool,
		help="install only TON node",
	)
	parser.add_argument("--backup", help="backup file for MyTonCtrl installation")
	return parser


def _parse_general_args(argv=None):
	parser = _build_general_arg_parser()
	args = parser.parse_args(argv)
	if args.command is None and args.event == "clc" and args.init_block is None:
		parser.error("--init-block is required with -e clc")
	return args


def get_context(local: MyPyClass, args) -> InstallerContext:
	user = get_current_user()
	vuser = "validator"
	telemetry = False or args.telemetry
	dump = False or args.dump

	if args.user is not None:
		user = args.user

	vc_port = int(
		os.getenv('VALIDATOR_CONSOLE_PORT') if os.getenv('VALIDATOR_CONSOLE_PORT') else random.randint(2000, 65000))
	ls_port = int(os.getenv('LITESERVER_PORT') if os.getenv('LITESERVER_PORT') else random.randint(2000, 65000))
	v_port = int(os.getenv('VALIDATOR_PORT') if os.getenv('VALIDATOR_PORT') else random.randint(2000, 64000))
	quic_port = int(os.getenv('QUIC_PORT')) if os.getenv('QUIC_PORT') else None
	ports = InstallerPorts(vc_port, ls_port, v_port, quic_port)

	archive_ttl = int(os.getenv('ARCHIVE_TTL')) if os.getenv('ARCHIVE_TTL') else None
	state_ttl = int(os.getenv('STATE_TTL')) if os.getenv('STATE_TTL') else None
	public_ip = os.getenv('PUBLIC_IP')
	add_shard = os.getenv('ADD_SHARD')
	archive_blocks = os.getenv('ARCHIVE_BLOCKS')
	collate_shard = os.getenv('COLLATE_SHARD', '')

	backup = None
	if args.backup is not None:
		if args.backup != "none":
			backup = args.backup

	paths = InstallerPaths()
	return InstallerContext(user, vuser, paths, ports, telemetry, dump, args.mode, args.only_mtc, args.only_node, backup,
	                       archive_ttl, state_ttl, public_ip, add_shard, archive_blocks, collate_shard)


def General(local: MyPyClass, console: MyPyConsole, args, ctx: InstallerContext):
	if args.command is not None:
		Command(local, args.command.split(), console)
		return
	if args.event is not None:
		Event(local, ctx, args.event, args.init_block)
		return

	FirstMytoncoreSettings(local, ctx)
	FirstNodeSettings(local, ctx)
	EnableValidatorConsole(local, ctx)
	EnableLiteServer(local, ctx)
	BackupMconfig(local, ctx)
	CreateSymlinks(local, ctx)
	EnableMode(local, ctx)
	ConfigureFromBackup(local, ctx)
	ConfigureOnlyNode(local, ctx)
	SetInitialSync(local, ctx)
	SetupCollator(local, ctx)


###
### Start of the program
###
def mytoninstaller():
	local = MyPyClass(__file__)
	console = MyPyConsole(local, "MyTonInstaller")

	Init(local)
	args = _parse_general_args()
	ctx = get_context(local, args)
	add_commands(local, console, ctx)
	if len(sys.argv) > 1:
		General(local, console, args, ctx)
	else:
		console.run()
	local.exit()
