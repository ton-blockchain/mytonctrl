#!/usr/bin/env python3
# -*- coding: utf_8 -*-

from mypylib.mypylib import *
from mypyconsole.mypyconsole import *
from custom_overlays import add_custom_overlay, list_custom_overlays, delete_custom_overlay

from mytoncore import *
import sys, getopt, os

local = MyPyClass(__file__)
console = MyPyConsole()
ton = MyTonCore()

def Init(argv):
	# Load translate table
	local.init_translator(local.buffer.my_dir + "translate.json")

	# Create user console
	console.name = "MyTonCtrl"
	console.startFunction = PreUp

	console.AddItem("update", Update, local.translate("update_cmd"))
	console.AddItem("upgrade", Upgrade, local.translate("upgrade_cmd"))
	console.AddItem("installer", Installer, local.translate("installer_cmd"))
	console.AddItem("status", PrintStatus, local.translate("status_cmd"))
	console.AddItem("seqno", Seqno, local.translate("seqno_cmd"))
	console.AddItem("getconfig", GetConfig, local.translate("getconfig_cmd"))

	console.AddItem("add_custom_overlay", add_custom_overlay, local.translate("add_custom_overlay_cmd"))
	console.AddItem("list_custom_overlays", list_custom_overlays, local.translate("list_custom_overlays_cmd"))
	console.AddItem("delete_custom_overlay", delete_custom_overlay, local.translate("delete_custom_overlay_cmd"))
	console.AddItem("set_archive_ttl", set_archive_ttl, local.translate("set_archive_ttl_cmd"))

	console.AddItem("nw", CreatNewWallet, local.translate("nw_cmd"))
	console.AddItem("aw", ActivateWallet, local.translate("aw_cmd"))
	console.AddItem("wl", PrintWalletsList, local.translate("wl_cmd"))
	console.AddItem("iw", ImportWallet, local.translate("iw_cmd"))
	console.AddItem("swv", SetWalletVersion, local.translate("swv_cmd"))
	console.AddItem("ew", ExportWallet, local.translate("ex_cmd"))
	console.AddItem("dw", DeleteWallet, local.translate("dw_cmd"))

	console.AddItem("vas", ViewAccountStatus, local.translate("vas_cmd"))
	console.AddItem("vah", ViewAccountHistory, local.translate("vah_cmd"))
	console.AddItem("mg", MoveCoins, local.translate("mg_cmd"))
	console.AddItem("mgtp", MoveCoinsThroughProxy, local.translate("mgtp_cmd"))

	console.AddItem("nb", CreatNewBookmark, local.translate("nb_cmd"))
	console.AddItem("bl", PrintBookmarksList, local.translate("bl_cmd"))
	console.AddItem("db", DeleteBookmark, local.translate("db_cmd"))

	console.AddItem("nd", NewDomain, local.translate("nd_cmd"))
	console.AddItem("dl", PrintDomainsList, local.translate("dl_cmd"))
	console.AddItem("vds", ViewDomainStatus, local.translate("vds_cmd"))
	console.AddItem("dd", DeleteDomain, local.translate("dd_cmd"))
	console.AddItem("gdfa", GetDomainFromAuction, local.translate("gdfa_cmd"))

	console.AddItem("ol", PrintOffersList, local.translate("ol_cmd"))
	console.AddItem("vo", VoteOffer, local.translate("vo_cmd"))
	console.AddItem("od", OfferDiff, local.translate("od_cmd"))

	console.AddItem("el", PrintElectionEntriesList, local.translate("el_cmd"))
	console.AddItem("ve", VoteElectionEntry, local.translate("ve_cmd"))
	console.AddItem("vl", PrintValidatorList, local.translate("vl_cmd"))
	console.AddItem("cl", PrintComplaintsList, local.translate("cl_cmd"))
	console.AddItem("vc", VoteComplaint, local.translate("vc_cmd"))

	console.AddItem("get", GetSettings, local.translate("get_cmd"))
	console.AddItem("set", SetSettings, local.translate("set_cmd"))
	console.AddItem("xrestart", Xrestart, local.translate("xrestart_cmd"))
	console.AddItem("xlist", Xlist, local.translate("xlist_cmd"))

	console.AddItem("new_pool", NewPool, local.translate("new_pool_cmd"))
	console.AddItem("pools_list", PrintPoolsList, local.translate("pools_list_cmd"))
	console.AddItem("get_pool_data", GetPoolData, local.translate("get_pool_data_cmd"))
	console.AddItem("activate_pool", ActivatePool, local.translate("activate_pool_cmd"))
	console.AddItem("deposit_to_pool", DepositToPool, local.translate("deposit_to_pool_cmd"))
	console.AddItem("withdraw_from_pool", WithdrawFromPool, local.translate("withdraw_from_pool_cmd"))
	console.AddItem("delete_pool", DeletePool, local.translate("delete_pool_cmd"))

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

