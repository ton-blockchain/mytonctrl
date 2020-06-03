#!/usr/bin/env python3
# -*- coding: utf_8 -*-
# su -l ${user} -c "cmd"

import random
import requests
from mypylib.mypylib import *

local = MyPyClass(__file__)
cport = random.randint(2000, 65000)
vport = random.randint(2000, 65000)


def Init():
	# filePath = local.buffer.get("myDir") + "translate.json"
	# file = open(filePath)
	# text = file.read()
	# file.close()
	# local.db["translate"] = json.loads(text)

	local.db["config"]["logLevel"] = "debug"
	local.Run()
#end define

def Translate(text):
	local.AddLog("start Translate", "debug")
	lang = local.buffer.get("lang")
	if lang == None:
		lang = "en"
	translate = local.db.get("translate")
	textList = text.split(' ')
	for item in textList:
		sitem = translate.get(item)
		if sitem is None:
			continue
		ritem = sitem.get(lang)
		if ritem is not None:
			text = text.replace(item, ritem)
	return text
#end define

# def UserWorker(title, text, notice=None):
# 	title = Translate(title)
# 	text = Translate(text)
# 	if notice is not None:
# 		notice = Translate(notice)
# 	print('')
# 	print(bcolors.INFO + title + bcolors.ENDC)
# 	print(text)
# 	if notice:
# 		print(bcolors.WARNING + notice + bcolors.ENDC)
# 	result = input(bcolors.OKGREEN + "MyTonCtrl> " + bcolors.ENDC)
# 	if len(result) == 0:
# 		result = None
# 	return result
# #end define

# def GetVarFromUser(title, text, var=None):
# 	notice = None
# 	if var is not None:
# 		notice = "find_file_to_path '{path}'. click_enter_to_apply".format(path=var)
# 	result = UserWorker(title, text, notice)
# 	if result is not None:
# 		var = result
# 	return var
# #end define

# def CheckLiteClient():
# 	try:
# 		LiteClientWorker("help")
# 		local.AddLog("CheckLiteClient - {green}OK{endc}".format(green=bcolors.OKGREEN, endc=bcolors.ENDC), "debug")
# 		return True
# 	except:
# 		local.AddLog("CheckLiteClient error. Bad config. Try again.", "warning")
# 		local.buffer["liteClient"]["appPath"] = None
# 		local.buffer["liteClient"]["configPath"] = None
# 		return False
# #end define

# def LiteclientConfiguration():
# 	title = "quick_setup_title_liteclient_config"
# 	appPath = local.buffer.get("liteClient").get("appPath")
# 	configPath = local.buffer.get("liteClient").get("configPath")
	
# 	# Получить параметры от пользователя
# 	appPath = GetVarFromUser(title, "quick_setup_text_liteclient_program_path", appPath)
# 	configPath = GetVarFromUser(title, "quick_setup_text_liteclient_config_path", configPath)

# 	# Запсись параметров
# 	local.db["liteClient"]["appPath"] = appPath
# 	local.db["liteClient"]["configPath"] = configPath

# 	# Проверка программы
# 	return CheckLiteClient()
# #end define

# def TryLiteclientConfiguration():
# 	while True:
# 		result = LiteclientConfiguration()
# 		if result is True:
# 			return
# #end define

# def CheckValidatorConsole():
# 	try:
# 		ValidatorConsoleWorker("help")
# 		local.AddLog("CheckValidatorConsole - {green}OK{endc}".format(green=bcolors.OKGREEN, endc=bcolors.ENDC), "debug")
# 		return True
# 	except:
# 		local.AddLog("CheckValidatorConsole error. Bad config. Try again.", "warning")
# 		local.buffer["validatorConsole"]["appPath"] = None
# 		local.buffer["validatorConsole"]["privKeyPath"] = None
# 		local.buffer["validatorConsole"]["pubKeyPath"] = None
# 		local.buffer["validatorConsole"]["addr"] = None
# 		return False
# #end define

