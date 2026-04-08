from __future__ import annotations

import base64
import pathlib
import subprocess
import json
import psutil
import inspect
import socket
import sys
import getopt
import os
import shutil
import tempfile
from pathlib import Path

from functools import partial

import requests

from mypylib.mypylib import (
	int2ip,
	get_git_author_and_repo,
	get_git_branch,
	get_git_hash,
	check_git_update,
	get_service_status,
	get_service_uptime,
	get_load_avg,
	run_as_root,
	time2human,
	get_timestamp,
	print_table,
	color_print,
	color_text,
	bcolors,
	Dict,
	MyPyClass
)

from mypyconsole.mypyconsole import MyPyConsole
from mytoncore.mytoncore import MyTonCore
from mytoncore.telemetry import (
	get_memory_info,
	get_swap_info,
)
from mytoncore.utils import get_package_resource_path, b642hex
from mytoncore.telemetry import is_host_virtual, get_bin_git_hash
from mytonctrl.console_cmd import add_command, check_usage_one_arg, check_usage_args_min_max_len
from mytonctrl.utils import GetItemFromList, timestamp2utcdatetime, fix_git_config, is_hex, GetColorInt, \
	pop_user_from_args, pop_arg_from_args, get_clang_major_version, get_os_version
from mytoninstaller.archive_blocks import download_blocks
from mytoninstaller.utils import get_ton_storage_port


CLANG_VERSION_REQUIRED = 21


def Init(local, ton, console, argv):
	# Load translate table
	with get_package_resource_path('mytonctrl', 'resources/translate.json') as translate_path:
		local.init_translator(translate_path)

	# this function substitutes local and ton instances if function has this args
	def inject_globals(func):
		args = []
		for arg_name in inspect.getfullargspec(func)[0]:
			if arg_name == 'local':
				args.append(local)
			elif arg_name == 'ton':
				args.append(ton)
		return partial(func, *args)

	# Create user console
	console.name = "MyTonCtrl"
	console.start_function = inject_globals(pre_up)
	console.debug = ton.GetSettings("debug")
	console.local = local

	add_command(local, console, "update", inject_globals(Update))
	add_command(local, console, "upgrade", inject_globals(Upgrade))
	add_command(local, console, "installer", inject_globals(Installer))
	add_command(local, console, "status", inject_globals(PrintStatus))
	add_command(local, console, "status_modes", inject_globals(mode_status))
	add_command(local, console, "status_settings", inject_globals(settings_status))
	add_command(local, console, "enable_mode", inject_globals(enable_mode))
	add_command(local, console, "disable_mode", inject_globals(disable_mode))
	add_command(local, console, "about", inject_globals(about))
	add_command(local, console, "get", inject_globals(GetSettings))
	add_command(local, console, "set", inject_globals(SetSettings))
	add_command(local, console, "download_archive_blocks", inject_globals(download_archive_blocks))
	add_command(local, console, "benchmark", inject_globals(run_benchmark))
	add_command(local, console, "set_quic_port", inject_globals(set_quic_port))

	from modules.backups import BackupModule
	module = BackupModule(ton, local)
	module.add_console_commands(console)

	from modules.custom_overlays import CustomOverlayModule
	module = CustomOverlayModule(ton, local)
	module.add_console_commands(console)

	from modules.btc_teleport import BtcTeleportModule
	module = BtcTeleportModule(ton, local)
	module.add_console_commands(console)

	if ton.using_validator():
		from modules.validator import ValidatorModule
		module = ValidatorModule(ton, local)
		module.add_console_commands(console)

		from modules.wallet import WalletModule
		module = WalletModule(ton, local)
		module.add_console_commands(console)

		from modules.utilities import UtilitiesModule
		module = UtilitiesModule(ton, local)
		module.add_console_commands(console)

		if ton.using_pool():  # add basic pool functions (pools_list, delete_pool, import_pool)
			from modules.pool import PoolModule
			module = PoolModule(ton, local)
			module.add_console_commands(console)

		if ton.using_nominator_pool():
			from modules.nominator_pool import NominatorPoolModule
			module = NominatorPoolModule(ton, local)
			module.add_console_commands(console)

		if ton.using_single_nominator():
			from modules.single_pool import SingleNominatorModule
			module = SingleNominatorModule(ton, local)
			module.add_console_commands(console)

		if ton.using_liquid_staking():
			from modules.controller import ControllerModule
			module = ControllerModule(ton, local)
			module.add_console_commands(console)

	if ton.using_validator() or ton.using_collator():
		from modules.collator_config import CollatorConfigModule
		module = CollatorConfigModule(ton, local)
		module.add_console_commands(console)

	if ton.using_collator():
		from modules.collator import CollatorModule
		module = CollatorModule(ton, local)
		module.add_console_commands(console)

	if ton.using_alert_bot():
		from modules.alert_bot import AlertBotModule
		module = AlertBotModule(ton, local)
		module.add_console_commands(console)

	# Process input parameters
	opts, args = getopt.getopt(argv,"hc:w:",["config=","wallets="])
	for opt, arg in opts:
		if opt == '-h':
			print ('mytonctrl.py -c <configfile> -w <wallets>')
			sys.exit()
		elif opt in ("-c", "--config"):
			configfile = arg
			if not os.access(configfile, os.R_OK):
				print ("Configuration file " + configfile + " could not be opened")
				sys.exit()

			ton.dbFile = configfile
			ton.Refresh()
		elif opt in ("-w", "--wallets"):
			wallets = arg
			if not os.access(wallets, os.R_OK):
				print ("Wallets path " + wallets  + " could not be opened")
				sys.exit()
			elif not os.path.isdir(wallets):
				print ("Wallets path " + wallets  + " is not a directory")
				sys.exit()
			ton.walletsDir = wallets

	local.db.config.logLevel = "debug" if console.debug else "info"
	local.db.config.isLocaldbSaving = False
	local.run()


