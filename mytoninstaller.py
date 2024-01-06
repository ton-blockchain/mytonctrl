#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import pwd
import random
import requests
from mypylib.mypylib import *
from mypyconsole.mypyconsole import *

local = MyPyClass(__file__)
console = MyPyConsole()
defaultLocalConfigPath = "/usr/bin/ton/local.config.json"


def Init():
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

	# Create user console
	console.name = "MyTonInstaller"
	console.color = console.RED
	console.AddItem("status", Status, "Print TON component status")
	console.AddItem("enable", Enable, "Enable some function: 'FN' - Full node, 'VC' - Validator console, 'LS' - Liteserver, 'DS' - DHT-Server, 'JR' - jsonrpc, 'PT' - pyTONv3. Example: 'enable FN'")
	console.AddItem("update", Enable, "Update some function: 'JR' - jsonrpc.  Example: 'update JR'") 
	console.AddItem("plsc", PrintLiteServerConfig, "Print LiteServer config")
	console.AddItem("clcf", CreateLocalConfigFile, "CreateLocalConfigFile")
	console.AddItem("drvcf", DRVCF, "Dangerous recovery validator config file")
	console.AddItem("setwebpass", SetWebPassword, "Set a password for the web admin interface")

	Refresh()
#end define

def Refresh():
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

def Status(args):
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

def Enable(args):
	name = args[0]
	if name == "PT":
		CreateLocalConfigFile(args)
	args = ["python3", local.buffer.my_path, "-u", local.buffer.user, "-e", "enable{name}".format(name=name)]
	run_as_root(args)
#end define

def DRVCF(args):
	args = ["python3", local.buffer.my_path, "-u", local.buffer.user, "-e", "drvcf"]
	run_as_root(args)
#end define

def get_own_ip():
	requests.packages.urllib3.util.connection.HAS_IPV6 = False
	ip = requests.get("https://ifconfig.me/ip").text
	return ip
#end define

def GetLiteServerConfig():
	keys_dir = local.buffer.keys_dir
	liteserver_key = keys_dir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"
	result = Dict()
	file = open(liteserver_pubkey, 'rb')
	data = file.read()
	file.close()
	key = base64.b64encode(data[4:])
	ip = get_own_ip()
	mconfig = GetConfig(path=local.buffer.mconfig_path)
	result.ip = ip2int(ip)
	result.port = mconfig.liteClient.liteServer.port
	result.id = Dict()
	result.id["@type"]= "pub.ed25519"
	result.id.key= key.decode()
	return result
#end define

def GetInitBlock():
	from mytoncore import MyTonCore
	ton = MyTonCore()
	initBlock = ton.GetInitBlock()
	return initBlock
#end define

def CreateLocalConfig(initBlock, localConfigPath=defaultLocalConfigPath):
	# dirty hack, but GetInitBlock() function uses the same technique
	from mytoncore import hex2base64

	# read global config file
	file = open("/usr/bin/ton/global.config.json", 'rt')
	text = file.read()
	data = json.loads(text)
	file.close()

	# edit config
	liteServerConfig = GetLiteServerConfig()
	data["liteservers"] = [liteServerConfig]
	data["validator"]["init_block"]["seqno"] = initBlock["seqno"]
	data["validator"]["init_block"]["root_hash"] = hex2base64(initBlock["rootHash"])
	data["validator"]["init_block"]["file_hash"] = hex2base64(initBlock["fileHash"])
	text = json.dumps(data, indent=4)

	# write local config file
	file = open(localConfigPath, 'wt')
	file.write(text)
	file.close()

	# chown
	user = local.buffer.user
	args = ["chown", "-R", user + ':' + user, localConfigPath]

	print("Local config file created:", localConfigPath)
#end define

def PrintLiteServerConfig(args):
	liteServerConfig = GetLiteServerConfig()
	text = json.dumps(liteServerConfig, indent=4)
	print(text)
#end define

def CreateLocalConfigFile(args):
	initBlock = GetInitBlock()
	initBlock_b64 = dict2b64(initBlock)
	args = ["python3", local.buffer.my_path, "-u", local.buffer.user, "-e", "clc", "-i", initBlock_b64]
	run_as_root(args)
#end define