# def ValidatorConsoleConfiguration():
# 	title = "quick_setup_title_validator_engine_console"
# 	appPath = local.buffer.get("validatorConsole").get("appPath")
# 	privKeyPath = local.buffer.get("validatorConsole").get("privKeyPath")
# 	pubKeyPath = local.buffer.get("validatorConsole").get("pubKeyPath")
	
# 	# Получить параметры от пользователя
# 	appPath = GetVarFromUser(title, "quick_setup_text_validator_engine_console_program_path", appPath)
# 	privKeyPath = GetVarFromUser(title, "quick_setup_text_validator_engine_console_privkey_path", privKeyPath)
# 	pubKeyPath = GetVarFromUser(title, "quick_setup_text_validator_engine_console_pubkey_path", pubKeyPath)
# 	addr = GetVarFromUser(title, "quick_setup_text_validator_engine_console_server_addr")

# 	# Запсись параметров
# 	local.db["validatorConsole"]["appPath"] = appPath
# 	local.db["validatorConsole"]["privKeyPath"] = privKeyPath
# 	local.db["validatorConsole"]["pubKeyPath"] = pubKeyPath
# 	local.db["validatorConsole"]["addr"] = addr

# 	# Проверка программы
# 	return CheckValidatorConsole()
# #end define

# def TryValidatorConsoleConfiguration():
# 	while True:
# 		result = ValidatorConsoleConfiguration()
# 		if result is True:
# 			return
# #end define

# def CheckFift():
# 	try:
# 		FiftWorker(["wallet.fif", "-h"])
# 		local.AddLog("CheckFift - {green}OK{endc}".format(green=bcolors.OKGREEN, endc=bcolors.ENDC), "debug")
# 		return True
# 	except:
# 		local.AddLog("CheckFift error. Bad config. Try again.", "warning")
# 		local.buffer["fift"]["appPath"] = None
# 		local.buffer["fift"]["libsPath"] = None
# 		local.buffer["fift"]["smartcontsPath"] = None
# 		return False
# #end define

# def FiftConfiguration():
# 	title = "quick_setup_title_fift_config"
# 	appPath = local.buffer.get("fift").get("appPath")
# 	libsPath = local.buffer.get("fift").get("libsPath")
# 	smartcontsPath = local.buffer.get("fift").get("smartcontsPath")
	
# 	# Получить параметры от пользователя
# 	appPath = GetVarFromUser(title, "quick_setup_title_text_app_path", appPath)
# 	libsPath = GetVarFromUser(title, "quick_setup_title_text_lib_path", libsPath)
# 	smartcontsPath = GetVarFromUser(title, "quick_setup_title_text_smartcont_path", smartcontsPath)

# 	# Запсись параметров
# 	local.db["fift"]["appPath"] = appPath
# 	local.db["fift"]["libsPath"] = libsPath
# 	local.db["fift"]["smartcontsPath"] = smartcontsPath

# 	# Проверка программы
# 	return CheckFift()
# #end define

# def TryFiftConfiguration():
# 	while True:
# 		result = FiftConfiguration()
# 		if result is True:
# 			return
# #end define

# def SearchPathsToConfigurations():
# 	homePath = os.getenv("HOME", "/home/")
# 	local.buffer["liteClient"]["appPath"] = SearchFileInDir(homePath, "lite-client")
# 	local.buffer["liteClient"]["configPath"] = SearchFileInDir(homePath, "ton-lite-client-test1.config.json")
# 	local.buffer["validatorConsole"]["appPath"] = SearchFileInDir(homePath, "validator-engine-console")
# 	local.buffer["validatorConsole"]["privKeyPath"] = SearchFileInDir(homePath, "client")
# 	local.buffer["validatorConsole"]["pubKeyPath"] = SearchFileInDir(homePath, "server.pub")
# 	local.buffer["fift"]["appPath"] = SearchFileInDir(homePath, "fift")
# 	local.buffer["fift"]["libsPath"] = GetDirFromPath(SearchFileInDir(homePath, "TonUtil.fif"))
# 	local.buffer["fift"]["smartcontsPath"] = GetDirFromPath(SearchFileInDir(homePath, "show-addr.fif"))
# #end define

