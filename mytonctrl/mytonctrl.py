#!/usr/bin/env python3
# -*- coding: utf_8 -*-
import subprocess
import json
import psutil
import inspect
import pkg_resources
import socket

from shutil import copyfile
from functools import partial

from mypylib.mypylib import (
	# GetGitAuthorAndRepo,
	# GetGitBranch,
	# GetGitHash,
	# CheckGitUpdate,
	# GetServiceStatus,
	# GetServiceUptime,
	# GetLoadAvg,
	# RunAsRoot,
	# time2human,
	# timeago,
	# Timestamp2Datetime,
	# GetTimestamp,
	# PrintTable,
	# ColorPrint,
	# ColorText,
	# bcolors,
	# MyPyClass,

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
	timeago,
	timestamp2datetime,
	get_timestamp,
	print_table,
	color_print,
	color_text,
	bcolors,
	MyPyClass
)

from mypyconsole.mypyconsole import MyPyConsole
from mytoncore.mytoncore import MyTonCore
from mytoncore.functions import (
	Slashing, 
	Elections,
	GetMemoryInfo,
	GetSwapInfo,
	GetBinGitHash,
)

import sys, getopt, os


def Init(local, ton, console, argv):
	# Load translate table
	translate_path = pkg_resources.resource_filename('mytonctrl', 'resources/translate.json')
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
	console.startFunction = inject_globals(PreUp) 

	console.AddItem("update", inject_globals(Update), local.translate("update_cmd"))
	console.AddItem("upgrade", inject_globals(Upgrade), local.translate("upgrade_cmd"))
	console.AddItem("installer", inject_globals(Installer), local.translate("installer_cmd"))
	console.AddItem("status", inject_globals(PrintStatus), local.translate("status_cmd"))
	console.AddItem("seqno", inject_globals(Seqno), local.translate("seqno_cmd"))
	console.AddItem("getconfig", inject_globals(GetConfig), local.translate("getconfig_cmd"))

	console.AddItem("nw", inject_globals(CreatNewWallet), local.translate("nw_cmd"))
	console.AddItem("aw", inject_globals(ActivateWallet), local.translate("aw_cmd"))
	console.AddItem("wl", inject_globals(PrintWalletsList), local.translate("wl_cmd"))
	console.AddItem("iw", inject_globals(ImportWallet), local.translate("iw_cmd"))
	console.AddItem("swv", inject_globals(SetWalletVersion), local.translate("swv_cmd"))
	console.AddItem("ew", inject_globals(ExportWallet), local.translate("ex_cmd"))
	console.AddItem("dw", inject_globals(DeleteWallet), local.translate("dw_cmd"))

	console.AddItem("vas", inject_globals(ViewAccountStatus), local.translate("vas_cmd"))
	console.AddItem("vah", inject_globals(ViewAccountHistory), local.translate("vah_cmd"))
	console.AddItem("mg", inject_globals(MoveCoins), local.translate("mg_cmd"))
	console.AddItem("mgtp", inject_globals(MoveCoinsThroughProxy), local.translate("mgtp_cmd"))

	console.AddItem("nb", inject_globals(CreatNewBookmark), local.translate("nb_cmd"))
	console.AddItem("bl", inject_globals(PrintBookmarksList), local.translate("bl_cmd"))
	console.AddItem("db", inject_globals(DeleteBookmark), local.translate("db_cmd"))

	# console.AddItem("nr", inject_globals(CreatNewAutoTransferRule), local.translate("nr_cmd")) # "Добавить правило автопереводов в расписание / Create new auto transfer rule"
	# console.AddItem("rl", inject_globals(PrintAutoTransferRulesList), local.translate("rl_cmd")) # "Показать правила автопереводов / Show auto transfer rule list"
	# console.AddItem("dr", inject_globals(DeleteAutoTransferRule), local.translate("dr_cmd")) # "Удалить правило автопереводов из расписания / Delete auto transfer rule"

	console.AddItem("nd", inject_globals(NewDomain), local.translate("nd_cmd"))
	console.AddItem("dl", inject_globals(PrintDomainsList), local.translate("dl_cmd"))
	console.AddItem("vds", inject_globals(ViewDomainStatus), local.translate("vds_cmd"))
	console.AddItem("dd", inject_globals(DeleteDomain), local.translate("dd_cmd"))
	console.AddItem("gdfa", inject_globals(GetDomainFromAuction), local.translate("gdfa_cmd"))

	console.AddItem("ol", inject_globals(PrintOffersList), local.translate("ol_cmd"))
	console.AddItem("vo", inject_globals(VoteOffer), local.translate("vo_cmd"))
	console.AddItem("od", inject_globals(OfferDiff), local.translate("od_cmd"))

	console.AddItem("el", inject_globals(PrintElectionEntriesList), local.translate("el_cmd"))
	console.AddItem("ve", inject_globals(VoteElectionEntry), local.translate("ve_cmd"))
	console.AddItem("vl", inject_globals(PrintValidatorList), local.translate("vl_cmd"))
	console.AddItem("cl", inject_globals(PrintComplaintsList), local.translate("cl_cmd"))
	console.AddItem("vc", inject_globals(VoteComplaint), local.translate("vc_cmd"))

	console.AddItem("get", inject_globals(GetSettings), local.translate("get_cmd"))
	console.AddItem("set", inject_globals(SetSettings), local.translate("set_cmd"))
	console.AddItem("xrestart", inject_globals(Xrestart), local.translate("xrestart_cmd"))
	console.AddItem("xlist", inject_globals(Xlist), local.translate("xlist_cmd"))
	#console.AddItem("gpk", inject_globals(GetPubKey), local.translate("gpk_cmd"))
	#console.AddItem("ssoc", inject_globals(SignShardOverlayCert), local.translate("ssoc_cmd"))
	#console.AddItem("isoc", inject_globals(ImportShardOverlayCert), local.translate("isoc_cmd"))

	#console.AddItem("new_nomination_controller", inject_globals(NewNominationController), local.translate("new_controller_cmd"))
	#console.AddItem("get_nomination_controller_data", inject_globals(GetNominationControllerData), local.translate("get_nomination_controller_data_cmd"))
	#console.AddItem("deposit_to_nomination_controller", inject_globals(DepositToNominationController), local.translate("deposit_to_controller_cmd"))
	#console.AddItem("withdraw_from_nomination_controller", inject_globals(WithdrawFromNominationController), local.translate("withdraw_from_nomination_controller_cmd"))
	#console.AddItem("request_to_nomination_controller", inject_globals(SendRequestToNominationController), local.translate("request_to_nomination_controller_cmd"))
	#console.AddItem("new_restricted_wallet", inject_globals(NewRestrictedWallet), local.translate("new_restricted_wallet_cmd"))

	console.AddItem("new_pool", inject_globals(NewPool), local.translate("new_pool_cmd"))
	console.AddItem("pools_list", inject_globals(PrintPoolsList), local.translate("pools_list_cmd"))
	console.AddItem("get_pool_data", inject_globals(GetPoolData), local.translate("get_pool_data_cmd"))
	console.AddItem("activate_pool", inject_globals(ActivatePool), local.translate("activate_pool_cmd"))
	console.AddItem("deposit_to_pool", inject_globals(DepositToPool), local.translate("deposit_to_pool_cmd"))
	console.AddItem("withdraw_from_pool", inject_globals(WithdrawFromPool), local.translate("withdraw_from_pool_cmd"))
	console.AddItem("delete_pool", inject_globals(DeletePool), local.translate("delete_pool_cmd"))
	#console.AddItem("update_validator_set", inject_globals(UpdateValidatorSet), local.translate("update_validator_set_cmd"))

	# console.AddItem("pt", inject_globals(PrintTest), "PrintTest")
	# console.AddItem("sl", inject_globals(sl), "sl")

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
	#end for

	local.db.config.logLevel = "debug"
	local.db.config.isLocaldbSaving = False
	local.run()