def Event(name):
	if name == "enableFN":
		FirstNodeSettings()
	if name == "enableVC":
		EnableValidatorConsole()
	if name == "enableLS":
		EnableLiteServer()
	if name == "enableDS":
		EnableDhtServer()
	if name == "drvcf":
		DangerousRecoveryValidatorConfigFile()
	if name == "enableJR":
		EnableJsonRpc()
	if name == "enablePT":
		EnablePytonv3()
	if name == "clc":
		ix = sys.argv.index("-i")
		initBlock_b64 = sys.argv[ix+1]
		initBlock = b642dict(initBlock_b64)
		CreateLocalConfig(initBlock)
#end define

def General():
	if "-u" in sys.argv:
		ux = sys.argv.index("-u")
		user = sys.argv[ux+1]
		local.buffer.user = user
		Refresh()
	if "-e" in sys.argv:
		ex = sys.argv.index("-e")
		name = sys.argv[ex+1]
		Event(name)
	if "-m" in sys.argv:
		mx = sys.argv.index("-m")
		mode = sys.argv[mx+1]
	if "-t" in sys.argv:
		mx = sys.argv.index("-t")
		telemetry = sys.argv[mx+1]
		local.buffer.telemetry = Str2Bool(telemetry)
	if "--dump" in sys.argv:
		mx = sys.argv.index("--dump")
		dump = sys.argv[mx+1]
		local.buffer.dump = Str2Bool(dump)
	#end if

		# Создать настройки для mytoncore.py
		FirstMytoncoreSettings()

		if mode == "full":
			FirstNodeSettings()
			EnableValidatorConsole()
			EnableLiteServer()
			BackupVconfig()
			BackupMconfig()
		#end if

		# Создать символические ссылки
		CreateSymlinks()
	#end if
#end define

def Str2Bool(str):
	if str == "true":
		return True
	return False
#end define

def FirstNodeSettings():
	local.add_log("start FirstNodeSettings fuction", "debug")

	# Создать переменные
	user = local.buffer.user
	vuser = local.buffer.vuser
	ton_work_dir = local.buffer.ton_work_dir
	ton_db_dir = local.buffer.ton_db_dir
	keys_dir = local.buffer.keys_dir
	tonLogPath = local.buffer.ton_log_path
	validatorAppPath = local.buffer.validator_app_path
	globalConfigPath = local.buffer.global_config_path
	vconfig_path = local.buffer.vconfig_path

	# Проверить конфигурацию
	if os.path.isfile(vconfig_path):
		local.add_log("Validators config.json already exist. Break FirstNodeSettings fuction", "warning")
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
	cmd = "{validatorAppPath} --threads {cpus} --daemonize --global-config {globalConfigPath} --db {ton_db_dir} --logname {tonLogPath} --state-ttl 604800 --verbosity 1"
	cmd = cmd.format(validatorAppPath=validatorAppPath, globalConfigPath=globalConfigPath, ton_db_dir=ton_db_dir, tonLogPath=tonLogPath, cpus=cpus)
	add2systemd(name="validator", user=vuser, start=cmd) # post="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py -e \"validator down\""

	# Получить внешний ip адрес
	ip = get_own_ip()
	vport = random.randint(2000, 65000)
	addr = "{ip}:{vport}".format(ip=ip, vport=vport)
	local.add_log("Use addr: " + addr, "debug")

	# Первый запуск
	local.add_log("First start validator - create config.json", "debug")
	args = [validatorAppPath, "--global-config", globalConfigPath, "--db", ton_db_dir, "--ip", addr, "--logname", tonLogPath]
	subprocess.run(args)

	# Скачать дамп
	DownloadDump()

	# chown 1
	local.add_log("Chown ton-work dir", "debug")
	args = ["chown", "-R", vuser + ':' + vuser, ton_work_dir]
	subprocess.run(args)

	# start validator
	StartValidator()
#end define

def DownloadDump():
	dump = local.buffer.dump
	if dump == False:
		return
	#end if

	local.add_log("start DownloadDump fuction", "debug")
	url = "https://dump.ton.org"
	dumpSize = requests.get(url + "/dumps/latest.size.archive.txt").text
	print("dumpSize:", dumpSize)
	needSpace = int(dumpSize) * 3
	diskSpace = psutil.disk_usage("/var")
	if needSpace > diskSpace.free:
		return
	#end if

	# apt install
	cmd = "apt install plzip pv -y"
	os.system(cmd)

	# download dump
	cmd = "curl -Ls {url}/dumps/latest.tar.lz | pv | plzip -d -n8 | tar -xC /var/ton-work/db".format(url=url)
	os.system(cmd)
