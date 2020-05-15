#!/usr/bin/env python3
# -*- coding: utf_8 -*-

from mypylib.mypylib import *
from mypyconsole.mypyconsole import MyPyConsole
from mytoncore import *

local = MyPyClass(__file__)
console = MyPyConsole()
ton = MyTonCore()
# Must control: /var/ton-work/db/keyring/

def Init():
	# Create user console
	console.name = "MyTonCtrl"
	console.AddItem("status", PrintStatus, "Показать статус TON / Show TON status")
	console.AddItem("seqno", Seqno, "Получить seqno кошелька / Get seqno wallet")

	console.AddItem("nw", CreatNewWallet, "Создать новый локальный кошелек / Create a new local wallet")
	console.AddItem("aw", ActivateWallet, "Активировать локальный кошелек / Activate local wallet")
	console.AddItem("wl", PrintWalletsList, "Показать локальные кошельки / Show wallets list")
	console.AddItem("iw", ImportWalletFromFile, "Импортировать кошелек из файла / Import wallet from files")
	console.AddItem("swa", SaveWalletAddressToFile, "Сохранить адрес кошелька в файл / Save wallet address to file")
	console.AddItem("dw", DeleteWallet, "Удалить локальный кошелек / Delete local wallet")

	console.AddItem("vas", ViewAccountStatus, "Показать статус аккаунта / View account status")
	console.AddItem("vah", ViewAccountHistory, "Показать историю аккаунта / View account history")
	console.AddItem("mg", MoveGrams, "Перевод средств на кошелек / Move grams to account")

	console.AddItem("nb", CreatNewBookmark, "Добавить аккаунт в закладки / Creat new bookmark")
	console.AddItem("bl", PrintBookmarksList, "Показать закладки / Show bookmarks list")
	console.AddItem("db", DeleteBookmark, "Удалить закладку / Delete bookmark")

	console.AddItem("nr", CreatNewRule, "Добавить правило в расписание / Creat new rule")
	console.AddItem("rl", PrintRulesList, "Показать правила расписания / Show rules list")
	console.AddItem("dr", DeleteRule, "Удалить правило из расписания / Delete rule")
	
	#console.AddItem("w2m", MoveGramsFromMixer, "Пропустить средства через миксер")
	
	console.AddItem("nd", NewDomain, "Арендовать новый домен / New domain")
	console.AddItem("dl", PrintDomainsList, "Показать арендованные домены / Show domains list")
	console.AddItem("vd", ViewDomainStatus, "Показать статус домена / View domain status")
	console.AddItem("dd", DeleteDomain, "Удалить домен / Delete domain")
	
	console.AddItem("ol", PrintOffersList, "Показать действующие предложения / Show offers list")
	console.AddItem("vo", VoteOffer, "Голосовать за предложение / Vote offer")

	console.AddItem("test", Test, "")
	
	local.db["config"]["logLevel"] = "debug"
	local.db["config"]["isLocaldbSaving"] = True
	local.Run()
#end define

def Test(args):
	start = "EQAuMmMD034cfrQgaqJqJ8q8xNA3byNn2Z2zGRQX5UN5y2pn"
	ok_arr = list()
	pending_arr = list()
	pending_arr.append(start)
	while True:
		try:
			TestWork(ok_arr, pending_arr)
		except KeyboardInterrupt:
			buff = ok_arr + pending_arr
			data = json.dumps(buff)
			file = open("testoutput.txt", "wt")
			file.write(data)
			file.close()
			break
		except:
			buff = ok_arr + pending_arr
			data = json.dumps(buff)
			file = open("testoutput.txt", "wt")
			file.write(data)
			file.close()
#end define

def TestWork(ok_arr, pending_arr):
	addr = pending_arr.pop(0)
	account = ton.GetAccount(addr)
	history = ton.GetAccountHistory(account, 1000)
	for item in history:
		outmsg = item.get("outmsg")
		if outmsg == 1:
			haddr = item.get("to")
		else:
			haddr = item.get("from")
		haddr = ton.HexAddr2Base64Addr(haddr)
		if haddr not in pending_arr and haddr not in ok_arr:
			pending_arr.append(haddr)
	ok_arr.append(addr)
	print(addr, len(ok_arr), len(pending_arr))