#end define

def PreUp(local, ton):
	CheckMytonctrlUpdate(local)
	check_vport(local, ton)
	# CheckTonUpdate()
#end define

def Installer(args):
	# args = ["python3", "/usr/src/mytonctrl/mytoninstaller.py"]
	args = ["python3", "-m", "mytoninstaller"]
	subprocess.run(args)
#end define

def GetItemFromList(data, index):
	try:
		return data[index]
	except: pass
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
	vconfig = ton.GetValidatorConfig()
	addr = vconfig.addrs.pop()
	ip = int2ip(addr.ip)
	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
		result = client_socket.connect_ex((ip, addr.port))
	if result != 0:
		color_print(local.translate("vport_error"))
#end define

def check_git(input_args, default_repo, text):
	src_dir = "/usr/src"
	git_path = f"{src_dir}/{default_repo}"
	default_author = "ton-blockchain"
	default_branch = "master"

	# Get author, repo, branch
	local_author, local_repo = get_git_author_and_repo(git_path)
	local_branch = get_git_branch(git_path)

	# Set author, repo, branch
	data = GetAuthorRepoBranchFromArgs(input_args)
	need_author = data.get("author")
	need_repo = data.get("repo")
	need_branch = data.get("branch")

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
	#end if

	return need_author, need_repo, need_branch
#end define

def Update(local, args):
	repo = "mytonctrl"
	author, repo, branch = check_git(args, repo, "update")

	# Run script
	update_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/update.sh')
	runArgs = ["bash", update_script_path, "-a", author, "-r", repo, "-b", branch]
	exitCode = run_as_root(runArgs)
	if exitCode == 0:
		text = "Update - {green}OK{endc}"
	else:
		text = "Update - {red}Error{endc}"
	color_print(text)
	local.exit()
#end define

def Upgrade(ton, args):
	repo = "ton"
	author, repo, branch = check_git(args, repo, "upgrade")

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

	# Run script
	upgrade_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/upgrade.sh')
	runArgs = ["bash", upgrade_script_path, "-a", author, "-r", repo, "-b", branch]
	exitCode = run_as_root(runArgs)
	if exitCode == 0:
		text = "Upgrade - {green}OK{endc}"
	else:
		text = "Upgrade - {red}Error{endc}"
	color_print(text)
#end define

def CheckMytonctrlUpdate(local):
	git_path = local.buffer.my_dir
	result = check_git_update(git_path)
	if result is True:
		color_print(local.translate("mytonctrl_update_available"))
#end define

def CheckTonUpdate(local):
	git_path = "/usr/src/ton"
	result = check_git_update(git_path)
	if result is True:
		color_print(local.translate("ton_update_available"))
#end define

def PrintTest(local, args):
	print(json.dumps(local.buffer, indent=2))
#end define

def sl(ton, args):
	Slashing(ton.local, ton)
#end define

