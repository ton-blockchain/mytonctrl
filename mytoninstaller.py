#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import random
from mypylib.mypylib import *
from mytoncore import *

local = MyPyClass(__file__)
cport=random.randint(2000, 65000)


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

def RunAsRoot(args):
	file = open("/etc/issue")
	text = file.read()
	file.close()
	if "Ubuntu" in text:
		args = ["sudo", "-S"] + args
	else:
		print("Введите пароль пользователя root / Enter root password")
		args = ["su", "-c"] + [" ".join(args)]
	subprocess.call(args)
#end define

def WriteSettingToFile(arr):
	local.AddLog("start WriteSettingToFile fuction", "debug")
	# Записать настройки в файл
	filePath = "/tmp/mytonsettings.json"
	settings = json.dumps(arr)
	file = open(filePath, 'w')
	file.write(settings)
	file.close()
	return filePath
#end define

def LoadSettings(mode):
	local.AddLog("start LoadSettings fuction", "debug")
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
		subprocess.call(["python3", "/usr/src/mytonctrl/mytoncore.py", '-s', filePath])

		# Создать новый кошелек для валидатора
		ton = MyTonCore()
		wallet = ton.CreateWallet("validator_wallet_001")
		arr["validatorWalletName"] = wallet.name

		# Создать новый ADNL адрес для валидатора
		adnlAddr = ton.CreatNewKey()
		ton.AddAdnlAddrToValidator(adnlAddr)
		arr["adnlAddr"] = adnlAddr
	#end if

	# Записать настройки в файл
	filePath = WriteSettingToFile(arr)

	# Подтянуть настройки в mytoncore.py
	subprocess.call(["python3", "/usr/src/mytonctrl/mytoncore.py", '-s', filePath])
#end define

def CreateVkeys():
	local.AddLog("start CreateVkeys fuction", "debug")
	os.makedirs("/tmp/vkeys/", exist_ok=True)

	# Создание ключей сервера для console
	args = ["/usr/bin/ton/utils/generate-random-id", "-m", "keys", "-n", "/tmp/vkeys/server"]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	server_key_hex = output_arr[0]
	server_key_b64 = output_arr[1]

	# Создание ключей клиента для console
	args = ["/usr/bin/ton/utils/generate-random-id", "-m", "keys", "-n", "/tmp/vkeys/client"]
	process = subprocess.run(args, stdout=subprocess.PIPE)
	output = process.stdout.decode("utf-8")
	output_arr = output.split(' ')
	client_key_hex = output_arr[0]
	client_key_b64 = output_arr[1]

	# Прописать наши ключи во времянном конфигурационном файле валидатора
	path = "/tmp/vconfig.json"
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
	text = json.dumps(vjson, indent=3)
	file = open(path, 'w')
	file.write(text)
	file.close()

	return server_key_hex
#end define

def CheckSettings():
	if CheckLiteClient() != True or CheckValidatorConsole() != True or CheckFift() != True:
		QuickSetup()
		local.dbSave()
#end define

def General():
	# Получить режим установки
	x = sys.argv.index("-m")
	mode = sys.argv[x+1]

	if mode == "full":
		# Проверить настройки валидатора
		vfile1 = "/var/ton-work/db/config.json"
		vfile2 = "/tmp/vconfig.json"
		if not os.path.isfile(vfile1) or not os.path.isfile(vfile2):
			RunAsRoot(["sh", "/usr/src/mytonctrl/scripts/vpreparation.sh"])

		# Создать ключи доступа к валидатору
		server_key_hex = CreateVkeys()

		# Запустить vconfig.sh
		local.AddLog("start vconfig.sh", "debug")
		RunAsRoot(["sh", "/usr/src/mytonctrl/scripts/vconfig.sh", "-kh", server_key_hex])
	#end if

	# Создать настройки для mytoncore.py
	LoadSettings(mode)

	# Прописать mytoncore.py в автозагрузку
	local.AddLog("start mytoncore.py", "debug")
	subprocess.call(["python3", "/usr/src/mytonctrl/mytoncore.py", "--add2cron"])
	subprocess.call(["python3", "/usr/src/mytonctrl/mytoncore.py", "-d"])

	# Конец
	local.AddLog("MyTonCtrl успешно установлен")
#end define



###
### Start of the program
###

if __name__ == "__main__":
	Init()
	General()
	local.Exit()
#end if