#end define

def PrintStatus(args):
	rootWorkchainEnabledTime_int = ton.GetRootWorkchainEnabledTime()
	config34 = ton.GetConfig34()
	totalValidators = config34["totalValidators"]
	oldStartWorkTime = config34["oldStartWorkTime"]
	shardsNumber = ton.GetShardsNumber()
	validatorStatus = ton.GetValidatorStatus()
	config15 = ton.GetConfig15()
	config17 = ton.GetConfig17()
	fullConfigAddr = ton.GetFullConfigAddr()
	fullElectorAddr = ton.GetFullElectorAddr()
	startWorkTime = ton.GetActiveElectionId(fullElectorAddr)
	validatorIndex = ton.GetValidatorIndex()
	validatorWallet = ton.GetLocalWallet(ton.validatorWalletName)
	dbSize = ton.GetDbSize()
	offersNumber = ton.GetOffersNumber()
	if validatorWallet is not None:
		validatorAccount = ton.GetAccount(validatorWallet.addr)
	else:
		validatorAccount = None
	PrintTonStatus(startWorkTime, totalValidators, shardsNumber, offersNumber)
	PrintLocalStatus(validatorIndex, validatorWallet, validatorAccount, validatorStatus, dbSize)
	PrintTonConfig(fullConfigAddr, fullElectorAddr, config15, config17)
	PrintTimes(rootWorkchainEnabledTime_int, startWorkTime, oldStartWorkTime, config15)
#end define

def PrintTonStatus(startWorkTime, totalValidators, shardsNumber, offersNumber):
	# Статус сети TON
	tps1 = "n/a" # fix me
	tps5 = "n/a" # fix me
	tps15 = "n/a" # fix me
	validators = totalValidators
	onlineValidators = "n/a" # fix me
	offers = offersNumber.get("all")
	newOffers = offersNumber.get("new")

	tps1_text = bcolors.Yellow(tps1)
	tps5_text = bcolors.Yellow(tps5)
	tps15_text = bcolors.Yellow(tps15)
	validators_text = bcolors.Green(validators)
	shards_text = bcolors.Green(shardsNumber)
	offers_text = bcolors.Green(offers)
	newOffers_text = bcolors.Green(newOffers)
	onlineValidators_text = bcolors.Yellow(onlineValidators)
	if startWorkTime == 0:
		electionStatus_text = bcolors.Yellow("close")
	else:
		electionStatus_text = bcolors.Green("open")

	ColorPrint("{cyan}===[ Статус сети TON ]==={endc}")
	print("Транзакций в секунду (TPS): {0}, {1}, {2}".format(tps1_text, tps5_text, tps15_text))
	print("Количество валидаторов, прошедших выборы: " + validators_text)
	print("Количество валидаторов в сети: " + onlineValidators_text)
	print("Количесвто шардчейнов: " + shards_text)
	print("Действующие предложения: {0}({1})".format(offers_text, newOffers_text))
	print("Статус выборов: " + electionStatus_text)
	print()
#end define