def about(local, ton, args):
	from modules import get_mode, get_mode_settings
	if not check_usage_one_arg("about", args):
		return
	mode_name = args[0]
	mode = get_mode(mode_name)
	if mode is None:
		color_print(f"{{red}}Mode {mode_name} not found{{endc}}")
		return
	mode_settings = get_mode_settings(mode_name)
	color_print(f'''{{cyan}}===[ {mode_name} MODE ]==={{endc}}''')
	color_print(f'''Description: {mode.description}''')
	color_print('Enabled: ' + color_text('{green}yes{endc}' if ton.get_mode_value(mode_name) else '{red}no{endc}'))
	print('Settings:', 'no' if len(mode_settings) == 0 else '')
	for setting_name, setting in mode_settings.items():
		color_print(f'  {{bold}}{setting_name}{{endc}}: {setting.description}.\n    Default value: {setting.default_value}')


def check_installer_user(local):
	args = ["whoami"]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	username = process.stdout.decode("utf-8").strip()

	args = ["ls", "-lh", "/var/ton-work/keys/"]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	actual_user = output.split('\n')[1].split()[2]

	if username != actual_user:
		local.add_log(f'mytonctrl was installed by another user. Probably you need to launch mtc with `{actual_user}` user.', 'error')
#end define


def pre_up(local: MyPyClass, ton: MyTonCore):
	try:
		local.try_function(check_mytonctrl_update, args=[local])
		local.try_function(check_installer_user, args=[local])
		local.try_function(check_vport, args=[local, ton])
		warnings(local, ton)
	except Exception as e:
		local.add_log(f'PreUp error: {e}', 'error')


def Installer(args):
	# args = ["python3", "/usr/src/mytonctrl/mytoninstaller.py"]
	cmd = ["python3", "-m", "mytoninstaller"]
	if args:
		cmd += ["-c", " ".join(args)]
	subprocess.run(cmd)
#end define


def GetAuthorRepoBranchFromArgs(args):
	data = dict()
	arg1 = GetItemFromList(args, 0)
	arg2 = GetItemFromList(args, 1)
	if arg1:
		if "https://" in arg1:
			buff = arg1[8:].split('/')
			print(f"buff: {buff}")
			data["author"] = buff[1]
			data["repo"] = buff[2]
			tree = GetItemFromList(buff, 3)
			if tree:
				data["branch"] = GetItemFromList(buff, 4)
		else:
			data["branch"] = arg1
	if arg2:
		data["branch"] = arg2
	return data
#end define


def check_vport(local, ton):
	try:
		vconfig = ton.GetValidatorConfig()
	except Exception:
		local.add_log("GetValidatorConfig error", "error")
		return
	addr = vconfig.addrs.pop()
	ip = int2ip(addr.ip)
	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
		result = client_socket.connect_ex((ip, addr.port))
	if result != 0:
		color_print(local.translate("vport_error"))
#end define


def check_git(input_args, default_repo, text, default_branch='master'):
	src_dir = "/usr/src"
	git_path = f"{src_dir}/{default_repo}"
	fix_git_config(git_path)
	default_author = "ton-blockchain"

	branch = pop_arg_from_args(input_args, '--branch')

	if '--url' in input_args:
		git_url = pop_arg_from_args(input_args, '--url')
		if not git_url:
			raise Exception("git url is empty after --url flag")
		if branch is None:
			if '#' in git_url:
				ref_fragment = git_url.rsplit('#', 1)[1]
				if not ref_fragment:
					raise Exception("--url fragment after # is empty")
				branch = ref_fragment
			else:
				branch = default_branch
		if '#' in git_url:
			git_url = git_url.split('#', 1)[0]
		return None, None, branch, git_url

	local_author, local_repo = get_git_author_and_repo(git_path)
	local_branch = get_git_branch(git_path)

	# Set author, repo, branch
	data = GetAuthorRepoBranchFromArgs(input_args)
	need_author = data.get("author")
	need_repo = data.get("repo")
	need_branch = data.get("branch") or branch

	# Check if remote repo is different from default
	if ((need_author is None and local_author != default_author) or
		(need_repo is None and local_repo != default_repo)):
		remote_url = f"https://github.com/{local_author}/{local_repo}/tree/{need_branch if need_branch else local_branch}"
		raise Exception(f"{text} error: You are on {remote_url} remote url, to update to the tip use `{text} {remote_url}` command")
	elif need_branch is None and local_branch != default_branch:
		raise Exception(f"{text} error: You are on {local_branch} branch, to update to the tip of {local_branch} branch use `{text} {local_branch}` command")
	#end if

	if need_author is None:
		need_author = local_author
	if need_repo is None:
		need_repo = local_repo
	if need_branch is None:
		need_branch = local_branch
	check_branch_exists(need_author, need_repo, need_branch)
	return need_author, need_repo, need_branch, None
#end define

def check_branch_exists(author, repo, branch):
	if len(branch) >= 6 and is_hex(branch):
		print('Hex name detected, skip branch existence check.')
		return
	url = f"https://github.com/{author}/{repo}.git"
	args = ["git", "ls-remote", "--heads", "--tags", url, branch]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	if branch not in output:
		raise Exception(f"Branch {branch} not found in {url}")
#end define

def Update(local, args):
	repo = "mytonctrl"
	author, repo, branch, _ = check_git(args, repo, "update")  # todo: implement --url for update
	# Run script
	with get_package_resource_path('mytonctrl', 'scripts/update.sh') as update_script_path:
		runArgs = ["bash", update_script_path, "-a", author, "-r", repo, "-b", branch]
		exitCode = run_as_root(runArgs)
	if exitCode == 0:
		text = "Update - {green}OK{endc}"
	else:
		text = "Update - {red}Error{endc}"
	color_print(text)
	local.exit()
#end define

