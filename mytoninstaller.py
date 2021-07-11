#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import pwd
import random
import requests
from mypylib.mypylib import *
from mypyconsole.mypyconsole import *

local = MyPyClass(__file__)
console = MyPyConsole()


def Init():
	local.db["config"]["isStartOnlyOneProcess"] = False
	local.db["config"]["logLevel"] = "debug"
	local.db["config"]["isIgnorLogWarning"] = True # disable warning
	local.Run()
	local.db["config"]["isIgnorLogWarning"] = False # enable warning


	# create variables
	user = os.environ.get("USER", "root")
	local.buffer["user"] = user
	local.buffer["vuser"] = "validator"
	local.buffer["cport"] = random.randint(2000, 65000)
	local.buffer["lport"] = random.randint(2000, 65000)

	# Create user console
	console.name = "MyTonInstaller"
	console.color = console.RED
	console.AddItem("status", Status, "Print TON component status")
	console.AddItem("enable", Enable, "Enable some function: 'FN' - Full node, 'VC' - Validator console, 'LS' - Liteserver. Example: 'enable FN'")
	console.AddItem("plsc", PrintLiteServerConfig, "Print LiteServer config")

	Refresh()
#end define

def Refresh():
	user = local.buffer["user"]
	local.buffer["mconfigPath"] = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	if user == 'root':
		local.buffer["mconfigPath"] = "/usr/local/bin/mytoncore/mytoncore.db"
	#end if

	# create variables
	binDir = "/usr/bin/"
	srcDir = "/usr/src/"
	tonWorkDir = "/var/ton-work/"
	tonBinDir = binDir + "ton/"
	tonSrcDir = srcDir + "ton/"
	local.buffer["binDir"] = binDir
	local.buffer["srcDir"] = srcDir
	local.buffer["tonWorkDir"] = tonWorkDir
	local.buffer["tonBinDir"] = tonBinDir
	local.buffer["tonSrcDir"] = tonSrcDir
	tonDbDir = tonWorkDir + "db/"
	local.buffer["tonDbDir"] = tonDbDir
	local.buffer["tonLogPath"] = tonWorkDir + "log"
	local.buffer["validatorAppPath"] = tonBinDir + "validator-engine/validator-engine"
	local.buffer["globalConfigPath"] = tonBinDir + "validator-engine/ton-global.config.json"
	local.buffer["vconfigPath"] = tonDbDir + "config.json"
#end define

def Status(args):
	vconfigPath = local.buffer["vconfigPath"]

	user = local.buffer["user"]
	mconfigPath = local.buffer["mconfigPath"]

	tonBinDir = local.buffer["tonBinDir"]
	server_key = tonBinDir + "validator-engine-console/server"
	client_key = tonBinDir + "validator-engine-console/client"
	liteserver_key = tonBinDir + "validator-engine-console/liteserver"
	liteserver_pubkey = liteserver_key + ".pub"


	fnStatus = os.path.isfile(vconfigPath)
	mtcStatus = os.path.isfile(mconfigPath)
	vcStatus = os.path.isfile(server_key) or os.path.isfile(client_key)
	lsStatus = os.path.isfile(liteserver_pubkey)

	print("Full node status:", fnStatus)
	print("Mytoncore status:", mtcStatus)
	print("V.console status:", vcStatus)
	print("Liteserver status:", lsStatus)
#end define

def Enable(args):
	name = args[0]
	user = local.buffer["user"]
	args = ["python3", local.buffer["myPath"], "-u", user, "-e", "enable{name}".format(name=name)]
	RunAsRoot(args)
#end define

def PrintLiteServerConfig(args):
	result = dict()
	file = open("/usr/bin/ton/validator-engine-console/liteserver.pub", 'rb')
	data = file.read()
	file.close()
	key = base64.b64encode(data[4:])
	ip = requests.get("https://ifconfig.me").text
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)
	liteClient = mconfig.get("liteClient")
	liteServer = liteClient.get("liteServer")
	result["ip"] = ip2int(ip)
	result["port"] = liteServer.get("port")
	result["id"] = dict()
	result["id"]["@type"]= "pub.ed25519"
	result["id"]["key"]= key.decode()
	text = json.dumps(result, indent=4)
	print(text)
#end define

def Event(name):
	if name == "enableFN":
		FirstNodeSettings()
	if name == "enableVC":
		EnableValidatorConsole()
	if name == "enableLS":
		EnableLiteServer()
#end define