def PrintLocalStatus(validatorIndex, validatorWallet, validatorAccount, validatorStatus, dbSize):
	# Статус локального валидатора
	if validatorWallet is None:
		return
	adnlAddr = ton.adnlAddr
	walletAddr = validatorWallet.addr
	walletBalance = validatorAccount.balance
	cpuNumber = psutil.cpu_count()
	loadavg = GetLoadAvg()
	cpuLoad1 = loadavg[0]
	cpuLoad5 = loadavg[1]
	cpuLoad15 = loadavg[2]
	netLoadAvg = GetNetworStatistics(ton)
	netLoad1 = netLoadAvg[0]
	netLoad5 = netLoadAvg[1]
	netLoad15 = netLoadAvg[2]
	validatorOutOfSync = validatorStatus.get("unixtime", GetTimestamp()) - validatorStatus.get("masterchainblocktime", 0)
	statisticsStatus_text_bool = True # fix me
	electionsThreadStatus_bool = True # fix me
	validatorStatus_bool = validatorStatus.get("isWorking")

	validatorIndex_text = bcolors.Green(validatorIndex)
	adnlAddr_text = bcolors.Yellow(adnlAddr)
	walletAddr_text = bcolors.Yellow(walletAddr)
	walletBalance_text = bcolors.Green(walletBalance, " GRM")

	# CPU status
	cpuNumber_text = bcolors.Yellow(cpuNumber)
	cpuLoad1_text = GetColorInt(cpuLoad1, cpuNumber)
	cpuLoad5_text = GetColorInt(cpuLoad5, cpuNumber)
	cpuLoad15_text = GetColorInt(cpuLoad15, cpuNumber)

	# Network status
	netLoad1_text = GetColorInt(netLoad1, 300)
	netLoad5_text = GetColorInt(netLoad5, 300)
	netLoad15_text = GetColorInt(netLoad15, 300)

	# Thread status
	statisticsStatus_text = GetColorStatus(statisticsStatus_text_bool)
	electionsThreadStatus_text = GetColorStatus(electionsThreadStatus_bool)
	validatorStatus_text = GetColorStatus(validatorStatus_bool)
	validatorSyncPercent_text = GetColorInt(validatorOutOfSync, 20, ending=" с")
	dbSize_text = GetColorInt(dbSize, 1000, ending=" Gb")

	ColorPrint("{cyan}===[ Статус локального валидатора ]==={endc}")
	print("Индекс валидатора: " + validatorIndex_text)
	print("ADNL адрес локального валидатора: " + adnlAddr_text)
	print("Адрес кошелька локального валидатора: " + walletAddr_text)
	print("Баланс кошелька локального валидатора: " + walletBalance_text)
	print("Средняя нагрузка[{0}]: {1}, {2}, {3}".format(cpuNumber_text, cpuLoad1_text, cpuLoad5_text, cpuLoad15_text))
	print("Средняя нагрузка сети (Mbit/s): {0}, {1}, {2}".format(netLoad1_text, netLoad5_text, netLoad15_text))
	print("Статус сбора статистики: " + statisticsStatus_text)
	print("Статус участия в выборах: " + electionsThreadStatus_text)
	print("Статус локального валидатора: " + validatorStatus_text)
	print("Рассинхронизация локального валидатора: " + validatorSyncPercent_text)
	print("Размер БД локального валидатора: " + dbSize_text)
	print()
#end define

def GetColorInt(input, border, ending=None):
	if input < border:
		result = bcolors.Green(input, ending)
	else:
		result = bcolors.Red(input, ending)
	return result
#end define

def GetColorStatus(input):
	if input == True:
		result = bcolors.Green("working")
	else:
		result = bcolors.Red("not working")
	return result
#end define

def PrintTonConfig(fullConfigAddr, fullElectorAddr, config15, config17):
	# Конфигурация сети TON
	validatorsElectedFor = config15["validatorsElectedFor"]
	electionsStartBefore = config15["electionsStartBefore"]
	electionsEndBefore = config15["electionsEndBefore"]
	stakeHeldFor = config15["stakeHeldFor"]
	minStake = config17["minStake"]
	maxStake = config17["maxStake"]

	fullConfigAddr_text = bcolors.Yellow(fullConfigAddr)
	fullElectorAddr_text = bcolors.Yellow(fullElectorAddr)
	validatorsElectedFor_text = bcolors.Yellow(validatorsElectedFor)
	electionsStartBefore_text = bcolors.Yellow(electionsStartBefore)
	electionsEndBefore_text = bcolors.Yellow(electionsEndBefore)
	stakeHeldFor_text = bcolors.Yellow(stakeHeldFor)
	minStake_text = bcolors.Yellow(minStake)
	maxStake_text = bcolors.Yellow(maxStake)

	ColorPrint("{cyan}===[ Конфигурация сети TON ]==={endc}")
	print("Адрес конфигуратора: {0}".format(fullConfigAddr_text))
	print("Адрес электора: {0}".format(fullElectorAddr_text))
	print("Периуд валидации: {0}, Длительность выборов: {1}-{2}, Периуд удержания ставки: {3}".format(validatorsElectedFor_text, electionsStartBefore_text, electionsEndBefore_text, stakeHeldFor_text))
	print("Минимальная ставка: {0}, Максимальная ставка: {1}".format(minStake_text, maxStake_text))
	print()