def Upgrade(local, ton, args: list):
	if '--btc-teleport' in args:  # upgrade --btc-teleport [branch] [-u <user>]
		branch = 'master'
		user = pop_user_from_args(args)
		if len(args) > args.index('--btc-teleport') + 1:
			branch = args[args.index('--btc-teleport') + 1]
		upgrade_btc_teleport(local, ton, reinstall=True, branch=branch, user=user)
		return

	author, repo, branch, git_url = check_git(args, default_repo="ton", text="upgrade")

	# bugfix if the files are in the wrong place
	liteClient = ton.GetSettings("liteClient")
	configPath = liteClient.get("configPath")
	pubkeyPath = liteClient.get("liteServer").get("pubkeyPath")
	if "ton-lite-client-test1" in configPath:
		liteClient["configPath"] = configPath.replace("lite-client/ton-lite-client-test1.config.json", "global.config.json")
	if "/usr/bin/ton" in pubkeyPath:
		liteClient["liteServer"]["pubkeyPath"] = "/var/ton-work/keys/liteserver.pub"
	ton.SetSettings("liteClient", liteClient)
	validatorConsole = ton.GetSettings("validatorConsole")
	privKeyPath = validatorConsole.get("privKeyPath")
	pubKeyPath = validatorConsole.get("pubKeyPath")
	if "/usr/bin/ton" in privKeyPath:
		validatorConsole["privKeyPath"] = "/var/ton-work/keys/client"
	if "/usr/bin/ton" in pubKeyPath:
		validatorConsole["pubKeyPath"] = "/var/ton-work/keys/server.pub"
	ton.SetSettings("validatorConsole", validatorConsole)

	clang_version = get_clang_major_version()
	if clang_version is None or clang_version < CLANG_VERSION_REQUIRED:
		text = f"{{red}}WARNING: THIS UPGRADE WILL MOST PROBABLY FAIL DUE TO A WRONG CLANG VERSION: {clang_version}, REQUIRED VERSION IS {CLANG_VERSION_REQUIRED}. RECOMMENDED TO EXIT NOW AND UPGRADE CLANG AS PER INSTRUCTIONS: https://gist.github.com/neodix42/24d6a401e928f7e895fcc8e7b7c5c24a{{endc}}\n"
		color_print(text)
		if input("Continue with upgrade anyway? [Y/n]\n").strip().lower() not in ('y', ''):
			print('aborted.')
			return

	# Run script
	with get_package_resource_path('mytonctrl', 'scripts/upgrade.sh') as upgrade_script_path:
		if git_url:
			runArgs = ["bash", upgrade_script_path, "-g", git_url, "-b", branch]
		else:
			runArgs = ["bash", upgrade_script_path, "-a", author, "-r", repo, "-b", branch]
		exitCode = run_as_root(runArgs)
	if ton.using_validator():
		upgrade_btc_teleport(local, ton)
	if exitCode == 0:
		text = "Upgrade - {green}OK{endc}"
	else:
		text = "Upgrade - {red}Error{endc}"
	color_print(text)
#end define


def upgrade_btc_teleport(local, ton, reinstall=False, branch: str = 'master', user = None):
	from modules.btc_teleport import BtcTeleportModule
	module = BtcTeleportModule(ton, local)
	local.try_function(module.init, args=[reinstall, branch, user])


def run_benchmark(args: list):
	if shutil.which("uv") is None:
		answer = input("uv is not installed. Install it? [y/n] ").strip().lower()
		if answer == "y":
			subprocess.run(["curl", "-LsSf", "https://astral.sh/uv/install.sh", "-o", "/tmp/uv_install.sh"], check=True)
			subprocess.run(["sh", "/tmp/uv_install.sh"], check=True)
			uv_local_bin = os.path.expanduser("~/.local/bin")
			if uv_local_bin not in os.environ.get("PATH", ""):
				os.environ["PATH"] = uv_local_bin + os.pathsep + os.environ.get("PATH", "")
			if shutil.which("uv") is None:
				color_print("{red}Error: uv installation failed{endc}")
				return
		else:
			return

	if get_service_status("validator"):
		color_print("{red}Error: validator service is running. Stop it before running benchmark: `sudo systemctl stop validator`{endc}")
		return

	with tempfile.TemporaryDirectory() as tmp_dir:
		tmp_dir = Path(tmp_dir)
		with get_package_resource_path('mytonctrl', 'scripts/benchmark.py') as benchmark_path:
			shutil.copy(benchmark_path, tmp_dir / "benchmark.py")

			subprocess.run(["uv", "init", "--python", "3.13", "--no-workspace", "--name", "benchmark"], cwd=tmp_dir, check=True)

			src_dir = Path("/usr/src/ton")
			test_dir = tmp_dir / "test"
			tontester_dir = test_dir / "tontester"

			shutil.copytree(src_dir / "test", test_dir)

			tl_dest = tmp_dir / "tl" / "generate" / "scheme"
			Path(tl_dest).mkdir(parents=True, exist_ok=True)

			for f in (src_dir / "tl" / "generate" / "scheme").glob('*.tl'):
				shutil.copy(f, tl_dest)

			subprocess.run(["uv", "add", tontester_dir], cwd=tmp_dir, check=True)

			subprocess.run(["uv", "run", tontester_dir / "generate_tl.py"], cwd=tmp_dir, check=True)

			cmd = ["uv", "run", "benchmark.py",
				"--build-dir", '/usr/bin/ton',
				"--source-dir", '/usr/src/ton',
				"--work-dir", str(tmp_dir / "test" / "integration" / ".network")] + args
			subprocess.run(cmd, cwd=tmp_dir)


def check_mytonctrl_update(local: MyPyClass):
	git_path = '/usr/src/mytonctrl'
	if not os.path.exists(git_path):
		return
	result = check_git_update(git_path)
	if result:
		color_print(local.translate("mytonctrl_update_available"))

def print_warning(local, warning_name: str):
	color_print("============================================================================================")
	color_print(local.translate(warning_name))
	color_print("============================================================================================")
#end define

def check_disk_usage(local, ton):
	usage = ton.GetDbUsage()
	if usage > 90:
		print_warning(local, "disk_usage_warning")
#end define

def check_sync(local, ton):
	validator_status = ton.GetValidatorStatus()
	if validator_status.initial_sync or ton.in_initial_sync():
		print_warning(local, "initial_sync_warning")
		return
	if not validator_status.is_working or validator_status.out_of_sync >= 20:
		print_warning(local, "sync_warning")
#end define

def check_validator_balance(local, ton):
	validator_status = ton.GetValidatorStatus()
	if not validator_status.is_working or validator_status.out_of_sync >= 20:
		# Do not check the validator wallet balance if the node is not synchronized (via public lite-servers)
		return
	if ton.using_validator():
		validator_wallet = ton.GetValidatorWallet()
		validator_account = local.try_function(ton.GetAccount, args=[validator_wallet.addrB64])
		if validator_account is None:
			local.add_log("Failed to check validator wallet balance", "warning")
			return
		if validator_account.balance < 100:
			print_warning(local, "validator_balance_warning")
#end define