#end define

def FirstMytoncoreSettings():
	local.add_log("start FirstMytoncoreSettings fuction", "debug")
	user = local.buffer.user

	# Прописать mytoncore.py в автозагрузку
	add2systemd(name="mytoncore", user=user, start="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py")

	# Проверить конфигурацию
	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path) or os.path.isfile(path2):
		local.add_log("mytoncore.db already exist. Break FirstMytoncoreSettings fuction", "warning")
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
	mconfig_path = local.buffer.mconfig_path
	mconfigDir = get_dir_from_path(mconfig_path)
	os.makedirs(mconfigDir, exist_ok=True)

	# create variables
	src_dir = local.buffer.src_dir
	ton_bin_dir = local.buffer.ton_bin_dir
	ton_src_dir = local.buffer.ton_src_dir

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
	mconfig.sendTelemetry = local.buffer.telemetry

	# Записать настройки в файл
	SetConfig(path=mconfig_path, data=mconfig)

	# chown 1
	args = ["chown", user + ':' + user, mconfigDir, mconfig_path]
	subprocess.run(args)

	# start mytoncore
	StartMytoncore()
#end define

def EnableValidatorConsole():
	local.add_log("start EnableValidatorConsole function", "debug")

	# Create variables
	user = local.buffer.user
	vuser = local.buffer.vuser
	cport = local.buffer.cport
	src_dir = local.buffer.src_dir
	ton_db_dir = local.buffer.ton_db_dir
	ton_bin_dir = local.buffer.ton_bin_dir
	vconfig_path = local.buffer.vconfig_path
	generate_random_id = ton_bin_dir + "utils/generate-random-id"
	keys_dir = local.buffer.keys_dir
	client_key = keys_dir + "client"
	server_key = keys_dir + "server"
	client_pubkey = client_key + ".pub"
	server_pubkey = server_key + ".pub"

	# Check if key exist
	if os.path.isfile(server_key) or os.path.isfile(client_key):
		local.add_log("Server or client key already exist. Break EnableValidatorConsole fuction", "warning")
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
	client_key_hex = output_arr[0]
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
	StartValidator()

	# read mconfig
	mconfig_path = local.buffer.mconfig_path
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

	# Подтянуть событие в mytoncore.py
	cmd = "python3 {src_dir}mytonctrl/mytoncore.py -e \"enableVC\"".format(src_dir=src_dir)
	args = ["su", "-l", user, "-c", cmd]
	subprocess.run(args)

	# restart mytoncore
	StartMytoncore()
#end define

def EnableLiteServer():
	local.add_log("start EnableLiteServer function", "debug")

	# Create variables
	user = local.buffer.user
	vuser = local.buffer.vuser
	lport = local.buffer.lport
	src_dir = local.buffer.src_dir
	ton_db_dir = local.buffer.ton_db_dir
	keys_dir = local.buffer.keys_dir
	ton_bin_dir = local.buffer.ton_bin_dir
	vconfig_path = local.buffer.vconfig_path
	generate_random_id = ton_bin_dir + "utils/generate-random-id"
	liteserver_key = keys_dir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"

	# Check if key exist
	if os.path.isfile(liteserver_pubkey):
		local.add_log("Liteserver key already exist. Break EnableLiteServer fuction", "warning")
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
	StartValidator()

	# edit mytoncore config file
	# read mconfig
	local.add_log("read mconfig", "debug")
	mconfig_path = local.buffer.mconfig_path
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
	StartMytoncore()
#end define

def StartValidator():
	# restart validator
	local.add_log("Start/restart validator service", "debug")
	args = ["systemctl", "restart", "validator"]
	subprocess.run(args)

	# sleep 10 sec
	local.add_log("sleep 10 sec", "debug")
	time.sleep(10)
#end define