#end define

def PrintTimes(rootWorkchainEnabledTime_int, startWorkTime, oldStartWorkTime, config15):
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
	rootWorkchainEnabledTime = Timestamp2Datetime(rootWorkchainEnabledTime_int)
	startValidationTime = Timestamp2Datetime(startValidation)
	endValidationTime = Timestamp2Datetime(endValidation)
	startElectionTime = Timestamp2Datetime(startElection)
	endElectionTime = Timestamp2Datetime(endElection)
	startNextElectionTime = Timestamp2Datetime(startNextElection)
	
	# datetime to color text
	rootWorkchainEnabledTime_text = bcolors.Yellow(rootWorkchainEnabledTime)
	startValidationTime_text = GetColorTime(startValidationTime, startValidation)
	endValidationTime_text = GetColorTime(endValidationTime, endValidation)
	startElectionTime_text = GetColorTime(startElectionTime, startElection)
	endElectionTime_text = GetColorTime(endElectionTime, endElection)
	startNextElectionTime_text = GetColorTime(startNextElectionTime, startNextElection)

	# Временные метки TON
	ColorPrint("{cyan}===[ Временные метки TON ]==={endc}")
	print("TON сеть была запущена: " + rootWorkchainEnabledTime_text)
	if startValidation < 0:
		return
	print("Начало цикла валидации: " + startValidationTime_text)
	print("Конец цикла валидации: " + endValidationTime_text)
	print("Начало выборов: " + startElectionTime_text)
	print("Конец выборов: " + endElectionTime_text)
	print("Начало следующих выборов: " + startNextElectionTime_text)
#end define

def GetColorTime(datetime, timestamp):
	newTimestamp = GetTimestamp()
	if timestamp > newTimestamp:
		result = bcolors.Green(datetime)
	else:
		result = bcolors.Yellow(datetime)
	return result
#end define

def Seqno(args):
	try:
		walletName = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} seqno <wallet-name>")
		return
	
	wallet = ton.GetLocalWallet(walletName)
	seqno = ton.GetSeqno(wallet)
	print(walletName, "seqno:", seqno)
#end define

def CreatNewWallet(args):
	try:
		walletName = args[0]
		workchain = args[1]
	except:
		walletName = ton.GenerateWalletName()
		workchain = 0
	wallet = ton.CreateWallet(walletName, workchain)
	table = list()
	table += [["Name", "Workchain", "Address"]]
	table += [[wallet.name, wallet.workchain, wallet.addr_init]]
	PrintTable(table)
#end define

def ActivateWallet(args):
	try:
		walletName = args[0]
	except Exception as err:
		walletName = "all"
	if walletName == "all":
		ton.WalletsCheck()
	else:
		wallet = ton.GetLocalWallet(walletName)
		if not os.path.isfile(wallet.bocFilePath):
			local.AddLog("Wallet {walletName} already activated".format(walletName=walletName), "warning")
			return
		account = ton.GetAccount(wallet.addr)
		if account.balance > 0:
			ton.SendFile(wallet.bocFilePath, wallet)
	ColorPrint("ActivateWallet - {green}OK{endc}")
#end define