# def QuickSetup():
# 	local.db["liteClient"] = dict()
# 	local.db["validatorConsole"] = dict()
# 	local.db["fift"] = dict()

# 	# Запустить поток для поиска файлов
# 	threading.Thread(target=SearchPathsToConfigurations, name="Search", daemon=True).start()

# 	title = "quick_setup_title_welcome"
# 	UserWorker(title, "quick_setup_text_welcome")
# 	TryLiteclientConfiguration()
# 	TryValidatorConsoleConfiguration()
# 	TryFiftConfiguration()
# #end define

# def CheckSettings():
#	if CheckLiteClient() != True or CheckValidatorConsole() != True or CheckFift() != True:
#		QuickSetup()
#		local.dbSave()
# #end define

# def Vpreparation():
# 	response = requests.get("https://ifconfig.me")
# 	ip = response.text
# 	vport = random.randint(2000, 65000)
# 	addr = "{ip}:{vport}".format(ip=ip, vport=vport)
	
# 	# Создать переменные
# 	dbPath = "/var/ton-work/db"
# 	logPath = "/var/ton-work/log"
# 	validatorAppPath = "/usr/bin/ton/validator-engine/validator-engine"
# 	validatorConfig = "/usr/bin/ton/validator-engine/ton-global.config.json"
# 	configPath = dbPath + "/config.json"
	
# 	# Подготовить папки валидатора
# 	os.makedirs(dbPath, exist_ok=True)
	
# 	# Создать пользователя
# 	file = open("/etc/passwd", 'rt')
# 	text = file.read()
# 	file.close()
# 	if "validator" not in text:
# 		args = ["/usr/sbin/useradd", "-d", "/dev/null", "-s", "/dev/null", "validator"]
# 		subprocess.run(args)
	
# 	# Проверка первого запуска валидатора
# 	if not os.path.isfile(configPath):
# 		args = [validatorAppPath, "-C", validatorConfig, "--db", dbPath, "--ip", addr, "-l", logPath]
# 		subprocess.run(args)
	
# 	# Прописать автозагрузку авлидатора
# 	Add2Systemd(name="validator", user="validator", start="/usr/bin/ton/validator-engine/validator-engine -d -C /usr/bin/ton/validator-engine/ton-global.config.json --db /var/ton-work/db -l /var/ton-work/log") # post="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py -e \"validator down\""

# 	# Сменить права на нужные директории
# 	args = ["chown", "-R", "validator:validator", "/var/ton-work"]
# 	subprocess.run(args)
	
# 	# Запустить валидатор
# 	args = ["systemctl", "start", "validator"]
# 	subprocess.run(args)
	
# 	# Подождать загрузку валидатора
# 	time.sleep(10)
# #end define

# def LoadSettings(mode, user):
# 	local.AddLog("start LoadSettings fuction", "debug")
	
# 	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
# 	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
# 	if os.path.isfile(path) or os.path.isfile(path2):
# 		return
# 	#end if
	
# 	arr = dict()
# 	arr["config"] = dict()
# 	arr["config"]["logLevel"] = "debug"
# 	arr["config"]["isLocaldbSaving"] = True

# 	# fift
# 	fift = dict()
# 	fift["appPath"] = "/usr/bin/ton/crypto/fift"
# 	fift["libsPath"] = "/usr/src/ton/crypto/fift/lib"
# 	fift["smartcontsPath"] = "/usr/src/ton/crypto/smartcont"
# 	arr["fift"] = fift

# 	# lite-client
# 	liteClient = dict()
# 	liteClient["appPath"] = "/usr/bin/ton/lite-client/lite-client"
# 	liteClient["configPath"] = "/usr/bin/ton/lite-client/ton-lite-client-test1.config.json"
# 	arr["liteClient"] = liteClient