def check_vps(local, ton):
	if ton.using_validator():
		data = local.try_function(is_host_virtual)
		if data and data["virtual"]:
			color_print(f"Virtualization detected: {data['product_name']}")
#end define

def check_tg_channel(local, ton):
	if ton.using_validator() and ton.local.db.get("subscribe_tg_channel") is None:
		print_warning(local, "subscribe_tg_channel_warning")
#end difine

def check_slashed(local, ton):
	validator_status = ton.GetValidatorStatus()
	if not ton.using_validator() or not validator_status.is_working or validator_status.out_of_sync >= 20:
		return
	from modules import ValidatorModule
	validator_module = ValidatorModule(ton, local)
	c = validator_module.get_my_complaint()
	if c:
		warning = local.translate("slashed_warning").format(int(c['suggestedFine']))
		print_warning(local, warning)
#end define

def check_adnl(local, ton):
	try:
		config = ton.GetValidatorConfig()
		if config.fullnodeslaves:
			return
	except Exception:
		pass
	from modules.utilities import UtilitiesModule
	utils_module = UtilitiesModule(ton, local)
	ok, error = utils_module.check_adnl_connection()
	if not ok:
		error = "{red}" + error + "{endc}"
		print_warning(local, error)
#end define

def check_ubuntu_version(local: MyPyClass):
	distro, ver = get_os_version()
	if distro == 'ubuntu':
		if ver not in ['22.04', '24.04']:
			warning = local.translate("ubuntu_version_warning").format(ver)
			print_warning(local, warning)

def check_node_port(local: MyPyClass, ton: MyTonCore):
	if not ton.using_validator():
		return
	try:
		vconfig = ton.GetValidatorConfig()
	except Exception:
		return
	for addr in vconfig["addrs"]:
		if addr.get("@type") == "engine.quicAddr":  # quic port exists
			return
	for addr in vconfig["addrs"]:
		port = addr["port"]
		if port > 64535:
			warning = local.translate("node_port_warning").format(port)
			print_warning(local, warning)
			return

def warnings(local: MyPyClass, ton: MyTonCore):
	local.try_function(check_disk_usage, args=[local, ton])
	local.try_function(check_sync, args=[local, ton])
	local.try_function(check_adnl, args=[local, ton])
	local.try_function(check_validator_balance, args=[local, ton])
	local.try_function(check_vps, args=[local, ton])
	local.try_function(check_tg_channel, args=[local, ton])
	local.try_function(check_slashed, args=[local, ton])
	local.try_function(check_ubuntu_version, args=[local])
	local.try_function(check_node_port, args=[local, ton])

def CheckTonUpdate(local):
	git_path = "/usr/src/ton"
	result = check_git_update(git_path)
	if result is True:
		color_print(local.translate("ton_update_available"))
#end define

def mode_status(ton, args):
	from modules import get_mode
	modes = ton.get_modes()
	table = [["Name", "Status", "Description"]]
	for mode_name in modes:
		mode = get_mode(mode_name)
		if mode is None:
			color_print(f"{{red}}Mode {mode_name} not found{{endc}}")
			continue
		status = color_text('{green}enabled{endc}' if modes[mode_name] else '{red}disabled{endc}')
		table.append([mode_name, status, mode.description])
	print_table(table)
#end define


def settings_status(ton, args):
	from modules import SETTINGS
	table = [["Name", "Description", "Mode", "Default value", "Current value"]]
	for name, setting in SETTINGS.items():
		current_value = ton.local.db.get(name)
		table.append([name, setting.description, setting.mode, setting.default_value, current_value])
	print_table(table)
#end define


def PrintStatus(local, ton, args):
	opt = None
	if len(args) == 1:
		opt = args[0]
	fast = opt == "fast"

	# Local status
	validator_status = ton.GetValidatorStatus()
	adnl_addr = ton.GetAdnlAddr()
	validator_index = None
	validator_efficiency = None
	validator_wallet = ton.GetValidatorWallet()
	validator_account = Dict()
	db_size = ton.GetDbSize()
	db_usage = ton.GetDbUsage()
	memory_info = get_memory_info()
	swap_info = get_swap_info()
	statistics = ton.GetSettings("statistics")
	net_load_avg = ton.GetStatistics("netLoadAvg", statistics)
	disks_load_avg = ton.GetStatistics("disksLoadAvg", statistics)
	disks_load_percent_avg = ton.GetStatistics("disksLoadPercentAvg", statistics)

	all_status = (validator_status.is_working and validator_status.out_of_sync < 20) and not fast

	vconfig = None
	try:
		vconfig = ton.GetValidatorConfig()
		fullnode_adnl = base64.b64decode(vconfig.fullnode).hex().upper()
	except Exception:
		fullnode_adnl = 'n/a'

	if all_status:
		network_name = ton.GetNetworkName()
		rootWorkchainEnabledTime_int = local.try_function(ton.GetRootWorkchainEnabledTime)
		config34 = ton.GetConfig34()
		config36 = ton.GetConfig36()
		totalValidators = config34["totalValidators"]

		oldStartWorkTime = config36.get("startWorkTime")
		if oldStartWorkTime is None:
			oldStartWorkTime = config34.get("startWorkTime")
		shardsNumber = ton.GetShardsNumber()

		config15 = ton.GetConfig15()
		config17 = ton.GetConfig17()
		fullConfigAddr = ton.GetFullConfigAddr()
		fullElectorAddr = ton.GetFullElectorAddr()
		startWorkTime = ton.GetActiveElectionId(fullElectorAddr)
		validator_index = ton.GetValidatorIndex()

		offersNumber = local.try_function(ton.GetOffersNumber)
		complaintsNumber = local.try_function(ton.GetComplaintsNumber)

		if validator_wallet is not None:
			validator_account = ton.GetAccount(validator_wallet.addrB64)
	#end if

	if all_status:
		PrintTonStatus(local, network_name, startWorkTime, totalValidators, shardsNumber, offersNumber, complaintsNumber)
	PrintLocalStatus(local, ton, adnl_addr, validator_index, validator_efficiency, validator_wallet, validator_account, validator_status,
		db_size, db_usage, memory_info, swap_info, net_load_avg, disks_load_avg, disks_load_percent_avg, fullnode_adnl, vconfig)
	if all_status and ton.using_validator():
		PrintTonConfig(local, fullConfigAddr, fullElectorAddr, config15, config17)
		PrintTimes(local, rootWorkchainEnabledTime_int, startWorkTime, oldStartWorkTime, config15)
