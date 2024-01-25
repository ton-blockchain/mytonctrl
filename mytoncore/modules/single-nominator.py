import pkg_resources

def create_single_nominator_pool(self, pool_name, owner_address):
	self.local.add_log("start create_single_nominator_pool function", "debug")

	file_path = self.poolsDir + pool_name
	if os.path.isfile(file_path + ".addr"):
		self.local.add_log("create_single_nominator_pool warning: Pool already exists: " + file_path, "warning")
		return
	#end if

	fift_script = pkg_resources.resource_filename('mytoncore', 'contracts/single-nominator-pool/init.fif')
	validator_wallet = self.GetValidatorWallet()
	args = [fift_script, owner_address, validator_wallet.addrB64, file_path]
	result = self.fift.Run(args)
	if "Saved single nominator pool" not in result:
		raise Exception("create_single_nominator_pool error: " + result)
	#end if
	
	pools = self.get_single_pools()
	new_pool = self.get_single_local_pool(pool_name)
	for pool in pools:
		if pool.name != new_pool.name and pool.addrB64 == new_pool.addrB64:
			new_pool.Delete()
			raise Exception("create_single_nominator_pool error: Pool with the same parameters already exists.")
	#end for
#end define

def activate_pool(self, pool, ex=True):
	self.local.add_log("start activate_pool function", "debug")
	for i in range(10):
		time.sleep(3)
		account = self.GetAccount(pool.addrB64)
		if account.balance > 0:
			self.SendFile(pool.bocFilePath, pool, timeout=False)
			return
	if ex:
		raise Exception("activate_pool error: time out")
#end define

def DepositToPool(self, poolAddr, amount):
	wallet = self.GetValidatorWallet()
	bocPath = self.local.buffer.my_temp_dir + wallet.name + "validator-deposit-query.boc"
	fiftScript = self.contractsDir + "nominator-pool/func/validator-deposit.fif"
	args = [fiftScript, bocPath]
	result = self.fift.Run(args)
	resultFilePath = self.SignBocWithWallet(wallet, bocPath, poolAddr, amount)
	self.SendFile(resultFilePath, wallet)
#end define

def WithdrawFromPool(self, poolAddr, amount):
	poolData = self.GetPoolData(poolAddr)
	if poolData["state"] == 0:
		self.WithdrawFromPoolProcess(poolAddr, amount)
	else:
		self.PendWithdrawFromPool(poolAddr, amount)
#end define

def WithdrawFromPoolProcess(self, poolAddr, amount):
	self.local.add_log("start WithdrawFromPoolProcess function", "debug")
	wallet = self.GetValidatorWallet()
	bocPath = self.local.buffer.my_temp_dir + wallet.name + "validator-withdraw-query.boc"
	fiftScript = self.contractsDir + "nominator-pool/func/validator-withdraw.fif"
	args = [fiftScript, amount, bocPath]
	result = self.fift.Run(args)
	resultFilePath = self.SignBocWithWallet(wallet, bocPath, poolAddr, 1.35)
	self.SendFile(resultFilePath, wallet)
#end define

def PendWithdrawFromPool(self, poolAddr, amount):
	self.local.add_log("start PendWithdrawFromPool function", "debug")
	pendingWithdraws = self.GetPendingWithdraws()
	pendingWithdraws[poolAddr] = amount
	self.local.save()
#end define

def HandlePendingWithdraw(self, pendingWithdraws, poolAddr):
	amount = pendingWithdraws.get(poolAddr)
	self.WithdrawFromPoolProcess(poolAddr, amount)
	pendingWithdraws.pop(poolAddr)
#end define

def GetPendingWithdraws(self):
	bname = "pendingWithdraws"
	pendingWithdraws = self.local.db.get(bname)
	if pendingWithdraws is None:
		pendingWithdraws = dict()
		self.local.db[bname] = pendingWithdraws
	return pendingWithdraws
#end define

def SignElectionRequestWithPoolWithValidator(self, pool, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor, stake):
	self.local.add_log("start SignElectionRequestWithPoolWithValidator function", "debug")
	fileName = self.tempDir + str(startWorkTime) + "_validator-query.boc"
	fiftScript = self.contractsDir + "nominator-pool/func/validator-elect-signed.fif"
	args = [fiftScript, pool.addrB64, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName, stake]
	result = self.fift.Run(args)
	pubkey = parse(result, "validator public key ", '\n')
	fileName = parse(result, "Saved to file ", '\n')
	return pubkey, fileName
#end define

def PoolProcessRecoverStake(self):
	self.local.add_log("start PoolProcessRecoverStake function", "debug")
	resultFilePath = self.tempDir + "recover-query.boc"
	fiftScript = self.contractsDir + "nominator-pool/func/recover-stake.fif"
	args = [fiftScript, resultFilePath]
	result = self.fift.Run(args)
	resultFilePath = parse(result, "Saved to file ", '\n')
	return resultFilePath