# 	if (mode == "full"):
# 		# validator-engine-console
# 		validatorConsole = dict()
# 		validatorConsole["appPath"] = "/usr/bin/ton/validator-engine-console/validator-engine-console"
# 		validatorConsole["privKeyPath"] = "/usr/bin/ton/validator-engine-console/client"
# 		validatorConsole["pubKeyPath"] = "/usr/bin/ton/validator-engine-console/server.pub"
# 		validatorConsole["addr"] = "127.0.0.1:{cport}".format(cport=cport)
# 		arr["validatorConsole"] = validatorConsole

# 		# Записать настройки в файл
# 		filePath = WriteSettingToFile(arr)

# 		# Подтянуть настройки в mytoncore.py
# 		args = ["su", "-l", user, "-c", "python3 /usr/src/mytonctrl/mytoncore.py -s " + filePath]
# 		subprocess.run(args)
		
# 		# Подтянуть событие в mytoncore.py
# 		args = ["su", "-l", user, "-c", "python3 /usr/src/mytonctrl/mytoncore.py -e \"toninstaller\""]
# 		subprocess.run(args)
# 	#end if
# #end define

# def CreateVkeys(user):
# 	local.AddLog("start CreateVkeys fuction", "debug")
	
# 	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
# 	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
# 	if os.path.isfile(path) or os.path.isfile(path2):
# 		return
# 	#end if
	
# 	# Переменые
# 	dbPath = "/var/ton-work/db"
# 	generate_random_id = "/usr/bin/ton/utils/generate-random-id"
# 	server_key = "/usr/bin/ton/validator-engine-console/server"
# 	server_pubkey = server_key + ".pub"
# 	client_key = "/usr/bin/ton/validator-engine-console/client"
# 	client_pubkey = client_key + ".pub"

# 	# Создание ключей сервера для console
# 	args = ["/usr/bin/ton/utils/generate-random-id", "-m", "keys", "-n", server_key]
# 	process = subprocess.run(args, stdout=subprocess.PIPE)
# 	output = process.stdout.decode("utf-8")
# 	output_arr = output.split(' ')
# 	server_key_hex = output_arr[0]
# 	server_key_b64 = output_arr[1].replace('\n', '')
	
# 	# Копировать ключ в папку валидатора
# 	args = ["mv", server_key, dbPath + "/keyring/" + server_key_hex]
# 	subprocess.run(args)

# 	# Создание ключей клиента для console
# 	args = [generate_random_id, "-m", "keys", "-n", client_key]
# 	process = subprocess.run(args, stdout=subprocess.PIPE)
# 	output = process.stdout.decode("utf-8")
# 	output_arr = output.split(' ')
# 	client_key_hex = output_arr[0]
# 	client_key_b64 = output_arr[1].replace('\n', '')
	
# 	# Сменить права на ключи
# 	args = ["chown", "-R", user + ':' + user, server_pubkey, client_key, client_pubkey]
# 	subprocess.run(args)

# 	# Прописать наши ключи в конфигурационном файле валидатора
# 	path = dbPath + "/config.json"
# 	file = open(path)
# 	text = file.read()
# 	file.close()
# 	vjson = json.loads(text)
# 	control = dict()
# 	control["id"] = server_key_b64
# 	control["port"] = cport
# 	allowed = dict()
# 	allowed["id"] = client_key_b64
# 	allowed["permissions"] = 15
# 	control["allowed"] = [allowed]
# 	vjson["control"] = [control]
# 	text = json.dumps(vjson, indent=4)
# 	file = open(path, 'w')
# 	file.write(text)
# 	file.close()
# #end define

# def OldGeneral():
# 	# Получить режим установки
# 	mx = sys.argv.index("-m")
# 	ux = sys.argv.index("-u")
# 	mode = sys.argv[mx+1]
# 	user = sys.argv[ux+1]