def PrintStatus(local, ton, args):
	opt = None
	if len(args) == 1:
		opt = args[0]
	adnlAddr = ton.GetAdnlAddr()
	rootWorkchainEnabledTime_int = ton.GetRootWorkchainEnabledTime()
	config34 = ton.GetConfig34()
	config36 = ton.GetConfig36()
	totalValidators = config34["totalValidators"]
	onlineValidators = None
	validatorEfficiency = None
	if opt != "fast":
		onlineValidators = ton.GetOnlineValidators()
		validatorEfficiency = ton.GetValidatorEfficiency()
	if onlineValidators:
		onlineValidators = len(onlineValidators)
	oldStartWorkTime = config36.get("startWorkTime")
	if oldStartWorkTime is None:
		oldStartWorkTime = config34.get("startWorkTime")
	shardsNumber = ton.GetShardsNumber()
	validatorStatus = ton.GetValidatorStatus()
	config15 = ton.GetConfig15()
	config17 = ton.GetConfig17()
	fullConfigAddr = ton.GetFullConfigAddr()
	fullElectorAddr = ton.GetFullElectorAddr()
	startWorkTime = ton.GetActiveElectionId(fullElectorAddr)
	validatorIndex = ton.GetValidatorIndex()
	validatorWallet = ton.GetValidatorWallet()
	dbSize = ton.GetDbSize()
	dbUsage = ton.GetDbUsage()
	memoryInfo = GetMemoryInfo()
	swapInfo = GetSwapInfo()
	offersNumber = ton.GetOffersNumber()
	complaintsNumber = ton.GetComplaintsNumber()
	statistics = ton.GetSettings("statistics")
	tpsAvg = ton.GetStatistics("tpsAvg", statistics)
	netLoadAvg = ton.GetStatistics("netLoadAvg", statistics)
	disksLoadAvg = ton.GetStatistics("disksLoadAvg", statistics)
	disksLoadPercentAvg = ton.GetStatistics("disksLoadPercentAvg", statistics)
	if validatorWallet is not None:
		validatorAccount = ton.GetAccount(validatorWallet.addrB64)
	else:
		validatorAccount = None
	PrintTonStatus(local, startWorkTime, totalValidators, onlineValidators, shardsNumber, offersNumber, complaintsNumber, tpsAvg)
	PrintLocalStatus(local, adnlAddr, validatorIndex, validatorEfficiency, validatorWallet, validatorAccount, validatorStatus, dbSize, dbUsage, memoryInfo, swapInfo, netLoadAvg, disksLoadAvg, disksLoadPercentAvg)
	PrintTonConfig(local, fullConfigAddr, fullElectorAddr, config15, config17)
	PrintTimes(local, rootWorkchainEnabledTime_int, startWorkTime, oldStartWorkTime, config15)
#end define

def PrintTonStatus(local, startWorkTime, totalValidators, onlineValidators, shardsNumber, offersNumber, complaintsNumber, tpsAvg):
	tps1 = tpsAvg[0]
	tps5 = tpsAvg[1]
	tps15 = tpsAvg[2]
	allValidators = totalValidators
	newOffers = offersNumber.get("new")
	allOffers = offersNumber.get("all")
	newComplaints = complaintsNumber.get("new")
	allComplaints = complaintsNumber.get("all")
	tps1_text = bcolors.green_text(tps1)
	tps5_text = bcolors.green_text(tps5)
	tps15_text = bcolors.green_text(tps15)
	tps_text = local.translate("ton_status_tps").format(tps1_text, tps5_text, tps15_text)
	onlineValidators_text = GetColorInt(onlineValidators, border=allValidators*2/3, logic="more")
	allValidators_text = bcolors.yellow_text(allValidators)
	validators_text = local.translate("ton_status_validators").format(onlineValidators_text, allValidators_text)
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
	print(tps_text)
	print(validators_text)
	print(shards_text)
	print(offers_text)
	print(complaints_text)
	print(election_text)
	print()
#end define

