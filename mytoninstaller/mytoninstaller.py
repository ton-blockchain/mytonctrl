#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os, sys
import inspect
import random
import json
import subprocess

from mypylib.mypylib import MyPyClass, run_as_root
from mypyconsole.mypyconsole import MyPyConsole

from mytoninstaller.config import GetLiteServerConfig
from mytoninstaller.utils import GetInitBlock
from mytoncore.utils import dict2b64, str2bool, b642dict

from mytoninstaller.settings import (
    FirstNodeSettings,
    FirstMytoncoreSettings,
    EnableValidatorConsole,
    EnableLiteServer,
    EnableDhtServer,
    EnableJsonRpc,
    EnablePytonv3,
	EnableTonHttpApi,
    DangerousRecoveryValidatorConfigFile,
    CreateSymlinks,
)
from mytoninstaller.config import (
    CreateLocalConfig,
    BackupVconfig,
    BackupMconfig,
)

from functools import partial


def Init(local, console):
	local.db.config.isStartOnlyOneProcess = False
	local.db.config.logLevel = "debug"
	local.db.config.isIgnorLogWarning = True # disable warning
	local.run()
	local.db.config.isIgnorLogWarning = False # enable warning


	# create variables
	user = os.environ.get("USER", "root")
	local.buffer.user = user
	local.buffer.vuser = "validator"
	local.buffer.cport = random.randint(2000, 65000)
	local.buffer.lport = random.randint(2000, 65000)

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
	console.AddItem("status", inject_globals(Status), "Print TON component status")
	console.AddItem("enable", inject_globals(Enable), "Enable some function: 'FN' - Full node, 'VC' - Validator console, 'LS' - Liteserver, 'DS' - DHT-Server, 'JR' - jsonrpc, 'PT' - ton-http-api. Example: 'enable FN'")
	console.AddItem("update", inject_globals(Enable), "Update some function: 'JR' - jsonrpc.  Example: 'update JR'") 
	console.AddItem("plsc", inject_globals(PrintLiteServerConfig), "Print LiteServer config")
	console.AddItem("clcf", inject_globals(CreateLocalConfigFile), "CreateLocalConfigFile")
	console.AddItem("drvcf", inject_globals(DRVCF), "Dangerous recovery validator config file")
	console.AddItem("setwebpass", inject_globals(SetWebPassword), "Set a password for the web admin interface")

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
	local.buffer.bin_dir = bin_dir
	local.buffer.src_dir = src_dir
	local.buffer.ton_work_dir = ton_work_dir
	local.buffer.ton_bin_dir = ton_bin_dir
	local.buffer.ton_src_dir = ton_src_dir
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


	fnStatus = os.path.isfile(local.buffer.vconfig_path)
	mtcStatus = os.path.isfile(local.buffer.mconfig_path)
	vcStatus = os.path.isfile(server_key) or os.path.isfile(client_key)
	lsStatus = os.path.isfile(liteserver_pubkey)

	print("Full node status:", fnStatus)
	print("Mytoncore status:", mtcStatus)
	print("V.console status:", vcStatus)
	print("Liteserver status:", lsStatus)
#end define


def Enable(local, args):
	name = args[0]
	if name == "PT":
		CreateLocalConfigFile(local, args)
	args = ["python3", "-m", "mytoninstaller", "-u", local.buffer.user, "-e", "enable{name}".format(name=name)]
	run_as_root(args)
#end define


def DRVCF(local, args):
	user = local.buffer["user"]
	args = ["python3", "-m", "mytoninstaller", "-u", local.buffer.user, "-e", "drvcf"]
	run_as_root(args)
#end define


def SetWebPassword(args):
	args = ["python3", "/usr/src/mtc-jsonrpc/mtc-jsonrpc.py", "-p"]
	subprocess.run(args)
#end define


def PrintLiteServerConfig(local, args):
	liteServerConfig = GetLiteServerConfig(local)
	text = json.dumps(liteServerConfig, indent=4)
	print(text)
#end define


def CreateLocalConfigFile(local, args):
	initBlock = GetInitBlock()
	initBlock_b64 = dict2b64(initBlock)
	user = local.buffer["user"]
	args = ["python3", "-m", "mytoninstaller", "-u", local.buffer.user, "-e", "clc", "-i", initBlock_b64]
	run_as_root(args)
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
	if name == "enablePT":
		# EnablePytonv3(local)
		EnableTonHttpApi(local)
	if name == "clc":
		ix = sys.argv.index("-i")
		initBlock_b64 = sys.argv[ix+1]
		initBlock = b642dict(initBlock_b64)
		CreateLocalConfig(local, initBlock)
#end define


def General(local):
	if "-u" in sys.argv:
		ux = sys.argv.index("-u")
		user = sys.argv[ux+1]
		local.buffer.user = user
		Refresh(local)
	if "-e" in sys.argv:
		ex = sys.argv.index("-e")
		name = sys.argv[ex+1]
		Event(local, name)
	if "-m" in sys.argv:
		mx = sys.argv.index("-m")
		mode = sys.argv[mx+1]
	if "-t" in sys.argv:
		mx = sys.argv.index("-t")
		telemetry = sys.argv[mx+1]
		local.buffer.telemetry = str2bool(telemetry)
	if "--dump" in sys.argv:
		mx = sys.argv.index("--dump")
		dump = sys.argv[mx+1]
		local.buffer.dump = str2bool(dump)
	#end if

		# Создать настройки для mytoncore.py
		FirstMytoncoreSettings(local)

		if mode == "full":
			FirstNodeSettings(local)
			EnableValidatorConsole(local)
			EnableLiteServer(local)
			BackupVconfig(local)
			BackupMconfig(local)
		#end if

		# Создать символические ссылки
		CreateSymlinks(local)
	#end if
#end define


###
### Start of the program
###
def mytoninstaller():
    local = MyPyClass(__file__)
    console = MyPyConsole()

    Init(local, console)
    if len(sys.argv) > 1:
        General(local)
    else:
        console.Run()
    local.exit()