#end define

def GetControllerData(self, addrB64):
	self.local.add_log("start GetControllerData function", "debug")
	account = self.GetAccount(addrB64)
	if account.status != "active":
		return
	cmd = "runmethodfull {addrB64} all_data".format(addrB64=addrB64)
	result = self.liteClient.Run(cmd)
	data = self.Result2List(result)
	controllerData = dict()
	wallet_data = dict()
	wallet_data["seqno"] = data[0][0]
	wallet_data["subwallet_id"] = data[0][1]
	wallet_data["controller_pubkey"] = data[0][2]
	wallet_data["last_used"] = data[0][3]
	static_data = dict()
	static_data["nominator_address"] = data[1][0]
	static_data["controller_reward_share"] = data[1][1]
	static_data["controller_cover_ability"] = data[1][2]
	balances = dict()
	balances["nominator_total_balance"] = data[2][0]
	balances["nominator_elector_balance"] = data[2][1]
	balances["nominator_withdrawal_request"] = data[2][2]
	balances["total_stake_on_elector"] = data[2][3]
	controllerData["wallet_data"] = wallet_data
	controllerData["static_data"] = static_data
	controllerData["balances"] = balances
	controllerData["last_sent_stake_time"] = data[3]
	return controllerData
#end define

def get_single_local_pool(self, pool_name):
	self.local.add_log("start get_single_local_pool function", "debug")
	if pool_name is None:
		return None
	filePath = self.poolsDir + pool_name

	# Create pool object
	pool = Pool(pool_name, filePath)
	if os.path.isfile(pool.addrFilePath) == False:
		raise Exception(f"get_single_local_pool error: Address file not found: {pool.addrFilePath}")
	#end if

	self.AddrFile2Object(pool)
	return pool
#end define

def GetPoolsNameList(self):
	self.local.add_log("start GetPoolsNameList function", "debug")
	poolsNameList = list()
	for fileName in os.listdir(self.poolsDir):
		if fileName.endswith(".addr"):
			fileName = fileName[:fileName.rfind('.')]
			poolsNameList.append(fileName)
	poolsNameList.sort()
	return poolsNameList
#end define

def get_single_pools(self):
	self.local.add_log("start get_single_pools function", "debug")
	pools = list()
	poolsNameList = self.GetPoolsNameList()
	for pool_name in poolsNameList:
		pool = self.get_single_local_pool(pool_name)
		pools.append(pool)
	return pools
#end define

def GetPool(self, mode):
	pools = self.get_single_pools()
	for pool in pools:
		if mode == "stake" and self.IsPoolReadyToStake(pool.addrB64):
			return pool
		if mode == "vote" and self.IsPoolReadyToVote(pool.addrB64):
			return pool
	raise Exception("Validator pool not found or not ready")
#end define

def GetPoolLastSentStakeTime(self, addrB64):
	poolData = self.GetPoolData(addrB64)
	return poolData["stakeAt"]
#end define

def IsPoolReadyToStake(self, addrB64):
	now = get_timestamp()
	config15 = self.GetConfig15()
	lastSentStakeTime = self.GetPoolLastSentStakeTime(addrB64)
	stakeFreezeDelay = config15["validatorsElectedFor"] + config15["stakeHeldFor"]
	result = lastSentStakeTime + stakeFreezeDelay < now
	print(f"{addrB64}: {result}. {lastSentStakeTime}, {stakeFreezeDelay}, {now}")
	return result
#end define

def IsPoolReadyToVote(self, addrB64):
	vwl = self.GetValidatorsWalletsList()
	result = addrB64 in vwl
	return result
#end define

def GetPoolData(self, addrB64):
	self.local.add_log("start GetPoolData function", "debug")
	cmd = f"runmethodfull {addrB64} get_pool_data"
	result = self.liteClient.Run(cmd)
	data = self.Result2List(result)
	if data is None:
		return
	poolConfig = dict()
	poolConfig["validatorAddress"] = data[4]
	poolConfig["validatorRewardShare"] = data[5]
	poolConfig["validatorRewardSharePercent"] = data[5] / 100
	poolConfig["maxNominatorsCount"] = data[6]
	poolConfig["minValidatorStake"] = ng2g(data[7])
	poolConfig["minNominatorStake"] = ng2g(data[8])
	poolData = dict()
	poolData["state"] = data[0]
	poolData["nominatorsCount"] = data[1]
	poolData["stakeAmountSent"] = ng2g(data[2])
	poolData["validatorAmount"] = ng2g(data[3])
	poolData["config"] = poolConfig
	poolData["nominators"] = data[9]
	poolData["withdrawRequests"] = data[10]
	poolData["stakeAt"] = data[11]
	poolData["savedValidatorSetHash"] = data[12]
	poolData["validatorSetChangesCount"] = data[13]
	poolData["validatorSetChangeTime"] = data[14]
	poolData["stakeHeldFor"] = data[15]
	return poolData
#end define
