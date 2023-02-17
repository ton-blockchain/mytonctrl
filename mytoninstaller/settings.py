import os
import os.path
import psutil
import subprocess
import requests
import random
import json
import pkg_resources

from mypylib.mypylib import Add2Systemd, GetDirFromPath, RunAsRoot, ColorPrint, ip2int
from mytoninstaller.utils import StartValidator, StartMytoncore
from mytoninstaller.config import SetConfig, GetConfig
from mytoncore.utils import hex2b64


def FirstNodeSettings(local):
	local.AddLog("start FirstNodeSettings fuction", "debug")

	# Создать переменные
	user = local.buffer["user"]
	vuser = local.buffer["vuser"]
	tonWorkDir = local.buffer["tonWorkDir"]
	tonDbDir = local.buffer["tonDbDir"]
	keysDir = local.buffer["keysDir"]
	tonLogPath = local.buffer["tonLogPath"]
	validatorAppPath = local.buffer["validatorAppPath"]
	globalConfigPath = local.buffer["globalConfigPath"]
	vconfigPath = local.buffer["vconfigPath"]

	# Проверить конфигурацию
	if os.path.isfile(vconfigPath):
		local.AddLog(f"Validators config '{vconfigPath}' already exist. Break FirstNodeSettings fuction", "warning")
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
	os.makedirs(keysDir, exist_ok=True)

	# Прописать автозагрузку
	cpus = psutil.cpu_count() - 1
	cmd = "{validatorAppPath} --threads {cpus} --daemonize --global-config {globalConfigPath} --db {tonDbDir} --logname {tonLogPath} --state-ttl 604800 --verbosity 1"
	cmd = cmd.format(validatorAppPath=validatorAppPath, globalConfigPath=globalConfigPath, tonDbDir=tonDbDir, tonLogPath=tonLogPath, cpus=cpus)
	Add2Systemd(name="validator", user=vuser, start=cmd) # post="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py -e \"validator down\""

	# Получить внешний ip адрес
	ip = requests.get("https://ifconfig.me").text
	vport = random.randint(2000, 65000)
	addr = "{ip}:{vport}".format(ip=ip, vport=vport)
	local.AddLog("Use addr: " + addr, "debug")

	# Первый запуск
	local.AddLog("First start validator - create config.json", "debug")
	args = [validatorAppPath, "--global-config", globalConfigPath, "--db", tonDbDir, "--ip", addr, "--logname", tonLogPath]
	subprocess.run(args)

	# Скачать дамп
	DownloadDump(local)

	# chown 1
	local.AddLog("Chown ton-work dir", "debug")
	args = ["chown", "-R", vuser + ':' + vuser, tonWorkDir]
	subprocess.run(args)

	# start validator
	StartValidator(local)
#end define


def DownloadDump(local):
	dump = local.buffer["dump"]
	if dump == False:
		return
	#end if

	local.AddLog("start DownloadDump fuction", "debug")
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
	cmd = "curl -s {url}/dumps/latest.tar.lz | pv | plzip -d -n8 | tar -xC /var/ton-work/db".format(url=url)
	os.system(cmd)
#end define


def FirstMytoncoreSettings(local):
	local.AddLog("start FirstMytoncoreSettings fuction", "debug")
	user = local.buffer["user"]

	# Прописать mytoncore.py в автозагрузку
	# Add2Systemd(name="mytoncore", user=user, start="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py")  # TODO: fix path
	Add2Systemd(name="mytoncore", user=user, start="/usr/bin/python3 -m mytoncore")

	# Проверить конфигурацию
	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	if os.path.isfile(path):
		local.AddLog(f"{path} already exist. Break FirstMytoncoreSettings fuction", "warning")
		return
	#end if

	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path2):
		local.AddLog(f"{path2}.db already exist. Break FirstMytoncoreSettings fuction", "warning")
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
	liteClient["configPath"] = tonBinDir + "global.config.json"
	mconfig["liteClient"] = liteClient

	# miner
	miner = dict()
	miner["appPath"] = tonBinDir + "crypto/pow-miner"
	mconfig["miner"] = miner

	# Telemetry
	mconfig["sendTelemetry"] = local.buffer["telemetry"]

	# Записать настройки в файл
	SetConfig(path=mconfigPath, data=mconfig)

	# chown 1
	args = ["chown", user + ':' + user, mconfigDir, mconfigPath]
	subprocess.run(args)

	# start mytoncore
	StartMytoncore(local)
#end define

