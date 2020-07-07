#!/usr/bin/env python3
# -*- coding: utf_8 -*-l

import crc16
import struct
import re
import requests
from mypylib.mypylib import *

local = MyPyClass(__file__)


class LiteClient:
	def __init__(self):
		self.appPath = None
		self.configPath = None
	#end define

	def Run(self, cmd):
		args = [self.appPath, "-C", self.configPath, "-v", "0", "--cmd", cmd]
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			raise Exception("LiteClient error: {err}".format(err=err))
		### debug on ###
		filePath = local.buffer.get("myTempDir") + "LiteClient.log"
		file = open(filePath, 'w')
		file.write(output)
		file.write(err)
		file.close()
		### debug off ###
		return output
	#end define
#end class

class ValidatorConsole:
	def __init__(self):
		self.appPath = None
		self.privKeyPath = None
		self.pubKeyPath = None
		self.addr = None
	#end define

	def Run(self, cmd):
		args = [self.appPath, "-k", self.privKeyPath, "-p", self.pubKeyPath, "-a", self.addr, "-v", "0", "--cmd", cmd]
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			raise Exception("ValidatorConsole error: {err}".format(err=err))
		### debug on ###
		filePath = local.buffer.get("myTempDir") + "ValidatorConsole.log"
		file = open(filePath, 'w')
		file.write(output)
		file.write(err)
		file.close()
		### debug off ###
		return output
	#end define
#end class

class Fift:
	def __init__(self):
		self.appPath = None
		self.libsPath = None
		self.smartcontsPath = None
	#end define

	def Run(self, args):
		for i in range(len(args)):
			args[i] = str(args[i])
		includePath = self.libsPath + ':' + self.smartcontsPath
		args = [self.appPath, "-I", includePath, "-s"] + args
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			raise Exception("Fift error: {err}".format(err=err))
		### debug on ###
		filePath = local.buffer.get("myTempDir") + "Fift.log"
		file = open(filePath, 'w')
		file.write(output)
		file.write(err)
		file.close()
		### debug off ###
		return output
	#end define
#end class

class Wallet:
	def __init__(self):
		self.name = None
		self.path = None
		self.addrFilePath = None
		self.privFilePath = None
		self.bocFilePath = None
		self.fullAddr = None
		self.workchain = None
		self.addr_hex = None
		self.addr = None
		self.addr_init = None
	#end define

	def Refresh(self):
		buff = self.fullAddr.split(':')
		self.workchain = buff[0]
		self.addr_hex = buff[1]
		self.addrFilePath = self.path + ".addr"
		self.privFilePath = self.path + ".pk"
		self.bocFilePath = self.path + "-query.boc"
	#end define

	def Delete(self):
		os.remove(self.addrFilePath)
		os.remove(self.privFilePath)
	#end define
#end class

class Account:
	def __init__(self):
		self.addr = None
		self.status = "empty"
		self.balance = 0
		self.lt = None
		self.hash = None
	#end define
#end class

class Domain(dict):
	def __init__(self):
		self["name"] = None
		self["adnlAddr"] = None
		self["walletName"] = None
	#end define
#end class