def PrintWalletsList(args):
	table = list()
	table += [["Name", "Status", "Balance", "Workchain", "Address"]]
	data = ton.GetWallets()
	if (data is None or len(data) == 0):
		print("No data")
		return
	for wallet in data:
		account = ton.GetAccount(wallet.addr)
		if account.status != "active":
			wallet.addr = wallet.addr_init
		table += [[wallet.name, account.status, account.balance, wallet.workchain, wallet.addr]]
	PrintTable(table)
#end define

def ImportWalletFromFile(args):
	try:
		filePath = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} iw <wallet-path>")
		return
	walletsDir = local.buffer.get("walletsDir")
	if (".addr" in filePath):
		filePath = filePath.replace(".addr", '')
	if (".pk" in filePath):
		filePath = filePath.replace(".pk", '')
	if os.path.isfile(filePath + ".addr") == False:
		local.AddLog("ImportWalletFromFile error: Address file not found: " + filePath, "error")
		return
	if os.path.isfile(filePath + ".pk") == False:
		local.AddLog("ImportWalletFromFile error: Private key not found: " + filePath, "error")
		return
	if '/' in filePath:
		walletName = filePath[filePath.rfind('/')+1:]
	else:
		walletName = filePath
	copyfile(filePath + ".addr", walletsDir + walletName + ".addr")
	copyfile(filePath + ".pk", walletsDir + walletName + ".pk")
	ColorPrint("ImportWalletFromFile - {green}OK{endc}")
#end define

def SaveWalletAddressToFile(args):
	try:
		walletName = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} sw <wallet-name>")
		return
	wallet = ton.GetLocalWallet(walletName)
	wjson = {"name":wallet.name, "workchain":wallet.workchain, "addr":wallet.addr, "addr_hex":wallet.addr_hex, "addr_init":wallet.addr_init}
	text = json.dumps(wjson)
	file = open(walletName + "-addr.json", 'w')
	file.write(text)
	file.close()
	ColorPrint("SaveWalletAddressToFile - {green}OK{endc}")
#end define

def DeleteWallet(args):
	try:
		walletName = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} dw <wallet-name>")
		return
	wallet = ton.GetLocalWallet(walletName)
	wallet.Delete()
	ColorPrint("DeleteWallet - {green}OK{endc}")
#end define

def ViewAccountStatus(args):
	try:
		addr = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} vas <account-addr>")
		return
	addr = ton.GetDestinationAddr(addr)
	account = ton.GetAccount(addr)
	statusTable = list()
	statusTable += [["Address", "Status", "Balance"]]
	statusTable += [[addr, account.status, account.balance]]
	historyTable = GetHistoryTable(addr, 10)
	PrintTable(statusTable)
	print()
	PrintTable(historyTable)
#end define

def ViewAccountHistory(args):
	try:
		addr = args[0]
		limit = int(args[1])
	except:
		ColorPrint("{red}Bad args. Usage:{endc} vah <account-addr> <limit>")
		return
	table = GetHistoryTable(addr, limit)
	PrintTable(table)
#end define

def GetHistoryTable(addr, limit):
	addr = ton.GetDestinationAddr(addr)
	account = ton.GetAccount(addr)
	history = ton.GetAccountHistory(account, limit)
	table = list()
	typeText = ColorText("{red}{bold}{endc}")
	table += [["Time", typeText, "Grams", "From/To"]]
	for item in history:
		time = item.get("time")
		grams = item.get("value")
		outmsg = item.get("outmsg")
		if outmsg == 1:
			type = ColorText("{red}{bold}>>>{endc}")
			fromto = item.get("to")
		else:
			type = ColorText("{blue}{bold}<<<{endc}")
			fromto = item.get("from")
		fromto = ton.HexAddr2Base64Addr(fromto)
		#datetime = Timestamp2Datetime(time, "%Y.%m.%d %H:%M:%S")
		datetime = timeago(time)
		table += [[datetime, type, grams, fromto]]
	return table
#end define

def MoveGrams(args):
	try:
		walletName = args[0]
		destination = args[1]
		gram = args[2]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} mg <wallet-name> <account-addr | bookmark-name> <gram-amount>")
		return
	destination = ton.GetDestinationAddr(destination)
	ton.MoveGrams(walletName, destination, gram)
	ColorPrint("MoveGrams - {green}OK{endc}")