# 	local.AddLog("Using: user - {user}, mode - {mode}".format(user=user, mode=mode))

# 	if mode == "full":
# 		# Проверить настройки валидатора
# 		vfile1 = "/var/ton-work/db/config.json"
# 		if not os.path.isfile(vfile1):
# 			Vpreparation()

# 		# Создать ключи доступа к валидатору
# 		CreateVkeys(user)
		
# 		# Сменить права на нужные директории
# 		args = ["chown", "-R", "validator:validator", "/var/ton-work"]
# 		subprocess.run(args)
# 	#end if

# 	# Создать настройки для mytoncore.py
# 	LoadSettings(mode, user)

# 	# Прописать mytoncore.py в автозагрузку
# 	Add2Systemd(name="mytoncore", user=user, start="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py")
	
	
# 	# Создаем символические ссылки
# 	mytonctrl_file = "/usr/bin/mytonctrl"
# 	fift_file = "/usr/bin/fift"
# 	liteclient_file = "/usr/bin/liteclient"
# 	validator_console_file = "/usr/bin/validator-console"
# 	file = open(mytonctrl_file, 'wt')
# 	file.write("/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py")
# 	file.close()
# 	file = open(fift_file, 'wt')
# 	file.write("/usr/bin/ton/crypto/fift")
# 	file.close()
# 	file = open(liteclient_file, 'wt')
# 	file.write("/usr/bin/ton/lite-client/lite-client -C /usr/bin/ton/lite-client/ton-lite-client-test1.config.json \$@")
# 	file.close()
# 	file = open(validator_console_file, 'wt')
# 	file.write("/usr/bin/ton/validator-engine-console/validator-engine-console -k /usr/bin/ton/validator-engine-console/client -p /usr/bin/ton/validator-engine-console/server.pub -a 127.0.0.1:" + str(cport))
# 	file.close()
# 	args = ["chmod", "+x", mytonctrl_file, fift_file, liteclient_file, validator_console_file]
# 	subprocess.run(args)
# #end define

def General():
	# Получить режим установки
	mx = sys.argv.index("-m")
	ux = sys.argv.index("-u")
	mode = sys.argv[mx+1]
	user = sys.argv[ux+1]

	if mode == "full":
		# Создать настройки для валидатора
		ValidatorSetting(user)
	#end if

	# Создать настройки для mytoncore.py
	MytoncoreSettings(user, mode)

	# Создать символические ссылки
	CreateSymlink()
#end define