def PrintLocalStatus(local, adnlAddr, validatorIndex, validatorEfficiency, validatorWallet, validatorAccount, validatorStatus, dbSize, dbUsage, memoryInfo, swapInfo, netLoadAvg, disksLoadAvg, disksLoadPercentAvg):
	if validatorWallet is None:
		return
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
	validatorOutOfSync = validatorStatus.get("outOfSync")

	validatorIndex_text = GetColorInt(validatorIndex, 0, logic="more")
	validatorIndex_text = local.translate("local_status_validator_index").format(validatorIndex_text)
	validatorEfficiency_text = GetColorInt(validatorEfficiency, 10, logic="more", ending=" %")
	validatorEfficiency_text = local.translate("local_status_validator_efficiency").format(validatorEfficiency_text)
	adnlAddr_text = local.translate("local_status_adnl_addr").format(bcolors.yellow_text(adnlAddr))
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
		diskLoad1_text = bcolors.green_text(item[0])  # TODO: this variables is unused. Why?
		diskLoad5_text = bcolors.green_text(item[1])  # TODO: this variables is unused. Why?
		diskLoad15_text = bcolors.green_text(item[2])
		diskLoadPercent1_text = GetColorInt(disksLoadPercentAvg[key][0], 80, logic="less", ending="%")  # TODO: this variables is unused. Why?
		diskLoadPercent5_text = GetColorInt(disksLoadPercentAvg[key][1], 80, logic="less", ending="%")  # TODO: this variables is unused. Why?
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
	mytoncoreStatus = GetColorStatus(mytoncoreStatus_bool)
	validatorStatus = GetColorStatus(validatorStatus_bool)
	mytoncoreStatus_text = local.translate("local_status_mytoncore_status").format(mytoncoreStatus, mytoncoreUptime_text)
	validatorStatus_text = local.translate("local_status_validator_status").format(validatorStatus, validatorUptime_text)
	validatorOutOfSync_text = local.translate("local_status_validator_out_of_sync").format(GetColorInt(validatorOutOfSync, 20, logic="less", ending=" s"))
	dbSize_text = GetColorInt(dbSize, 1000, logic="less", ending=" Gb")
	dbUsage_text = GetColorInt(dbUsage, 80, logic="less", ending="%")
	dbStatus_text = local.translate("local_status_db").format(dbSize_text, dbUsage_text)
	
	# Mytonctrl and validator git hash
	mtcGitPath = "/usr/src/mytonctrl"
	validatorGitPath = "/usr/src/ton"
	validatorBinGitPath = "/usr/bin/ton/validator-engine/validator-engine"
	mtcGitHash = get_git_hash(mtcGitPath, short=True)
	validatorGitHash = GetBinGitHash(validatorBinGitPath, short=True)
	mtcGitBranch = get_git_branch(mtcGitPath)
	validatorGitBranch = get_git_branch(validatorGitPath)
	mtcGitHash_text = bcolors.yellow_text(mtcGitHash)
	validatorGitHash_text = bcolors.yellow_text(validatorGitHash)
	mtcGitBranch_text = bcolors.yellow_text(mtcGitBranch)
	validatorGitBranch_text = bcolors.yellow_text(validatorGitBranch)
	mtcVersion_text = local.translate("local_status_version_mtc").format(mtcGitHash_text, mtcGitBranch_text)
	validatorVersion_text = local.translate("local_status_version_validator").format(validatorGitHash_text, validatorGitBranch_text)

	color_print(local.translate("local_status_head"))
	print(validatorIndex_text)
	print(validatorEfficiency_text)
	print(adnlAddr_text)
	print(walletAddr_text)
	print(walletBalance_text)
	print(cpuLoad_text)
	print(netLoad_text)
	print(memoryLoad_text)
	
	print(disksLoad_text)
	print(mytoncoreStatus_text)
	print(validatorStatus_text)
	print(validatorOutOfSync_text)
	print(dbStatus_text)
	print(mtcVersion_text)
	print(validatorVersion_text)
	print()
#end define

def GetColorInt(data, border, logic, ending=None):
	if data is None:
		result = bcolors.green_text("n/a")
	elif logic == "more":
		if data >= border:
			result = bcolors.green_text(data, ending)
		else:
			result = bcolors.red_text(data, ending)
	elif logic == "less":
		if data <= border:
			result = bcolors.green_text(data, ending)
		else:
			result = bcolors.red_text(data, ending)
	return result
#end define

def GetColorStatus(input):
	if input == True:
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
	rootWorkchainEnabledTime = timestamp2datetime(rootWorkchainEnabledTime_int)
	startValidationTime = timestamp2datetime(startValidation)
	endValidationTime = timestamp2datetime(endValidation)
	startElectionTime = timestamp2datetime(startElection)
	endElectionTime = timestamp2datetime(endElection)
	startNextElectionTime = timestamp2datetime(startNextElection)

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
	newTimestamp = GetTimestamp()
	if timestamp > newTimestamp:
		result = bcolors.green_text(datetime)
	else:
		result = bcolors.yellow_text(datetime)
	return result
#end define

def Seqno(ton, args):
	try:
		walletName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} seqno <wallet-name>")
		return
	wallet = ton.GetLocalWallet(walletName)
	seqno = ton.GetSeqno(wallet)
	print(walletName, "seqno:", seqno)
#end define

def CreatNewWallet(ton, args):
	version = "v1"
	try:
		if len(args) == 0:
			walletName = ton.GenerateWalletName()
			workchain = 0
		else:
			workchain = int(args[0])
			walletName = args[1]
		if len(args) > 2:
			version = args[2]
		if len(args) == 4:
			subwallet = int(args[3])
		else:
			subwallet = 698983191 + workchain # 0x29A9A317 + workchain
	except:
		color_print("{red}Bad args. Usage:{endc} nw <workchain-id> <wallet-name> [<version> <subwallet>]")
		return
	wallet = ton.CreateWallet(walletName, workchain, version, subwallet=subwallet)
	table = list()
	table += [["Name", "Workchain", "Address"]]
	table += [[wallet.name, wallet.workchain, wallet.addrB64_init]]
	PrintTable(table)
#end define

def ActivateWallet(local, ton, args):
	try:
		walletName = args[0]
	except Exception as err:
		walletName = "all"
	if walletName == "all":
		ton.WalletsCheck()
	else:
		wallet = ton.GetLocalWallet(walletName)
		if not os.path.isfile(wallet.bocFilePath):
			local.add_log("Wallet {walletName} already activated".format(walletName=walletName), "warning")
			return
		ton.ActivateWallet(wallet)
	color_print("ActivateWallet - {green}OK{endc}")
#end define

def PrintWalletsList(ton, args):
	table = list()
	table += [["Name", "Status", "Balance", "Ver", "Wch", "Address"]]
	data = ton.GetWallets()
	if (data is None or len(data) == 0):
		print("No data")
		return
	for wallet in data:
		account = ton.GetAccount(wallet.addrB64)
		if account.status != "active":
			wallet.addrB64 = wallet.addrB64_init
		table += [[wallet.name, account.status, account.balance, wallet.version, wallet.workchain, wallet.addrB64]]
	PrintTable(table)