def StartMytoncore():
	# restart mytoncore
	local.add_log("Start/restart mytoncore service", "debug")
	args = ["systemctl", "restart", "mytoncore"]
	subprocess.run(args)
#end define

def GetConfig(**kwargs):
	path = kwargs.get("path")
	file = open(path, 'rt')
	text = file.read()
	file.close()
	config = Dict(json.loads(text))
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
	local.add_log("Backup validator config file 'config.json' to 'config.json.backup'", "debug")
	vconfig_path = local.buffer.vconfig_path
	backupPath = vconfig_path + ".backup"
	args = ["cp", vconfig_path, backupPath]
	subprocess.run(args)
#end define

def BackupMconfig():
	local.add_log("Backup mytoncore config file 'mytoncore.db' to 'mytoncore.db.backup'", "debug")
	mconfig_path = local.buffer.mconfig_path
	backupPath = mconfig_path + ".backup"
	args = ["cp", mconfig_path, backupPath]
	subprocess.run(args)
#end define

def GetPortsFromVconfig():
	vconfig_path = local.buffer.vconfig_path

	# read vconfig
	local.add_log("read vconfig", "debug")
	vconfig = GetConfig(path=vconfig_path)

	# read mconfig
	local.add_log("read mconfig", "debug")
	mconfig_path = local.buffer.mconfig_path
	mconfig = GetConfig(path=mconfig_path)

	# edit mytoncore config file
	local.add_log("edit mytoncore config file", "debug")
	mconfig.liteClient.liteServer.port = mconfig.liteservers[0].port
	mconfig.validatorConsole.addr = f"127.0.0.1:{mconfig.control[0].port}"

	# write mconfig
	local.add_log("write mconfig", "debug")
	SetConfig(path=mconfig_path, data=mconfig)

	# restart mytoncore
	StartMytoncore()
#end define