#end define

def PrintTonStatus(local, network_name, startWorkTime, totalValidators, shardsNumber, offersNumber, complaintsNumber):
	newOffers = offersNumber.get("new") if offersNumber else 'n/a'
	allOffers = offersNumber.get("all") if offersNumber else 'n/a'
	newComplaints = complaintsNumber.get("new") if complaintsNumber else 'n/a'
	allComplaints = complaintsNumber.get("all") if complaintsNumber else 'n/a'

	color_network_name = bcolors.green_text(network_name) if network_name == "mainnet" else bcolors.yellow_text(network_name)
	network_name_text = local.translate("ton_status_network_name").format(color_network_name)
	allValidators_text = bcolors.yellow_text(totalValidators)
	validators_text = local.translate("ton_status_validators").format(allValidators_text)
	shards_text = local.translate("ton_status_shards").format(bcolors.green_text(shardsNumber))
	newOffers_text = bcolors.green_text(newOffers)
	allOffers_text = bcolors.yellow_text(allOffers)
	offers_text = local.translate("ton_status_offers").format(newOffers_text, allOffers_text)
	newComplaints_text = bcolors.green_text(newComplaints)
	allComplaints_text = bcolors.yellow_text(allComplaints)
	complaints_text = local.translate("ton_status_complaints").format(newComplaints_text, allComplaints_text)

	if startWorkTime == 0:
		election_text = bcolors.yellow_text("closed")
	else:
		election_text = bcolors.green_text("open")
	election_text = local.translate("ton_status_election").format(election_text)

	color_print(local.translate("ton_status_head"))
	print(network_name_text)
	#print(tps_text)
	print(validators_text)
	print(shards_text)
	print(offers_text)
	print(complaints_text)
	print(election_text)
	print()
#end define