#end define

def ImportWalletFromFile(local, ton, args):
	try:
		filePath = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} iw <wallet-path>")
		return
	if (".addr" in filePath):
		filePath = filePath.replace(".addr", '')
	if (".pk" in filePath):
		filePath = filePath.replace(".pk", '')
	if os.path.isfile(filePath + ".addr") == False:
		local.add_log("ImportWalletFromFile error: Address file not found: " + filePath, "error")
		return
	if os.path.isfile(filePath + ".pk") == False:
		local.add_log("ImportWalletFromFile error: Private key not found: " + filePath, "error")
		return
	if '/' in filePath:
		walletName = filePath[filePath.rfind('/')+1:]
	else:
		walletName = filePath
	copyfile(filePath + ".addr", ton.walletsDir + walletName + ".addr")
	copyfile(filePath + ".pk", ton.walletsDir + walletName + ".pk")
	color_print("ImportWalletFromFile - {green}OK{endc}")
#end define

def ImportWallet(ton, args):
	try:
		addr = args[0]
		key = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} iw <wallet-addr> <wallet-secret-key>")
		return
	name = ton.ImportWallet(addr, key)
	print("Wallet name:", name)
#end define

def SetWalletVersion(ton, args):
	try:
		addr = args[0]
		version = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} swv <wallet-addr> <wallet-version>")
		return
	ton.SetWalletVersion(addr, version)
	color_print("SetWalletVersion - {green}OK{endc}")
#end define

def ExportWallet(ton, args):
	try:
		name = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} ew <wallet-name>")
		return
	addr, key = ton.ExportWallet(name)
	print("Wallet name:", name)
	print("Address:", addr)
	print("Secret key:", key)
#end define

def DeleteWallet(ton, args):
	try:
		walletName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} dw <wallet-name>")
		return
	if input("Are you sure you want to delete this wallet (yes/no): ") != "yes":
		print("Cancel wallet deletion")
		return
	wallet = ton.GetLocalWallet(walletName)
	wallet.Delete()
	color_print("DeleteWallet - {green}OK{endc}")
#end define

def ViewAccountStatus(ton, args):
	try:
		addrB64 = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} vas <account-addr>")
		return
	addrB64 = ton.GetDestinationAddr(addrB64)
	account = ton.GetAccount(addrB64)
	version = ton.GetWalletVersionFromHash(account.codeHash)
	statusTable = list()
	statusTable += [["Address", "Status", "Version", "Balance"]]
	statusTable += [[addrB64, account.status, version, account.balance]]
	historyTable = GetHistoryTable(ton, addrB64, 10)
	PrintTable(statusTable)
	print()
	PrintTable(historyTable)
#end define

def ViewAccountHistory(ton, args):
	try:
		addr = args[0]
		limit = int(args[1])
	except:
		color_print("{red}Bad args. Usage:{endc} vah <account-addr> <limit>")
		return
	table = GetHistoryTable(ton, addr, limit)
	PrintTable(table)
#end define

def GetHistoryTable(ton, addr, limit):
	addr = ton.GetDestinationAddr(addr)
	account = ton.GetAccount(addr)
	history = ton.GetAccountHistory(account, limit)
	table = list()
	typeText = color_text("{red}{bold}{endc}")
	table += [["Time", typeText, "Coins", "From/To"]]
	for message in history:
		if message.srcAddr is None:
			continue
		srcAddrFull = f"{message.srcWorkchain}:{message.srcAddr}"
		destAddFull = f"{message.destWorkchain}:{message.destAddr}"
		if srcAddrFull == account.addrFull:
			type = color_text("{red}{bold}>>>{endc}")
			fromto = destAddFull
		else:
			type = color_text("{blue}{bold}<<<{endc}")
			fromto = srcAddrFull
		fromto = ton.AddrFull2AddrB64(fromto)
		#datetime = timestamp2datetime(message.time, "%Y.%m.%d %H:%M:%S")
		datetime = timeago(message.time)
		table += [[datetime, type, message.value, fromto]]
	return table
#end define

def MoveCoins(ton, args):
	try:
		walletName = args[0]
		destination = args[1]
		amount = args[2]
		flags = args[3:]
	except:
		color_print("{red}Bad args. Usage:{endc} mg <wallet-name> <account-addr | bookmark-name> <amount>")
		return
	wallet = ton.GetLocalWallet(walletName)
	destination = ton.GetDestinationAddr(destination)
	ton.MoveCoins(wallet, destination, amount, flags=flags)
	color_print("MoveCoins - {green}OK{endc}")
#end define

def MoveCoinsThroughProxy(ton, args):
	try:
		walletName = args[0]
		destination = args[1]
		amount = args[2]
	except:
		color_print("{red}Bad args. Usage:{endc} mgtp <wallet-name> <account-addr | bookmark-name> <amount>")
		return
	wallet = ton.GetLocalWallet(walletName)
	destination = ton.GetDestinationAddr(destination)
	ton.MoveCoinsThroughProxy(wallet, destination, amount)
	color_print("MoveCoinsThroughProxy - {green}OK{endc}")
#end define