def DangerousRecoveryValidatorConfigFile():
	local.add_log("start DangerousRecoveryValidatorConfigFile function", "info")

	# install and import cryptography library
	args = ["pip3", "install", "cryptography"]
	subprocess.run(args)
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

	# Get keys from keyring
	keys = list()
	keyringDir = "/var/ton-work/db/keyring/"
	keyring = os.listdir(keyringDir)
	os.chdir(keyringDir)
	sorted(keyring, key=os.path.getmtime)
	for item in keyring:
		b64String = hex2b64(item)
		keys.append(b64String)
	#end for

	# Create config object
	vconfig = Dict()
	vconfig["@type"] = "engine.validator.config"
	vconfig.out_port = 3278

	# Create addrs object
	buff = Dict()
	buff["@type"] = "engine.addr"
	buff.ip = ip2int(get_own_ip())
	buff.port = None
	buff.categories = [0, 1, 2, 3]
	buff.priority_categories = []
	vconfig.addrs = [buff]

	# Get liteserver fragment
	mconfig_path = local.buffer.mconfig_path
	mconfig = GetConfig(path=mconfig_path)
	lkey = mconfig.liteClient.liteServer.pubkeyPath
	lport = mconfig.liteClient.liteServer.port

	# Read lite server pubkey
	file = open(lkey, 'rb')
	data = file.read()
	file.close()
	ls_pubkey = data[4:]

	# Search lite server priv key
	for item in keyring:
		path = keyringDir + item
		file = open(path, 'rb')
		data = file.read()
		file.close()
		peivkey = data[4:]
		privkeyObject = Ed25519PrivateKey.from_private_bytes(peivkey)
		pubkeyObject = privkeyObject.public_key()
		pubkey = pubkeyObject.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
		if pubkey == ls_pubkey:
			ls_id = hex2b64(item)
			keys.remove(ls_id)
	#end for

	# Create LS object
	buff = Dict()
	buff["@type"] = "engine.liteServer"
	buff.id = ls_id
	buff.port = lport
	vconfig.liteservers = [buff]

	# Get validator-console fragment
	ckey = mconfig.validatorConsole.pubKeyPath
	addr = mconfig.validatorConsole.addr
	buff = addr.split(':')
	cport = int(buff[1])

	# Read validator-console pubkey
	file = open(ckey, 'rb')
	data = file.read()
	file.close()
	vPubkey = data[4:]

	# Search validator-console priv key
	for item in keyring:
		path = keyringDir + item
		file = open(path, 'rb')
		data = file.read()
		file.close()
		peivkey = data[4:]
		privkeyObject = Ed25519PrivateKey.from_private_bytes(peivkey)
		pubkeyObject = privkeyObject.public_key()
		pubkey = pubkeyObject.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
		if pubkey == vPubkey:
			vcId = hex2b64(item)
			keys.remove(vcId)
	#end for

	# Create VC object
	buff = Dict()
	buff2 = Dict()
	buff["@type"] = "engine.controlInterface"
	buff.id = vcId
	buff.port = cport
	buff2["@type"] = "engine.controlProcess"
	buff2.id = None
	buff2.permissions = 15
	buff.allowed = buff2
	vconfig.control = [buff]

	# Get dht fragment
	files = os.listdir("/var/ton-work/db")
	for item in files:
		if item[:3] == "dht":
			dhtS = item[4:]
			dhtS = dhtS.replace('_', '/')
			dhtS = dhtS.replace('-', '+')
			break
	#end for

	# Get ght from keys
	for item in keys:
		if dhtS in item:
			dhtId = item
			keys.remove(dhtId)
	#end for

	# Create dht object
	buff = Dict()
	buff["@type"] = "engine.dht"
	buff.id = dhtId
	vconfig.dht = [buff]

	# Create adnl object
	adnl2 = Dict()
	adnl2["@type"] = "engine.adnl"
	adnl2.id = dhtId
	adnl2.category = 0

	# Create adnl object
	adnlId = hex2b64(mconfig["adnlAddr"])
	keys.remove(adnlId)
	adnl3 = Dict()
	adnl3["@type"] = "engine.adnl"
	adnl3.id = adnlId
	adnl3.category = 0

	# Create adnl object
	adnl1 = Dict()
	adnl1["@type"] = "engine.adnl"
	adnl1.id = keys.pop(0)
	adnl1.category = 1

	vconfig.adnl = [adnl1, adnl2, adnl3]

	# Get dumps from tmp
	dumps = list()
	dumpsDir = "/tmp/mytoncore/"
	dumpsList = os.listdir(dumpsDir)
	os.chdir(dumpsDir)
	sorted(dumpsList, key=os.path.getmtime)
	for item in dumpsList:
		if "ElectionEntry.json" in item:
			dumps.append(item)
	#end for

	# Create validators object
	validators = list()

	# Read dump file
	while len(keys) > 0:
		dumpPath = dumps.pop()
		file = open(dumpPath, 'rt')
		data = file.read()
		file.close()
		dump = json.loads(data)
		vkey = hex2b64(dump["validatorKey"])
		temp_key = Dict()
		temp_key["@type"] = "engine.validatorTempKey"
		temp_key.key = vkey
		temp_key.expire_at = dump["endWorkTime"]
		adnl_addr = Dict()
		adnl_addr["@type"] = "engine.validatorAdnlAddress"
		adnl_addr.id = adnlId
		adnl_addr.expire_at = dump["endWorkTime"]

		# Create validator object
		validator = Dict()
		validator["@type"] = "engine.validator"
		validator.id = vkey
		validator.temp_keys = [temp_key]
		validator.adnl_addrs = [adnl_addr]
		validator.election_date = dump["startWorkTime"]
		validator.expire_at = dump["endWorkTime"]
		if vkey in keys:
			validators.append(validator)
			keys.remove(vkey)
		#end if
	#end while

	# Add validators object to vconfig
	vconfig.validators = validators


	print("vconfig:", json.dumps(vconfig, indent=4))
	print("keys:", keys)
#end define

def hex2b64(input):
	hexBytes = bytes.fromhex(input)
	b64Bytes = base64.b64encode(hexBytes)
	b64String = b64Bytes.decode()
	return b64String
#end define

def b642hex(input):
	b64Bytes = input.encode()
	hexBytes = base64.b64decode(b64Bytes)
	hexString = hexBytes.hex()
	return hexString
#end define

def CreateSymlinks():
	local.add_log("start CreateSymlinks fuction", "debug")
	cport = local.buffer.cport

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
	file.write("/usr/bin/ton/lite-client/lite-client -C /usr/bin/ton/global.config.json $@")
	file.close()
	if cport:
		file = open(validator_console_file, 'wt')
		file.write("/usr/bin/ton/validator-engine-console/validator-engine-console -k /var/ton-work/keys/client -p /var/ton-work/keys/server.pub -a 127.0.0.1:" + str(cport) + " $@")
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