class MyTonCore():
	def __init__(self):
		self.walletsDir = None
		self.dbFile = None
		self.adnlAddr = None
		self.tempDir = None
		self.validatorWalletName = None
		self.nodeName = None

		self.liteClient = LiteClient()
		self.validatorConsole = ValidatorConsole()
		self.fift = Fift()

		self.Refresh()
		self.Init()
	#end define

	def Init(self):
		# Check all directorys
		os.makedirs(self.walletsDir, exist_ok=True)
	#end define

	def Refresh(self):
		if self.dbFile:
			local.dbLoad(self.dbFile)
		else:
			local.dbLoad()

		if not self.walletsDir:
			self.walletsDir = dir(local.buffer.get("myWorkDir") + "wallets")

		self.tempDir = local.buffer.get("myTempDir")

		self.adnlAddr = local.db.get("adnlAddr")
		self.validatorWalletName = local.db.get("validatorWalletName")
		self.nodeName = local.db.get("nodeName")
		if self.nodeName is None:
			self.nodeName=""
		else:
			self.nodeName = self.nodeName + "_"

		liteClient = local.db.get("liteClient")
		if liteClient is not None:
			self.liteClient.appPath = liteClient["appPath"]
			self.liteClient.configPath = liteClient["configPath"]

		validatorConsole = local.db.get("validatorConsole")
		if validatorConsole is not None:
			self.validatorConsole.appPath = validatorConsole["appPath"]
			self.validatorConsole.privKeyPath = validatorConsole["privKeyPath"]
			self.validatorConsole.pubKeyPath = validatorConsole["pubKeyPath"]
			self.validatorConsole.addr = validatorConsole["addr"]

		fift = local.db.get("fift")
		if fift is not None:
			self.fift.appPath = fift["appPath"]
			self.fift.libsPath = fift["libsPath"]
			self.fift.smartcontsPath = fift["smartcontsPath"]
	#end define

	def GetVarFromWorkerOutput(self, text, search):
		if ':' not in search:
			search += ':'
		if search is None or text is None:
			return None
		if search not in text:
			return None
		start = text.find(search) + len(search)
		count = 0
		bcount = 0
		textLen = len(text)
		end = textLen
		for i in range(start, textLen):
			letter = text[i]
			if letter == '(':
				count += 1
				bcount += 1
			elif letter == ')':
				count -= 1
			if letter == ')' and count < 1:
				end = i + 1
				break
			elif letter == '\n' and count < 1:
				end = i
				break
		result = text[start:end]
		if count != 0 and bcount == 0:
			result = result.replace(')', '')
		return result
	#end define

	def GetSeqno(self, wallet):
		local.AddLog("start GetSeqno function", "debug")
		cmd = "runmethod {addr} seqno".format(addr=wallet.addr)
		result = self.liteClient.Run(cmd)
		if "cannot run any methods" in result:
			return None
		if "result" not in result:
			return 0
		seqno = self.GetVarFromWorkerOutput(result, "result")
		seqno = seqno.replace(' ', '')
		seqno = Pars(seqno, '[', ']')
		seqno = int(seqno)
		return seqno
	#end define

	def GetAccount(self, addr):
		local.AddLog("start GetAccount function", "debug")
		account = Account()
		cmd = "getaccount {addr}".format(addr=addr)
		result = self.liteClient.Run(cmd)
		storage = self.GetVarFromWorkerOutput(result, "storage")
		if storage is None:
			return account
		balance = self.GetVarFromWorkerOutput(storage, "balance")
		grams = self.GetVarFromWorkerOutput(balance, "grams")
		value = self.GetVarFromWorkerOutput(grams, "value")
		state = self.GetVarFromWorkerOutput(storage, "state")
		status = Pars(state, "account_", '\n')
		account.addr = addr
		account.status = status
		account.balance = ng2g(value)
		account.lt = Pars(result, "lt = ", ' ')
		account.hash = Pars(result, "hash = ", '\n')
		return account
	#end define
	
	def GetAccountHistory(self, account, limit):
		local.AddLog("start GetAccountHistory function", "debug")
		lt=account.lt
		hash=account.hash
		history = list()
		ready = 0
		while True:
			cmd = "lasttrans {addr} {lt} {hash}".format(addr=account.addr, lt=lt, hash=hash)
			result = self.liteClient.Run(cmd)
			buff =  Pars(result, "previous transaction has", '\n')
			lt = Pars(buff, "lt ", ' ')
			hash = Pars(buff, "hash ", ' ')
			arr = result.split("transaction #0")
			for item in arr:
				ready += 1
				if "from block" not in item:
					continue
				if "VALUE:" not in item:
					continue
				time = Pars(item, "time=", ' ')
				time = int(time)
				outmsg = Pars(item, "outmsg_cnt=", '\n')
				outmsg = int(outmsg)
				if outmsg == 1:
					item = Pars(item, "outbound message")
				buff = dict()
				buff["time"] = time
				buff["outmsg"] = outmsg
				buff["from"] = Pars(item, "FROM: ", ' ')
				buff["to"] = Pars(item, "TO: ", ' ')
				value = Pars(item, "VALUE:", '\n')
				if '+' in value: # wtf?
					value = value[:value.find('+')] # wtf? `-1:0000000000000000000000000000000000000000000000000000000000000000 1583059577 1200000000+extra`
				buff["value"] = ng2g(value)
				history.append(buff)
			if lt is None or ready >= limit:
				return history
	#end define
	
	def GetDomainAddr(self, domainName):
		cmd = "dnsresolve {domainName} -1".format(domainName=domainName)
		result = self.liteClient.Run(cmd)
		if "not found" in result:
			raise Exception("GetDomainAddr error: domain \"{domainName}\" not found".format(domainName=domainName))
		resolver = Pars(result, "next resolver", '\n')
		buff = resolver.replace(' ', '')
		buffList = buff.split('=')
		fullHexAddr = buffList[0]
		addr = buffList[1]
		return addr
	#end define
	
	def GetDomainEndTime(self, domainName):
		local.AddLog("start GetDomainEndTime function", "debug")
		buff = domainName.split('.')
		subdomain = buff.pop(0)
		dnsDomain = ".".join(buff)
		dnsAddr = self.GetDomainAddr(dnsDomain)
		
		cmd = "runmethod {addr} getexpiration \"{subdomain}\"".format(addr=dnsAddr, subdomain=subdomain)
		result = self.liteClient.Run(cmd)
		result = Pars(result, "result:", '\n')
		result = Pars(result, "[", "]")
		result = result.replace(' ', '')
		result = int(result)
		return result
	#end define
	
	def GetDomainAdnlAddr(self, domainName):
		local.AddLog("start GetDomainAdnlAddr function", "debug")
		cmd = "dnsresolve {domainName} 1".format(domainName=domainName)
		result = self.liteClient.Run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "adnl address" in line:
				adnlAddr = Pars(line, "=", "\n")
				adnlAddr = adnlAddr.replace(' ', '')
				adnlAddr = adnlAddr.lower()
				return adnlAddr
	#end define

	def GetLocalWallet(self, walletName):
		local.AddLog("start GetLocalWallet function", "debug")
		try:
			walletPath = self.walletsDir + walletName
			wallet = self.GetWalletFromFile(walletPath)
		except Exception as err:
			wallet = None
		return wallet
	#end define

	def GetWalletFromFile(self, filePath):
		local.AddLog("start GetWalletFromFile function", "debug")
		# Check input args
		if (".addr" in filePath):
			filePath = filePath.replace(".addr", '')
		if (".pk" in filePath):
			filePath = filePath.replace(".pk", '')
		if os.path.isfile(filePath + ".pk") == False:
			raise Exception("GetWalletFromFile error: Private key not found: " + filePath)
			return None

		# Create wallet
		wallet = Wallet()
		wallet.path = filePath
		if '/' in filePath:
			wallet.name = filePath[filePath.rfind('/')+1:]
		else:
			wallet.name = filePath
		#args = ["show-addr.fif", filePath]
		#result = self.fift.Run(args)
		#wallet.fullAddr = Pars(result, "Source wallet address = ", '\n').replace(' ', '')
		#buff = self.GetVarFromWorkerOutput(result, "Bounceable address (for later access)")
		#wallet.addr = buff.replace(' ', '')
		#buff = self.GetVarFromWorkerOutput(result, "Non-bounceable address (for init only)")
		#wallet.addr_init = buff.replace(' ', '')
		
		addrFilePath = filePath + ".addr"
		file = open(addrFilePath, "rb")
		data = file.read()
		addr_hex = data[:32].hex()
		workchain = struct.unpack("i", data[32:])[0]
		wallet.fullAddr = str(workchain) + ":" + addr_hex
		wallet.addr = self.HexAddr2Base64Addr(wallet.fullAddr)
		wallet.addr_init = self.HexAddr2Base64Addr(wallet.fullAddr, False)
		wallet.Refresh()
		return wallet
	#end define
	
	def GetFullConfigAddr(self):
		local.AddLog("start GetFullConfigAddr function", "debug")
		fullConfigAddr = local.buffer.get("fullConfigAddr")
		if fullConfigAddr is None:
			result = self.liteClient.Run("getconfig 0")
			configAddr_hex = self.GetVarFromWorkerOutput(result, "config_addr:x")
			fullConfigAddr = "-1:{configAddr_hex}".format(configAddr_hex=configAddr_hex)
			local.buffer["fullConfigAddr"] = fullConfigAddr
		return fullConfigAddr
	#end define

	def GetFullElectorAddr(self):
		local.AddLog("start GetFullElectorAddr function", "debug")
		fullElectorAddr = local.buffer.get("fullElectorAddr")
		if fullElectorAddr is None:
			result = self.liteClient.Run("getconfig 1")
			electorAddr_hex = self.GetVarFromWorkerOutput(result, "elector_addr:x")
			fullElectorAddr = "-1:{electorAddr_hex}".format(electorAddr_hex=electorAddr_hex)
			local.buffer["fullElectorAddr"] = fullElectorAddr
		return fullElectorAddr
	#end define
	
	def GetFullMinterAddr(self):
		local.AddLog("start GetFullMinterAddr function", "debug")
		fullMinterAddr = local.buffer.get("fullMinterAddr")
		if fullMinterAddr is None:
			result = self.liteClient.Run("getconfig 2")
			minterAddr_hex = self.GetVarFromWorkerOutput(result, "minter_addr:x")
			fullMinterAddr = "-1:{minterAddr_hex}".format(minterAddr_hex=minterAddr_hex)
			local.buffer["fullMinterAddr"] = fullMinterAddr
		return fullMinterAddr
	#end define
	
	def GetFullDnsRootAddr(self):
		local.AddLog("start GetFullDnsRootAddr function", "debug")
		fullDnsRootAddr = local.buffer.get("fullDnsRootAddr")
		if fullDnsRootAddr is None:
			result = self.liteClient.Run("getconfig 4")
			dnsRootAddr_hex = self.GetVarFromWorkerOutput(result, "dns_root_addr:x")
			fullDnsRootAddr = "-1:{dnsRootAddr_hex}".format(dnsRootAddr_hex=dnsRootAddr_hex)
			local.buffer["fullDnsRootAddr"] = fullDnsRootAddr
		return fullDnsRootAddr
	#end define

	def GetActiveElectionId(self, fullElectorAddr):
		local.AddLog("start GetActiveElectionId function", "debug")
		cmd = "runmethod {fullElectorAddr} active_election_id".format(fullElectorAddr=fullElectorAddr)
		result = self.liteClient.Run(cmd)
		active_election_id = self.GetVarFromWorkerOutput(result, "result")
		active_election_id = active_election_id.replace(' ', '')
		active_election_id = Pars(active_election_id, '[', ']')
		active_election_id = int(active_election_id)
		return active_election_id
	#end define

	def GetValidatorsElectedFor(self):
		local.AddLog("start GetValidatorsElectedFor function", "debug")
		config15 = self.GetConfig15()
		return config15["validatorsElectedFor"]
	#end define

	def GetMinStake(self):
		local.AddLog("start GetMinStake function", "debug")
		config17 = self.GetConfig17()
		return config17["minStake"]
	#end define

	def GetRootWorkchainEnabledTime(self):
		local.AddLog("start GetRootWorkchainEnabledTime function", "debug")
		config12 = self.GetConfig12()
		result = config12["workchains"]["root"]["enabledSince"]
		return result
	#end define

	def GetTotalValidators(self):
		local.AddLog("start GetTotalValidators function", "debug")
		config34 = self.GetConfig34()
		result = config34["totalValidators"]
		return result
	#end define

	def GetShardsNumber(self):
		local.AddLog("start GetShardsNumber function", "debug")
		result = self.liteClient.Run("allshards")
		shardsNumber = result.count("shard #")
		return shardsNumber
	#end define

	def GetValidatorStatus(self):
		local.AddLog("start GetValidatorStatus function", "debug")
		validatorStatus = dict()
		try:
			validatorStatus["isWorking"] = True
			result = self.validatorConsole.Run("getstats")
			validatorStatus["unixtime"] = int(Pars(result, "unixtime", '\n'))
			validatorStatus["masterchainblocktime"] = int(Pars(result, "masterchainblocktime", '\n'))
			validatorStatus["stateserializermasterchainseqno"] = int(Pars(result, "stateserializermasterchainseqno", '\n'))
			validatorStatus["shardclientmasterchainseqno"] = int(Pars(result, "shardclientmasterchainseqno", '\n'))
			buff = Pars(result, "masterchainblock", '\n')
			validatorStatus["masterchainblock"] = self.GVS_GetItemFromBuff(buff)
			buff = Pars(result, "gcmasterchainblock", '\n')
			validatorStatus["gcmasterchainblock"] = self.GVS_GetItemFromBuff(buff)
			buff = Pars(result, "keymasterchainblock", '\n')
			validatorStatus["keymasterchainblock"] = self.GVS_GetItemFromBuff(buff)
			buff = Pars(result, "rotatemasterchainblock", '\n')
			validatorStatus["rotatemasterchainblock"] = self.GVS_GetItemFromBuff(buff)
		except:
			validatorStatus["isWorking"] = False
		return validatorStatus
	#end define
	
	def GVS_GetItemFromBuff(self, buff):
		buffList = buff.split(':')
		buff2 = buffList[0]
		buff2 = buff2.replace(' ', '')
		buff2 = buff2.replace('(', '')
		buff2 = buff2.replace(')', '')
		buffList2 = buff2.split(',')
		item = buffList2[2]
		item = int(item)
		return item
	#end define

	def GetConfig12(self):
		local.AddLog("start GetConfig12 function", "debug")
		config12 = dict()
		config12["workchains"] = dict()
		config12["workchains"]["root"] = dict()
		result = self.liteClient.Run("getconfig 12")
		workchains = self.GetVarFromWorkerOutput(result, "workchains")
		workchain_root = self.GetVarFromWorkerOutput(workchains, "root")
		config12["workchains"]["root"]["enabledSince"] = int(Pars(workchain_root, "enabled_since:", ' '))
		return config12
	#end define

	def GetConfig15(self):
		local.AddLog("start GetConfig15 function", "debug")
		config15 = dict()
		result = self.liteClient.Run("getconfig 15")
		config15["validatorsElectedFor"] = int(Pars(result, "validators_elected_for:", ' '))
		config15["electionsStartBefore"] = int(Pars(result, "elections_start_before:", ' '))
		config15["electionsEndBefore"] = int(Pars(result, "elections_end_before:", ' '))
		config15["stakeHeldFor"] = int(Pars(result, "stake_held_for:", ')'))
		return config15
	#end define

	def GetConfig17(self):
		local.AddLog("start GetConfig17 function", "debug")
		config17 = dict()
		result = self.liteClient.Run("getconfig 17")
		minStake = self.GetVarFromWorkerOutput(result, "min_stake")
		minStake = self.GetVarFromWorkerOutput(minStake, "value")
		config17["minStake"] = ng2g(minStake)
		maxStake = self.GetVarFromWorkerOutput(result, "max_stake")
		maxStake = self.GetVarFromWorkerOutput(maxStake, "value")
		config17["maxStake"] = ng2g(maxStake)
		return config17
	#end define

	def GetConfig34(self):
		local.AddLog("start GetConfig34 function", "debug")
		config34 = dict()
		result = self.liteClient.Run("getconfig 34")
		config34["totalValidators"] = int(Pars(result, "total:", ' '))
		config34["startWorkTime"] = int(Pars(result, "utime_since:", ' '))
		config34["endWorkTime"] = int(Pars(result, "utime_until:", ' '))
		lines = result.split('\n')
		validators = list()
		for line in lines:
			if "public_key:" in line:
				validatorAdnlAddr = Pars(line, "adnl_addr:x", ')')
				validatorPubkey = Pars(line, "pubkey:x", ')')
				if config34["totalValidators"] > 1:
					validatorWeight = int(Pars(line, "weight:", ' '))
				else:
					validatorWeight = int(Pars(line, "weight:", ')'))
				buff = dict()
				buff["adnlAddr"] = validatorAdnlAddr
				buff["pubkey"] = validatorPubkey
				buff["weight"] = validatorWeight
				validators.append(buff)
		config34["validators"] = validators
		return config34
	#end define
	
	def GetConfig36(self):
		local.AddLog("start GetConfig36 function", "debug")
		config36 = dict()
		result = self.liteClient.Run("getconfig 36")
		try:
			config36["totalValidators"] = int(Pars(result, "total:", ' '))
			config36["startWorkTime"] = int(Pars(result, "utime_since:", ' '))
			config36["endWorkTime"] = int(Pars(result, "utime_until:", ' '))
			lines = result.split('\n')
			validators = list()
			for line in lines:
				if "public_key:" in line:
					validatorAdnlAddr = Pars(line, "adnl_addr:x", ')')
					validatorPubkey = Pars(line, "pubkey:x", ')')
					validatorWeight = Pars(line, "weight:", ' ')
					buff = dict()
					buff["adnlAddr"] = validatorAdnlAddr
					buff["pubkey"] = validatorPubkey
					buff["weight"] = validatorWeight
					validators.append(buff)
			config36["validators"] = validators
		except:
			pass
		return config36
	#end define

	def CreatNewKey(self):
		local.AddLog("start CreatNewKey function", "debug")
		result = self.validatorConsole.Run("newkey")
		key = Pars(result, "created new key ", '\n')
		return key
	#end define

	def GetPubKeyBase64(self, key):
		local.AddLog("start GetPubKeyBase64 function", "debug")
		result = self.validatorConsole.Run("exportpub " + key)
		validatorPubkey_b64 = Pars(result, "got public key: ", '\n')
		return validatorPubkey_b64
	#end define

	def AddKeyToValidator(self, key, startWorkTime, endWorkTime):
		local.AddLog("start AddKeyToValidator function", "debug")
		output = False
		cmd = "addpermkey {key} {startWorkTime} {endWorkTime}".format(key=key, startWorkTime=startWorkTime, endWorkTime=endWorkTime)
		result = self.validatorConsole.Run(cmd)
		if ("success" in result):
			output = True
		return output
	#end define

	def AddKeyToTemp(self, key, endWorkTime):
		local.AddLog("start AddKeyToTemp function", "debug")
		output = False
		result = self.validatorConsole.Run("addtempkey {key} {key} {endWorkTime}".format(key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output
	#end define

	def AddAdnlAddrToValidator(self, adnlAddr):
		local.AddLog("start AddAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.Run("addadnl {adnlAddr} 0".format(adnlAddr=adnlAddr))
		if ("success" in result):
			output = True
		return output
	#end define

	def GetAdnlAddr(self):
		local.AddLog("start GetAdnlAddr function", "debug")
		adnlAddr = self.adnlAddr
		if adnlAddr is None:
			# Create ADNL address
			adnlAddr = self.CreatNewKey()
			self.AddAdnlAddrToValidator(adnlAddr)
			self.adnlAddr = adnlAddr
		return adnlAddr
	#end define

	def AttachAdnlAddrToValidator(self, adnlAddr, key, endWorkTime):
		local.AddLog("start AttachAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.Run("addvalidatoraddr {key} {adnlAddr} {endWorkTime}".format(adnlAddr=adnlAddr, key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output
	#end define
	
	def CreateConfigProposalRequest(self, offerHash, validatorIndex):
		local.AddLog("start CreateConfigProposalRequest function", "debug")
		fileName = self.tempDir + self.nodeName + "_validator-to-sign.req"
		args = ["config-proposal-vote-req.fif", "-i", validatorIndex, offerHash]
		result = self.fift.Run(args)
		fileName = Pars(result, "Saved to file ", '\n')
		resultList = result.split('\n')
		i = 0
		start_index = 0
		for item in resultList:
			if "Creating a request to vote for configuration proposal" in item:
				start_index = i
			i += 1
		var1 = resultList[start_index + 1]
		var2 = resultList[start_index + 2] # var2 not using
		return var1
	#end define

	def CreateElectionRequest(self, wallet, startWorkTime, adnlAddr, maxFactor):
		local.AddLog("start CreateElectionRequest function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-to-sign.bin"
		args = ["validator-elect-req.fif", wallet.addr, startWorkTime, maxFactor, adnlAddr, fileName]
		result = self.fift.Run(args)
		fileName = Pars(result, "Saved to file ", '\n')
		resultList = result.split('\n')
		i = 0
		start_index = 0
		for item in resultList:
			if "Creating a request to participate in validator elections" in item:
				start_index = i
			i += 1
		var1 = resultList[start_index + 1]
		var2 = resultList[start_index + 2] # var2 not using
		return var1
	#end define

	def GetValidatorSignature(self, validatorKey, var1):
		local.AddLog("start GetValidatorSignature function", "debug")
		cmd = "sign {validatorKey} {var1}".format(validatorKey=validatorKey, var1=var1)
		result = self.validatorConsole.Run(cmd)
		validatorSignature = Pars(result, "got signature ", '\n')
		return validatorSignature
	#end define

	def SignElectionRequestWithValidator(self, wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor):
		local.AddLog("start SignElectionRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-query.boc"
		args = ["validator-elect-signed.fif", wallet.addr, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		validatorPubkey = Pars(result, "validator public key ", '\n')
		fileName = Pars(result, "Saved to file ", '\n')
		return validatorPubkey, fileName
	#end define

	def SignFileWithWallet(self, wallet, filePath, addr, gram):
		local.AddLog("start SignFileWithWallet function", "debug")
		seqno = self.GetSeqno(wallet)
		resultFilePath = self.tempDir + self.nodeName + wallet.name + "_wallet-query"
		args = ["wallet.fif", wallet.path, addr, seqno, gram, "-B", filePath, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = Pars(result, "Saved to file ", ")")
		return resultFilePath
	#end define

	def SendFile(self, filePath, wallet):
		local.AddLog("start SendFile function", "debug")
		oldSeqno = self.GetSeqno(wallet)
		result = self.liteClient.Run("sendfile " + filePath)
		self.WaitTransaction(wallet, oldSeqno)
		os.remove(filePath)
	#end define
	
	def WaitTransaction(self, wallet, oldSeqno):
		local.AddLog("start WaitTransaction function", "debug")
		for i in range(10): # wait 30 sec
			time.sleep(3)
			seqno = self.GetSeqno(wallet)
			if seqno != oldSeqno:
				return
		raise Exception("WaitTransaction error: time out")
	#end define

	def GetReturnedStake(self, fullElectorAddr, wallet):
		local.AddLog("start GetReturnedStake function", "debug")
		cmd = "runmethod {fullElectorAddr} compute_returned_stake 0x{addr_hex}".format(fullElectorAddr=fullElectorAddr, addr_hex=wallet.addr_hex)
		result = self.liteClient.Run(cmd)
		returnedStake = self.GetVarFromWorkerOutput(result, "result")
		returnedStake = returnedStake.replace(' ', '')
		returnedStake = Pars(returnedStake, '[', ']')
		returnedStake = ng2g(returnedStake)
		return returnedStake
	#end define

	def RecoverStake(self):
		local.AddLog("start RecoverStake function", "debug")
		resultFilePath = self.tempDir + self.nodeName + "recover-query"
		args = ["recover-stake.fif", resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = Pars(result, "Saved to file ", '\n')
		return resultFilePath
	#end define

	def ElectionEntry(self,args=None):
		#self.TestElectionEntry()
	
		local.AddLog("start ElectionEntry function", "debug")
		walletName = self.validatorWalletName
		wallet = self.GetLocalWallet(walletName)

		# Get startWorkTime and endWorkTime
		fullElectorAddr = self.GetFullElectorAddr()
		startWorkTime = self.GetActiveElectionId(fullElectorAddr)

		# Check if elections started
		if (startWorkTime == 0):
			local.AddLog("Elections have not yet begun", "debug")
			return

		# Check if election entry is completed
		vconfig = self.GetConfigFromValidator()
		validators = vconfig.get("validators")
		for item in validators:
			if item.get("election_date") == startWorkTime:
				local.AddLog("Elections entry already completed", "debug")
				return

		# Get account balance and minimum stake
		account = self.GetAccount(wallet.addr)
		minStake = self.GetMinStake()

		# Check if we have enough grams
		if minStake > account.balance:
			local.AddLog("You don't have enough grams. Minimum stake: " + str(minStake), "debug")
			return

		# Default maxFactor multiplier
		rateMultiplier = 1

		# Check if optional arguments have been passed to us
		if args:
			desiredStake = args[0]
			m = re.match(r"(\d+\.?\d?)\%", desiredStake)
			if m:
				# Stake was in percent
				stake = round((account.balance / 100) * float(m.group(1)))
			elif desiredStake.isnumeric():
				# Stake was a number
				stake = int(desiredStake)
			else:
				local.AddLog("Specified stake must be a percentage or whole number", "error")
				return

			# Limit stake to maximum available amount minus 10 (for transaction fees)
			if stake > account.balance - 10:
				stake = account.balance - 10

			if minStake > stake:
				local.AddLog('Stake is smaller then Minimum stake: ' + str(minStake), "error")
				return

			# Get rateMultiplier
			if len(args) > 1:
				rateMultiplier = float(args[1])
		else:
			# Calculate stake
			if len(validators) == 0:
				stake = int(account.balance*0.99/2)
			if len(validators) > 0 or (stake is not None and stake < minStake):
				stake = int(account.balance*0.99)

		# Calculate endWorkTime
		validatorsElectedFor = self.GetValidatorsElectedFor()
		endWorkTime = startWorkTime + validatorsElectedFor + 300 # 300 sec - margin of seconds

		# Create keys
		validatorKey = self.CreatNewKey()
		validatorPubkey_b64  = self.GetPubKeyBase64(validatorKey)

		# Add key to validator
		self.AddKeyToValidator(validatorKey, startWorkTime, endWorkTime)
		self.AddKeyToTemp(validatorKey, endWorkTime)

		# Get ADNL address
		adnlAddr = self.GetAdnlAddr()
		self.AttachAdnlAddrToValidator(adnlAddr, validatorKey, endWorkTime)

		# Create fift's
		maxFactor = round((stake / minStake) * rateMultiplier, 1)
		var1 = self.CreateElectionRequest(wallet, startWorkTime, adnlAddr, maxFactor)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		validatorPubkey, resultFilePath = self.SignElectionRequestWithValidator(wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor)

		# Send boc file to TON
		resultFilePath = self.SignFileWithWallet(wallet, resultFilePath, fullElectorAddr, stake)
		self.SendFile(resultFilePath, wallet)

		# Save vars to json file
		self.SaveElectionVarsToJsonFile(wallet=wallet, account=account, stake=stake, maxFactor=maxFactor, fullElectorAddr=fullElectorAddr, startWorkTime=startWorkTime, validatorsElectedFor=validatorsElectedFor, endWorkTime=endWorkTime, validatorKey=validatorKey, validatorPubkey_b64=validatorPubkey_b64, adnlAddr=adnlAddr, var1=var1, validatorSignature=validatorSignature, validatorPubkey=validatorPubkey)

		local.AddLog("ElectionEntry completed. Start work time: " + str(startWorkTime))
	#end define

	def ReturnStake(self):
		local.AddLog("start ReturnStake function", "debug")
		#self.TestReturnStake()
		fullElectorAddr = self.GetFullElectorAddr()
		walletName = self.validatorWalletName
		wallet = self.GetLocalWallet(walletName)
		returnedStake = self.GetReturnedStake(fullElectorAddr, wallet)
		if returnedStake == 0:
			local.AddLog("You have nothing on the return stake", "debug")
			return
		resultFilePath = self.RecoverStake()
		resultFilePath = self.SignFileWithWallet(wallet, resultFilePath, fullElectorAddr, 1)
		self.SendFile(resultFilePath, wallet)
		local.AddLog("ReturnStake completed")
	#end define

	def SaveElectionVarsToJsonFile(self, **kwargs):
		local.AddLog("start SaveElectionVarsToJsonFile function", "debug")
		fileName = self.tempDir + self.nodeName + str(kwargs.get("startWorkTime")) + "_ElectionEntry.json"
		wallet = kwargs.get("wallet")
		account = kwargs.get("account")
		arr = {"wallet":wallet.__dict__, "account":account.__dict__}
		del kwargs["wallet"]
		del kwargs["account"]
		arr.update(kwargs)
		string = json.dumps(arr, indent=4)
		file = open(fileName, 'w')
		file.write(string)
		file.close()
	#ned define

	def CreateWallet(self, walletName, workchain=0):
		local.AddLog("start CreateWallet function", "debug")
		walletPath = self.walletsDir + walletName
		# if os.path.isfile(walletPath + ".pk"):
		# 	local.AddLog("CreateWallet error: Wallet already exists: " + walletName, "warning")
		# 	return
		args = ["new-wallet.fif", workchain, walletPath]
		result = self.fift.Run(args)
		if "Creating new wallet" not in result:
			raise Exception("CreateWallet error")
		wallet = self.GetLocalWallet(walletName)
		account = self.GetAccount(wallet.addr)
		return wallet
	#end define

	def GetWalletsNameList(self):
		local.AddLog("start GetWalletsNameList function", "debug")
		walletsNameList = list()
		for fileName in os.listdir(self.walletsDir):
			if fileName.endswith(".addr"):
				fileName = fileName[:fileName.rfind('.')]
				walletsNameList.append(fileName)
		walletsNameList.sort()
		return walletsNameList
	#end define

	def GetWallets(self):
		local.AddLog("start GetWallets function", "debug")
		wallets = list()
		walletsNameList = self.GetWalletsNameList()
		for walletName in walletsNameList:
			wallet = self.GetLocalWallet(walletName)
			wallets.append(wallet)
		return wallets
	#end define

	def GenerateWalletName(self):
		local.AddLog("start GenerateWalletName function", "debug")
		index = 1
		index_str = str(index).rjust(3, '0')
		walletPrefix = "wallet_"
		indexList = list()
		walletName = walletPrefix + index_str
		walletsNameList = self.GetWalletsNameList()
		if walletName in walletsNameList:
			for item in walletsNameList:
				if item.startswith(walletPrefix):
					index = item[item.rfind('_')+1:]
					index = int(index)
					indexList.append(index)
			index = max(indexList) + 1
			index_str = str(index).rjust(3, '0')
			walletName = walletPrefix + index_str
		return walletName
	#end define

	def WalletsCheck(self):
		local.AddLog("start WalletsCheck function", "debug")
		wallets = self.GetWallets()
		for wallet in wallets:
			if os.path.isfile(wallet.bocFilePath):
				account = self.GetAccount(wallet.addr)
				if account.balance > 0:
					self.SendFile(wallet.bocFilePath, wallet)
	#end define

	def GetConfigFromValidator(self):
		local.AddLog("start GetConfigFromValidator function", "debug")
		result = self.validatorConsole.Run("getconfig")
		string = Pars(result, "---------", "--------")
		vconfig = json.loads(string)
		return vconfig
	#end define

	def MoveGrams(self, walletName, destinationAddr, gram, flags):
		local.AddLog("start MoveGrams function", "debug")
		if gram == "all":
			mode = 130
			gram = 0
		elif gram == "alld":
			mode = 160
			gram = 0
		else:
			mode = 3
		wallet = self.GetLocalWallet(walletName)
		seqno = self.GetSeqno(wallet)
		resultFilePath = local.buffer.get("myTempDir") + walletName + "_wallet-query"
		args = ["wallet.fif", wallet.path, destinationAddr, seqno, gram, resultFilePath, "-m", mode]
		args += flags
		result = self.fift.Run(args)
		resultFilePath = Pars(result, "Saved to file ", ")")
		self.SendFile(resultFilePath, wallet)
	#end define
	
	def GetValidatorKey(self):
		data = self.GetConfigFromValidator()
		validators = data["validators"]
		for validator in validators:
			validatorId = validator["id"]
			key_bytes = base64.b64decode(validatorId)
			validatorKey = key_bytes.hex().upper()
			timestamp = GetTimestamp()
			if timestamp > validator["election_date"]:
				return validatorKey
	#end define
	
	def TestElectionEntry(self):
		local.AddLog("start TestElectionEntry function", "debug")
		walletName = "validator_wallet_002"
		wallet = self.GetLocalWallet(walletName)

		# Get startWorkTime and endWorkTime
		fullElectorAddr = self.GetFullElectorAddr()
		startWorkTime = self.GetActiveElectionId(fullElectorAddr)

		# Check if elections started
		if (startWorkTime == 0):
			local.AddLog("Elections have not yet begun", "debug")
			return

		# Check if election entry is completed
		vconfig = self.GetConfigFromValidator()
		validators = vconfig.get("validators")
		for item in validators:
			if item.get("election_date") == startWorkTime:
				local.AddLog("Elections entry already completed", "debug")
				return

		# Get account balance and minimum stake
		account = self.GetAccount(wallet.addr)
		minStake = self.GetMinStake()

		# Check if we have enough grams
		if minStake > account.balance:
			local.AddLog("You don't have enough grams. Minimum stake: " + str(minStake), "debug")
			return

		# Calculate stake
		if len(validators) == 0:
			stake = int(account.balance*0.99/2)
		if len(validators) > 0 or (stake is not None and stake < minStake):
			stake = int(account.balance*0.99)

		# Calculate endWorkTime
		validatorsElectedFor = self.GetValidatorsElectedFor()
		endWorkTime = startWorkTime + validatorsElectedFor + 300 # 300 sec - margin of seconds

		# Create keys
		validatorKey = self.CreatNewKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)

		# Add key to validator
		self.AddKeyToValidator(validatorKey, startWorkTime, endWorkTime)
		self.AddKeyToTemp(validatorKey, endWorkTime)

		# Get ADNL address
		adnlAddr = self.CreatNewKey()
		self.AddAdnlAddrToValidator(adnlAddr)
		self.AttachAdnlAddrToValidator(adnlAddr, validatorKey, endWorkTime)

		# Create fift's
		maxFactor = round(stake / minStake, 1)
		var1 = self.CreateElectionRequest(wallet, startWorkTime, adnlAddr, maxFactor)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		validatorPubkey, resultFilePath = self.SignElectionRequestWithValidator(wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor)

		# Send boc file to TON
		resultFilePath = self.SignFileWithWallet(wallet, resultFilePath, fullElectorAddr, stake)
		self.SendFile(resultFilePath, wallet)

		# Save vars to json file
		# self.SaveElectionVarsToJsonFile(wallet=wallet, account=account, stake=stake, maxFactor=maxFactor, fullElectorAddr=fullElectorAddr, startWorkTime=startWorkTime, validatorsElectedFor=validatorsElectedFor, endWorkTime=endWorkTime, validatorKey=validatorKey, validatorPubkey_b64=validatorPubkey_b64, adnlAddr=adnlAddr, var1=var1, validatorSignature=validatorSignature, validatorPubkey=validatorPubkey)
		
		self.validatorConsole.Run("delpermkey {validatorKey}".format(validatorKey=validatorKey))

		local.AddLog("TestElectionEntry completed. Start work time: " + str(startWorkTime))
	#end define
	
	def TestReturnStake(self):
		local.AddLog("start TestReturnStake function", "debug")
		fullElectorAddr = self.GetFullElectorAddr()
		walletName = "validator_wallet_002"
		wallet = self.GetLocalWallet(walletName)
		returnedStake = self.GetReturnedStake(fullElectorAddr, wallet)
		if returnedStake == 0:
			local.AddLog("You have nothing on the return stake", "debug")
			return
		resultFilePath = self.RecoverStake()
		resultFilePath = self.SignFileWithWallet(wallet, resultFilePath, fullElectorAddr, 1)
		self.SendFile(resultFilePath, wallet)
		local.AddLog("TestReturnStake completed")
	#end define
	
	def GetElectionEntries(self):
		local.AddLog("start GetElectionEntries function", "debug")
		fullConfigAddr = self.GetFullElectorAddr()
		# Get raw data
		cmd = "runmethod {fullConfigAddr} participant_list_extended".format(fullConfigAddr=fullConfigAddr)
		result = self.liteClient.Run(cmd)
		rawElectionEntries = self.Result2List(result)
		
		# Get json
		# Parser by @skydev (https://github.com/skydev0h)
		entries = list()
		startWorkTime = rawElectionEntries[0]
		endElectionsTime = rawElectionEntries[1]
		minStake = rawElectionEntries[2]
		allStakes = rawElectionEntries[3]
		electionEntries = rawElectionEntries[4]
		wtf1 = rawElectionEntries[5]
		wtf2 = rawElectionEntries[6]
		for entry in electionEntries:
			if len(entry) == 0:
				continue
				
			# Create dict
			item = dict()
			item["validatorPubkey"] = dec2hex(entry[0]).upper()
			item["stake"] = ng2g(entry[1][0])
			item["maxFactor"] = round(entry[1][1] / 655.36) / 100.0
			item["walletAddr_hex"] = dec2hex(entry[1][2]).upper()
			item["walletAddr"] = self.HexAddr2Base64Addr("-1:"+item["walletAddr_hex"])
			item["adnlAddr"] = dec2hex(entry[1][3]).upper()
			entries.append(item)
		return entries
	#end define
	
	def GetOffers(self):
		local.AddLog("start GetOffers function", "debug")
		fullConfigAddr = self.GetFullConfigAddr()
		# Get raw data
		cmd = "runmethod {fullConfigAddr} list_proposals".format(fullConfigAddr=fullConfigAddr)
		result = self.liteClient.Run(cmd)
		rawOffers = self.Result2List(result)
		rawOffers = rawOffers[0]

		# Get json
		offers = list()
		for offer in rawOffers:
			if len(offer) == 0:
				continue
			hash = offer[0]
			subdata = offer[1]
			
			# Create dict
			item = dict()
			item["config"] = dict()
			item["hash"] = hash
			item["endTime"] = subdata[0]
			item["critFlag"] = subdata[1]
			item["config"]["id"] = subdata[2][0]
			item["config"]["value"] = subdata[2][1]
			item["config"]["oldValueHash"] = subdata[2][2]
			item["votedValidators"] = subdata[4]
			item["weightRemaining"] = subdata[5] # *weight_remaining*
			item["roundsRemaining"] = subdata[6] # *rounds_remaining*
			item["wins"] = subdata[7] # *wins*
			item["losses"] = subdata[8] # *losses*
			offers.append(item)
		#end for
		return offers
	#end define
	
	def SignProposalVoteRequestWithValidator(self, offerHash, validatorIndex, validatorPubkey_b64, validatorSignature):
		local.AddLog("start SignProposalVoteRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + "_vote-msg-body.boc"
		args = ["config-proposal-vote-signed.fif", "-i", validatorIndex, offerHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		fileName = Pars(result, "Saved to file ", '\n')
		return fileName
	#end define
	
	def VoteOffer(self, offerHash):
		local.AddLog("start VoteOffer function", "debug")
		offerHash = int(offerHash)
		fullConfigAddr = self.GetFullConfigAddr()
		walletName = self.validatorWalletName
		wallet = self.GetLocalWallet(walletName)
		validatorKey = self.GetValidatorKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)
		validatorIndex = self.GetValidatorIndex()
		offer = self.GetOffer(offerHash)
		if validatorIndex in offer.get("votedValidators"):
			local.AddLog("Proposal already has been voted", "debug")
			return
		var1 = self.CreateConfigProposalRequest(offerHash, validatorIndex)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		resultFilePath = self.SignProposalVoteRequestWithValidator(offerHash, validatorIndex, validatorPubkey_b64, validatorSignature)
		resultFilePath = self.SignFileWithWallet(wallet, resultFilePath, fullConfigAddr, 1.5)
		self.SendFile(resultFilePath, wallet)
		self.AddSaveOffer(offerHash)
	#end define
	
	def GetOffer(self, offerHash):
		local.AddLog("start GetOffer function", "debug")
		offers = self.GetOffers()
		for offer in offers:
			if offerHash == offer.get("hash"):
				return offer
		raise Exception("GetOffer error: offer not found.")
	#end define
	
	def GetOffersNumber(self):
		local.AddLog("start GetOffersNumber function", "debug")
		result = dict()
		offers = self.GetOffers()
		saveOffers = self.GetSaveOffers()
		buff = 0
		for offer in offers:
			offerHash = offer.get("hash")
			if offerHash in saveOffers:
				continue
			buff += 1
		result["all"] = len(offers)
		result["new"] = buff
		return result
	#end define
	
	def GetValidatorIndex(self):
		config34 = self.GetConfig34()
		validators = config34.get("validators")
		myValidatorAdnlAddr = self.GetAdnlAddr()
		index = 0
		for validator in validators:
			validatorAdnlAddr = validator.get("adnlAddr")
			if myValidatorAdnlAddr == validatorAdnlAddr:
				return index
			index += 1
		local.AddLog("GetValidatorIndex error: index not found.", "warning")
		return -1
	#end define
	
	def GetDbSize(self, exceptions="log"):
		local.AddLog("start GetDbSize function", "debug")
		exceptions = exceptions.split()
		totalSize = 0
		path = "/var/ton-work/"
		for directory, subdirectory, files in os.walk(path):
			for file in files:
				buff = file.split('.')
				ext = buff[-1]
				if ext in exceptions:
					continue
				filePath = os.path.join(directory, file)
				totalSize += os.path.getsize(filePath)
		result = round(totalSize / 10**9, 2)
		return result
	#end define
	
	def Result2List(self, text):
		buff = Pars(text, "result:", "\n")
		buff = buff.replace(')', ']')
		buff = buff.replace('(', '[')
		buff = buff.replace(']', ' ] ')
		buff = buff.replace('[', ' [ ')
		arr = buff.split()
		
		# Get good raw data
		output = ""
		arrLen = len(arr)
		for i in range(arrLen):
			item = arr[i]
			# get next item
			if i+1 < arrLen:
				nextItem = arr[i+1]
			else:
				nextItem = None
			# add item to output
			if item == '[':
				output += item
			elif nextItem == ']':
				output += item
			elif '{' in item or '}' in item:
				output += "\"{item}\", ".format(item=item)
			elif i+1 == arrLen:
				output += item
			else:
				output += item + ', '
		#end for
		data = json.loads(output)
		return data
	#end define
	
	def NewDomain(self, domain):
		local.AddLog("start NewDomain function", "debug")
		domainName = domain["name"]
		buff = domainName.split('.')
		subdomain = buff.pop(0)
		dnsDomain = ".".join(buff)
		dnsAddr = self.GetDomainAddr(dnsDomain)
		wallet = self.GetLocalWallet(domain["walletName"])
		expireInSec = 700000 # fix me
		catId = 1 # fix me
		
		# Check if domain is busy
		domainEndTime = self.GetDomainEndTime(domainName)
		if domainEndTime > 0:
			raise Exception("NewDomain error: domain is busy")
		#end if
		
		fileName = self.tempDir + self.nodeName + "_dns-msg-body.boc"
		args = ["auto-dns.fif", dnsAddr, "add", subdomain, expireInSec, "owner", wallet.addr, "cat", catId, "adnl", domain["adnlAddr"], "-o", fileName]
		result = self.fift.Run(args)
		resultFilePath = Pars(result, "Saved to file ", ')')
		resultFilePath = self.SignFileWithWallet(wallet, resultFilePath, dnsAddr, 1.7)
		self.SendFile(resultFilePath, wallet)
		self.AddDomain(domain)
	#end define
	
	def AddDomain(self, domain):
		if "domains" not in local.db:
			local.db["domains"] = list()
		#end if
		local.db["domains"].append(domain)
		local.dbSave()
	#end define
	
	def GetDomains(self):
		domains = local.db.get("domains")
		for domain in domains:
			domainName = domain.get("name")
			domain["endTime"] = self.GetDomainEndTime(domainName)
		return domains
	#end define
	
	def GetDomain(self, domainName):
		domain = dict()
		domain["name"] = domainName
		domain["adnlAddr"] = self.GetDomainAdnlAddr(domainName)
		domain["endTime"] = self.GetDomainEndTime(domainName)
		return domain
	#end define
	
	def DeleteDomain(self, domainName):
		domains = local.db.get("domains")
		for domain in domains:
			if (domainName == domain.get("name")):
				domains.remove(domain)
				local.dbSave()
				return
		raise Exception("DeleteDomain error: Domain not found")
	#end define
	
	def AddRule(self, rule):
		if "rules" not in local.db:
			local.db["rules"] = list()
		#end if
		local.db["rules"].append(rule)
		local.dbSave()
	#end define
	
	def GetRules(self):
		rules = local.db.get("rules")
		return rules
	#end define
	
	def AddBookmark(self, bookmark):
		if "bookmarks" not in local.db:
			local.db["bookmarks"] = list()
		#end if
		local.db["bookmarks"].append(bookmark)
		local.dbSave()
	#end define
	
	def GetBookmarks(self):
		bookmarks = local.db.get("bookmarks")
		for bookmark in bookmarks:
			self.WriteBookmarkData(bookmark)
		return bookmarks
	#end define
	
	def GetBookmarkAddr(self, type, name):
		bookmarks = local.db.get("bookmarks")
		for bookmark in bookmarks:
			bookmarkType = bookmark.get("type")
			bookmarkName = bookmark.get("name")
			bookmarkAddr = bookmark.get("addr")
			if (bookmarkType == type and bookmarkName == name):
				return bookmarkAddr
		raise Exception("GetBookmarkAddr error: Bookmark not found")
	#end define
	
	def DeleteBookmark(self, name, type):
		bookmarks = local.db.get("bookmarks")
		for bookmark in bookmarks:
			bookmarkType = bookmark.get("type")
			bookmarkName = bookmark.get("name")
			if (type == bookmarkType and name == bookmarkName):
				bookmarks.remove(bookmark)
				local.dbSave()
				return
		raise Exception("DeleteBookmark error: Bookmark not found")
	#end define
	
	def WriteBookmarkData(self, bookmark):
		type = bookmark.get("type")
		if type == "account":
			addr = bookmark.get("addr")
			account = self.GetAccount(addr)
			if account.status == "empty":
				data = "empty"
			else:
				data = account.balance
		elif type == "domain":
			domainName = bookmark.get("addr")
			endTime = self.GetDomainEndTime(domainName)
			if endTime == 0:
				data = "free"
			else:
				data = Timestamp2Datetime(endTime, "%d.%m.%Y")
		else:
			data = "null"
		bookmark["data"] = data
	#end define
	
	def AddSaveOffer(self, offerHash):
		if "saveOffers" not in local.db:
			local.db["saveOffers"] = list()
		#end if
		saveOffers = local.db.get("saveOffers")
		if offerHash not in saveOffers:
			saveOffers.append(offerHash)
			local.dbSave()
	#end define
	
	def GetSaveOffers(self):
		saveOffers = local.db.get("saveOffers")
		return saveOffers
	#end define
	
	def IsAccountAddr(self, str):
		type = GetStrType(str)
		if type == "account":
			result = True
		else:
			result = False
		return result
	#end define
	
	def IsDomainName(self, str):
		type = GetStrType(str)
		if type == "domain":
			result = True
		else:
			result = False
		return result
	#end define
	
	def GetStrType(self, str):
		if len(str) == 48 and '.' not in str:
			result = "account"
		elif '.' in str:
			result = "domain"
		else:
			result = "undefined"
		return result
	#end define
	
	def GetDestinationAddr(self, destination):
		destinationType = self.GetStrType(destination)
		if destinationType != "account":
			walletsNameList = self.GetWalletsNameList()
			if destination in walletsNameList:
				wallet = self.GetLocalWallet(destination)
				destination = wallet.addr
			else:
				destination = self.GetBookmarkAddr("account", destination)
		return destination
	#end define
	
	def HexAddr2Base64Addr(self, fullAddr, bounceable=True, testnet=True):
		buff = fullAddr.split(':')
		workchain = int(buff[0])
		addr_hex = buff[1]
		b = bytearray(36)
		b[0] = 0x51 - bounceable * 0x40 + testnet * 0x80
		b[1] = workchain % 256
		b[2:34] = bytearray.fromhex(addr_hex)
		buff = bytes(b[:34])
		crc = crc16.crc16xmodem(buff)
		b[34] = crc >> 8
		b[35] = crc & 0xff
		result = base64.b64encode(b)
		result = result.decode()
		result = result.replace('+', '-')
		result = result.replace('/', '_')
		return result
	#end define
	
	def GetNetworStatistics(self):
		filePath = self.tempDir + "statistics.json"
		with open(filePath) as file:
			text = file.read()
			data = json.loads(text)
			return data
	#end define
#end class

def ng2g(ng):
	return int(ng)/10**9
#end define

def Init():
	local.Run()
	local.buffer["network"] = dict()
	local.buffer["network"]["type"] = "bytes"
	local.buffer["network"]["in"] = [0]*15*6
	local.buffer["network"]["out"] = [0]*15*6
	local.buffer["network"]["all"] = [0]*15*6
#end define

def Elections(ton):
	if ton.validatorWalletName is None:
		return
	ton.ReturnStake()
	ton.ElectionEntry()
#end define

def Statistics(ton):
	ReadNetworkData()
	SaveNetworStatistics(ton)
#end define

def Offers(ton):
	saveOffers = ton.GetSaveOffers()
	offers = ton.GetOffers()
	for offer in offers:
		offerHash = offer.get("hash")
		if offerHash in saveOffers:
			ton.VoteOffer(offerHash)
#end define

def Domains(ton):
	pass
#end define

def Telemetry(ton):
	data = dict()
	data["adnlAddr"] = ton.adnlAddr
	data["validatorStatus"] = ton.GetValidatorStatus()
	data["cpuLoad"] = GetLoadAvg()
	data["netLoad"] = ton.GetNetworStatistics()
	url = "https://toncenter.com/api/newton_test/status/report_status"
	output = json.dumps(data)
	resp = requests.post(url, data=output, timeout=3)

	if ton.adnlAddr != "660A8EC119287FE4B8E38D69045E0017EB5BFE1FBBEBE1AA26D492DA4F3A1D69":
		return
	data = dict()
	config34 = ton.GetConfig34()
	config36 = ton.GetConfig36()
	data["currentValidators"] = config34["validators"]
	if len(config36) > 0:
		data["nextValidators"] = config36["validators"]
	url = "https://toncenter.com/api/newton_test/status/report_validators"
	output = json.dumps(data)
	resp = requests.post(url, data=output, timeout=3)
#end define

def ReadNetworkData():
	local.AddLog("start ReadNetworkData function", "debug")
	interfaceName = GetInternetInterfaceName()
	buff = psutil.net_io_counters(pernic=True)
	data = buff[interfaceName]
	network_in = data.bytes_recv
	network_out = data.bytes_sent
	network_all = network_in + network_out

	local.buffer["network"]["in"].pop(0)
	local.buffer["network"]["in"].append(network_in)
	local.buffer["network"]["out"].pop(0)
	local.buffer["network"]["out"].append(network_out)
	local.buffer["network"]["all"].pop(0)
	local.buffer["network"]["all"].append(network_all)
#end define

def SaveNetworStatistics(ton):
	local.AddLog("start SaveNetworStatistics function", "debug")
	data = local.buffer["network"]["all"]
	data = data[::-1]
	zerodata = data[0]
	buff1 = data[1*6-1]
	buff5 = data[5*6-1]
	buff15 = data[15*6-1]

	# get avg
	if buff1 != 0:
		buff1 = zerodata - buff1
	if buff5 != 0:
		buff5 = zerodata - buff5
	if buff15 != 0:
		buff15 = zerodata - buff15

	# bytes -> bytes/s
	buff1 = buff1 / (1*60)
	buff5 = buff5 / (5*60)
	buff15 = buff15 / (15*60)

	# bytes/s -> bits/s
	buff1 = buff1 * 8
	buff5 = buff5 * 8
	buff15 = buff15 * 8

	# bits/s -> Mbits/s
	netLoad1 = b2mb(buff1)
	netLoad5 = b2mb(buff5)
	netLoad15 = b2mb(buff15)

	# save statistics
	filePath = ton.tempDir + "statistics.json"
	data = [netLoad1, netLoad5, netLoad15]
	text = json.dumps(data)
	with open(filePath, 'w') as file:
		file.write(text)
#end define

def General():
	local.AddLog("start General function", "debug")
	ton = MyTonCore()

	# Запустить потоки
	local.StartCycle(Elections, sec=600, args=(ton, ))
	local.StartCycle(Statistics, sec=10, args=(ton, ))
	local.StartCycle(Offers, sec=600, args=(ton, ))
	local.StartCycle(Domains, sec=600, args=(ton, ))
	local.StartCycle(Telemetry, sec=60, args=(ton, ))
	Sleep()
#end define




###
### Start of the program
###

if __name__ == "__main__":
	Init()
	General()
#end if