def CreatNewBookmark(ton, args):
	try:
		name = args[0]
		addr = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} nb <bookmark-name> <account-addr | domain-name>")
		return
	if ton.IsAddr(addr):
		type = "account"
	else:
		type = "domain"
	#end if

	bookmark = dict()
	bookmark["name"] = name
	bookmark["type"] = type
	bookmark["addr"] = addr
	ton.AddBookmark(bookmark)
	color_print("CreatNewBookmark - {green}OK{endc}")
#end define

def PrintBookmarksList(ton, args):
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

def DeleteBookmark(ton, args):
	try:
		name = args[0]
		type = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} db <bookmark-name> <bookmark-type>")
		return
	ton.DeleteBookmark(name, type)
	color_print("DeleteBookmark - {green}OK{endc}")
#end define

# def CreatNewAutoTransferRule(args):
# 	try:
# 		name = args[0]
# 		addr = args[1]
# 	except:
# 		color_print("{red}Bad args. Usage:{endc} nr <rule-name> <account-addr | domain-name>")
# 		return
# 	rule = dict()
# 	rule["name"] = name
# 	rule["addr"] = addr
# 	ton.AddAutoTransferRule(rule)
# 	color_print("CreatNewAutoTransferRule - {green}OK{endc}")
# #end define

# def PrintAutoTransferRulesList(args):
# 	data = ton.GetRules()
# 	if (data is None or len(data) == 0):
# 		print("No data")
# 		return
# 	table = list()
# 	table += [["Name", "fix me"]]
# 	for item in data:
# 		table += [[item.get("name"), item.get("fix me")]]
# 	PrintTable(table)
# #end define

# def DeleteAutoTransferRule(args):
# 	print("fix me")
# #end define

def PrintOffersList(ton, args):
	offers = ton.GetOffers()
	if "--json" in args:
		text = json.dumps(offers, indent=2)
		print(text)
	else:
		table = list()
		table += [["Hash", "Votes", "W/L", "Approved", "Is passed"]]
		for item in offers:
			hash = item.get("hash")
			votedValidators = len(item.get("votedValidators"))
			wins = item.get("wins")
			losses = item.get("losses")
			wl = "{0}/{1}".format(wins, losses)
			approvedPercent = item.get("approvedPercent")
			approvedPercent_text = "{0}%".format(approvedPercent)
			isPassed = item.get("isPassed")
			if "hash" not in args:
				hash = Reduct(hash)
			if isPassed == True:
				isPassed = bcolors.green_text("true")
			if isPassed == False:
				isPassed = bcolors.red_text("false")
			table += [[hash, votedValidators, wl, approvedPercent_text, isPassed]]
		PrintTable(table)
#end define

def VoteOffer(ton, args):
	if len(args) == 0:
		color_print("{red}Bad args. Usage:{endc} vo <offer-hash>")
		return
	for offerHash in args:
		ton.VoteOffer(offerHash)
	color_print("VoteOffer - {green}OK{endc}")
#end define

def OfferDiff(ton, args):
	try:
		offerHash = args[0]
		offerHash = offerHash
	except:
		color_print("{red}Bad args. Usage:{endc} od <offer-hash>")
		return
	ton.GetOfferDiff(offerHash)
#end define

def GetConfig(ton, args):
	try:
		configId = args[0]
		configId = int(configId)
	except:
		color_print("{red}Bad args. Usage:{endc} gc <config-id>")
		return
	data = ton.GetConfig(configId)
	text = json.dumps(data, indent=2)
	print(text)
#end define

def PrintComplaintsList(ton, args):
	past = "past" in args
	complaints = ton.GetComplaints(past=past)
	if "--json" in args:
		text = json.dumps(complaints, indent=2)
		print(text)
	else:
		table = list()
		table += [["Election id", "ADNL", "Fine (part)", "Votes", "Approved", "Is passed"]]
		for key, item in complaints.items():
			electionId = item.get("electionId")
			adnl = item.get("adnl")
			suggestedFine = item.get("suggestedFine")
			suggestedFinePart = item.get("suggestedFinePart")
			Fine_text = "{0} ({1})".format(suggestedFine, suggestedFinePart)
			votedValidators = len(item.get("votedValidators"))
			approvedPercent = item.get("approvedPercent")
			approvedPercent_text = "{0}%".format(approvedPercent)
			isPassed = item.get("isPassed")
			if "adnl" not in args:
				adnl = Reduct(adnl)
			if isPassed == True:
				isPassed = bcolors.green_text("true")
			if isPassed == False:
				isPassed = bcolors.red_text("false")
			table += [[electionId, adnl, Fine_text, votedValidators, approvedPercent_text, isPassed]]
		PrintTable(table)
#end define

def VoteComplaint(ton, args):
	try:
		electionId = args[0]
		complaintHash = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} vc <election-id> <complaint-hash>")
		return
	ton.VoteComplaint(electionId, complaintHash)
	color_print("VoteComplaint - {green}OK{endc}")
#end define

def NewDomain(ton, args):
	try:
		domainName = args[0]
		walletName = args[1]
		adnlAddr = args[2]
	except:
		color_print("{red}Bad args. Usage:{endc} nd <domain-name> <wallet-name> <site-adnl-addr>")
		return
	domain = dict()
	domain["name"] = domainName
	domain["adnlAddr"] = adnlAddr
	domain["walletName"] = walletName
	ton.NewDomain(domain)
	color_print("NewDomain - {green}OK{endc}")
#end define

def PrintDomainsList(ton, args):
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
		endTime = timestamp2datetime(endTime, "%d.%m.%Y")
		adnlAddr = item.get("adnlAddr")
		table += [[domainName, walletName, endTime, adnlAddr]]
	PrintTable(table)