def ValidatorSetting(user):
	local.AddLog("start ValidatorSetting fuction", "debug")

	# Прописать автозагрузку авлидатора
	Add2Systemd(name="validator", user="validator", start="/usr/bin/ton/validator-engine/validator-engine -d -C /usr/bin/ton/validator-engine/ton-global.config.json --db /var/ton-work/db -l /var/ton-work/log") # post="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py -e \"validator down\""

	# Проверить конфигурацию валидатора
	path = "/var/ton-work/db/config.json"
	if os.path.isfile(path):
		local.AddLog("Validators config.json already exist. Break ValidatorSetting fuction", "debug")
		return
	#end if

	# Получить внешний ip адрес
	response = requests.get("https://ifconfig.me")
	ip = response.text
	vport = random.randint(2000, 65000)
	addr = "{ip}:{vport}".format(ip=ip, vport=vport)
	local.AddLog("Usnig addr: " + addr, "debug")
	
	# Создать переменные
	dbPath = "/var/ton-work/db"
	logPath = "/var/ton-work/log"
	validatorAppPath = "/usr/bin/ton/validator-engine/validator-engine"
	validatorConfig = "/usr/bin/ton/validator-engine/ton-global.config.json"
	configPath = dbPath + "/config.json"
	
	# Подготовить папки валидатора
	os.makedirs(dbPath, exist_ok=True)
	
	# Создать пользователя
	file = open("/etc/passwd", 'rt')
	text = file.read()
	file.close()
	if "validator" not in text:
		local.AddLog("Creating new user: validator", "debug")
		args = ["/usr/sbin/useradd", "-d", "/dev/null", "-s", "/dev/null", "validator"]
		subprocess.run(args)
	#end if
	
	# Проверка первого запуска валидатора
	if not os.path.isfile(configPath):
		local.AddLog("First validator startup", "debug")
		args = [validatorAppPath, "-C", validatorConfig, "--db", dbPath, "--ip", addr, "-l", logPath]
		subprocess.run(args)
	#end if

	# Создать ключи доступа к валидатору
	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path) or os.path.isfile(path2):
		result = subprocess.call(["ls", "-lh", path])
		result2 = subprocess.call(["ls", "-lh", path2])
		local.AddLog("mytoncore.db already exist. Break ValidatorSetting fuction", "debug")
		return
	#end if
	
	# Создать переменные
	generate_random_id = "/usr/bin/ton/utils/generate-random-id"
	server_key = "/usr/bin/ton/validator-engine-console/server"
	server_pubkey = server_key + ".pub"
	client_key = "/usr/bin/ton/validator-engine-console/client"
	client_pubkey = client_key + ".pub"

	# Создание ключей сервера для console
	local.AddLog("Generating server key", "debug")
	args = ["/usr/bin/ton/utils/generate-random-id", "-m", "keys", "-n", server_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	server_key_hex = output_arr[0]
	server_key_b64 = output_arr[1].replace('\n', '')
	
	# Копировать ключ в папку валидатора
	local.AddLog("Coping the key to the validator directory", "debug")
	args = ["mv", server_key, dbPath + "/keyring/" + server_key_hex]
	subprocess.run(args)

	# Создание ключей клиента для console
	local.AddLog("Generating client key", "debug")
	args = [generate_random_id, "-m", "keys", "-n", client_key]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	client_key_hex = output_arr[0]
	client_key_b64 = output_arr[1].replace('\n', '')
	
	# Сменить права на ключи
	args = ["chown", "-R", user + ':' + user, server_pubkey, client_key, client_pubkey]
	subprocess.run(args)

	# Прописать наши ключи в конфигурационном файле валидатора
	local.AddLog("Writing settings to validators config file", "debug")
	path = dbPath + "/config.json"
	file = open(path)
	text = file.read()
	file.close()
	vjson = json.loads(text)
	control = dict()
	control["id"] = server_key_b64
	control["port"] = cport
	allowed = dict()
	allowed["id"] = client_key_b64
	allowed["permissions"] = 15
	control["allowed"] = [allowed]
	vjson["control"] = [control]
	text = json.dumps(vjson, indent=4)
	file = open(path, 'w')
	file.write(text)
	file.close()

	# Сменить права на нужные директории
	args = ["chown", "-R", "validator:validator", "/var/ton-work"]
	subprocess.run(args)

	# Запустить валидатор
	local.AddLog("Launching validator", "debug")
	args = ["systemctl", "start", "validator"]
	subprocess.run(args)
	
	# Подождать загрузку валидатора
	local.AddLog("Waiting for validator to load. Pause 10 seconds.")
	time.sleep(10)
#end define

def MytoncoreSettings(user, mode):
	local.AddLog("start MytoncoreSettings fuction", "debug")

	# Прописать mytoncore.py в автозагрузку
	Add2Systemd(name="mytoncore", user=user, start="/usr/bin/python3 /usr/src/mytonctrl/mytoncore.py")
	
	path = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
	path2 = "/usr/local/bin/mytoncore/mytoncore.db"
	if os.path.isfile(path) or os.path.isfile(path2):
		local.AddLog("mytoncore.db already exist. Break MytoncoreSettings fuction", "debug")
		return
	#end if

	arr = dict()
	arr["config"] = dict()
	arr["config"]["logLevel"] = "debug"
	arr["config"]["isLocaldbSaving"] = True

	# fift
	fift = dict()
	fift["appPath"] = "/usr/bin/ton/crypto/fift"
	fift["libsPath"] = "/usr/src/ton/crypto/fift/lib"
	fift["smartcontsPath"] = "/usr/src/ton/crypto/smartcont"
	arr["fift"] = fift

	# lite-client
	liteClient = dict()
	liteClient["appPath"] = "/usr/bin/ton/lite-client/lite-client"
	liteClient["configPath"] = "/usr/bin/ton/lite-client/ton-lite-client-test1.config.json"
	arr["liteClient"] = liteClient

	# Записать настройки в файл
	filePath = WriteSettingToFile(arr)

	# Подтянуть настройки в mytoncore.py
	args = ["su", "-l", user, "-c", "python3 /usr/src/mytonctrl/mytoncore.py -s " + filePath]
	subprocess.run(args)


	if (mode == "full"):
		# validator-engine-console
		validatorConsole = dict()
		validatorConsole["appPath"] = "/usr/bin/ton/validator-engine-console/validator-engine-console"
		validatorConsole["privKeyPath"] = "/usr/bin/ton/validator-engine-console/client"
		validatorConsole["pubKeyPath"] = "/usr/bin/ton/validator-engine-console/server.pub"
		validatorConsole["addr"] = "127.0.0.1:{cport}".format(cport=cport)
		arr["validatorConsole"] = validatorConsole

		# Записать настройки в файл
		filePath = WriteSettingToFile(arr)

		# Подтянуть настройки в mytoncore.py
		args = ["su", "-l", user, "-c", "python3 /usr/src/mytonctrl/mytoncore.py -s " + filePath]
		subprocess.run(args)

		# Навсякий подождать, пока mytoncore подтянет настройки. Возможно это лишнее.
		time.sleep(3)

		# Подтянуть событие в mytoncore.py
		args = ["su", "-l", user, "-c", "python3 /usr/src/mytonctrl/mytoncore.py -e \"toninstaller\""]
		subprocess.run(args)
	#end if

	# Запустить mytoncore.py
	args = ["systemctl", "start", "mytoncore"]
	subprocess.run(args)
#end define

def WriteSettingToFile(arr):
	local.AddLog("start WriteSettingToFile fuction", "debug")
	filePath = "/tmp/mytonsettings.json"
	settings = json.dumps(arr)
	file = open(filePath, 'w')
	file.write(settings)
	file.close()
	return filePath
#end define

def CreateSymlink():
	local.AddLog("start CreateSymlink fuction", "debug")
	mytonctrl_file = "/usr/bin/mytonctrl"
	fift_file = "/usr/bin/fift"
	liteclient_file = "/usr/bin/liteclient"
	validator_console_file = "/usr/bin/validator-console"
	env_file = "/etc/environment"
	file = open(mytonctrl_file, 'wt')
	file.write("/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py")
	file.close()
	file = open(fift_file, 'wt')
	file.write("/usr/bin/ton/crypto/fift")
	file.close()
	file = open(liteclient_file, 'wt')
	file.write("/usr/bin/ton/lite-client/lite-client -C /usr/bin/ton/lite-client/ton-lite-client-test1.config.json \$@")
	file.close()
	file = open(validator_console_file, 'wt')
	file.write("/usr/bin/ton/validator-engine-console/validator-engine-console -k /usr/bin/ton/validator-engine-console/client -p /usr/bin/ton/validator-engine-console/server.pub -a 127.0.0.1:" + str(cport))
	file.close()
	args = ["chmod", "+x", mytonctrl_file, fift_file, liteclient_file, validator_console_file]
	subprocess.run(args)

	# env
	fiftpath = "export FIFTPATH=/usr/src/ton/crypto/fift/lib/:/usr/src/ton/crypto/smartcont/"
	file = open(env_file, 'a+')
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
	General()
	local.Exit()
#end if