def General():
	if "-u" in sys.argv:
		ux = sys.argv.index("-u")
		user = sys.argv[ux+1]
		local.buffer["user"] = user
		Refresh()
	if "-e" in sys.argv:
		ex = sys.argv.index("-e")
		name = sys.argv[ex+1]
		Event(name)
	if "-m" in sys.argv:
		mx = sys.argv.index("-m")
		mode = sys.argv[mx+1]
	
		# Создать настройки для mytoncore.py
		FirstMytoncoreSettings()

		if mode == "full":
			FirstNodeSettings()
			EnableValidatorConsole()
			EnableLiteServer()
			BackupVconfig()
		#end if

		# Создать символические ссылки
		CreateSymlinks()
	#end if
#end define

def FirstNodeSettings():
	local.AddLog("start FirstNodeSettings fuction", "debug")

	# Создать переменные
	user = local.buffer["user"]
	vuser = local.buffer["vuser"]
	tonWorkDir = local.buffer["tonWorkDir"]
	tonDbDir = local.buffer["tonDbDir"]
	tonLogPath = local.buffer["tonLogPath"]
	validatorAppPath = local.buffer["validatorAppPath"]
	globalConfigPath = local.buffer["globalConfigPath"]
	vconfigPath = local.buffer["vconfigPath"]

	# Проверить конфигурацию
	if os.path.isfile(vconfigPath):
		local.AddLog("Validators config.json already exist. Break FirstNodeSettings fuction", "warning")
		return
	#end if

	# Создать пользователя
	file = open("/etc/passwd", 'rt')
	text = file.read()
	file.close()
	if vuser not in text:
		local.AddLog("Creating new user: " + vuser, "debug")
		args = ["/usr/sbin/useradd", "-d", "/dev/null", "-s", "/dev/null", vuser]
		subprocess.run(args)
	#end if

	# Подготовить папки валидатора
	os.makedirs(tonDbDir, exist_ok=True)
	
	# Прописать автозагрузку
	cmd = "{validatorAppPath} --daemonize --global-config {globalConfigPath} --db {tonDbDir} --logname {tonLogPath} --state-ttl 604800 --verbosity 1"
	cmd = cmd.format(validatorAppPath=validatorAppPath, globalConfigPath=globalConfigPath, tonDbDir=tonDbDir, tonLogPath=tonLogPath)
	Add2Systemd(name="validator", user=vuser, start=cmd) # post="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py -e \"validator down\""

	# Получить внешний ip адрес
	ip = requests.get("https://ifconfig.me").text
	vport = random.randint(2000, 65000)
	addr = "{ip}:{vport}".format(ip=ip, vport=vport)
	local.AddLog("Use addr: " + addr, "debug")
	
	# Первый запуск
	local.AddLog("First start validator - create config.json", "debug")
	args = [validatorAppPath, "--global-config", globalConfigPath, "--db", tonDbDir, "--ip", addr, "--logname", tonLogPath, "--sync-before", "3600000"]
	subprocess.run(args)

	# chown 1
	local.AddLog("Chown ton-work dir", "debug")
	args = ["chown", "-R", vuser + ':' + vuser, tonWorkDir]
	subprocess.run(args)

	# start validator
	StartValidator()
#end define

def FirstMytoncoreSettings():
	local.AddLog("start FirstMytoncoreSettings fuction", "debug")
	user = local.buffer["user"]

	# Прописать mytoncore.py в автозагрузку
	Add2Systemd(name="mytoncore", user=user, start="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py")
	
	# Проверить конфигурацию
	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path) or os.path.isfile(path2):
		local.AddLog("mytoncore.db already exist. Break FirstMytoncoreSettings fuction", "warning")
		return
	#end if

	#amazon bugfix
	path = "/home/{user}/.local/".format(user=user)
	os.makedirs(path, exist_ok=True)
	owner = pwd.getpwuid(os.stat(path).st_uid).pw_name
	if owner != user:
		local.AddLog("User does not have permission to access his `.local` folder", "warning")
		chownOwner = "{user}:{user}".format(user=user)
		args = ["chown", "-R", chownOwner, path]
		subprocess.run(args)
	#end if

	# Подготовить папку mytoncore
	mconfigPath = local.buffer["mconfigPath"]
	mconfigDir = GetDirFromPath(mconfigPath)
	os.makedirs(mconfigDir, exist_ok=True)

	# create variables
	srcDir = local.buffer["srcDir"]
	tonBinDir = local.buffer["tonBinDir"]
	tonSrcDir = local.buffer["tonSrcDir"]

	# general config
	mconfig = dict()
	mconfig["config"] = dict()
	mconfig["config"]["logLevel"] = "debug"
	mconfig["config"]["isLocaldbSaving"] = True

	# fift
	fift = dict()
	fift["appPath"] = tonBinDir + "crypto/fift"
	fift["libsPath"] = tonSrcDir + "crypto/fift/lib"
	fift["smartcontsPath"] = tonSrcDir + "crypto/smartcont"
	mconfig["fift"] = fift

	# lite-client
	liteClient = dict()
	liteClient["appPath"] = tonBinDir + "lite-client/lite-client"
	liteClient["configPath"] = tonBinDir + "lite-client/ton-lite-client-test1.config.json"
	mconfig["liteClient"] = liteClient

	# miner
	miner = dict()
	miner["appPath"] = tonBinDir + "crypto/pow-miner"
	mconfig["miner"] = miner

	# Telemetry
	if ("--no_send_telemetry" in sys.argv):
		sendTelemetry = False
	else:
		sendTelemetry = True
	mconfig["sendTelemetry"] = sendTelemetry

	# Записать настройки в файл
	SetConfig(path=mconfigPath, data=mconfig)

	# chown 1
	args = ["chown", user + ':' + user, mconfigDir, mconfigPath]
	subprocess.run(args)

	# start mytoncore
	StartMytoncore()