def EnableValidatorConsole(local):
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
	keysDir = local.buffer["keysDir"]
	client_key = keysDir + "client"
	server_key = keysDir + "server"
	client_pubkey = client_key + ".pub"
	server_pubkey = server_key + ".pub"

	# Check if key exist
	if os.path.isfile(server_key):
		local.AddLog(f"Server key '{server_key}' already exist. Break EnableValidatorConsole fuction", "warning")
		return
	#end if

	if os.path.isfile(client_key):
		local.AddLog(f"Client key '{client_key}' already exist. Break EnableValidatorConsole fuction", "warning")
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
	StartValidator(local)

	# read mconfig
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)

	# edit mytoncore config file
	validatorConsole = dict()
	validatorConsole["appPath"] = tonBinDir + "validator-engine-console/validator-engine-console"
	validatorConsole["privKeyPath"] = client_key
	validatorConsole["pubKeyPath"] = server_pubkey
	validatorConsole["addr"] = "127.0.0.1:{cport}".format(cport=cport)
	mconfig["validatorConsole"] = validatorConsole

	# write mconfig
	SetConfig(path=mconfigPath, data=mconfig)

	# Подтянуть событие в mytoncore.py
	# cmd = "python3 {srcDir}mytonctrl/mytoncore.py -e \"enableVC\"".format(srcDir=srcDir)
	cmd = 'python3 -m mytoncore -e "enableVC"'
	args = ["su", "-l", user, "-c", cmd]
	subprocess.run(args)

	# restart mytoncore
	StartMytoncore(local)
#end define

def EnableLiteServer(local):
	local.AddLog("start EnableLiteServer function", "debug")

	# Create variables
	user = local.buffer["user"]
	vuser = local.buffer["vuser"]
	lport = local.buffer["lport"]
	srcDir = local.buffer["srcDir"]
	tonDbDir = local.buffer["tonDbDir"]
	keysDir = local.buffer["keysDir"]
	tonBinDir = local.buffer["tonBinDir"]
	vconfigPath = local.buffer["vconfigPath"]
	generate_random_id = tonBinDir + "utils/generate-random-id"
	liteserver_key = keysDir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"

	# Check if key exist
	if os.path.isfile(liteserver_pubkey):
		local.AddLog(f"Liteserver key '{liteserver_pubkey}' already exist. Break EnableLiteServer fuction", "warning")
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
	StartValidator(local)

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
	StartMytoncore(local)
#end define


def EnableDhtServer(local):
	local.AddLog("start EnableDhtServer function", "debug")
	vuser = local.buffer["vuser"]
	tonBinDir = local.buffer["tonBinDir"]
	globalConfigPath = local.buffer["globalConfigPath"]
	dht_server = tonBinDir + "dht-server/dht-server"
	generate_random_id = tonBinDir + "utils/generate-random-id"
	tonDhtServerDir = "/var/ton-dht-server/"
	tonDhtKeyringDir = tonDhtServerDir + "keyring/"

	# Проверить конфигурацию
	dht_config_path = "/var/ton-dht-server/config.json"
	if os.path.isfile(dht_config_path):
		local.AddLog(f"DHT-Server '{dht_config_path}' already exist. Break EnableDhtServer fuction", "warning")
		return
	#end if

	# Подготовить папку
	os.makedirs(tonDhtServerDir, exist_ok=True)

	# Прописать автозагрузку
	cmd = "{dht_server} -C {globalConfigPath} -D {tonDhtServerDir}"
	cmd = cmd.format(dht_server=dht_server, globalConfigPath=globalConfigPath, tonDhtServerDir=tonDhtServerDir)
	Add2Systemd(name="dht-server", user=vuser, start=cmd)

	# Получить внешний ip адрес
	ip = requests.get("https://ifconfig.me").text
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
		raise Exception(err)
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


def EnableJsonRpc(local):
	local.AddLog("start EnableJsonRpc function", "debug")
	user = local.buffer["user"]

	jsonrpcinstaller_path = pkg_resources.resource_filename('mytoninstaller.scripts', 'jsonrpcinstaller.sh')
	local.AddLog(f"Running script: {jsonrpcinstaller_path}", "debug")
	exitCode = RunAsRoot(["bash", jsonrpcinstaller_path, "-u", user])  # TODO: fix path
	if exitCode == 0:
		text = "EnableJsonRpc - {green}OK{endc}"
	else:
		text = "EnableJsonRpc - {red}Error{endc}"
	ColorPrint(text)
#end define


def EnablePytonv3(local):
	local.AddLog("start EnablePytonv3 function", "debug")
	user = local.buffer["user"]

	pythonv3installer_path = pkg_resources.resource_filename('mytoninstaller.scripts', 'pytonv3installer.sh')
	local.AddLog(f"Running script: {pythonv3installer_path}", "debug")
	exitCode = RunAsRoot(["bash", pythonv3installer_path, "-u", user])
	if exitCode == 0:
		text = "EnablePytonv3 - {green}OK{endc}"
	else:
		text = "EnablePytonv3 - {red}Error{endc}"
	ColorPrint(text)
#end define