def PrintLocalStatus(local, ton, adnlAddr, validatorIndex, validatorEfficiency, validatorWallet, validatorAccount, validator_status, dbSize, dbUsage, memoryInfo, swapInfo, netLoadAvg, disksLoadAvg, disksLoadPercentAvg, fullnode_adnl, vconfig):
	walletAddr = 'n/a'
	if validatorWallet is not None:
		walletAddr = validatorWallet.addrB64

	walletBalance = validatorAccount.balance
	cpuNumber = psutil.cpu_count()
	loadavg = get_load_avg()
	cpuLoad1 = loadavg[0]
	cpuLoad5 = loadavg[1]
	cpuLoad15 = loadavg[2]
	netLoad1 = netLoadAvg[0]
	netLoad5 = netLoadAvg[1]
	netLoad15 = netLoadAvg[2]

	validatorIndex_text = GetColorInt(validatorIndex, 0, logic="more")
	validatorIndex_text = local.translate("local_status_validator_index").format(validatorIndex_text)
	validatorEfficiency_text = GetColorInt(validatorEfficiency, 10, logic="more", ending=" %")
	validatorEfficiency_text = local.translate("local_status_validator_efficiency").format(validatorEfficiency_text)
	adnlAddr_text = local.translate("local_status_adnl_addr").format(bcolors.yellow_text(adnlAddr))
	fullnode_adnl_text = local.translate("local_status_fullnode_adnl").format(bcolors.yellow_text(fullnode_adnl))
	walletAddr_text = local.translate("local_status_wallet_addr").format(bcolors.yellow_text(walletAddr))
	walletBalance_text = local.translate("local_status_wallet_balance").format(bcolors.green_text(walletBalance))

	# CPU status
	cpuNumber_text = bcolors.yellow_text(cpuNumber)
	cpuLoad1_text = GetColorInt(cpuLoad1, cpuNumber, logic="less")
	cpuLoad5_text = GetColorInt(cpuLoad5, cpuNumber, logic="less")
	cpuLoad15_text = GetColorInt(cpuLoad15, cpuNumber, logic="less")
	cpuLoad_text = local.translate("local_status_cpu_load").format(cpuNumber_text, cpuLoad1_text, cpuLoad5_text, cpuLoad15_text)

	# Memory status
	ramUsage = memoryInfo.get("usage")
	ramUsagePercent = memoryInfo.get("usagePercent")
	swapUsage = swapInfo.get("usage")
	swapUsagePercent = swapInfo.get("usagePercent")
	ramUsage_text = GetColorInt(ramUsage, 100, logic="less", ending=" Gb")
	ramUsagePercent_text = GetColorInt(ramUsagePercent, 90, logic="less", ending="%")
	swapUsage_text = GetColorInt(swapUsage, 100, logic="less", ending=" Gb")
	swapUsagePercent_text = GetColorInt(swapUsagePercent, 90, logic="less", ending="%")
	ramLoad_text = "{cyan}ram:[{default}{data}, {percent}{cyan}]{endc}"
	ramLoad_text = ramLoad_text.format(cyan=bcolors.cyan, default=bcolors.default, endc=bcolors.endc, data=ramUsage_text, percent=ramUsagePercent_text)
	swapLoad_text = "{cyan}swap:[{default}{data}, {percent}{cyan}]{endc}"
	swapLoad_text = swapLoad_text.format(cyan=bcolors.cyan, default=bcolors.default, endc=bcolors.endc, data=swapUsage_text, percent=swapUsagePercent_text)
	memoryLoad_text = local.translate("local_status_memory").format(ramLoad_text, swapLoad_text)

	# Network status
	netLoad1_text = GetColorInt(netLoad1, 300, logic="less")
	netLoad5_text = GetColorInt(netLoad5, 300, logic="less")
	netLoad15_text = GetColorInt(netLoad15, 300, logic="less")
	netLoad_text = local.translate("local_status_net_load").format(netLoad1_text, netLoad5_text, netLoad15_text)

	# Disks status
	disksLoad_data = list()
	for key, item in disksLoadAvg.items():
		diskLoad15_text = bcolors.green_text(item[2])
		diskLoadPercent15_text = GetColorInt(disksLoadPercentAvg[key][2], 80, logic="less", ending="%")
		buff = "{}, {}"
		buff = "{}{}:[{}{}{}]{}".format(bcolors.cyan, key, bcolors.default, buff, bcolors.cyan, bcolors.endc)
		disksLoad_buff = buff.format(diskLoad15_text, diskLoadPercent15_text)
		disksLoad_data.append(disksLoad_buff)
	disksLoad_data = ", ".join(disksLoad_data)
	disksLoad_text = local.translate("local_status_disks_load").format(disksLoad_data)

	# Thread status
	mytoncoreStatus_bool = get_service_status("mytoncore")
	validatorStatus_bool = get_service_status("validator")
	mytoncoreUptime = get_service_uptime("mytoncore")
	validatorUptime = get_service_uptime("validator")
	mytoncoreUptime_text = bcolors.green_text(time2human(mytoncoreUptime))
	validatorUptime_text = bcolors.green_text(time2human(validatorUptime))
	mytoncoreStatus_color = GetColorStatus(mytoncoreStatus_bool)
	validatorStatus_color = GetColorStatus(validatorStatus_bool)
	mytoncoreStatus_text = local.translate("local_status_mytoncore_status").format(mytoncoreStatus_color, mytoncoreUptime_text)
	validatorStatus_text = local.translate("local_status_validator_status").format(validatorStatus_color, validatorUptime_text)
	btc_teleport_status_text = None
	if ton.using_validator():
		btc_teleport_status_bool = get_service_status("btc_teleport")
		btc_teleport_status_uptime = get_service_uptime("btc_teleport")
		btc_teleport_status_text = local.translate("local_status_btc_teleport_status").format(
			GetColorStatus(btc_teleport_status_bool),
			bcolors.green_text(time2human(btc_teleport_status_uptime)) if btc_teleport_status_bool else 'n/a'
		)

	validator_initial_sync_text = ''
	validator_out_of_sync_text = ''

	if validator_status.initial_sync:
		validator_initial_sync_text = local.translate("local_status_validator_initial_sync").format(validator_status['process.initial_sync'])
	elif ton.in_initial_sync():  # states have been downloaded, now downloading blocks
		validator_initial_sync_text = local.translate("local_status_validator_initial_sync").format(
			f'Syncing blocks, last known block was {validator_status.out_of_sync} s ago'
		)
	else:
		validator_out_of_sync_text = local.translate("local_status_validator_out_of_sync").format(GetColorInt(validator_status.out_of_sync, 20, logic="less"))
		master_out_of_sync_text = local.translate("local_status_master_out_of_sync").format(GetColorInt(validator_status.masterchain_out_of_sync, 20, logic="less", ending=" sec"))
		shard_out_of_sync_text = local.translate("local_status_shard_out_of_sync").format(GetColorInt(validator_status.shardchain_out_of_sync, 5, logic="less", ending=" blocks"))

	validator_out_of_ser_text = None

	if validator_status.stateserializerenabled:
		validator_out_of_ser_text = local.translate("local_status_validator_out_of_ser").format(f'{validator_status.out_of_ser} blocks ago')

	active_validator_groups = None

	if ton.using_validator() and validator_status.validator_groups_master is not None and validator_status.validator_groups_shard is not None:
		active_validator_groups = local.translate("active_validator_groups").format(validator_status.validator_groups_master, validator_status.validator_groups_shard)

	collated, validated = None, None
	ls_queries = None
	node_stats = local.try_function(ton.get_node_statistics)
	if node_stats is not None:
		if ton.using_validator():
			if 'collated' in node_stats and 'validated' in node_stats:
				collated = local.translate('collated_blocks').format(node_stats['collated']['ok'], node_stats['collated']['error'])
				validated = local.translate('validated_blocks').format(node_stats['validated']['ok'], node_stats['validated']['error'])
			else:
				collated = local.translate('collated_blocks').format('collecting data...', 'wait for the next validation round')
				validated = local.translate('validated_blocks').format('collecting data...', 'wait for the next validation round')
		if ton.using_liteserver():
			if 'ls_queries' in node_stats:
				ls_queries = local.translate('ls_queries').format(node_stats['ls_queries']['time'], node_stats['ls_queries']['ok'], node_stats['ls_queries']['error'])
	else:
		local.add_log("Failed to get node statistics", "warning")

	dbSize_text = GetColorInt(dbSize, 1000, logic="less", ending=" Gb")
	dbUsage_text = GetColorInt(dbUsage, 80, logic="less", ending="%")
	dbStatus_text = local.translate("local_status_db").format(dbSize_text, dbUsage_text)

	# Mytonctrl and validator git hash
	mtcGitPath = "/usr/src/mytonctrl"
	validatorGitPath = "/usr/src/ton"
	validatorBinGitPath = "/usr/bin/ton/validator-engine/validator-engine"
	btc_teleport_path = "/usr/src/ton-teleport-btc-periphery/"
	mtcGitHash = get_git_hash(mtcGitPath, short=True)
	validatorGitHash = get_bin_git_hash(validatorBinGitPath, short=True)
	btc_teleport_git_hash = None
	btc_teleport_git_branch = None
	if ton.using_validator():
		if os.path.exists(btc_teleport_path):
			btc_teleport_git_hash = get_git_hash(btc_teleport_path, short=True)
			btc_teleport_git_branch = get_git_branch(btc_teleport_path)
		else:
			btc_teleport_git_hash = "n/a"
			btc_teleport_git_branch = "n/a"
	fix_git_config(mtcGitPath)
	fix_git_config(validatorGitPath)
	mtcGitBranch = get_git_branch(mtcGitPath)
	validatorGitBranch = get_git_branch(validatorGitPath)
	mtcGitHash_text = bcolors.yellow_text(mtcGitHash)
	validatorGitHash_text = bcolors.yellow_text(validatorGitHash)
	mtcGitBranch_text = bcolors.yellow_text(mtcGitBranch)
	validatorGitBranch_text = bcolors.yellow_text(validatorGitBranch)
	mtcVersion_text = local.translate("local_status_version_mtc").format(mtcGitHash_text, mtcGitBranch_text)
	validatorVersion_text = local.translate("local_status_version_validator").format(validatorGitHash_text, validatorGitBranch_text)
	btc_teleport_version_text = None
	if btc_teleport_git_hash:
		btc_teleport_git_hash_text = bcolors.yellow_text(btc_teleport_git_hash)
		btc_teleport_git_branch_text = bcolors.yellow_text(btc_teleport_git_branch)
		btc_teleport_version_text = local.translate("local_status_version_teleport").format(btc_teleport_git_hash_text, btc_teleport_git_branch_text)

	color_print(local.translate("local_status_head"))
	node_mode = ton.get_node_mode()
	color_print(local.translate("node_mode").format(node_mode))
	node_ip = ton.get_validator_engine_ip()
	is_node_remote = node_ip != '127.0.0.1'
	if is_node_remote:
		nodeIpAddr_text = local.translate("node_ip_address").format(node_ip)
		color_print(nodeIpAddr_text)
	# Node ports
	if vconfig is not None:
		try:
			main_port = None
			quic_port = None
			for addr in vconfig.get("addrs", []):
				if addr.get("@type") == "engine.addr" and main_port is None:
					main_port = addr.get("port")
				elif addr.get("@type") == "engine.quicAddr" and quic_port is None:
					quic_port = addr.get("port")
			ports_parts = []
			if main_port is not None:
				ports_parts.append(bcolors.yellow_text(main_port))
			if ton.using_validator():
				if quic_port is not None:
					ports_parts.append(bcolors.yellow_text(f"{quic_port} (QUIC)"))
				elif main_port is not None:
					ports_parts.append(bcolors.yellow_text(f"{main_port + 1000} (QUIC)"))
			if ports_parts:
				color_print(local.translate("node_ports").format(", ".join(ports_parts)))
		except Exception:
			pass
	if ton.using_validator():
		print(validatorIndex_text)
		# print(validatorEfficiency_text)
	print(adnlAddr_text)
	print(fullnode_adnl_text)
	if ton.using_validator():
		print(walletAddr_text)
		print(walletBalance_text)
	print(cpuLoad_text)
	print(netLoad_text)
	print(memoryLoad_text)

	print(disksLoad_text)
	print(mytoncoreStatus_text)
	if not is_node_remote:
		print(validatorStatus_text)
	if btc_teleport_status_text:
		print(btc_teleport_status_text)
	if validator_initial_sync_text:
		print(validator_initial_sync_text)
	if validator_out_of_sync_text:
		print(validator_out_of_sync_text)
		print(master_out_of_sync_text)
		print(shard_out_of_sync_text)
	if validator_out_of_ser_text:
		print(validator_out_of_ser_text)
	if active_validator_groups:
		print(active_validator_groups)
	if collated and validated:
		print(collated)
		print(validated)
	if ls_queries:
		print(ls_queries)
	print(dbStatus_text)
	print(mtcVersion_text)
	print(validatorVersion_text)
	if btc_teleport_version_text:
		print(btc_teleport_version_text)
	print()