def EnableDhtServer():
	local.add_log("start EnableDhtServer function", "debug")
	vuser = local.buffer.vuser
	ton_bin_dir = local.buffer.ton_bin_dir
	globalConfigPath = local.buffer.global_config_path
	dht_server = ton_bin_dir + "dht-server/dht-server"
	generate_random_id = ton_bin_dir + "utils/generate-random-id"
	tonDhtServerDir = "/var/ton-dht-server/"
	tonDhtKeyringDir = tonDhtServerDir + "keyring/"

	# Проверить конфигурацию
	if os.path.isfile("/var/ton-dht-server/config.json"):
		local.add_log("DHT-Server config.json already exist. Break EnableDhtServer fuction", "warning")
		return
	#end if

	# Подготовить папку
	os.makedirs(tonDhtServerDir, exist_ok=True)

	# Прописать автозагрузку
	cmd = "{dht_server} -C {globalConfigPath} -D {tonDhtServerDir}"
	cmd = cmd.format(dht_server=dht_server, globalConfigPath=globalConfigPath, tonDhtServerDir=tonDhtServerDir)
	add2systemd(name="dht-server", user=vuser, start=cmd)

	# Получить внешний ip адрес
	ip = get_own_ip()
	port = random.randint(2000, 65000)
	addr = "{ip}:{port}".format(ip=ip, port=port)

	# Первый запуск
	args = [dht_server, "-C", globalConfigPath, "-D", tonDhtServerDir, "-I", addr]
	subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

	# Получить вывод конфига
	key = os.listdir(tonDhtKeyringDir)[0]
	ip = ip2int(ip)
	text = '{"@type": "adnl.addressList", "addrs": [{"@type": "adnl.address.udp", "ip": ' + str(ip) + ', "port": ' + str(port) + '}], "version": 0, "reinit_date": 0, "priority": 0, "expire_at": 0}'
	args = [generate_random_id, "-m", "dht", "-k", tonDhtKeyringDir + key, "-a", text]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		raise Exeption(err)
	#end if

	data = json.loads(output)
	text = json.dumps(data, indent=4)
	print(text)

	# chown 1
	args = ["chown", "-R", vuser + ':' + vuser, tonDhtServerDir]
	subprocess.run(args)

	# start DHT-Server
	args = ["systemctl", "restart", "dht-server"]
	subprocess.run(args)
#end define

def SetWebPassword(args):
	args = ["python3", "/usr/src/mtc-jsonrpc/mtc-jsonrpc.py", "-p"]
	subprocess.run(args)
#end define

def EnableJsonRpc():
	local.add_log("start EnableJsonRpc function", "debug")
	user = local.buffer.user
	exitCode = run_as_root(["bash", "/usr/src/mytonctrl/scripts/jsonrpcinstaller.sh", "-u", user])
	if exitCode == 0:
		text = "EnableJsonRpc - {green}OK{endc}"
	else:
		text = "EnableJsonRpc - {red}Error{endc}"
	color_print(text)
#end define

def EnablePytonv3():
	local.add_log("start EnablePytonv3 function", "debug")
	user = local.buffer.user
	exitCode = run_as_root(["bash", "/usr/src/mytonctrl/scripts/pytonv3installer.sh", "-u", user])
	if exitCode == 0:
		text = "EnablePytonv3 - {green}OK{endc}"
	else:
		text = "EnablePytonv3 - {red}Error{endc}"
	color_print(text)
#end define

def str2b64(s):
	b = s.encode("utf-8")
	b64 = base64.b64encode(b)
	b64 = b64.decode("utf-8")
	return b64
#end define

def b642str(b64):
	b64 = b64.encode("utf-8")
	b = base64.b64decode(b64)
	s = b.decode("utf-8")
	return s
#end define

def dict2b64(d):
	s = json.dumps(d)
	b64 = str2b64(s)
	return b64
#end define

def b642dict(b64):
	s = b642str(b64)
	d = json.loads(s)
	return d
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
	local.exit()
#end if