def EnableTonHttpApi(local):
	local.AddLog("start EnablePytonv3 function", "debug")
	user = local.buffer["user"]

	ton_http_api_installer_path = pkg_resources.resource_filename('mytoninstaller.scripts', 'tonhttpapiinstaller.sh')
	exitCode = RunAsRoot(["bash", ton_http_api_installer_path, "-u", user])
	if exitCode == 0:
		text = "EnableTonHttpApi - {green}OK{endc}"
	else:
		text = "EnableTonHttpApi - {red}Error{endc}"
	ColorPrint(text)


def DangerousRecoveryValidatorConfigFile(local):
	local.AddLog("start DangerousRecoveryValidatorConfigFile function", "info")

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
	vconfig = dict()
	vconfig["@type"] = "engine.validator.config"
	vconfig["out_port"] = 3278

	# Create addrs object
	buffer = dict()
	buffer["@type"] = "engine.addr"
	buffer["ip"] = ip2int(requests.get("https://ifconfig.me").text)
	buffer["port"] = None
	buffer["categories"] = [0, 1, 2, 3]
	buffer["priority_categories"] = []
	vconfig["addrs"] = [buffer]

	# Get liteserver fragment
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)
	lkey = mconfig["liteClient"]["liteServer"]["pubkeyPath"]
	lport = mconfig["liteClient"]["liteServer"]["port"]

	# Read lite server pubkey
	file = open(lkey, 'rb')
	data = file.read()
	file.close()
	lsPubkey = data[4:]

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
		if pubkey == lsPubkey:
			lsId = hex2b64(item)
			keys.remove(lsId)
	#end for

	# Create LS object
	buffer = dict()
	buffer["@type"] = "engine.liteServer"
	buffer["id"] = lsId
	buffer["port"] = lport
	vconfig["liteservers"] = [buffer]

	# Get validator-console fragment
	ckey = mconfig["validatorConsole"]["pubKeyPath"]
	addr = mconfig["validatorConsole"]["addr"]
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
	buffer = dict()
	buffer2 = dict()
	buffer["@type"] = "engine.controlInterface"
	buffer["id"] = vcId
	buffer["port"] = cport
	buffer2["@type"] = "engine.controlProcess"
	buffer2["id"] = None
	buffer2["permissions"] = 15
	buffer["allowed"] = buffer2
	vconfig["control"] = [buffer]

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
	buffer = dict()
	buffer["@type"] = "engine.dht"
	buffer["id"] = dhtId
	vconfig["dht"] = [buffer]

	# Create adnl object
	adnl2 = dict()
	adnl2["@type"] = "engine.adnl"
	adnl2["id"] = dhtId
	adnl2["category"] = 0

	# Create adnl object
	adnlId = hex2b64(mconfig["adnlAddr"])
	keys.remove(adnlId)
	adnl3 = dict()
	adnl3["@type"] = "engine.adnl"
	adnl3["id"] = adnlId
	adnl3["category"] = 0

	# Create adnl object
	adnl1 = dict()
	adnl1["@type"] = "engine.adnl"
	adnl1["id"] = keys.pop(0)
	adnl1["category"] = 1

	vconfig["adnl"] = [adnl1, adnl2, adnl3]

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
		temp_key = dict()
		temp_key["@type"] = "engine.validatorTempKey"
		temp_key["key"] = vkey
		temp_key["expire_at"] = dump["endWorkTime"]
		adnl_addr = dict()
		adnl_addr["@type"] = "engine.validatorAdnlAddress"
		adnl_addr["id"] = adnlId
		adnl_addr["expire_at"] = dump["endWorkTime"]

		# Create validator object
		validator = dict()
		validator["@type"] = "engine.validator"
		validator["id"] = vkey
		validator["temp_keys"] = [temp_key]
		validator["adnl_addrs"] = [adnl_addr]
		validator["election_date"] = dump["startWorkTime"]
		validator["expire_at"] = dump["endWorkTime"]
		if vkey in keys:
			validators.append(validator)
			keys.remove(vkey)
		#end if
	#end while

	# Add validators object to vconfig
	vconfig["validators"] = validators


	print("vconfig:", json.dumps(vconfig, indent=4))
	print("keys:", keys)
#end define


def CreateSymlinks(local):
	local.AddLog("start CreateSymlinks fuction", "debug")
	cport = local.buffer["cport"]

	mytonctrl_file = "/usr/bin/mytonctrl"
	fift_file = "/usr/bin/fift"
	liteclient_file = "/usr/bin/lite-client"
	validator_console_file = "/usr/bin/validator-console"
	env_file = "/etc/environment"
	file = open(mytonctrl_file, 'wt')
	# file.write("/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py $@")  # TODO: fix path
	file.write("/usr/bin/python3 -m mytonctrl $@")  # TODO: fix path
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