#end define

def GetColorStatus(status: bool):
	if status:
		result = bcolors.green_text("working")
	else:
		result = bcolors.red_text("not working")
	return result
#end define

def PrintTonConfig(local, fullConfigAddr, fullElectorAddr, config15, config17):
	validatorsElectedFor = config15["validatorsElectedFor"]
	electionsStartBefore = config15["electionsStartBefore"]
	electionsEndBefore = config15["electionsEndBefore"]
	stakeHeldFor = config15["stakeHeldFor"]
	minStake = config17["minStake"]
	maxStake = config17["maxStake"]

	fullConfigAddr_text = local.translate("ton_config_configurator_addr").format(bcolors.yellow_text(fullConfigAddr))
	fullElectorAddr_text = local.translate("ton_config_elector_addr").format(bcolors.yellow_text(fullElectorAddr))
	validatorsElectedFor_text = bcolors.yellow_text(validatorsElectedFor)
	electionsStartBefore_text = bcolors.yellow_text(electionsStartBefore)
	electionsEndBefore_text = bcolors.yellow_text(electionsEndBefore)
	stakeHeldFor_text = bcolors.yellow_text(stakeHeldFor)
	elections_text = local.translate("ton_config_elections").format(validatorsElectedFor_text, electionsStartBefore_text, electionsEndBefore_text, stakeHeldFor_text)
	minStake_text = bcolors.yellow_text(minStake)
	maxStake_text = bcolors.yellow_text(maxStake)
	stake_text = local.translate("ton_config_stake").format(minStake_text, maxStake_text)

	color_print(local.translate("ton_config_head"))
	print(fullConfigAddr_text)
	print(fullElectorAddr_text)
	print(elections_text)
	print(stake_text)
	print()
#end define

def PrintTimes(local, rootWorkchainEnabledTime_int, startWorkTime, oldStartWorkTime, config15):
	validatorsElectedFor = config15["validatorsElectedFor"]
	electionsStartBefore = config15["electionsStartBefore"]
	electionsEndBefore = config15["electionsEndBefore"]

	if startWorkTime == 0:
		startWorkTime = oldStartWorkTime
	#end if

	# Calculate time
	startValidation = startWorkTime
	endValidation = startWorkTime + validatorsElectedFor
	startElection = startWorkTime - electionsStartBefore
	endElection = startWorkTime - electionsEndBefore
	startNextElection = startElection + validatorsElectedFor

	# timestamp to datetime
	rootWorkchainEnabledTime = timestamp2utcdatetime(rootWorkchainEnabledTime_int)
	startValidationTime = timestamp2utcdatetime(startValidation)
	endValidationTime = timestamp2utcdatetime(endValidation)
	startElectionTime = timestamp2utcdatetime(startElection)
	endElectionTime = timestamp2utcdatetime(endElection)
	startNextElectionTime = timestamp2utcdatetime(startNextElection)

	# datetime to color text
	rootWorkchainEnabledTime_text = local.translate("times_root_workchain_enabled_time").format(bcolors.yellow_text(rootWorkchainEnabledTime))
	startValidationTime_text = local.translate("times_start_validation_time").format(GetColorTime(startValidationTime, startValidation))
	endValidationTime_text = local.translate("times_end_validation_time").format(GetColorTime(endValidationTime, endValidation))
	startElectionTime_text = local.translate("times_start_election_time").format(GetColorTime(startElectionTime, startElection))
	endElectionTime_text = local.translate("times_end_election_time").format(GetColorTime(endElectionTime, endElection))
	startNextElectionTime_text = local.translate("times_start_next_election_time").format(GetColorTime(startNextElectionTime, startNextElection))

	color_print(local.translate("times_head"))
	print(rootWorkchainEnabledTime_text)
	print(startValidationTime_text)
	print(endValidationTime_text)
	print(startElectionTime_text)
	print(endElectionTime_text)
	print(startNextElectionTime_text)