#end define

def CreatNewBookmark(args):
	try:
		name = args[0]
		addr = args[1]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} nb <bookmark-name> <account-addr | domain-name>")
		return
	type = ton.GetStrType(addr)
	bookmark = dict()
	bookmark["name"] = name
	bookmark["type"] = type
	bookmark["addr"] = addr
	ton.AddBookmark(bookmark)
	ColorPrint("CreatNewBookmark - {green}OK{endc}")
#end define

def PrintBookmarksList(args):
	data = ton.GetBookmarks()
	if (data is None or len(data) == 0):
		print("No data")
		return
	table = list()
	table += [["Name", "Type", "Address / Domain", "Balance / Exp. date"]]
	for item in data:
		name = item.get("name")
		type = item.get("type")
		addr = item.get("addr")
		data = item.get("data")
		table += [[name, type, addr, data]]
	PrintTable(table)
#end define

def DeleteBookmark(args):
	try:
		name = args[0]
		type = args[1]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} db <bookmark-name> <bookmark-type>")
		return
	ton.DeleteBookmark(name, type)
	ColorPrint("DeleteBookmark - {green}OK{endc}")
#end define

def CreatNewRule(args):
	print("fix me")
#end define

def PrintRulesList(args):
	data = ton.GetRules()
	if (data is None or len(data) == 0):
		print("No data")
		return
	table = list()
	table += [["Name", "fix me"]]
	for item in data:
		table += [[item.get("name"), item.get("fix me")]]
	PrintTable(table)
#end define

def DeleteRule(args):
	print("fix me")
#end define

# def MoveGramsFromMixer(args):
# 	print("fix me")
# #end define

def PrintOffersList(args):
	offers = ton.GetOffers()
	print(json.dumps(offers, indent=4))
#end define

def VoteOffer(args):
	try:
		offerHash = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} vo <offer-hash>")
		return
	ton.VoteOffer(offerHash)
	ColorPrint("VoteOffer - {green}OK{endc}")
#end define

def NewDomain(args):
	try:
		domainName = args[0]
		walletName = args[1]
		adnlAddr = args[2]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} nd <domain-name> <wallet-name> <site-adnl-addr>")
		return
	domain = dict()
	domain["name"] = domainName
	domain["adnlAddr"] = adnlAddr
	domain["walletName"] = walletName
	ton.NewDomain(domain)
	ColorPrint("NewDomain - {green}OK{endc}")
#end define

def PrintDomainsList(args):
	data = ton.GetDomains()
	if (data is None or len(data) == 0):
		print("No data")
		return
	table = list()
	table += [["Domain", "Wallet", "Expiration date", "ADNL address"]]
	for item in data:
		domainName = item.get("name")
		walletName = item.get("walletName")
		endTime = item.get("endTime")
		endTime = Timestamp2Datetime(endTime, "%d.%m.%Y")
		adnlAddr = item.get("adnlAddr")
		table += [[domainName, walletName, endTime, adnlAddr]]
	PrintTable(table)
#end define

def ViewDomainStatus(args):
	try:
		domainName = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} vd <domain-name>")
		return
	domain = ton.GetDomain(domainName)
	endTime = domain.get("endTime")
	endTime = Timestamp2Datetime(endTime, "%d.%m.%Y")
	adnlAddr = domain.get("adnlAddr")
	table = list()
	table += [["Domain", "Expiration date", "ADNL address"]]
	table += [[domainName, endTime, adnlAddr]]
	PrintTable(table)
#end define

def DeleteDomain(args):
	try:
		domainName = args[0]
	except:
		ColorPrint("{red}Bad args. Usage:{endc} dd <domain-name>")
		return
	ton.DeleteDomain(domainName)
	ColorPrint("DeleteDomain - {green}OK{endc}")
#end define




###
### Start of the program
###

if __name__ == "__main__":
	Init()
	console.Run()
#end if