def PreUp():
	CheckMytonctrlUpdate()  # check mtc current branch update only if there wasnt warning about mtc2
	CheckMytonctrl2Update()
	CheckDiskUsage()
	check_vport()
	# CheckTonUpdate()
#end define

def Installer(args):
	args = ["python3", "/usr/src/mytonctrl/mytoninstaller.py"]
	subprocess.run(args)
#end define

def GetItemFromList(data, index):
	try:
		return data[index]
	except: pass
#end define

def check_vport():
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
		raise Exception(f"{text} error: You are on {remote_url} remote url, to {text} to the tip use `{text} {remote_url}` command")
	elif need_branch is None and local_branch != default_branch:
		raise Exception(f"{text} error: You are on {local_branch} branch, to {text} to the tip of {local_branch} branch use `{text} {local_branch}` command")
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

def Update(args):
	repo = "mytonctrl"
	author, repo, branch = check_git(args, repo, "update")

	# Run script
	runArgs = ["bash", "/usr/src/mytonctrl/scripts/update.sh", "-a", author, "-r", repo, "-b", branch]
	exitCode = run_as_root(runArgs)
	if exitCode == 0:
		text = "Update - {green}OK{endc}"
	else:
		text = "Update - {red}Error{endc}"
	color_print(text)
	local.exit()
#end define

def Upgrade(args):
	repo = "ton"
	author, repo, branch = check_git(args, repo, "upgrade")

	# Run script
	runArgs = ["bash", "/usr/src/mytonctrl/scripts/upgrade.sh", "-a", author, "-r", repo, "-b", branch]
	exitCode = run_as_root(runArgs)
	if exitCode == 0:
		text = "Upgrade - {green}OK{endc}"
	else:
		text = "Upgrade - {red}Error{endc}"
	color_print(text)
#end define

def CheckMytonctrlUpdate():
	git_path = local.buffer.my_dir
	result = check_git_update(git_path)
	if result is True:
		color_print(local.translate("mytonctrl_update_available"))
#end define


def CheckMytonctrl2Update():
	try:
		if not ton.find_myself_in_el():  # we are not validator in current and prev rounds
			print('============================================================================================')
			color_print(local.translate("update_mtc2_warning"))
			print('============================================================================================')
	except Exception as err:
		local.add_log(f'Failed to check node as validator: {err}', "error")
# end define


def CheckDiskUsage():
	usage = ton.GetDbUsage()
	if usage > 90:
		print('============================================================================================')
		color_print(local.translate("disk_usage_warning"))
		print('============================================================================================')
#end define


def CheckTonUpdate():
	git_path = "/usr/src/ton"
	result = check_git_update(git_path)
	if result is True:
		color_print(local.translate("ton_update_available"))
#end define