#end define


def GetColorTime(datetime, timestamp):
	newTimestamp = get_timestamp()
	if timestamp > newTimestamp:
		result = bcolors.green_text(datetime)
	else:
		result = bcolors.yellow_text(datetime)
	return result
#end define

def GetSettings(ton, args):
	if not check_usage_one_arg("get", args):
		return
	name = args[0]
	result = ton.GetSettings(name)
	print(json.dumps(result, indent=2))
#end define

def SetSettings(local, ton, args):
	if not check_usage_args_min_max_len("set", args, min_len=2, max_len=3):
		return
	name = args[0]
	value = args[1]
	if name == 'usePool' or name == 'useController':
		mode_name = 'nominator-pool' if name == 'usePool' else 'liquid-staking'
		color_print(f"{{red}} Error: set {name} ... is deprecated and does not work {{endc}}."
					f"\nInstead, use {{bold}}enable_mode {mode_name}{{endc}}")
		return
	force = False
	if len(args) > 2:
		if args[2] == "--force":
			force = True
	from modules import get_setting
	setting = get_setting(name)
	if setting is None and not force:
		color_print(f"{{red}} Error: setting {name} not found.{{endc}} Use flag --force to set it anyway")
		return
	if setting is not None and setting.mode is not None:
		if not ton.get_mode_value(setting.mode) and not force:
			color_print(f"{{red}} Error: mode {setting.mode} is disabled.{{endc}} Use flag --force to set it anyway")
			return
	ton.SetSettings(name, value)
	color_print("SetSettings - {green}OK{endc}")
#end define


def enable_mode(local, ton, args):
	if not check_usage_one_arg("enable_mode", args):
		return
	name = args[0]
	ton.enable_mode(name)
	color_print("enable_mode - {green}OK{endc}")
	local.exit()


def disable_mode(local, ton, args):
	if not check_usage_one_arg("disable_mode", args):
		return
	name = args[0]
	ton.disable_mode(name)
	color_print("disable_mode - {green}OK{endc}")
	local.exit()


def download_archive_blocks(local, args: list):
	if not check_usage_args_min_max_len('download_archive_blocks', args, 2, 5):
		return

	only_master = '--only-master' in args
	args.remove('--only-master') if only_master else None
	api_port = None
	if args[0].isdigit():
		api_port = int(args.pop(0))
	path = pathlib.Path(args[0])
	from_block = args[1]
	to_block = args[2] if len(args) >= 3 else None
	try:
		from_block, to_block = int(from_block), int(to_block) if to_block else None
	except ValueError:
		color_print("{red}Bad args. from_block and to_block must be integers.{endc}")
		return

	if api_port is None:
		api_port = get_ton_storage_port(local)
		if api_port is None:
			raise Exception('Failed to get Ton Storage API port and port was not provided')

	# check ton storage is alive
	local_ts_url = f"http://127.0.0.1:{api_port}"

	try:
		requests.get(local_ts_url + '/api/v1/list', timeout=3)
	except Exception as e:
		color_print(f"{{red}}Error: cannot connect to ton-storage at 127.0.0.1:{api_port}: {type(e)}: {e}. "
					f"Make sure `ton_storage` daemon is running or install it via `installer enable TS`.{{endc}}")
		return

	local.buffer.ton_storage = Dict()
	local.buffer.ton_storage.api_port = api_port
	local.buffer.global_config_path = '/usr/bin/ton/global.config.json'
	download_blocks(local, str(path.absolute()), from_block, to_block, only_master)


def set_quic_port(local: MyPyClass, ton: MyTonCore, args: list[str]):
	if not check_usage_args_min_max_len("set_quic_port", args, 1, 2):
		return
	try:
		port = int(args[0])
	except ValueError:
		color_print("{red}Port must be an integer{endc}")
		return
	if port < 0 or port > 65535:
		color_print("{red}Port must be between 0 and 65535{endc}")
		return
	category = 2
	if len(args) > 1:
		try:
			category = int(args[1])
		except ValueError:
			color_print("{red}Category must be an integer{endc}")
			return

	vconfig = ton.GetValidatorConfig()
	ip = int2ip(vconfig["addrs"][0]["ip"])
	adnl_addr = ton.GetAdnlAddr()
	if adnl_addr is None:
		raise Exception("ADNL address is not set")

	for addr in vconfig["addrs"]:
		if addr.get("@type") == "engine.addr" and category not in addr.get("categories", []):
			raise Exception(f"Category {category} is not set for address {addr}")


	for addr in vconfig["addrs"]:
		if addr.get("@type") == "engine.quicAddr":
			addr_ip = int2ip(addr["ip"])
			addr_port = addr["port"]
			cat = addr["categories"]
			priocat = addr["priority_categories"]
			cat = f"[ {' '.join(map(str, cat))} ]"
			priocat = f"[ {' '.join(map(str, priocat))} ]"
			result = ton.validatorConsole.Run(f"del-quic-addr {addr_ip}:{addr_port} {cat} {priocat}")
			color_print(f"Deleted quic addr {addr_ip}:{addr_port}: {result.splitlines()[-1].strip()}")

	if port > 0:
		ton.update_adnl_category(adnl_addr=adnl_addr, category=category)

		from modules.collator import CollatorModule
		collators = CollatorModule(ton, local).get_collators()
		collator_adnls = []
		for collator in collators:
			collator_adnls.append(b642hex(collator['adnl_id']).upper())
		for collator_adnl in set(collator_adnls):
			ton.update_adnl_category(adnl_addr=collator_adnl, category=category)

		result = ton.validatorConsole.Run(f"add-quic-addr {ip}:{port} [ {category} ] [ ]")
		local.add_log(f"Added quic addr {ip}:{port}: {result.splitlines()[-1].strip()}", "info")


### Start of the program
def mytonctrl():
	local = MyPyClass('mytonctrl.py')
	mytoncore_local = MyPyClass('mytoncore.py')
	ton = MyTonCore(mytoncore_local)
	console = MyPyConsole(local)
	Init(local, ton, console, sys.argv[1:])
	console.Run()