#end define

def EnableValidatorConsole():
	local.AddLog("start EnableValidatorConsole function", "debug")

	# Create variables
	user = local.buffer["user"]
	vuser = local.buffer["vuser"]
	cport = local.buffer["cport"]
	srcDir = local.buffer["srcDir"]
	tonDbDir = local.buffer["tonDbDir"]
	tonBinDir = local.buffer["tonBinDir"]
	vconfigPath = local.buffer["vconfigPath"]
	generate_random_id = tonBinDir + "utils/generate-random-id"
	server_key = tonBinDir + "validator-engine-console/server"
	server_pubkey = server_key + ".pub"
	client_key = tonBinDir + "validator-engine-console/client"
	client_pubkey = client_key + ".pub"

	# Check if key exist
	if os.path.isfile(server_key) or os.path.isfile(client_key):
		local.AddLog("Server or client key already exist. Break EnableValidatorConsole fuction", "warning")
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
	newKeyPath = tonDbDir + "/keyring/" + server_key_hex
	args = ["mv", server_key, newKeyPath]
	subprocess.run(args)

	# generate client key
	args = [generate_random_id, "--mode", "keys", "--name", client_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	client_key_hex = output_arr[0]
	client_key_b64 = output_arr[1].replace('\n', '')

	# chown 1
	args = ["chown", vuser + ':' + vuser, newKeyPath]
	subprocess.run(args)
	
	# chown 2
	args = ["chown", user + ':' + user, server_pubkey, client_key, client_pubkey]
	subprocess.run(args)

	# read vconfig
	vconfig = GetConfig(path=vconfigPath)

	# prepare config
	control = dict()
	control["id"] = server_key_b64
	control["port"] = cport
	allowed = dict()
	allowed["id"] = client_key_b64
	allowed["permissions"] = 15
	control["allowed"] = [allowed] # fix me
	vconfig["control"].append(control)

	# write vconfig
	SetConfig(path=vconfigPath, data=vconfig)

	# restart validator
	StartValidator()

	# read mconfig
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)

	# edit mytoncore config file
	validatorConsole = dict()
	validatorConsole["appPath"] = tonBinDir + "validator-engine-console/validator-engine-console"
	validatorConsole["privKeyPath"] = tonBinDir + "validator-engine-console/client"
	validatorConsole["pubKeyPath"] = tonBinDir + "validator-engine-console/server.pub"
	validatorConsole["addr"] = "127.0.0.1:{cport}".format(cport=cport)
	mconfig["validatorConsole"] = validatorConsole

	# write mconfig
	SetConfig(path=mconfigPath, data=mconfig)

	# Подтянуть событие в mytoncore.py
	cmd = "python3 {srcDir}mytonctrl/mytoncore.py -e \"enableVC\"".format(srcDir=srcDir)
	args = ["su", "-l", user, "-c", cmd]
	subprocess.run(args)
	
	# restart mytoncore
	StartMytoncore()
#end define