def PrintStatus(args):
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
	PrintTonStatus(startWorkTime, totalValidators, onlineValidators, shardsNumber, offersNumber, complaintsNumber, tpsAvg)
	PrintLocalStatus(adnlAddr, validatorIndex, validatorEfficiency, validatorWallet, validatorAccount, validatorStatus, dbSize, dbUsage, memoryInfo, swapInfo, netLoadAvg, disksLoadAvg, disksLoadPercentAvg)
	PrintTonConfig(fullConfigAddr, fullElectorAddr, config15, config17)
	PrintTimes(rootWorkchainEnabledTime_int, startWorkTime, oldStartWorkTime, config15)
#end define

def PrintTonStatus(startWorkTime, totalValidators, onlineValidators, shardsNumber, offersNumber, complaintsNumber, tpsAvg):
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

def PrintLocalStatus(adnlAddr, validatorIndex, validatorEfficiency, validatorWallet, validatorAccount, validatorStatus, dbSize, dbUsage, memoryInfo, swapInfo, netLoadAvg, disksLoadAvg, disksLoadPercentAvg):
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
		diskLoad1_text = bcolors.green_text(item[0])
		diskLoad5_text = bcolors.green_text(item[1])
		diskLoad15_text = bcolors.green_text(item[2])
		diskLoadPercent1_text = GetColorInt(disksLoadPercentAvg[key][0], 80, logic="less", ending="%")
		diskLoadPercent5_text = GetColorInt(disksLoadPercentAvg[key][1], 80, logic="less", ending="%")
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

def PrintTonConfig(fullConfigAddr, fullElectorAddr, config15, config17):
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
	newTimestamp = get_timestamp()
	if timestamp > newTimestamp:
		result = bcolors.green_text(datetime)
	else:
		result = bcolors.yellow_text(datetime)
	return result
#end define

def Seqno(args):
	try:
		walletName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} seqno <wallet-name>")
		return
	wallet = ton.GetLocalWallet(walletName)
	seqno = ton.GetSeqno(wallet)
	print(walletName, "seqno:", seqno)
#end define

def CreatNewWallet(args):
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
	print_table(table)
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
			local.add_log("Wallet {walletName} already activated".format(walletName=walletName), "warning")
			return
		ton.ActivateWallet(wallet)
	color_print("ActivateWallet - {green}OK{endc}")
#end define

def PrintWalletsList(args):
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
	print_table(table)
#end define

def ImportWalletFromFile(args):
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

def ImportWallet(args):
	try:
		addr = args[0]
		key = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} iw <wallet-addr> <wallet-secret-key>")
		return
	name = ton.ImportWallet(addr, key)
	print("Wallet name:", name)
#end define

def SetWalletVersion(args):
	try:
		addr = args[0]
		version = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} swv <wallet-addr> <wallet-version>")
		return
	ton.SetWalletVersion(addr, version)
	color_print("SetWalletVersion - {green}OK{endc}")
#end define

def ExportWallet(args):
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

def DeleteWallet(args):
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

def ViewAccountStatus(args):
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
	historyTable = GetHistoryTable(addrB64, 10)
	print_table(statusTable)
	print()
	print_table(historyTable)
#end define

def ViewAccountHistory(args):
	try:
		addr = args[0]
		limit = int(args[1])
	except:
		color_print("{red}Bad args. Usage:{endc} vah <account-addr> <limit>")
		return
	table = GetHistoryTable(addr, limit)
	print_table(table)
#end define

def GetHistoryTable(addr, limit):
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

def MoveCoins(args):
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

def MoveCoinsThroughProxy(args):
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

def CreatNewBookmark(args):
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
	print_table(table)
#end define

def DeleteBookmark(args):
	try:
		name = args[0]
		type = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} db <bookmark-name> <bookmark-type>")
		return
	ton.DeleteBookmark(name, type)
	color_print("DeleteBookmark - {green}OK{endc}")
#end define

def PrintOffersList(args):
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
		print_table(table)
#end define

def VoteOffer(args):
	if len(args) == 0:
		color_print("{red}Bad args. Usage:{endc} vo <offer-hash>")
		return
	for offerHash in args:
		ton.VoteOffer(offerHash)
	color_print("VoteOffer - {green}OK{endc}")
#end define