#end define

def ViewDomainStatus(ton, args):
	try:
		domainName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} vds <domain-name>")
		return
	domain = ton.GetDomain(domainName)
	endTime = domain.get("endTime")
	endTime = timestamp2datetime(endTime, "%d.%m.%Y")
	adnlAddr = domain.get("adnlAddr")
	table = list()
	table += [["Domain", "Expiration date", "ADNL address"]]
	table += [[domainName, endTime, adnlAddr]]
	print_table(table)
#end define

def DeleteDomain(ton, args):
	try:
		domainName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} dd <domain-name>")
		return
	ton.DeleteDomain(domainName)
	color_print("DeleteDomain - {green}OK{endc}")
#end define

def GetDomainFromAuction(ton, args):
	try:
		walletName = args[0]
		addr = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} gdfa <wallet-name> <addr>")
		return
	ton.GetDomainFromAuction(walletName, addr)
	color_print("GetDomainFromAuction - {green}OK{endc}")
#end define

def PrintElectionEntriesList(ton, args):
	past = "past" in args
	entries = ton.GetElectionEntries(past=past)
	if "--json" in args:
		text = json.dumps(entries, indent=2)
		print(text)
	else:
		table = list()
		table += [["ADNL", "Pubkey", "Wallet", "Stake", "Max-factor"]]
		for key, item in entries.items():
			adnl = item.get("adnlAddr")
			pubkey = item.get("pubkey")
			walletAddr = item.get("walletAddr")
			stake = item.get("stake")
			maxFactor = item.get("maxFactor")
			if "adnl" not in args:
				adnl = Reduct(adnl)
			if "pubkey" not in args:
				pubkey = Reduct(pubkey)
			if "wallet" not in args:
				walletAddr = Reduct(walletAddr)
			table += [[adnl, pubkey, walletAddr, stake, maxFactor]]
		print_table(table)
#end define

def VoteElectionEntry(ton, args):
	Elections(ton.local, ton)
	color_print("VoteElectionEntry - {green}OK{endc}")
#end define

def PrintValidatorList(ton, args):
	past = "past" in args
	validators = ton.GetValidatorsList(past=past)
	if "--json" in args:
		text = json.dumps(validators, indent=2)
		print(text)
	else:
		table = list()
		table += [["ADNL", "Pubkey", "Wallet", "Efficiency", "Online"]]
		for item in validators:
			adnl = item.get("adnlAddr")
			pubkey = item.get("pubkey")
			walletAddr = item.get("walletAddr")
			efficiency = item.get("efficiency")
			online = item.get("online")
			if "adnl" not in args:
				adnl = Reduct(adnl)
			if "pubkey" not in args:
				pubkey = Reduct(pubkey)
			if "wallet" not in args:
				walletAddr = Reduct(walletAddr)
			if "offline" in args and online != False:
				continue
			if online == True:
				online = bcolors.green_text("true")
			if online == False:
				online = bcolors.red_text("false")
			table += [[adnl, pubkey, walletAddr, efficiency, online]]
		print_table(table)
#end define

def Reduct(item):
	item = str(item)
	if item is None:
		result = None
	else:
		end = len(item)
		result = item[0:6] + "..." + item[end-6:end]
	return result
#end define

def GetSettings(ton, args):
	try:
		name = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} get <settings-name>")
		return
	result = ton.GetSettings(name)
	print(json.dumps(result, indent=2))
#end define

def SetSettings(ton, args):
	try:
		name = args[0]
		value = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} set <settings-name> <settings-value>")
		return
	ton.SetSettings(name, value)
	color_print("SetSettings - {green}OK{endc}")
#end define

def Xrestart(inputArgs):
	if len(inputArgs) < 2:
		color_print("{red}Bad args. Usage:{endc} xrestart <timestamp> <args>")
		return
	xrestart_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/xrestart.py')
	args = ["python3", xrestart_script_path]  # TODO: Fix path
	args += inputArgs
	exitCode = run_as_root(args)
	if exitCode == 0:
		text = "Xrestart - {green}OK{endc}"
	else:
		text = "Xrestart - {red}Error{endc}"
	color_print(text)
#end define

def Xlist(args):
	color_print("Xlist - {green}OK{endc}")
#end define

def GetPubKey(ton, args):
	adnlAddr = ton.GetAdnlAddr()
	pubkey = ton.GetPubKey(adnlAddr)
	print("pubkey:", pubkey)
#end define

def SignShardOverlayCert(ton, args):
	try:
		adnl = args[0]
		pubkey = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} ssoc <pubkey>")
		return
	ton.SignShardOverlayCert(adnl, pubkey)
#end define

def ImportShardOverlayCert(ton, args):
	ton.ImportShardOverlayCert()
#end define

def NewNominationController(ton, args):
	try:
		name = args[0]
		nominatorAddr = args[1]
		rewardShare = args[2]
		coverAbility = args[3]
	except:
		color_print("{red}Bad args. Usage:{endc} new_controller <controller-name> <nominator-addr> <reward-share> <cover-ability>")
		return
	ton.CreateNominationController(name, nominatorAddr, rewardShare=rewardShare, coverAbility=coverAbility)
	color_print("NewNominationController - {green}OK{endc}")
#end define

def GetNominationControllerData(ton, args):
	try:
		addrB64 = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} get_nomination_controller_data <controller-name | controller-addr>")
		return
	addrB64 = ton.GetDestinationAddr(addrB64)
	controllerData = ton.GetControllerData(addrB64)
	print(json.dumps(controllerData, indent=4))