def EnableLiteServer():
	local.AddLog("start EnableLiteServer function", "debug")

	# Create variables
	user = local.buffer["user"]
	vuser = local.buffer["vuser"]
	lport = local.buffer["lport"]
	srcDir = local.buffer["srcDir"]
	tonDbDir = local.buffer["tonDbDir"]
	tonBinDir = local.buffer["tonBinDir"]
	vconfigPath = local.buffer["vconfigPath"]
	generate_random_id = tonBinDir + "utils/generate-random-id"
	liteserver_key = tonBinDir + "validator-engine-console/liteserver"
	liteserver_pubkey = liteserver_key + ".pub"

	# Check if key exist
	if os.path.isfile(liteserver_pubkey):
		local.AddLog("Liteserver key already exist. Break EnableLiteServer fuction", "warning")
		return
	#end if

	# generate liteserver key
	local.AddLog("generate liteserver key", "debug")
	args = [generate_random_id, "--mode", "keys", "--name", liteserver_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	liteserver_key_hex = output_arr[0]
	liteserver_key_b64 = output_arr[1].replace('\n', '')

	# move key
	local.AddLog("move key", "debug")
	newKeyPath = tonDbDir + "/keyring/" + liteserver_key_hex
	args = ["mv", liteserver_key, newKeyPath]
	subprocess.run(args)

	# chown 1
	local.AddLog("chown 1", "debug")
	args = ["chown", vuser + ':' + vuser, newKeyPath]
	subprocess.run(args)

	# chown 2
	local.AddLog("chown 2", "debug")
	args = ["chown", user + ':' + user, liteserver_pubkey]
	subprocess.run(args)

	# read vconfig
	local.AddLog("read vconfig", "debug")
	vconfig = GetConfig(path=vconfigPath)

	# prepare vconfig
	local.AddLog("prepare vconfig", "debug")
	liteserver = dict()
	liteserver["id"] = liteserver_key_b64
	liteserver["port"] = lport
	vconfig["liteservers"].append(liteserver)

	# write vconfig
	local.AddLog("write vconfig", "debug")
	SetConfig(path=vconfigPath, data=vconfig)

	# restart validator
	StartValidator()

	# edit mytoncore config file
	# read mconfig
	local.AddLog("read mconfig", "debug")
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)

	# edit mytoncore config file
	local.AddLog("edit mytoncore config file", "debug")
	liteServer = dict()
	liteServer["pubkeyPath"] = liteserver_pubkey
	liteServer["ip"] = "127.0.0.1"
	liteServer["port"] = lport
	mconfig["liteClient"]["liteServer"] = liteServer

	# write mconfig
	local.AddLog("write mconfig", "debug")
	SetConfig(path=mconfigPath, data=mconfig)
	
	# restart mytoncore
	StartMytoncore()
#end define

def StartValidator():
	# restart validator
	local.AddLog("Start/restart validator service", "debug")
	args = ["systemctl", "restart", "validator"]
	subprocess.run(args)

	# sleep 10 sec
	local.AddLog("sleep 10 sec", "debug")
	time.sleep(10)
#end define

def StartMytoncore():
	# restart mytoncore
	local.AddLog("Start/restart mytoncore service", "debug")
	args = ["systemctl", "restart", "mytoncore"]
	subprocess.run(args)
#end define

def GetConfig(**kwargs):
	path = kwargs.get("path")
	file = open(path, 'rt')
	text = file.read()
	file.close()
	config = json.loads(text)
	return config
#end define

def SetConfig(**kwargs):
	path = kwargs.get("path")
	data = kwargs.get("data")

	# write config
	text = json.dumps(data, indent=4)
	file = open(path, 'wt')
	file.write(text)
	file.close()
#end define

def BackupVconfig():
	local.AddLog("Backup validator config file 'config.json' to 'config.json.backup'", "debug")
	vconfigPath = local.buffer["vconfigPath"]
	backupPath = vconfigPath + ".backup"
	args = ["cp", vconfigPath, backupPath]
	subprocess.run(args)
#end define

def CreateSymlinks():
	local.AddLog("start CreateSymlinks fuction", "debug")
	cport = local.buffer["cport"]

	mytonctrl_file = "/usr/bin/mytonctrl"
	fift_file = "/usr/bin/fift"
	liteclient_file = "/usr/bin/lite-client"
	validator_console_file = "/usr/bin/validator-console"
	env_file = "/etc/environment"
	file = open(mytonctrl_file, 'wt')
	file.write("/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py $@")
	file.close()
	file = open(fift_file, 'wt')
	file.write("/usr/bin/ton/crypto/fift $@")
	file.close()
	file = open(liteclient_file, 'wt')
	file.write("/usr/bin/ton/lite-client/lite-client -C /usr/bin/ton/lite-client/ton-lite-client-test1.config.json $@")
	file.close()
	if cport:
		file = open(validator_console_file, 'wt')
		file.write("/usr/bin/ton/validator-engine-console/validator-engine-console -k /usr/bin/ton/validator-engine-console/client -p /usr/bin/ton/validator-engine-console/server.pub -a 127.0.0.1:" + str(cport) + " $@")
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


###
### Start of the program
###

if __name__ == "__main__":
	Init()
	if len(sys.argv) > 1:
		General()
	else:
		console.Run()
	local.Exit()
#end if