def OfferDiff(args):
	try:
		offerHash = args[0]
		offerHash = offerHash
	except:
		color_print("{red}Bad args. Usage:{endc} od <offer-hash>")
		return
	ton.GetOfferDiff(offerHash)
#end define

def GetConfig(args):
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

def PrintComplaintsList(args):
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
		print_table(table)
#end define

def VoteComplaint(args):
	try:
		electionId = args[0]
		complaintHash = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} vc <election-id> <complaint-hash>")
		return
	ton.VoteComplaint(electionId, complaintHash)
	color_print("VoteComplaint - {green}OK{endc}")
#end define

def NewDomain(args):
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
		endTime = timestamp2datetime(endTime, "%d.%m.%Y")
		adnlAddr = item.get("adnlAddr")
		table += [[domainName, walletName, endTime, adnlAddr]]
	print_table(table)
#end define

def ViewDomainStatus(args):
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

def DeleteDomain(args):
	try:
		domainName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} dd <domain-name>")
		return
	ton.DeleteDomain(domainName)
	color_print("DeleteDomain - {green}OK{endc}")
#end define

def GetDomainFromAuction(args):
	try:
		walletName = args[0]
		addr = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} gdfa <wallet-name> <addr>")
		return
	ton.GetDomainFromAuction(walletName, addr)
	color_print("GetDomainFromAuction - {green}OK{endc}")
#end define

def PrintElectionEntriesList(args):
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

def VoteElectionEntry(args):
	Elections(ton)
	color_print("VoteElectionEntry - {green}OK{endc}")
#end define

def PrintValidatorList(args):
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

def GetSettings(args):
	try:
		name = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} get <settings-name>")
		return
	result = ton.GetSettings(name)
	print(json.dumps(result, indent=2))
#end define

def SetSettings(args):
	try:
		name = args[0]
		value = args[1]
	except:
		color_print("{red}Bad args. Usage:{endc} set <settings-name> <settings-value>")
		return
	result = ton.SetSettings(name, value)
	color_print("SetSettings - {green}OK{endc}")
#end define

def Xrestart(inputArgs):
	if len(inputArgs) < 2:
		color_print("{red}Bad args. Usage:{endc} xrestart <timestamp> <args>")
		return
	args = ["python3", "/usr/src/mytonctrl/scripts/xrestart.py"]
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

def NewPool(args):
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

def ActivatePool(args):
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

def PrintPoolsList(args):
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

def GetPoolData(args):
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

def DepositToPool(args):
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

def WithdrawFromPool(args):
	try:
		poolAddr = args[0]
		amount = float(args[1])
	except:
		color_print("{red}Bad args. Usage:{endc} withdraw_from_pool <pool-addr> <amount>")
		return
	ton.WithdrawFromPool(poolAddr, amount)
	color_print("WithdrawFromPool - {green}OK{endc}")
#end define

def DeletePool(args):
	try:
		poolName = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} delete_pool <pool-name>")
		return
	pool = ton.GetLocalPool(poolName)
	pool.Delete()
	color_print("DeletePool - {green}OK{endc}")
#end define

def UpdateValidatorSet(args):
	try:
		poolAddr = args[0]
	except:
		color_print("{red}Bad args. Usage:{endc} update_validator_set <pool-addr>")
		return
	wallet = self.GetValidatorWallet()
	self.PoolUpdateValidatorSet(poolAddr, wallet)
	color_print("DeletePool - {green}OK{endc}")
#end define


def set_archive_ttl(args):
	if len(args) != 1:
		color_print("{red}Bad args. Usage:{endc} set_archive_ttl <ttl>")
		return
	ttl = args[0]
	result = run_as_root(['python3', '/usr/src/mytonctrl/scripts/set_archive_ttl.py', ttl])
	if result:
		color_print("set_archive_ttl - {red}Error{endc}")
		return
	color_print("set_archive_ttl - {green}OK{endc}")
#end define


###
### Start of the program
###

if __name__ == "__main__":
	Init(sys.argv[1:])
	console.Run()
#end if