#end define

def DepositToNominationController(ton, args):
	try:
		walletName = args[0]
		destination = args[1]
		amount = float(args[2])
	except:
		color_print("{red}Bad args. Usage:{endc} add_to_nomination_controller <wallet-name> <controller-addr> <amount>")
		return
	destination = ton.GetDestinationAddr(destination)
	ton.DepositToNominationController(walletName, destination, amount)
	color_print("DepositToNominationController - {green}OK{endc}")
#end define

def WithdrawFromNominationController(ton, args):
	try:
		walletName = args[0]
		destination = args[1]
		amount = float(args[2])
	except:
		color_print("{red}Bad args. Usage:{endc} withdraw_from_nomination_controller <wallet-name> <controller-addr> <amount>")
		return
	destination = ton.GetDestinationAddr(destination)
	ton.WithdrawFromNominationController(walletName, destination, amount)
	color_print("WithdrawFromNominationController - {green}OK{endc}")
#end define

def SendRequestToNominationController(ton, args):
	try:
		walletName = args[0]
		destination = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} request_to_nomination_controller <wallet-name> <controller-addr>")
		return
	destination = ton.GetDestinationAddr(destination)
	ton.SendRequestToNominationController(walletName, destination)
	color_print("SendRequestToNominationController - {green}OK{endc}")
#end define

def NewRestrictedWallet(ton, args):
	try:
		workchain = int(args[0])
		name = args[1]
		ownerAddr = args[2]
		#subwallet = args[3]
	except:
		color_print("{red}Bad args. Usage:{endc} new_restricted_wallet <workchain-id> <wallet-name> <owner-addr>")
		return
	ton.CreateRestrictedWallet(name, ownerAddr, workchain=workchain)
	color_print("NewRestrictedWallet - {green}OK{endc}")
#end define

def NewPool(ton, args):
	try:
		poolName = args[0]
		validatorRewardSharePercent = float(args[1])
		maxNominatorsCount = int(args[2])
		minValidatorStake = int(args[3])
		minNominatorStake = int(args[4])
	except:
		color_print("{red}Bad args. Usage:{endc} new_pool <pool-name> <validator-reward-share-percent> <max-nominators-count> <min-validator-stake> <min-nominator-stake>")
		return
	ton.CreatePool(poolName, validatorRewardSharePercent, maxNominatorsCount, minValidatorStake, minNominatorStake)
	color_print("NewPool - {green}OK{endc}")
#end define

def ActivatePool(local, ton, args):
	try:
		poolName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} activate_pool <pool-name>")
		return
	pool = ton.GetLocalPool(poolName)
	if not os.path.isfile(pool.bocFilePath):
		local.add_log(f"Pool {poolName} already activated", "warning")
		return
	ton.ActivatePool(pool)
	color_print("ActivatePool - {green}OK{endc}")
#end define

def PrintPoolsList(ton, args):
	table = list()
	table += [["Name", "Status", "Balance", "Address"]]
	data = ton.GetPools()
	if (data is None or len(data) == 0):
		print("No data")
		return
	for pool in data:
		account = ton.GetAccount(pool.addrB64)
		if account.status != "active":
			pool.addrB64 = pool.addrB64_init
		table += [[pool.name, account.status, account.balance, pool.addrB64]]
	print_table(table)
#end define

def GetPoolData(ton, args):
	try:
		poolName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} get_pool_data <pool-name | pool-addr>")
		return
	if ton.IsAddr(poolName):
		poolAddr = poolName
	else:
		pool = ton.GetLocalPool(poolName)
		poolAddr = pool.addrB64
	poolData = ton.GetPoolData(poolAddr)
	print(json.dumps(poolData, indent=4))
#end define

def DepositToPool(ton, args):
	try:
		walletName = args[0]
		pollAddr = args[1]
		amount = float(args[2])
	except:
		color_print("{red}Bad args. Usage:{endc} deposit_to_pool <wallet-name> <pool-addr> <amount>")
		return
	ton.DepositToPool(walletName, pollAddr, amount)
	color_print("DepositToPool - {green}OK{endc}")
#end define

def WithdrawFromPool(ton, args):
	try:
		poolAddr = args[0]
		amount = float(args[1])
	except:
		color_print("{red}Bad args. Usage:{endc} withdraw_from_pool <pool-addr> <amount>")
		return
	ton.WithdrawFromPool(poolAddr, amount)
	color_print("WithdrawFromPool - {green}OK{endc}")
#end define

def DeletePool(ton, args):
	try:
		poolName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} delete_pool <pool-name>")
		return
	pool = ton.GetLocalPool(poolName)
	pool.Delete()
	color_print("DeletePool - {green}OK{endc}")
#end define

def UpdateValidatorSet(ton, args):
	try:
		poolAddr = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} update_validator_set <pool-addr>")
		return
	wallet = ton.GetValidatorWallet()
	ton.PoolUpdateValidatorSet(poolAddr, wallet)
	color_print("DeletePool - {green}OK{endc}")
#end define


###
### Start of the program
###

def mytonctrl():
	local = MyPyClass('mytonctrl.py')
	mytoncore_local = MyPyClass('mytoncore.py')
	ton = MyTonCore(mytoncore_local)
	console = MyPyConsole()

	Init(local, ton, console, sys.argv[1:])
	console.Run()
#end define
