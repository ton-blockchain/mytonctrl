import os
import base64
import time
import re
import json
import hashlib
import struct
import psutil
import subprocess
import pkg_resources
import requests
from fastcrc import crc16

from modules import MODES
from mytoncore.utils import xhex2hex, ng2g
from mytoncore.liteclient import LiteClient
from mytoncore.validator_console import ValidatorConsole
from mytoncore.fift import Fift
from mytoncore.models import (
    Wallet,
    Account,
    Block,
    Trans,
    Message,
    Pool,
)

from mypylib.mypylib import (
	parse,
	get_timestamp,
	timestamp2datetime,
	dec2hex,
	Dict
)


class MyTonCore():
	def __init__(self, local):
		self.local = local
		self.walletsDir = None
		self.dbFile = None
		self.contractsDir = None
		self.poolsDir = None
		self.tempDir = None
		self.nodeName = None

		self.liteClient = LiteClient(self.local)
		self.validatorConsole = ValidatorConsole(self.local)
		self.fift = Fift(self.local)

		self.Refresh()
		self.Init()
	#end define

	def Init(self):
		# Check all directorys
		os.makedirs(self.walletsDir, exist_ok=True)
		os.makedirs(self.contractsDir, exist_ok=True)
		os.makedirs(self.poolsDir, exist_ok=True)
	#end define

	def Refresh(self):
		if self.dbFile:
			self.local.load_db(self.dbFile)

		if not self.walletsDir:
			self.walletsDir = self.local.buffer.my_work_dir + "wallets/"
		self.contractsDir = self.local.buffer.my_work_dir + "contracts/"
		self.poolsDir = self.local.buffer.my_work_dir + "pools/"
		self.tempDir = self.local.buffer.my_temp_dir

		self.nodeName = self.local.db.get("nodeName")
		if self.nodeName is None:
			self.nodeName=""
		else:
			self.nodeName = self.nodeName + "_"

		liteClient = self.local.db.get("liteClient")
		if liteClient is not None:
			self.liteClient.ton = self # magic
			self.liteClient.appPath = liteClient["appPath"]
			self.liteClient.configPath = liteClient["configPath"]
			liteServer = liteClient.get("liteServer")
			if liteServer is not None:
				self.liteClient.pubkeyPath = liteServer["pubkeyPath"]
				self.liteClient.addr = "{0}:{1}".format(liteServer["ip"], liteServer["port"])
		#end if

		validatorConsole = self.local.db.get("validatorConsole")
		if validatorConsole is not None:
			self.validatorConsole.appPath = validatorConsole["appPath"]
			self.validatorConsole.privKeyPath = validatorConsole["privKeyPath"]
			self.validatorConsole.pubKeyPath = validatorConsole["pubKeyPath"]
			self.validatorConsole.addr = validatorConsole["addr"]
		#end if

		fift = self.local.db.get("fift")
		if fift is not None:
			self.fift.appPath = fift["appPath"]
			self.fift.libsPath = fift["libsPath"]
			self.fift.smartcontsPath = fift["smartcontsPath"]
		#end if

		# Check config file
		self.CheckConfigFile(fift, liteClient)
	#end define

	def CheckConfigFile(self, fift, liteClient):
		mconfig_path = self.local.buffer.db_path
		backup_path = mconfig_path + ".backup"
		if fift is None or liteClient is None:
			self.local.add_log("The config file is broken", "warning")
			print(f"self.local.db: {self.local.db}")
			if os.path.isfile(backup_path):
				self.local.add_log("Restoring the configuration file", "info")
				args = ["cp", backup_path, mconfig_path]
				subprocess.run(args)
				self.Refresh()
		elif os.path.isfile(backup_path) == False:
			self.local.add_log("Create backup config file", "info")
			args = ["cp", mconfig_path, backup_path]
			subprocess.run(args)
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
		self.local.add_log("start GetSeqno function", "debug")
		cmd = "runmethodfull {addr} seqno".format(addr=wallet.addrB64)
		result = self.liteClient.Run(cmd)
		if "cannot run any methods" in result:
			return None
		if "result" not in result:
			return 0
		seqno = self.GetVarFromWorkerOutput(result, "result")
		seqno = seqno.replace(' ', '')
		seqno = parse(seqno, '[', ']')
		seqno = int(seqno)
		return seqno
	#end define

	def GetAccount(self, inputAddr):
		#self.local.add_log("start GetAccount function", "debug")
		workchain, addr = self.ParseInputAddr(inputAddr)
		account = Account(workchain, addr)
		cmd = "getaccount {inputAddr}".format(inputAddr=inputAddr)
		result = self.liteClient.Run(cmd)
		storage = self.GetVarFromWorkerOutput(result, "storage")
		if storage is None:
			return account
		addr = self.GetVarFromWorkerOutput(result, "addr")
		workchain = self.GetVar(addr, "workchain_id")
		address = self.GetVar(addr, "address")
		addrFull = "{}:{}".format(workchain, xhex2hex(address))
		balance = self.GetVarFromWorkerOutput(storage, "balance")
		grams = self.GetVarFromWorkerOutput(balance, "grams")
		value = self.GetVarFromWorkerOutput(grams, "value")
		state = self.GetVarFromWorkerOutput(storage, "state")
		code_buff = self.GetVarFromWorkerOutput(state, "code")
		data_buff = self.GetVarFromWorkerOutput(state, "data")
		code = self.GetVarFromWorkerOutput(code_buff, "value")
		data = self.GetVarFromWorkerOutput(data_buff, "value")
		code = self.GetBody(code)
		data = self.GetBody(data)
		codeHash = self.GetCodeHash(code)
		status = parse(state, "account_", '\n')
		account.workchain = int(workchain)
		account.addr = xhex2hex(address)
		account.addrB64 = self.AddrFull2AddrB64(addrFull)
		account.addrFull = addrFull
		account.status = status
		account.balance = ng2g(value)
		account.lt = parse(result, "lt = ", ' ')
		account.hash = parse(result, "hash = ", '\n')
		account.codeHash = codeHash
		return account
	#end define

	def GetCodeHash(self, code):
		if code is None:
			return
		codeBytes = bytes.fromhex(code)
		codeHash = hashlib.sha256(codeBytes).hexdigest()
		return codeHash
	#end define

	def GetAccountHistory(self, account, limit):
		self.local.add_log("start GetAccountHistory function", "debug")
		addr = f"{account.workchain}:{account.addr}"
		lt = account.lt
		transHash = account.hash
		history = list()
		while True:
			data, lt, transHash = self.LastTransDump(addr, lt, transHash)
			history += data
			if lt is None or len(history) >= limit:
				return history
	#end define

	def LastTransDump(self, addr, lt, transHash, count=10):
		history = list()
		cmd = f"lasttransdump {addr} {lt} {transHash} {count}"
		result = self.liteClient.Run(cmd)
		data = self.Result2Dict(result)
		prevTrans = self.GetKeyFromDict(data, "previous transaction")
		prevTransLt = self.GetVar(prevTrans, "lt")
		prevTransHash = self.GetVar(prevTrans, "hash")
		for key, item in data.items():
			if "transaction #" not in key:
				continue
			block_str = parse(key, "from block ", ' ')
			description = self.GetKeyFromDict(item, "description")
			type = self.GetVar(description, "trans_")
			time = self.GetVarFromDict(item, "time")
			#outmsg = self.GetVarFromDict(item, "outmsg_cnt")
			total_fees = self.GetVarFromDict(item, "total_fees.grams.value")
			messages = self.GetMessagesFromTransaction(item)
			transData = dict()
			transData["type"] = type
			transData["trans"] = Trans(Block(block_str))
			transData["time"] = time
			#transData["outmsg"] = outmsg
			transData["total_fees"] = total_fees
			history += self.ParsMessages(messages, transData)
		return history, prevTransLt, prevTransHash
	#end define

	def ParsMessages(self, messages, transData):
		history = list()
		#for item in messages:
		for data in messages:
			src = None
			dest = None
			ihr_disabled = self.GetVarFromDict(data, "message.ihr_disabled")
			bounce = self.GetVarFromDict(data, "message.bounce")
			bounced = self.GetVarFromDict(data, "message.bounced")

			srcWorkchain = self.GetVarFromDict(data, "message.info.src.workchain_id")
			address = self.GetVarFromDict(data, "message.info.src.address")
			srcAddr = xhex2hex(address)
			#if address:
			#	src = "{}:{}".format(workchain, xhex2hex(address))
			#end if

			destWorkchain = self.GetVarFromDict(data, "message.info.dest.workchain_id")
			address = self.GetVarFromDict(data, "message.info.dest.address")
			destAddr = xhex2hex(address)
			#if address:
			#	dest = "{}:{}".format(workchain, xhex2hex(address))
			#end if

			grams = self.GetVarFromDict(data, "message.info.value.grams.value")
			ihr_fee = self.GetVarFromDict(data, "message.info.ihr_fee.value")
			fwd_fee = self.GetVarFromDict(data, "message.info.fwd_fee.value")
			import_fee = self.GetVarFromDict(data, "message.info.import_fee.value")

			#body = self.GetVarFromDict(data, "message.body.value")
			message = self.GetItemFromDict(data, "message")
			body = self.GetItemFromDict(message, "body")
			value = self.GetItemFromDict(body, "value")
			body = self.GetBodyFromDict(value)
			comment = self.GetComment(body)

			#storage_ph
			#credit_ph
			#compute_ph.gas_fees
			#compute_ph.gas_used
			#compute_ph.gas_limit

			message = Message()
			message.type = transData.get("type")
			message.block = transData.get("block")
			message.trans = transData.get("trans")
			message.time = transData.get("time")
			#message.outmsg = transData.get("outmsg")
			message.total_fees = ng2g(transData.get("total_fees"))
			message.ihr_disabled = ihr_disabled
			message.bounce = bounce
			message.bounced = bounced
			message.srcWorkchain = srcWorkchain
			message.destWorkchain = destWorkchain
			message.srcAddr = srcAddr
			message.destAddr = destAddr
			message.value = ng2g(grams)
			message.body = body
			message.comment = comment
			message.ihr_fee = ng2g(ihr_fee)
			message.fwd_fee = ng2g(fwd_fee)
			#message.storage_ph = storage_ph
			#message.credit_ph = credit_ph
			#message.compute_ph = compute_ph
			history.append(message)
		#end for
		return history
	#end define

	def GetMessagesFromTransaction(self, data):
		result = list()
		for key, item in data.items():
			if ("inbound message" in key or
			"outbound message" in key):
				result.append(item)
		#end for
		result.reverse()
		return result
	#end define

	def GetBody(self, buff):
		if buff is None:
			return
		#end if

		body = ""
		arr = buff.split('\n')
		for item in arr:
			if "x{" not in item:
				continue
			buff = parse(item, '{', '}')
			buff = buff.replace('_', '')
			if len(buff)%2 == 1:
				buff = "0" + buff
			body += buff
		#end for
		return body
	#end define

	def GetBodyFromDict(self, buff):
		if buff is None:
			return
		#end if

		body = ""
		for item in buff:
			if "x{" not in item:
				continue
			buff = parse(item, '{', '}')
			buff = buff.replace('_', '')
			if len(buff)%2 == 1:
				buff = "0" + buff
			body += buff
		#end for
		if body == "":
			body = None
		return body
	#end define

	def GetComment(self, body):
		if body is None:
			return
		#end if

		start = body[:8]
		data = body[8:]
		result = None
		if start == "00000000":
			buff = bytes.fromhex(data)
			try:
				result = buff.decode("utf-8")
			except: pass
		return result
	#end define

	def GetLocalWallet(self, walletName, version=None, subwallet=None):
		self.local.add_log("start GetLocalWallet function", "debug")
		if walletName is None:
			return None
		walletPath = self.walletsDir + walletName
		if version and "h" in version:
			wallet = self.GetHighWalletFromFile(walletPath, subwallet, version)
		else:
			wallet = self.GetWalletFromFile(walletPath, version)
		return wallet
	#end define

	def GetWalletFromFile(self, filePath, version):
		self.local.add_log("start GetWalletFromFile function", "debug")
		# Check input args
		if (".addr" in filePath):
			filePath = filePath.replace(".addr", '')
		if (".pk" in filePath):
			filePath = filePath.replace(".pk", '')
		if os.path.isfile(filePath + ".pk") == False:
			raise Exception("GetWalletFromFile error: Private key not found: " + filePath)
		#end if

		# Create wallet object
		walletName = filePath[filePath.rfind('/')+1:]
		wallet = Wallet(walletName, filePath, version)
		self.AddrFile2Object(wallet)
		self.WalletVersion2Wallet(wallet)
		return wallet
	#end define

	def GetHighWalletFromFile(self, filePath, subwallet, version):
		self.local.add_log("start GetHighWalletFromFile function", "debug")
		# Check input args
		if (".addr" in filePath):
			filePath = filePath.replace(".addr", '')
		if (".pk" in filePath):
			filePath = filePath.replace(".pk", '')
		if os.path.isfile(filePath + ".pk") == False:
			raise Exception("GetHighWalletFromFile error: Private key not found: " + filePath)
		#end if

		# Create wallet object
		walletName = filePath[filePath.rfind('/')+1:]
		wallet = Wallet(walletName, filePath, version)
		wallet.subwallet = subwallet
		wallet.addrFilePath = f"{filePath}{subwallet}.addr"
		wallet.bocFilePath = f"{filePath}{subwallet}-query.boc"
		self.AddrFile2Object(wallet)
		self.WalletVersion2Wallet(wallet)
		return wallet
	#end define

	def AddrFile2Object(self, object):
		file = open(object.addrFilePath, "rb")
		data = file.read()
		object.addr = data[:32].hex()
		object.workchain = struct.unpack("i", data[32:])[0]
		object.addrFull = f"{object.workchain}:{object.addr}"
		object.addrB64 = self.AddrFull2AddrB64(object.addrFull)
		object.addrB64_init = self.AddrFull2AddrB64(object.addrFull, bounceable=False)
		file.close()
	#end define

	def WalletVersion2Wallet(self, wallet):
		if wallet.version is not None:
			return
		self.local.add_log("start WalletVersion2Wallet function", "debug")
		walletsVersionList = self.GetWalletsVersionList()
		version = walletsVersionList.get(wallet.addrB64)
		if version is None:
			account = self.GetAccount(wallet.addrB64)
			version = self.GetVersionFromCodeHash(account.codeHash)
			self.SetWalletVersion(wallet.addrB64, version)
		if version is None:
			self.local.add_log("Wallet version not found: " + wallet.addrB64, "warning")
			return
		wallet.version = version
	#end define

	def SetWalletVersion(self, addrB64, version):
		walletsVersionList = self.GetWalletsVersionList()
		walletsVersionList[addrB64] = version
		self.local.save()
	#end define

	def GetVersionFromCodeHash(self, inputHash):
		self.local.add_log("start GetVersionFromCodeHash function", "debug")
		arr = dict()
		arr["v1r1"] = "d670136510daff4fee1889b8872c4c1e89872ffa1fe58a23a5f5d99cef8edf32"
		arr["v1r2"] = "2705a31a7ac162295c8aed0761cc6e031ab65521dd7b4a14631099e02de99e18"
		arr["v1r3"] = "c3b9bb03936742cfbb9dcdd3a5e1f3204837f613ef141f273952aa41235d289e"
		arr["v2r1"] = "fa44386e2c445f1edf64702e893e78c3f9a687a5a01397ad9e3994ee3d0efdbf"
		arr["v2r2"] = "d5e63eff6fa268d612c0cf5b343c6674b7312c58dfd9ffa1b536f2014a919164"
		arr["v3r1"] = "4505c335cb60f221e58448c71595bb6d7c980c01a798b392ebb53d86cb6061dc"
		arr["v3r2"] = "8a6d73bdd8704894f17d8c76ce6139034b8a51b1802907ca36283417798a219b"
		arr["v4"] = "7ae380664c513769eaa5c94f9cd5767356e3f7676163baab66a4b73d5edab0e5"
		arr["hv1"] = "fc8e48ed7f9654ba76757f52cc6031b2214c02fab9e429ffa0340f5575f9f29c"
		arr["pool"] = "399838da9489139680e90fd237382e96ba771fdf6ea27eb7d513965b355038b4"
		arr["spool"] = "fc2ae44bcaedfa357d0091769aabbac824e1c28f14cc180c0b52a57d83d29054"
		arr["spool_r2"] = "42bea8fea43bf803c652411976eb2981b9bdb10da84eb788a63ea7a01f2a044d"
		arr["liquid_pool_r1"] = "82bc5760719c34395f80df76c42dc5d287f08f6562c643601ebed6944302dcc2"
		arr["liquid_pool_r2"] = "95abec0a66ac63b0fbcf28466eb8240ddcd88f97300691511d9c9975d5521e4a"
		arr["liquid_pool_r3"] = "22a023bc75b649ff2b5b183cd0d34cd413e6e27ee6d6ad0787f75ad39787ed4e"
		arr["liquid_pool_r4"] = "77282b45fd7cfc72ca68fe97af33ad10078730ceaf55e20534c9526c48d602d2"
		arr["controller_r1"] = "0949cf92963dd27bb1e6bf76487807f20409131b6110acbc18b7fbb90280ccf0"
		arr["controller_r2"] = "01118b9553151fb9bc81704a4b3e0fc7b899871a527d44435a51574806863e2c"
		arr["controller_r3"] = "e4d8ce8ff7b4b60c76b135eb8702ce3c86dc133fcee7d19c7aa18f71d9d91438"
		arr["controller_r4"] = "dec125a4850c4ba24668d84252b04c6ad40abf5c9d413a429b56bfff09ea25d4"
		for version, hash in arr.items():
			if hash == inputHash:
				return version
		#end for
	#end define

	def GetWalletsVersionList(self):
		bname = "walletsVersionList"
		walletsVersionList = self.local.db.get(bname)
		if walletsVersionList is None:
			walletsVersionList = dict()
			self.local.db[bname] = walletsVersionList
		return walletsVersionList
	#end define

	def GetFullConfigAddr(self):
		# Get buffer
		bname = "fullConfigAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetFullConfigAddr function", "debug")
		result = self.liteClient.Run("getconfig 0")
		configAddr_hex = self.GetVarFromWorkerOutput(result, "config_addr:x")
		fullConfigAddr = "-1:{configAddr_hex}".format(configAddr_hex=configAddr_hex)

		# Set buffer
		self.SetFunctionBuffer(bname, fullConfigAddr)
		return fullConfigAddr
	#end define

	def GetFullElectorAddr(self):
		# Get buffer
		bname = "fullElectorAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		# Get data
		self.local.add_log("start GetFullElectorAddr function", "debug")
		result = self.liteClient.Run("getconfig 1")
		electorAddr_hex = self.GetVarFromWorkerOutput(result, "elector_addr:x")
		fullElectorAddr = "-1:{electorAddr_hex}".format(electorAddr_hex=electorAddr_hex)

		# Set buffer
		self.SetFunctionBuffer(bname, fullElectorAddr)
		return fullElectorAddr
	#end define

	def GetFullMinterAddr(self):
		# Get buffer
		bname = "fullMinterAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetFullMinterAddr function", "debug")
		result = self.liteClient.Run("getconfig 2")
		minterAddr_hex = self.GetVarFromWorkerOutput(result, "minter_addr:x")
		fullMinterAddr = "-1:{minterAddr_hex}".format(minterAddr_hex=minterAddr_hex)

		# Set buffer
		self.SetFunctionBuffer(bname, fullMinterAddr)
		return fullMinterAddr
	#end define

	def GetFullDnsRootAddr(self):
		# Get buffer
		bname = "fullDnsRootAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetFullDnsRootAddr function", "debug")
		result = self.liteClient.Run("getconfig 4")
		dnsRootAddr_hex = self.GetVarFromWorkerOutput(result, "dns_root_addr:x")
		fullDnsRootAddr = "-1:{dnsRootAddr_hex}".format(dnsRootAddr_hex=dnsRootAddr_hex)

		# Set buffer
		self.SetFunctionBuffer(bname, fullDnsRootAddr)
		return fullDnsRootAddr
	#end define

	def GetActiveElectionId(self, fullElectorAddr):
		# Get buffer
		bname = "activeElectionId"
		buff = self.GetFunctionBuffer(bname)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetActiveElectionId function", "debug")
		cmd = "runmethodfull {fullElectorAddr} active_election_id".format(fullElectorAddr=fullElectorAddr)
		result = self.liteClient.Run(cmd)
		activeElectionId = self.GetVarFromWorkerOutput(result, "result")
		activeElectionId = activeElectionId.replace(' ', '')
		activeElectionId = parse(activeElectionId, '[', ']')
		activeElectionId = int(activeElectionId)

		# Set buffer
		self.SetFunctionBuffer(bname, activeElectionId)
		return activeElectionId
	#end define

	def GetValidatorsElectedFor(self):
		self.local.add_log("start GetValidatorsElectedFor function", "debug")
		config15 = self.GetConfig15()
		return config15["validatorsElectedFor"]
	#end define

	def GetMinStake(self):
		self.local.add_log("start GetMinStake function", "debug")
		config17 = self.GetConfig17()
		return config17["minStake"]
	#end define

	def GetRootWorkchainEnabledTime(self):
		self.local.add_log("start GetRootWorkchainEnabledTime function", "debug")
		config12 = self.GetConfig(12)
		enabledTime = config12["workchains"]["root"]["node"]["value"]["enabled_since"]
		return enabledTime
	#end define

	def GetTotalValidators(self):
		self.local.add_log("start GetTotalValidators function", "debug")
		config34 = self.GetConfig34()
		result = config34["totalValidators"]
		return result
	#end define

	def GetLastBlock(self):
		block = None
		cmd = "last"
		result = self.liteClient.Run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "latest masterchain block" in line:
				buff = line.split(' ')
				block = Block(buff[7])
				break
		return block
	#end define

	def GetInitBlock_new(self):
		#block = self.GetLastBlock()
		#cmd = f"gethead {block}"
		#result = self.liteClient.Run(cmd)
		#seqno =  parse(result, "prev_key_block_seqno=", '\n')
		statesDir = "/var/ton-work/db/archive/states"
		os.chdir(statesDir)
		files = filter(os.path.isfile, os.listdir(statesDir))
		files = [os.path.join(statesDir, f) for f in files] # add path to each file
		files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
		for fileName in files:
			buff = fileName.split('_')
			seqno = int(buff[1])
			workchain = int(buff[2])
			if workchain != -1:
				continue
			shardchain = int(buff[3])
			data = self.GetBlockHead(workchain, shardchain, seqno)
			return data
	#end define

	def GetInitBlock(self):
		block = self.GetLastBlock()
		cmd = f"gethead {block}"
		result = self.liteClient.Run(cmd)
		seqno =  parse(result, "prev_key_block_seqno=", '\n')
		data = self.GetBlockHead(-1, 8000000000000000, seqno)
		return data
	#end define

	def GetBlockHead(self, workchain, shardchain, seqno):
		block = self.GetBlock(workchain, shardchain, seqno)
		data = dict()
		data["seqno"] = block.seqno
		data["rootHash"] = block.rootHash
		data["fileHash"] = block.fileHash
		return data
	#end define

	def GetBlock(self, workchain, shardchain, seqno):
		cmd = "byseqno {workchain}:{shardchain} {seqno}"
		cmd = cmd.format(workchain=workchain, shardchain=shardchain, seqno=seqno)
		result = self.liteClient.Run(cmd)
		block_str =  parse(result, "block header of ", ' ')
		block = Block(block_str)
		return block
	#end define

	def GetTransactions(self, block):
		transactions = list()
		cmd = "listblocktrans {block} 999999".format(block=block)
		result = self.liteClient.Run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "transaction #" in line:
				buff = line.split(' ')
				trans_id = buff[1]
				trans_id = trans_id.replace('#', '')
				trans_id = trans_id.replace(':', '')
				trans_addr = buff[3]
				trans_lt = buff[5]
				trans_hash = buff[7]
				trans = Trans(block, trans_addr, trans_lt, trans_hash)
				transactions.append(trans)
		return transactions
	#end define

	def GetTrans(self, trans):
		addr = f"{trans.block.workchain}:{trans.addr}"
		messageList = list()
		cmd = f"dumptrans {trans.block} {addr} {trans.lt}"
		result = self.liteClient.Run(cmd)
		data = self.Result2Dict(result)
		for key, item in data.items():
			if "transaction is" not in key:
				continue
			description = self.GetKeyFromDict(item, "description")
			type = self.GetVar(description, "trans_")
			time = self.GetVarFromDict(item, "time")
			#outmsg = self.GetVarFromDict(item, "outmsg_cnt")
			total_fees = self.GetVarFromDict(item, "total_fees.grams.value")
			messages = self.GetMessagesFromTransaction(item)
			transData = dict()
			transData["type"] = type
			transData["trans"] = trans
			transData["time"] = time
			#transData["outmsg"] = outmsg
			transData["total_fees"] = total_fees
			messageList += self.ParsMessages(messages, transData)
		return messageList
	#end define

	def GetShards(self, block=None):
		shards = list()
		if block:
			cmd = "allshards {block}".format(block=block)
		else:
			cmd = "allshards"
		result = self.liteClient.Run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "shard #" in line:
				buff = line.split(' ')
				shard_id = buff[1]
				shard_id = shard_id.replace('#', '')
				shard_block = Block(buff[3])
				shard = {"id": shard_id, "block": shard_block}
				shards.append(shard)
		return shards
	#end define

	def GetShardsNumber(self, block=None):
		shards = self.GetShards(block)
		shardsNum = len(shards)
		return shardsNum
	#end define

	def GetValidatorStatus(self):
		# Get buffer
		bname = "validator_status"
		buff = self.GetFunctionBuffer(bname)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetValidatorStatus function", "debug")
		status = Dict()
		try:
			# Parse
			status.is_working = True
			result = self.validatorConsole.Run("getstats")
			status.unixtime = int(parse(result, "unixtime", '\n'))
			status.masterchainblocktime = int(parse(result, "masterchainblocktime", '\n'))
			status.stateserializermasterchainseqno = int(parse(result, "stateserializermasterchainseqno", '\n'))
			status.shardclientmasterchainseqno = int(parse(result, "shardclientmasterchainseqno", '\n'))
			buff = parse(result, "masterchainblock", '\n')
			status.masterchainblock = self.GVS_GetItemFromBuff(buff)
			buff = parse(result, "gcmasterchainblock", '\n')
			status.gcmasterchainblock = self.GVS_GetItemFromBuff(buff)
			buff = parse(result, "keymasterchainblock", '\n')
			status.keymasterchainblock = self.GVS_GetItemFromBuff(buff)
			buff = parse(result, "rotatemasterchainblock", '\n')
			status.rotatemasterchainblock = self.GVS_GetItemFromBuff(buff)
			# Calculate
			status.masterchain_out_of_sync = status.unixtime - status.masterchainblocktime
			status.shardchain_out_of_sync = status.masterchainblock - status.shardclientmasterchainseqno
			status.masterchain_out_of_ser = status.masterchainblock - status.stateserializermasterchainseqno
			status.out_of_sync = status.masterchain_out_of_sync if status.masterchain_out_of_sync > status.shardchain_out_of_sync else status.shardchain_out_of_sync
			status.out_of_ser = status.masterchain_out_of_ser
		except Exception as ex:
			self.local.add_log(f"GetValidatorStatus warning: {ex}", "warning")
			status.is_working = False
		#end try

		# old vars
		status.outOfSync = status.out_of_sync
		status.isWorking = status.is_working

		# Set buffer
		self.SetFunctionBuffer(bname, status)
		return status
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

	def GetConfig(self, configId):
		# Get buffer
		bname = "config" + str(configId)
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		text = "start GetConfig function ({})".format(configId)
		self.local.add_log(text, "debug")
		cmd = "getconfig {configId}".format(configId=configId)
		result = self.liteClient.Run(cmd)
		start = result.find("ConfigParam")
		text = result[start:]
		data = self.Tlb2Json(text)

		# Set buffer
		self.SetFunctionBuffer(bname, data)
		return data
	#end define

	def GetConfig15(self):
		config = self.GetConfig(15)
		config15 = dict()
		config15["validatorsElectedFor"] = config["validators_elected_for"]
		config15["electionsStartBefore"] = config["elections_start_before"]
		config15["electionsEndBefore"] = config["elections_end_before"]
		config15["stakeHeldFor"] = config["stake_held_for"]
		return config15
	#end define

	def GetConfig17(self):
		config = self.GetConfig(17)
		config17 = dict()
		config17["minStake"] = ng2g(config["min_stake"]["amount"]["value"])
		config17["maxStake"] = ng2g(config["max_stake"]["amount"]["value"])
		config17["maxStakeFactor"] = config["max_stake_factor"]
		return config17
	#end define

	def GetConfig32(self):
		# Get buffer
		bname = "config32"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetConfig32 function", "debug")
		config32 = Dict()
		result = self.liteClient.Run("getconfig 32")
		config32["totalValidators"] = int(parse(result, "total:", ' '))
		config32["mainValidators"] = int(parse(result, "main:", ' '))
		config32["startWorkTime"] = int(parse(result, "utime_since:", ' '))
		config32["endWorkTime"] = int(parse(result, "utime_until:", ' '))
		lines = result.split('\n')
		validators = list()
		for line in lines:
			if "public_key:" in line:
				validatorAdnlAddr = parse(line, "adnl_addr:x", ')')
				pubkey = parse(line, "pubkey:x", ')')
				try:
					validatorWeight = int(parse(line, "weight:", ' '))
				except ValueError:
					validatorWeight = int(parse(line, "weight:", ')'))
				buff = Dict()
				buff["adnlAddr"] = validatorAdnlAddr
				buff["pubkey"] = pubkey
				buff["weight"] = validatorWeight
				validators.append(buff)
		config32["validators"] = validators

		# Set buffer
		self.SetFunctionBuffer(bname, config32)
		return config32
	#end define

	def GetConfig34(self):
		# Get buffer
		bname = "config34"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetConfig34 function", "debug")
		config34 = Dict()
		result = self.liteClient.Run("getconfig 34")
		config34["totalValidators"] = int(parse(result, "total:", ' '))
		config34["mainValidators"] = int(parse(result, "main:", ' '))
		config34["startWorkTime"] = int(parse(result, "utime_since:", ' '))
		config34["endWorkTime"] = int(parse(result, "utime_until:", ' '))
		config34["totalWeight"] = int(parse(result, "total_weight:", ' '))
		lines = result.split('\n')
		validators = list()
		for line in lines:
			if "public_key:" in line:
				validatorAdnlAddr = parse(line, "adnl_addr:x", ')')
				pubkey = parse(line, "pubkey:x", ')')
				try:
					validatorWeight = int(parse(line, "weight:", ' '))
				except ValueError:
					validatorWeight = int(parse(line, "weight:", ')'))
				buff = Dict()
				buff["adnlAddr"] = validatorAdnlAddr
				buff["pubkey"] = pubkey
				buff["weight"] = validatorWeight
				validators.append(buff)
		config34["validators"] = validators

		# Set buffer
		self.SetFunctionBuffer(bname, config34)
		return config34
	#end define

	def GetConfig36(self):
		# Get buffer
		bname = "config36"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		self.local.add_log("start GetConfig36 function", "debug")
		config36 = dict()
		try:
			result = self.liteClient.Run("getconfig 36")
			config36["totalValidators"] = int(parse(result, "total:", ' '))
			config36["startWorkTime"] = int(parse(result, "utime_since:", ' '))
			config36["endWorkTime"] = int(parse(result, "utime_until:", ' '))
			lines = result.split('\n')
			validators = list()
			for line in lines:
				if "public_key:" in line:
					validatorAdnlAddr = parse(line, "adnl_addr:x", ')')
					pubkey = parse(line, "pubkey:x", ')')
					validatorWeight = parse(line, "weight:", ' ')
					buff = dict()
					buff["adnlAddr"] = validatorAdnlAddr
					buff["pubkey"] = pubkey
					buff["weight"] = validatorWeight
					validators.append(buff)
			config36["validators"] = validators
		except:
			config36["validators"] = list()
		#end try

		# Set buffer
		self.SetFunctionBuffer(bname, config36)
		return config36
	#end define

	def CreateNewKey(self):
		self.local.add_log("start CreateNewKey function", "debug")
		result = self.validatorConsole.Run("newkey")
		key = parse(result, "created new key ", '\n')
		return key
	#end define

	def GetPubKeyBase64(self, key):
		self.local.add_log("start GetPubKeyBase64 function", "debug")
		result = self.validatorConsole.Run("exportpub " + key)
		validatorPubkey_b64 = parse(result, "got public key: ", '\n')
		return validatorPubkey_b64
	#end define

	def GetPubKey(self, key):
		self.local.add_log("start GetPubKey function", "debug")
		pubkey_b64 = self.GetPubKeyBase64(key)
		buff = pubkey_b64.encode("utf-8")
		buff = base64.b64decode(buff)
		buff = buff[4:]
		pubkey_hex = buff.hex()
		pubkey_hex = pubkey_hex.upper()
		return pubkey_hex
	#end define

	def AddKeyToValidator(self, key, startWorkTime, endWorkTime):
		self.local.add_log("start AddKeyToValidator function", "debug")
		output = False
		cmd = "addpermkey {key} {startWorkTime} {endWorkTime}".format(key=key, startWorkTime=startWorkTime, endWorkTime=endWorkTime)
		result = self.validatorConsole.Run(cmd)
		if ("success" in result):
			output = True
		return output
	#end define

	def AddKeyToTemp(self, key, endWorkTime):
		self.local.add_log("start AddKeyToTemp function", "debug")
		output = False
		result = self.validatorConsole.Run("addtempkey {key} {key} {endWorkTime}".format(key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output
	#end define

	def AddAdnlAddrToValidator(self, adnlAddr):
		self.local.add_log("start AddAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.Run("addadnl {adnlAddr} 0".format(adnlAddr=adnlAddr))
		if ("success" in result):
			output = True
		return output
	#end define

	def GetAdnlAddr(self):
		adnlAddr = self.local.db.get("adnlAddr")
		return adnlAddr
	#end define

	def AttachAdnlAddrToValidator(self, adnlAddr, key, endWorkTime):
		self.local.add_log("start AttachAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.Run("addvalidatoraddr {key} {adnlAddr} {endWorkTime}".format(adnlAddr=adnlAddr, key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output
	#end define

	def CreateConfigProposalRequest(self, offerHash, validatorIndex):
		self.local.add_log("start CreateConfigProposalRequest function", "debug")
		fileName = self.tempDir + self.nodeName + "proposal_validator-to-sign.req"
		args = ["config-proposal-vote-req.fif", "-i", validatorIndex, offerHash, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
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

	def CreateComplaintRequest(self, electionId, complaintHash, validatorIndex):
		self.local.add_log("start CreateComplaintRequest function", "debug")
		fileName = self.tempDir + "complaint_validator-to-sign.req"
		args = ["complaint-vote-req.fif", validatorIndex, electionId, complaintHash, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
		resultList = result.split('\n')
		i = 0
		start_index = 0
		for item in resultList:
			if "Creating a request to vote for complaint" in item:
				start_index = i
			i += 1
		var1 = resultList[start_index + 1]
		var2 = resultList[start_index + 2] # var2 not using
		return var1
	#end define

	def remove_proofs_from_complaint(self, input_file_name: str):
		self.local.add_log("start remove_proofs_from_complaint function", "debug")
		output_file_name = self.tempDir + "complaint-new.boc"
		fift_script = pkg_resources.resource_filename('mytoncore', 'complaints/remove-proofs-v2.fif')
		args = [fift_script, input_file_name, output_file_name]
		result = self.fift.Run(args)
		return output_file_name


	def PrepareComplaint(self, electionId, inputFileName):
		self.local.add_log("start PrepareComplaint function", "debug")
		fileName = self.tempDir + "complaint-msg-body.boc"
		args = ["envelope-complaint.fif", electionId, inputFileName, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", ')')
		return fileName
	#end define

	def CreateElectionRequest(self, addrB64, startWorkTime, adnlAddr, maxFactor):
		self.local.add_log("start CreateElectionRequest function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-to-sign.bin"
		args = ["validator-elect-req.fif", addrB64, startWorkTime, maxFactor, adnlAddr, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
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
		self.local.add_log("start GetValidatorSignature function", "debug")
		cmd = "sign {validatorKey} {var1}".format(validatorKey=validatorKey, var1=var1)
		result = self.validatorConsole.Run(cmd)
		validatorSignature = parse(result, "got signature ", '\n')
		return validatorSignature
	#end define

	def SignElectionRequestWithValidator(self, wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor):
		self.local.add_log("start SignElectionRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-query.boc"
		args = ["validator-elect-signed.fif", wallet.addrB64, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName
	#end define

	def SignBocWithWallet(self, wallet, boc_path, dest, coins, **kwargs):
		self.local.add_log("start SignBocWithWallet function", "debug")
		flags = kwargs.get("flags", list())
		subwalletDefault = 698983191 + wallet.workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwalletDefault)
		boc_mode = kwargs.get("boc_mode", "--body")

		# Balance checking
		account = self.GetAccount(wallet.addrB64)
		self.check_account_balance(account, coins + 0.1)

		# Bounceable checking
		destAccount = self.GetAccount(dest)
		bounceable = self.IsBounceableAddrB64(dest)
		if bounceable == False and destAccount.status == "active":
			flags += ["--force-bounce"]
			text = "Find non-bounceable flag, but destination account already active. Using bounceable flag"
			self.local.AddLog(text, "warning")
		elif "-n" not in flags and bounceable == True and destAccount.status != "active":
			raise Exception("Find bounceable flag, but destination account is not active. Use non-bounceable address or flag -n")
		#end if

		seqno = self.GetSeqno(wallet)
		result_file_path = self.tempDir + self.nodeName + wallet.name + "_wallet-query"
		if "v1" in wallet.version:
			fift_script = "wallet.fif"
			args = [fift_script, wallet.path, dest, seqno, coins, boc_mode, boc_path, result_file_path]
		elif "v2" in wallet.version:
			fift_script = "wallet-v2.fif"
			args = [fift_script, wallet.path, dest, seqno, coins, boc_mode, boc_path, result_file_path]
		elif "v3" in wallet.version:
			fift_script = "wallet-v3.fif"
			args = [fift_script, wallet.path, dest, subwallet, seqno, coins, boc_mode, boc_path, result_file_path]
		else:
			raise Exception(f"SignBocWithWallet error: Wallet version '{wallet.version}' is not supported")
		if flags:
			args += flags
		result = self.fift.Run(args)
		result_file_path = parse(result, "Saved to file ", ")")
		return result_file_path
	#end define

	def SendFile(self, filePath, wallet=None, **kwargs):
		self.local.add_log("start SendFile function: " + filePath, "debug")
		timeout = kwargs.get("timeout", 30)
		remove = kwargs.get("remove", True)
		duplicateSendfile = self.local.db.get("duplicateSendfile", True)
		telemetry = self.local.db.get("sendTelemetry", False)
		duplicateApi = self.local.db.get("duplicateApi", telemetry)
		if not os.path.isfile(filePath):
			raise Exception("SendFile error: no such file '{filePath}'".format(filePath=filePath))
		if timeout and wallet:
			wallet.oldseqno = self.GetSeqno(wallet)
		self.liteClient.Run("sendfile " + filePath)
		if duplicateSendfile:
			try:
				self.liteClient.Run("sendfile " + filePath, useLocalLiteServer=False)
				self.liteClient.Run("sendfile " + filePath, useLocalLiteServer=False)
			except: pass
		if duplicateApi:
			self.send_boc_toncenter(filePath)
		if timeout and wallet:
			self.WaitTransaction(wallet, timeout)
		if remove == True:
			os.remove(filePath)
	#end define

	def send_boc_toncenter(self, file_path: str):
		self.local.add_log('Start send_boc_toncenter function: ' + file_path, 'debug')
		with open(file_path, "rb") as f:
			boc = f.read()
			boc_b64 = base64.b64encode(boc).decode("utf-8")
		data = {"boc": boc_b64}
		network_name = self.GetNetworkName()
		if network_name == 'testnet':
			default_url = 'https://testnet.toncenter.com/api/v2/sendBoc'
		elif network_name == 'mainnet':
			default_url = 'https://toncenter.com/api/v2/sendBoc'
		else:
			default_url = None
		url = self.local.db.get("duplicateApiUrl", default_url)
		if url == None:
			return False
		result = requests.post(url=url, json=data)
		if result.status_code != 200:
			self.local.add_log(f'Failed to send boc to toncenter: {result.content}', 'info')
			return False
		self.local.add_log('Sent boc to toncenter', 'info')
		return True

	def WaitTransaction(self, wallet, timeout=30):
		self.local.add_log("start WaitTransaction function", "debug")
		timesleep = 3
		steps = timeout // timesleep
		for i in range(steps):
			time.sleep(timesleep)
			seqno = self.GetSeqno(wallet)
			if seqno != wallet.oldseqno:
				return
		raise Exception("WaitTransaction error: time out")
	#end define

	def GetReturnedStake(self, fullElectorAddr, inputAddr):
		self.local.add_log("start GetReturnedStake function", "debug")
		workchain, addr = self.ParseInputAddr(inputAddr)
		cmd = f"runmethodfull {fullElectorAddr} compute_returned_stake 0x{addr}"
		result = self.liteClient.Run(cmd)
		returnedStake = self.GetVarFromWorkerOutput(result, "result")
		returnedStake = returnedStake.replace(' ', '')
		returnedStake = parse(returnedStake, '[', ']')
		returnedStake = ng2g(returnedStake)
		return returnedStake
	#end define

	def ProcessRecoverStake(self):
		self.local.add_log("start ProcessRecoverStake function", "debug")
		resultFilePath = self.tempDir + self.nodeName + "recover-query"
		args = ["recover-stake.fif", resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath
	#end define

	def GetStake(self, account, args=None):
		stake = self.local.db.get("stake")
		usePool = self.using_pool()
		useController = self.using_liquid_staking()
		stakePercent = self.local.db.get("stakePercent", 99)
		vconfig = self.GetValidatorConfig()
		validators = vconfig.get("validators")
		config17 = self.GetConfig17()

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
				self.local.add_log("Specified stake must be a percentage or whole number", "error")
				return

			# Limit stake to maximum available amount minus 10 (for transaction fees)
			if stake > account.balance - 10:
				stake = account.balance - 10

		is_single_nominator = self.is_account_single_nominator(account)

		if stake is None and usePool and not is_single_nominator:
			stake = account.balance - 20
		if stake is None and useController:
			stake = account.balance - 50
		if stake is None:
			sp = stakePercent / 100
			if sp > 1 or sp < 0:
				self.local.add_log("Wrong stakePercent value. Using default stake.", "warning")
			elif len(vconfig.validators) == 0:
				stake = int(account.balance*sp/2)
				if stake < config17["minStake"]:  # not enough funds to divide them by 2
					stake = int(account.balance*sp)
			elif len(vconfig.validators) > 0:
				stake = int(account.balance*sp)

		# Check if we have enough coins
		if stake > config17["maxStake"]:
			text = "Stake is greater than the maximum value. Will be used the maximum stake."
			self.local.add_log(text, "warning")
			stake = config17["maxStake"]
		if config17["minStake"] > stake:
			text = "Stake less than the minimum stake. Minimum stake: {minStake}".format(minStake=config17["minStake"])
			# self.local.add_log(text, "error")
			raise Exception(text)
		if stake > account.balance:
			text = "Don't have enough coins. stake: {stake}, account balance: {balance}".format(stake=stake, balance=account.balance)
			# self.local.add_log(text, "error")
			raise Exception(text)

		return stake

	def GetMaxFactor(self):
		# Either use defined maxFactor, or set maximal allowed by config17
		maxFactor = self.local.db.get("maxFactor")
		if maxFactor is None:
			config17 = self.GetConfig17()
			maxFactor = config17["maxStakeFactor"] / 65536
		maxFactor = round(maxFactor, 1)
		return maxFactor
	#end define

	def GetValidatorWallet(self, mode="stake"):
		self.local.add_log("start GetValidatorWallet function", "debug")
		walletName = self.local.db.get("validatorWalletName")
		wallet = self.GetLocalWallet(walletName)
		return wallet
	#end define

	def ElectionEntry(self, args=None):
		usePool = self.using_pool()
		useController = self.using_liquid_staking()
		wallet = self.GetValidatorWallet()
		addrB64 = wallet.addrB64
		if wallet is None:
			raise Exception("Validator wallet not found")
		#end if

		self.local.add_log("start ElectionEntry function", "debug")
		# Check if validator is not synchronized
		validatorStatus = self.GetValidatorStatus()
		validatorOutOfSync = validatorStatus.get("outOfSync")
		if validatorOutOfSync > 60:
			self.local.add_log("Validator is not synchronized", "error")
			return
		#end if

		# Get startWorkTime and endWorkTime
		fullElectorAddr = self.GetFullElectorAddr()
		startWorkTime = self.GetActiveElectionId(fullElectorAddr)

		# Check if elections started
		if (startWorkTime == 0):
			self.local.add_log("Elections have not yet begun", "info")
			return
		#end if

		# Get ADNL address
		adnl_addr = self.GetAdnlAddr()
		adnl_addr_bytes = bytes.fromhex(adnl_addr)

		# Check wether it is too early to participate
		if "participateBeforeEnd" in self.local.db:
			now = time.time()
			if (startWorkTime - now) > self.local.db["participateBeforeEnd"] and \
			   (now + self.local.db["periods"]["elections"]) < startWorkTime:
				return
		#end if

		vconfig = self.GetValidatorConfig()

		have_adnl = False
		# Check if ADNL address is in the list
		for a in vconfig.adnl:
			if base64.b64decode(a.id) == adnl_addr_bytes:
				have_adnl = True
				break
		#end for
		if not have_adnl:
			raise Exception('ADNL address is not found')
		#end if

		# Check if election entry already completed
		entries = self.GetElectionEntries()
		if adnl_addr in entries:
			self.local.add_log("Elections entry already completed", "info")
			return
		#end if

		if usePool:
			pool = self.get_pool()
			addrB64 = pool.addrB64
		elif useController:
			controllerAddr = self.GetController(mode="stake")
			self.CheckController(controllerAddr)
			self.CreateLoanRequest(controllerAddr)
			addrB64 = controllerAddr

		# Calculate stake
		account = self.GetAccount(addrB64)
		stake = self.GetStake(account, args)

		# Calculate endWorkTime
		validatorsElectedFor = self.GetValidatorsElectedFor()
		endWorkTime = startWorkTime + validatorsElectedFor + 300 # 300 sec - margin of seconds

		# Create keys
		validatorKey = self.GetValidatorKeyByTime(startWorkTime, endWorkTime)
		validatorPubkey_b64  = self.GetPubKeyBase64(validatorKey)

		# Attach ADNL addr to validator
		self.AttachAdnlAddrToValidator(adnl_addr, validatorKey, endWorkTime)

		# Get max factor
		maxFactor = self.GetMaxFactor()

		# Create fift's. Continue with pool or walet
		if usePool:
			var1 = self.CreateElectionRequest(pool.addrB64, startWorkTime, adnl_addr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validatorKey, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithPoolWithValidator(pool, startWorkTime, adnl_addr, validatorPubkey_b64, validatorSignature, maxFactor, stake)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, pool.addrB64, 1.3)
			self.SendFile(resultFilePath, wallet)
		elif useController:
			var1 = self.CreateElectionRequest(controllerAddr, startWorkTime, adnl_addr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validatorKey, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithController(controllerAddr, startWorkTime, adnl_addr, validatorPubkey_b64, validatorSignature, maxFactor, stake)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, controllerAddr, 1.03)
			self.SendFile(resultFilePath, wallet)
		else:
			var1 = self.CreateElectionRequest(wallet.addrB64, startWorkTime, adnl_addr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validatorKey, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithValidator(wallet, startWorkTime, adnl_addr, validatorPubkey_b64, validatorSignature, maxFactor)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, stake)
			self.SendFile(resultFilePath, wallet)
		#end if

		# Save vars to json file
		self.SaveElectionVarsToJsonFile(wallet=wallet, account=account, stake=stake, maxFactor=maxFactor, fullElectorAddr=fullElectorAddr, startWorkTime=startWorkTime, validatorsElectedFor=validatorsElectedFor, endWorkTime=endWorkTime, validatorKey=validatorKey, validatorPubkey_b64=validatorPubkey_b64, adnlAddr=adnl_addr, var1=var1, validatorSignature=validatorSignature, validatorPubkey=validatorPubkey)
		self.local.add_log("ElectionEntry completed. Start work time: " + str(startWorkTime))

		self.clear_tmp()

	#end define

	def clear_tmp(self):
		start = time.time()
		count = 0
		week_ago = 60 * 60 * 24 * 7
		dir = self.tempDir
		for f in os.listdir(dir):
			ts = os.path.getmtime(os.path.join(dir, f))
			if ts < time.time() - week_ago:
				count += 1
				os.remove(os.path.join(dir, f))

		self.local.add_log(f"Removed {count} old files from tmp dir for {int(time.time() - start)} seconds", "info")

	def GetValidatorKeyByTime(self, startWorkTime, endWorkTime):
		self.local.add_log("start GetValidatorKeyByTime function", "debug")
		# Check temp key
		vconfig = self.GetValidatorConfig()
		for item in vconfig.validators:
			if item.get("election_date") == startWorkTime:
				validatorKey_b64 = item.get("id")
				validatorKey = base64.b64decode(validatorKey_b64).hex()
				validatorKey = validatorKey.upper()
				return validatorKey
		#end for

		# Create temp key
		validatorKey = self.CreateNewKey()
		self.AddKeyToValidator(validatorKey, startWorkTime, endWorkTime)
		self.AddKeyToTemp(validatorKey, endWorkTime)
		return validatorKey
	#end define

	def RecoverStake(self):
		wallet = self.GetValidatorWallet()
		if wallet is None:
			raise Exception("Validator wallet not found")
		#end if

		self.local.add_log("start RecoverStake function", "debug")
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.GetReturnedStake(fullElectorAddr, wallet.addrB64)
		if returnedStake == 0:
			self.local.add_log("You have nothing on the return stake", "debug")
			return
		#end if

		resultFilePath = self.ProcessRecoverStake()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, 1)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("RecoverStake completed")
	#end define

	def PoolRecoverStake(self, poolAddr):
		wallet = self.GetValidatorWallet()
		if wallet is None:
			raise Exception("Validator wallet not found")
		#end if

		self.local.add_log("start PoolRecoverStake function", "debug")
		resultFilePath = self.PoolProcessRecoverStake()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 1.2)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("PoolRecoverStake completed")
	#end define

	def PoolsUpdateValidatorSet(self):
		self.local.add_log("start PoolsUpdateValidatorSet function", "debug")
		wallet = self.GetValidatorWallet()
		pools = self.GetPools()
		for pool in pools:
			self.PoolUpdateValidatorSet(pool.addrB64, wallet)
	#end define

	def PoolUpdateValidatorSet(self, poolAddr, wallet):
		self.local.add_log("start PoolUpdateValidatorSet function", "debug")
		poolData = self.GetPoolData(poolAddr)
		if poolData is None:
			return
		#end if

		timeNow = int(time.time())
		config34 = self.GetConfig34()
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.GetReturnedStake(fullElectorAddr, poolAddr)
		pendingWithdraws = self.GetPendingWithdraws()
		if (poolData["state"] == 2 and
			poolData["validatorSetChangesCount"] < 2 and
			poolData["validatorSetChangeTime"] < config34["startWorkTime"]):
			self.PoolProcessUpdateValidatorSet(poolAddr, wallet)
			poolData = self.GetPoolData(poolAddr)
		if (returnedStake > 0 and
			poolData["state"] == 2 and
			poolData["validatorSetChangesCount"] >= 2 and
			timeNow - poolData["validatorSetChangeTime"] > poolData["stakeHeldFor"] + 60):
			self.PoolRecoverStake(poolAddr)
			poolData = self.GetPoolData(poolAddr)
		if (poolData["state"] == 0 and self.HasPoolWithdrawRequests(poolAddr)):
			self.PoolWithdrawRequests(poolAddr, wallet)
			poolData = self.GetPoolData(poolAddr)
		if (poolData["state"] == 0 and poolAddr in pendingWithdraws):
			self.HandlePendingWithdraw(pendingWithdraws, poolAddr)
	#end define

	def PoolProcessUpdateValidatorSet(self, poolAddr, wallet):
		self.local.add_log("start PoolProcessUpdateValidatorSet function", "debug")
		resultFilePath = self.tempDir + "pool-update-validator-set-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/update-validator-set.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 1.1)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("PoolProcessUpdateValidatorSet completed")
	#end define

	def PoolWithdrawRequests(self, poolAddr, wallet):
		self.local.add_log("start PoolWithdrawRequests function", "debug")
		resultFilePath = self.PoolProcessWihtdrawRequests()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 10)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("PoolWithdrawRequests completed")
	#end define

	def PoolProcessWihtdrawRequests(self):
		self.local.add_log("start PoolProcessWihtdrawRequests function", "debug")
		resultFilePath = self.tempDir + "pool-withdraw-requests-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/process-withdraw-requests.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath
	#end define

	def HasPoolWithdrawRequests(self, poolAddr):
		cmd = f"runmethodfull {poolAddr} has_withdraw_requests"
		result = self.liteClient.Run(cmd)
		buff = self.Result2List(result)
		data = int(buff[0])
		if data == -1:
			return True
		else:
			return False
	#end define

	def SaveElectionVarsToJsonFile(self, **kwargs):
		self.local.add_log("start SaveElectionVarsToJsonFile function", "debug")
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

	def CreateWallet(self, name, workchain=0, version="v1", **kwargs):
		self.local.add_log("start CreateWallet function", "debug")
		subwallet_default = 698983191 + workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwallet_default)
		wallet_path = self.walletsDir + name
		if os.path.isfile(wallet_path + ".pk") and "v3" not in version:
			self.local.add_log("CreateWallet error: Wallet already exists: " + name, "warning")
		else:
			fift_args = self.get_new_wallet_fift_args(version, workchain=workchain, 
				wallet_path=wallet_path, subwallet=subwallet)
			result = self.fift.Run(fift_args)
			if "Creating new" not in result:
				print(result)
				raise Exception("CreateWallet error")
			#end if
		wallet = self.GetLocalWallet(name, version)
		self.SetWalletVersion(wallet.addrB64, version)
		return wallet
	#end define

	def CreateHighWallet(self, name, **kwargs):
		workchain = kwargs.get("workchain", 0)
		subwallet_default = 698983191 + workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwallet_default)
		version = kwargs.get("version", "hv1")
		self.local.AddLog("start CreateHighWallet function", "debug")
		wallet_path = self.walletsDir + name
		if os.path.isfile(wallet_path + ".pk") and os.path.isfile(wallet_path + str(subwallet) + ".addr"):
			self.local.AddLog("CreateHighWallet error: Wallet already exists: " + name + str(subwallet), "warning")
		else:
			args = ["new-highload-wallet.fif", workchain, subwallet, wallet_path]
			result = self.fift.Run(args)
			if "Creating new high-load wallet" not in result:
				raise Exception("CreateHighWallet error")
			#end if
		hwallet = self.GetLocalWallet(name, version, subwallet)
		self.SetWalletVersion(hwallet.addrB64, version)
		return hwallet
	#end define

	def ActivateWallet(self, wallet):
		self.local.add_log("start ActivateWallet function", "debug")
		account = self.GetAccount(wallet.addrB64)
		if account.status == "empty":
			raise Exception("ActivateWallet error: account status is empty")
		elif account.status == "active":
			self.local.add_log("ActivateWallet warning: account status is active", "warning")
		else:
			self.SendFile(wallet.bocFilePath, wallet, remove=False)
	#end define

	def import_wallet_with_version(self, key, version, **kwargs):
		wallet_name = kwargs.get("wallet_name")
		workchain = kwargs.get("workchain", 0)
		subwallet_default = 698983191 + workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwallet_default)
		if type(key) == bytes:
			pk_bytes = key
		else:
			pk_bytes = base64.b64decode(key)
		if wallet_name == None:
			wallet_name = self.GenerateWalletName()
		wallet_path = self.walletsDir + wallet_name
		with open(wallet_path + ".pk", 'wb') as file:
			file.write(pk_bytes)
		fift_args = self.get_new_wallet_fift_args(version, workchain=workchain, 
			wallet_path=wallet_path, subwallet=subwallet)
		result = self.fift.Run(fift_args)
		if "Creating new" not in result:
			print(result)
			raise Exception("import_wallet_with_version error")
		wallet = self.GetLocalWallet(wallet_name, version)
		self.SetWalletVersion(wallet.addrB64, version)
		return wallet
	#end define

	def get_new_wallet_fift_args(self, version, **kwargs):
		workchain = kwargs.get("workchain")
		wallet_path = kwargs.get("wallet_path")
		subwallet = kwargs.get("subwallet")
		if "v1" in version:
			fift_script = "new-wallet.fif"
			args = [fift_script, workchain, wallet_path]
		elif "v2" in version:
			fift_script = "new-wallet-v2.fif"
			args = [fift_script, workchain, wallet_path]
		elif "v3" in version:
			fift_script = "new-wallet-v3.fif"
			args = [fift_script, workchain, subwallet, wallet_path]
		else:
			raise Exception(f"get_wallet_fift error: fift script for `{version}` not found")
		return args
	#end define

	def addr_b64_to_bytes(self, addr_b64):
		workchain, addr, bounceable = self.ParseAddrB64(addr_b64)
		workchain_bytes = int.to_bytes(workchain, 4, "big", signed=True)
		addr_bytes = bytes.fromhex(addr)
		result = addr_bytes + workchain_bytes
		return result
	#end define

	def GetWalletsNameList(self):
		self.local.add_log("start GetWalletsNameList function", "debug")
		walletsNameList = list()
		for fileName in os.listdir(self.walletsDir):
			if fileName.endswith(".addr"):
				fileName = fileName[:fileName.rfind('.')]
				pkFileName = self.walletsDir + fileName + ".pk"
				if os.path.isfile(pkFileName):
					walletsNameList.append(fileName)
		walletsNameList.sort()
		return walletsNameList
	#end define

	def GenerateWalletName(self):
		self.local.add_log("start GenerateWalletName function", "debug")
		index = 1
		index_str = str(index).rjust(3, '0')
		walletPrefix = "wallet_"
		indexList = list()
		walletName = walletPrefix + index_str
		walletsNameList = self.GetWalletsNameList()
		if walletName in walletsNameList:
			for item in walletsNameList:
				if item.startswith(walletPrefix):
					try:
						index = item[item.rfind('_')+1:]
						index = int(index)
						indexList.append(index)
					except: pass
			index = max(indexList) + 1
			index_str = str(index).rjust(3, '0')
			walletName = walletPrefix + index_str
		return walletName
	#end define

	def GetValidatorConfig(self):
		#self.local.add_log("start GetValidatorConfig function", "debug")
		result = self.validatorConsole.Run("getconfig")
		text = parse(result, "---------", "--------")
		vconfig = json.loads(text)
		return Dict(vconfig)
	#end define

	def GetOverlaysStats(self):
		self.local.add_log("start GetOverlaysStats function", "debug")
		resultFilePath = self.local.buffer.my_temp_dir + "getoverlaysstats.json"
		result = self.validatorConsole.Run(f"getoverlaysstatsjson {resultFilePath}")
		if "wrote stats" not in result:
			raise Exception(f"GetOverlaysStats error: {result}")
		file = open(resultFilePath)
		text = file.read()
		file.close()
		data = json.loads(text)
		return data
	#end define

	def GetWalletId(self, wallet):
		subwalletDefault = 698983191 + wallet.workchain # 0x29A9A317 + workchain
		cmd = f"runmethodfull {wallet.addrB64} wallet_id"
		result = self.liteClient.Run(cmd)
		result = self.GetVarFromWorkerOutput(result, "result")
		if result is None or "error" in result:
			return subwalletDefault
		subwallet = parse(result, '[', ']')
		subwallet = int(subwallet)
		return subwallet
	#end define

	def check_account_balance(self, account, coins):
		if not isinstance(account, Account):
			account = self.GetAccount(account)
		if account.balance < coins:
			raise Exception(f"Account {account.addrB64} balance is less than requested coins. Balance: {account.balance}, requested amount: {coins} (need {coins - account.balance} more)")
		# end if
	# end define

	def check_account_active(self, account):
		if not isinstance(account, Account):
			address = account
			account = self.GetAccount(account)
		else:
			address = account.addrB64
		if account.status != "active":
			raise Exception(f"Account {address} account is uninitialized")
		# end if
	# end define

	def MoveCoins(self, wallet, dest, coins, **kwargs):
		self.local.add_log("start MoveCoins function", "debug")
		flags = kwargs.get("flags", list())
		timeout = kwargs.get("timeout", 30)
		subwallet = kwargs.get("subwallet")
		if "v3" in wallet.version and subwallet is None:
			subwallet = self.GetWalletId(wallet)
		if coins == "all":
			mode = 130
			coins = 0
		elif coins == "alld":
			mode = 160
			coins = 0
		else:
			coins = float(coins)
			mode = 3
		#end if

		# Balance checking
		account = self.GetAccount(wallet.addrB64)
		self.check_account_balance(account, coins + 0.1)
		self.check_account_active(account)

		# Bounceable checking
		destAccount = self.GetAccount(dest)
		bounceable = self.IsBounceableAddrB64(dest)
		if bounceable == False and destAccount.status == "active":
			flags += ["-b"]
			text = "Find non-bounceable flag, but destination account already active. Using bounceable flag"
			self.local.add_log(text, "warning")
		elif "-n" not in flags and bounceable == True and destAccount.status != "active":
			raise Exception("Find bounceable flag, but destination account is not active. Use non-bounceable address or flag -n")
		#end if

		seqno = self.GetSeqno(wallet)
		resultFilePath = self.local.buffer.my_temp_dir + wallet.name + "_wallet-query"
		if "v1" in wallet.version:
			fiftScript = "wallet.fif"
			args = [fiftScript, wallet.path, dest, seqno, coins, "-m", mode, resultFilePath]
		elif "v2" in wallet.version:
			fiftScript = "wallet-v2.fif"
			args = [fiftScript, wallet.path, dest, seqno, coins, "-m", mode, resultFilePath]
		elif "v3" in wallet.version:
			fiftScript = "wallet-v3.fif"
			args = [fiftScript, wallet.path, dest, subwallet, seqno, coins, "-m", mode, resultFilePath]
		else:
			raise Exception(f"MoveCoins error: Wallet version '{wallet.version}' is not supported")
		if flags:
			args += flags
		result = self.fift.Run(args)
		savedFilePath = parse(result, "Saved to file ", ")")
		self.SendFile(savedFilePath, wallet, timeout=timeout)
	#end define



	def MoveCoinsFromHW(self, wallet, destList, **kwargs):
		self.local.add_log("start MoveCoinsFromHW function", "debug")
		flags = kwargs.get("flags")
		timeout = kwargs.get("timeout", 30)

		if len(destList) == 0:
			self.local.add_log("MoveCoinsFromHW warning: destList is empty, break function", "warning")
			return
		#end if

		orderFilePath = self.local.buffer.my_temp_dir + wallet.name + "_order.txt"
		lines = list()
		for dest, coins in destList:
			lines.append("SEND {dest} {coins}".format(dest=dest, coins=coins))
		text = "\n".join(lines)
		file = open(orderFilePath, 'wt')
		file.write(text)
		file.close()

		if "v1" in wallet.version:
			fiftScript = "highload-wallet.fif"
		elif "v2" in wallet.version:
			fiftScript = "highload-wallet-v2.fif"
		seqno = self.GetSeqno(wallet)
		resultFilePath = self.local.buffer.my_temp_dir + wallet.name + "_wallet-query"
		args = [fiftScript, wallet.path, wallet.subwallet, seqno, orderFilePath, resultFilePath]
		if flags:
			args += flags
		result = self.fift.Run(args)
		savedFilePath = parse(result, "Saved to file ", ")")
		self.SendFile(savedFilePath, wallet, timeout=timeout)
	#end define

	def GetValidatorKey(self):
		vconfig = self.GetValidatorConfig()
		validators = sorted(vconfig["validators"], key=lambda i: i['election_date'], reverse=True)
		for validator in validators:
			validatorId = validator["id"]
			key_bytes = base64.b64decode(validatorId)
			validatorKey = key_bytes.hex().upper()
			timestamp = get_timestamp()
			if validator["election_date"] < timestamp < validator["expire_at"]:
				return validatorKey
		raise Exception("GetValidatorKey error: validator key not found. Are you sure you are a validator?")
	#end define

	def GetElectionEntries(self, past=False):
		# Get buffer
		bname = "electionEntries" + str(past)
		buff = self.GetFunctionBuffer(bname)
		if buff:
			return buff
		#end if

		# Check if the elections are open
		entries = dict()
		fullElectorAddr = self.GetFullElectorAddr()
		electionId = self.GetActiveElectionId(fullElectorAddr)
		if past == False and electionId == 0:
			return entries
		#end if

		if past:
			config34 = self.GetConfig34()
			electionId = config34.get("startWorkTime")
			end = config34.get("endWorkTime")
			buff = end - electionId
			electionId = electionId - buff
			saveElections = self.GetSaveElections()
			entries = saveElections.get(str(electionId))
			return entries
		#end if

		# Get raw data
		self.local.add_log("start GetElectionEntries function", "debug")
		cmd = "runmethodfull {fullElectorAddr} participant_list_extended".format(fullElectorAddr=fullElectorAddr)
		result = self.liteClient.Run(cmd)
		rawElectionEntries = self.Result2List(result)

		# Get json
		# Parser by @skydev (https://github.com/skydev0h)
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
			adnlAddr = Dec2HexAddr(entry[1][3])
			item["adnlAddr"] = adnlAddr
			item["pubkey"] = Dec2HexAddr(entry[0])
			item["stake"] = ng2g(entry[1][0])
			item["maxFactor"] = round(entry[1][1] / 655.36) / 100.0
			item["walletAddr_hex"] = Dec2HexAddr(entry[1][2])
			item["walletAddr"] = self.AddrFull2AddrB64("-1:"+item["walletAddr_hex"])
			entries[adnlAddr] = item
		#end for

		# Set buffer
		self.SetFunctionBuffer(bname, entries)

		# Save elections
		electionId = str(electionId)
		saveElections = self.GetSaveElections()
		saveElections[electionId] = entries
		return entries
	#end define

	def GetSaveElections(self):
		timestamp = get_timestamp()
		saveElections = self.local.db.get("saveElections")
		if saveElections is None:
			saveElections = dict()
			self.local.db["saveElections"] = saveElections
		buff = saveElections.copy()
		for key, item in buff.items():
			diffTime = timestamp - int(key)
			if diffTime > 604800:
				saveElections.pop(key)
		return saveElections
	#end define

	def GetSaveElectionEntries(self, electionId):
		electionId = str(electionId)
		saveElections = self.GetSaveElections()
		result = saveElections.get(electionId)
		return result
	#end define

	def calculate_offer_pseudohash(self, offer_hash: str, param_id: int):
		config_val = self.GetConfig(param_id)
		pseudohash_bytes = offer_hash.encode() + json.dumps(config_val, sort_keys=True).encode()
		return hashlib.sha256(pseudohash_bytes).hexdigest()

	def GetOffers(self):
		self.local.add_log("start GetOffers function", "debug")
		fullConfigAddr = self.GetFullConfigAddr()
		# Get raw data
		cmd = "runmethodfull {fullConfigAddr} list_proposals".format(fullConfigAddr=fullConfigAddr)
		result = self.liteClient.Run(cmd)
		rawOffers = self.Result2List(result)
		rawOffers = rawOffers[0]
		config34 = self.GetConfig34()
		totalWeight = config34.get("totalWeight")

		# Get json
		offers = list()
		for offer in rawOffers:
			if len(offer) == 0:
				continue
			hash = str(offer[0])
			subdata = offer[1]

			# Create dict
			# parser from: https://github.com/ton-blockchain/ton/blob/dab7ee3f9794db5a6d32c895dbc2564f681d9126/crypto/smartcont/config-code.fc#L607
			item = Dict()
			item["config"] = Dict()
			item["hash"] = hash
			item["endTime"] = subdata[0] # *expires*
			item["critFlag"] = subdata[1] # *critical*
			param_id = subdata[2][0] # *param_id*
			item["config"]["id"] = param_id
			item["config"]["value"] = subdata[2][1] # *param_val*
			item["config"]["hash"] = subdata[2][2] # *param_hash*
			item["vsetId"] = subdata[3] # *vset_id*
			item["votedValidators"] = subdata[4] # *voters_list*
			weightRemaining = subdata[5] # *weight_remaining*
			item["roundsRemaining"] = subdata[6] # *rounds_remaining*
			item["wins"] = subdata[7] # *losses*
			item["losses"] = subdata[8] # *wins*
			requiredWeight = totalWeight * 3 / 4
			if len(item["votedValidators"]) == 0:
				weightRemaining = requiredWeight
			availableWeight = requiredWeight - weightRemaining
			item["weightRemaining"] = weightRemaining
			item["approvedPercent"] = round(availableWeight / totalWeight * 100, 3)
			item["isPassed"] = (weightRemaining < 0)
			#item["pseudohash"] = hashlib.sha256(param_val.encode()).hexdigest()
			item['pseudohash'] = self.calculate_offer_pseudohash(hash, param_id)
			offers.append(item)
		#end for
		return offers
	#end define

	def GetComplaints(self, electionId=None, past=False):
		# Get buffer
		bname = "complaints" + str(past)
		buff = self.GetFunctionBuffer(bname)
		if buff:
			return buff
		#end if

		# Calculate complaints time
		complaints = dict()
		fullElectorAddr = self.GetFullElectorAddr()
		if electionId is None:
			config32 = self.GetConfig32()
			electionId = config32.get("startWorkTime")
			end = config32.get("endWorkTime")
			buff = end - electionId
		if past:
			electionId = electionId - buff
			saveComplaints = self.GetSaveComplaints()
			complaints = saveComplaints.get(str(electionId))
			return complaints
		#end if

		# Get raw data
		self.local.add_log("start GetComplaints function", "debug")
		cmd = "runmethodfull {fullElectorAddr} list_complaints {electionId}".format(fullElectorAddr=fullElectorAddr, electionId=electionId)
		result = self.liteClient.Run(cmd)
		rawComplaints = self.Result2List(result)
		if rawComplaints is None:
			return complaints
		rawComplaints = rawComplaints[0]
		config34 = self.GetConfig34()
		totalWeight = config34.get("totalWeight")

		# Get json
		for complaint in rawComplaints:
			if len(complaint) == 0:
				continue
			chash = complaint[0]
			subdata = complaint[1]

			# Create dict
			# parser from: https://github.com/ton-blockchain/ton/blob/dab7ee3f9794db5a6d32c895dbc2564f681d9126/crypto/smartcont/elector-code.fc#L1149
			item = dict()
			buff = subdata[0] # *complaint*
			item["electionId"] = electionId
			item["hash"] = chash
			item["hash_hex"] = dec2hex(chash)
			pubkey = Dec2HexAddr(buff[0]) # *validator_pubkey*
			adnl = self.GetAdnlFromPubkey(pubkey)
			item["pubkey"] = pubkey
			item["adnl"] = adnl
			item["description"] = buff[1] # *description*
			item["createdTime"] = buff[2] # *created_at*
			item["severity"] = buff[3] # *severity*
			rewardAddr = buff[4]
			rewardAddr = "-1:" + Dec2HexAddr(rewardAddr)
			rewardAddr = self.AddrFull2AddrB64(rewardAddr)
			item["rewardAddr"] = rewardAddr # *reward_addr*
			item["paid"] = buff[5] # *paid*
			suggestedFine = buff[6] # *suggested_fine*
			item["suggestedFine"] = ng2g(suggestedFine)
			suggestedFinePart = buff[7] # *suggested_fine_part*
			item["suggestedFinePart"] = suggestedFinePart /256 *100
			votedValidators = subdata[1] # *voters_list*
			item["votedValidators"] = votedValidators
			item["vsetId"] = subdata[2] # *vset_id*
			weightRemaining = subdata[3] # *weight_remaining*
			requiredWeight = totalWeight * 2 / 3
			if len(votedValidators) == 0:
				weightRemaining = requiredWeight
			availableWeight = requiredWeight - weightRemaining
			item["weightRemaining"] = weightRemaining
			item["approvedPercent"] = round(availableWeight / totalWeight * 100, 3)
			item["isPassed"] = (weightRemaining < 0)
			pseudohash = pubkey + str(electionId)
			item["pseudohash"] = pseudohash
			complaints[chash] = item
		#end for

		# sort complaints by their creation time and hash
		complaints = dict(sorted(complaints.items(), key=lambda item: (item[1]["createdTime"], item[0])))

		# Set buffer
		self.SetFunctionBuffer(bname, complaints)

		# Save complaints
		if len(complaints) > 0:
			electionId = str(electionId)
			saveComplaints = self.GetSaveComplaints()
			saveComplaints[electionId] = complaints
		return complaints
	#end define

	def GetSaveComplaints(self):
		timestamp = get_timestamp()
		saveComplaints = self.local.db.get("saveComplaints")
		if saveComplaints is None:
			saveComplaints = dict()
			self.local.db["saveComplaints"] = saveComplaints
		buff = saveComplaints.copy()
		for key, item in buff.items():
			diffTime = timestamp - int(key)
			if diffTime > 604800:
				saveComplaints.pop(key)
		return saveComplaints
	#end define

	def GetSaveVl(self):
		timestamp = get_timestamp()
		save_vl = self.local.db.get("saveValidatorsLoad")
		if save_vl is None:
			save_vl = dict()
			self.local.db["saveValidatorsLoad"] = save_vl
		for key, item in list(save_vl.items()):
			diff_time = timestamp - int(key)
			if diff_time > 172800:  # 48 hours
				save_vl.pop(key)
		return save_vl
	#end define

	def GetAdnlFromPubkey(self, inputPubkey):
		config32 = self.GetConfig32()
		validators = config32["validators"]
		for validator in validators:
			adnl = validator["adnlAddr"]
			pubkey = validator["pubkey"]
			if pubkey == inputPubkey:
				return adnl
	#end define

	def GetComplaintsNumber(self):
		self.local.add_log("start GetComplaintsNumber function", "debug")
		result = dict()
		complaints = self.GetComplaints()
		voted_complaints = self.GetVotedComplaints(complaints)
		buff = 0
		for chash in complaints:
			if chash in voted_complaints:
				continue
			buff += 1
		result["all"] = len(complaints)
		result["new"] = buff
		return result
	#end define

	def SignProposalVoteRequestWithValidator(self, offerHash, validatorIndex, validatorPubkey_b64, validatorSignature):
		self.local.add_log("start SignProposalVoteRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + "proposal_vote-msg-body.boc"
		args = ["config-proposal-vote-signed.fif", "-i", validatorIndex, offerHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
		return fileName
	#end define

	def SignComplaintVoteRequestWithValidator(self, complaintHash, electionId, validatorIndex, validatorPubkey_b64, validatorSignature):
		self.local.add_log("start SignComplaintRequestWithValidator function", "debug")
		fileName = self.tempDir + "complaint_vote-msg-body.boc"
		args = ["complaint-vote-signed.fif", validatorIndex, electionId, complaintHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
		return fileName
	#end define

	def VoteOffer(self, offerHash):
		self.local.add_log("start VoteOffer function", "debug")
		fullConfigAddr = self.GetFullConfigAddr()
		wallet = self.GetValidatorWallet(mode="vote")
		validatorKey = self.GetValidatorKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)
		validatorIndex = self.GetValidatorIndex()
		offer = self.GetOffer(offerHash)
		if validatorIndex in offer.get("votedValidators"):
			self.local.add_log("Proposal already has been voted", "debug")
			return
		self.add_save_offer(offer)
		var1 = self.CreateConfigProposalRequest(offerHash, validatorIndex)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		resultFilePath = self.SignProposalVoteRequestWithValidator(offerHash, validatorIndex, validatorPubkey_b64, validatorSignature)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullConfigAddr, 1.5)
		self.SendFile(resultFilePath, wallet)
	#end define

	def VoteComplaint(self, electionId, complaintHash):
		self.local.add_log("start VoteComplaint function", "debug")
		complaintHash = int(complaintHash)
		fullElectorAddr = self.GetFullElectorAddr()
		wallet = self.GetValidatorWallet(mode="vote")
		validatorKey = self.GetValidatorKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)
		validatorIndex = self.GetValidatorIndex()
		var1 = self.CreateComplaintRequest(electionId, complaintHash, validatorIndex)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		resultFilePath = self.SignComplaintVoteRequestWithValidator(complaintHash, electionId, validatorIndex, validatorPubkey_b64, validatorSignature)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, 1.5)
		self.SendFile(resultFilePath, wallet)
	#end define

	def SaveComplaints(self, electionId):
		self.local.add_log("start SaveComplaints function", "debug")
		filePrefix = self.tempDir + "scheck_"
		cmd = "savecomplaints {electionId} {filePrefix}".format(electionId=electionId, filePrefix=filePrefix)
		result = self.liteClient.Run(cmd)
		lines = result.split('\n')
		complaintsHashes = list()
		for line in lines:
			if "SAVE_COMPLAINT" in line:
				buff = line.split('\t')
				chash = buff[2]
				validatorPubkey = buff[3]
				createdTime = buff[4]
				filePath = buff[5]
				ok = self.CheckComplaint(filePath)
				if ok is True:
					complaintsHashes.append(chash)
		return complaintsHashes
	#end define

	def CheckComplaint(self, file_path: str):
		self.local.add_log("start CheckComplaint function", "debug")
		cmd = "loadproofcheck {filePath}".format(filePath=file_path)
		result = self.liteClient.Run(cmd, timeout=30)
		lines = result.split('\n')
		ok = False
		for line in lines:
			if "COMPLAINT_VOTE_FOR" in line:
				buff = line.split('\t')
				chash = buff[1]
				ok_buff = buff[2]
				if ok_buff == "YES":
					ok = True
		return ok
	#end define

	def get_valid_complaints(self, complaints: dict, election_id: int):
		self.local.add_log("start get_valid_complaints function", "debug")
		config32 = self.GetConfig32()
		start = config32.get("startWorkTime")
		assert start == election_id, 'provided election_id != election_id from config32'
		end = config32.get("endWorkTime")
		validators_load = self.GetValidatorsLoad(start, end - 60, saveCompFiles=True)
		voted_complaints = self.GetVotedComplaints(complaints)
		voted_complaints_pseudohashes = [complaint['pseudohash'] for complaint in voted_complaints.values()]
		result = {}
		for complaint in complaints.values():
			if complaint['pseudohash'] in voted_complaints_pseudohashes or complaint['pseudohash'] in result:
				self.local.add_log(f"skip checking complaint {complaint['hash_hex']}: "
								   f"complaint with this pseudohash ({complaint['pseudohash']})"
								   f" has already been voted", "debug")
				continue
			# check that complaint is valid

			if complaint['electionId'] != start:
				self.local.add_log(f"skip checking complaint {complaint['hash_hex']}: "
								   f"election_id ({election_id}) doesn't match with "
								   f"start work time ({config32.get('startWorkTime')})", "info")
				continue

			exists = False
			for item in validators_load.values():
				if 'fileName' not in item:
					continue
				pubkey = item.get("pubkey")
				if pubkey is None:
					continue
				pseudohash = pubkey + str(election_id)
				if pseudohash == complaint['pseudohash']:
					exists = True
					vid = item['id']
					break

			if not exists:
				self.local.add_log(f"complaint {complaint['hash_hex']} declined: complaint info was not found, probably it's wrong", "info")
				continue

			if vid >= config32['mainValidators']:
				self.local.add_log(f"complaint {complaint['hash_hex']} declined: complaint created for non masterchain validator", "info")
				continue

			# check complaint fine value
			if complaint['suggestedFine'] != 101:  # https://github.com/ton-blockchain/ton/blob/5847897b3758bc9ea85af38e7be8fc867e4c133a/lite-client/lite-client.cpp#L3708
				self.local.add_log(f"complaint {complaint['hash_hex']} declined: complaint fine value is {complaint['suggestedFine']} ton", "info")
				continue
			if complaint['suggestedFinePart'] != 0:  # https://github.com/ton-blockchain/ton/blob/5847897b3758bc9ea85af38e7be8fc867e4c133a/lite-client/lite-client.cpp#L3709
				self.local.add_log(f"complaint {complaint['hash_hex']} declined: complaint fine part value is {complaint['suggestedFinePart']} ton", "info")
				continue

			result[complaint['pseudohash']] = complaint
		return result

	def GetOnlineValidators(self):
		onlineValidators = list()
		validators = self.GetValidatorsList(fast=True)
		for validator in validators:
			online = validator.get("online")
			if online is True:
				onlineValidators.append(validator)
		if len(onlineValidators) == 0:
			onlineValidators = None
		return onlineValidators
	#end define

	def GetValidatorsLoad(self, start, end, saveCompFiles=False) -> dict:
		# Get buffer
		bname = f"validatorsLoad{start}{end}"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if
		text = "start GetValidatorsLoad function ({}, {})".format(start, end)
		self.local.add_log(text, "debug")
		if saveCompFiles is True:
			filePrefix = self.tempDir + f"checkload_{start}_{end}"
		else:
			filePrefix = ""
		cmd = f"checkloadall {start} {end} {filePrefix}"
		result = self.liteClient.Run(cmd, timeout=30)
		lines = result.split('\n')
		data = dict()
		for line in lines:
			if "val" in line and "pubkey" in line:
				buff = line.split(' ')
				vid = buff[1]
				vid = vid.replace('#', '')
				vid = vid.replace(':', '')
				vid = int(vid)
				pubkey = buff[3]
				pubkey = pubkey.replace(',', '')
				blocksCreated_buff = buff[6]
				blocksCreated_buff = blocksCreated_buff.replace('(', '')
				blocksCreated_buff = blocksCreated_buff.replace(')', '')
				blocksCreated_buff = blocksCreated_buff.split(',')
				masterBlocksCreated = float(blocksCreated_buff[0])
				workBlocksCreated = float(blocksCreated_buff[1])
				blocksExpected_buff = buff[8]
				blocksExpected_buff = blocksExpected_buff.replace('(', '')
				blocksExpected_buff = blocksExpected_buff.replace(')', '')
				blocksExpected_buff = blocksExpected_buff.split(',')
				masterBlocksExpected = float(blocksExpected_buff[0])
				workBlocksExpected = float(blocksExpected_buff[1])
				if masterBlocksExpected == 0:
					mr = 0
				else:
					mr = masterBlocksCreated / masterBlocksExpected
				if workBlocksExpected == 0:
					wr = 0
				else:
					wr = workBlocksCreated / workBlocksExpected
				r = (mr + wr) / 2
				efficiency = round(r * 100, 2)
				if efficiency > 10:
					online = True
				else:
					online = False
				item = dict()
				item["id"] = vid
				item["pubkey"] = pubkey
				item["masterBlocksCreated"] = masterBlocksCreated
				item["workBlocksCreated"] = workBlocksCreated
				item["masterBlocksExpected"] = masterBlocksExpected
				item["workBlocksExpected"] = workBlocksExpected
				item["mr"] = mr
				item["wr"] = wr
				item["efficiency"] = efficiency
				item["online"] = online

				# Get complaint file
				index = lines.index(line)
				nextIndex = index + 2
				if nextIndex < len(lines):
					nextLine = lines[nextIndex]
					if "COMPLAINT_SAVED" in nextLine:
						buff = nextLine.split('\t')
						item["var1"] = buff[1]
						item["var2"] = buff[2]
						item["fileName"] = buff[3]
				data[vid] = item
		#end for

		# Set buffer
		self.SetFunctionBuffer(bname, data)
		return data
	#end define

	def GetValidatorsList(self, past=False, fast=False):
		# Get buffer
		bname = "validatorsList" + str(past)
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		timestamp = get_timestamp()
		end = timestamp - 60
		config = self.GetConfig34()
		if fast:
			start = end - 1000
		else:
			start = config.get("startWorkTime")
		if past:
			config = self.GetConfig32()
			start = config.get("startWorkTime")
			end = config.get("endWorkTime") - 60
			save_vl = self.GetSaveVl()
			start_str = str(start)
			if start_str in save_vl:
				return save_vl[start_str]
		#end if

		validatorsLoad = self.GetValidatorsLoad(start, end)
		validators = config["validators"]
		electionId = config.get("startWorkTime")
		saveElectionEntries = self.GetSaveElectionEntries(electionId)
		for vid in range(len(validators)):
			validator = validators[vid]
			adnlAddr = validator["adnlAddr"]
			if len(validatorsLoad) > 0:
				validator["mr"] = validatorsLoad[vid]["mr"]
				validator["wr"] = validatorsLoad[vid]["wr"]
				validator["efficiency"] = validatorsLoad[vid]["efficiency"]
				validator["online"] = validatorsLoad[vid]["online"]
				validator["blocks_created"] = validatorsLoad[vid]["masterBlocksCreated"] + validatorsLoad[vid]["workBlocksCreated"]
				validator["blocks_expected"] = validatorsLoad[vid]["masterBlocksExpected"] + validatorsLoad[vid]["workBlocksExpected"]
				validator["is_masterchain"] = False
				if vid < config["mainValidators"]:
					validator["is_masterchain"] = True
				if not validator["is_masterchain"]:
					validator["efficiency"] = round(validator["wr"] * 100, 2)
			if saveElectionEntries and adnlAddr in saveElectionEntries:
				validator["walletAddr"] = saveElectionEntries[adnlAddr]["walletAddr"]
		#end for

		# Set buffer
		self.SetFunctionBuffer(bname, validators)
		if past:
			save_vl = self.GetSaveVl()
			save_vl[str(start)] = validators
		return validators
	#end define

	def CheckValidators(self, start, end):
		self.local.add_log("start CheckValidators function", "debug")
		electionId = start
		complaints = self.GetComplaints(electionId)
		valid_complaints = self.get_valid_complaints(complaints, electionId)
		voted_complaints = self.GetVotedComplaints(complaints)
		voted_complaints_pseudohashes = [complaint['pseudohash'] for complaint in voted_complaints.values()]
		data = self.GetValidatorsLoad(start, end, saveCompFiles=True)
		fullElectorAddr = self.GetFullElectorAddr()
		wallet = self.GetValidatorWallet(mode="vote")
		config = self.GetConfig32()

		# Check wallet and balance
		if wallet is None:
			raise Exception("Validator wallet not fond")
		account = self.GetAccount(wallet.addrB64)
		if account.balance < 300:
			raise Exception("Validator wallet balance must be greater than 300")
		for key, item in data.items():
			fileName = item.get("fileName")
			if fileName is None:
				continue
			var1 = item.get("var1")
			var2 = item.get("var2")
			pubkey = item.get("pubkey")
			pseudohash = pubkey + str(electionId)
			if pseudohash in valid_complaints or pseudohash in voted_complaints_pseudohashes:  # do not create complaints that already created or voted by ourself
				continue
			if item['id'] >= config['mainValidators']:  # do not create complaints for non-masterchain validators
				continue
			# Create complaint
			fileName = self.remove_proofs_from_complaint(fileName)
			fileName = self.PrepareComplaint(electionId, fileName)
			fileName = self.SignBocWithWallet(wallet, fileName, fullElectorAddr, 300)
			self.SendFile(fileName, wallet)
			self.local.add_log("var1: {}, var2: {}, pubkey: {}, election_id: {}".format(var1, var2, pubkey, electionId), "debug")
	#end define

	def GetOffer(self, offerHash):
		self.local.add_log("start GetOffer function", "debug")
		offers = self.GetOffers()
		for offer in offers:
			if offerHash == offer.get("hash"):
				return offer
		raise Exception("GetOffer error: offer not found.")
	#end define

	def GetOffersNumber(self):
		self.local.add_log("start GetOffersNumber function", "debug")
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

	def GetValidatorIndex(self, adnlAddr=None):
		config34 = self.GetConfig34()
		validators = config34.get("validators")
		if adnlAddr is None:
			adnlAddr = self.GetAdnlAddr()
		index = 0
		for validator in validators:
			searchAdnlAddr = validator.get("adnlAddr")
			if adnlAddr == searchAdnlAddr:
				return index
			index += 1
		self.local.add_log("GetValidatorIndex warning: index not found.", "warning")
		return -1
	#end define

	def GetValidatorEfficiency(self, adnlAddr=None):
		self.local.add_log("start GetValidatorEfficiency function", "debug")
		validators = self.GetValidatorsList()
		if adnlAddr is None:
			adnlAddr = self.GetAdnlAddr()
		for validator in validators:
			searchAdnlAddr = validator.get("adnlAddr")
			if adnlAddr == searchAdnlAddr:
				efficiency = validator.get("efficiency")
				return efficiency
		self.local.add_log("GetValidatorEfficiency warning: efficiency not found.", "warning")
	#end define

	def GetDbUsage(self):
		path = "/var/ton-work/db"
		data = psutil.disk_usage(path)
		return data.percent
	#end define

	def GetDbSize(self, exceptions="log"):
		self.local.add_log("start GetDbSize function", "debug")
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

	def check_adnl(self):
		telemetry = self.local.db.get("sendTelemetry", False)
		check_adnl = self.local.db.get("checkAdnl", telemetry)
		if not check_adnl:
			return
		url = 'http://45.129.96.53/adnl_check'
		try:
			data = self.get_local_adnl_data()
			response = requests.post(url, json=data, timeout=5).json()
		except Exception as e:
			self.local.add_log(f'Failed to check adnl connection: {type(e)}: {e}', 'error')
			return False
		result = response.get("ok")
		if not result:
			self.local.add_log(f'Failed to check adnl connection to local node: {response.get("message")}', 'error')
		return result
	#end define

	def get_local_adnl_data(self):

		def int2ip(dec):
			import socket
			return socket.inet_ntoa(struct.pack("!i", dec))

		vconfig = self.GetValidatorConfig()

		data = {"host": int2ip(vconfig["addrs"][0]["ip"]), "port": vconfig["addrs"][0]["port"]}

		dht_id = vconfig["dht"][0]["id"]
		dht_id_hex = base64.b64decode(dht_id).hex().upper()

		result = self.validatorConsole.Run(f"exportpub {dht_id_hex}")
		pubkey = parse(result, "got public key: ", "\n")
		data["pubkey"] = base64.b64encode(base64.b64decode(pubkey)[4:]).decode()
		return data
	#end define

	def Result2List(self, text):
		buff = parse(text, "result:", "\n")
		if buff is None or "error" in buff:
			return
		buff = buff.replace(')', ']')
		buff = buff.replace('(', '[')
		buff = buff.replace(']', ' ] ')
		buff = buff.replace('[', ' [ ')
		buff = buff.replace('bits:', '')
		buff = buff.replace('refs:', '')
		buff = buff.replace('.', '')
		buff = buff.replace(';', '')
		arr = buff.split()

		# Get good raw data
		output = ""
		arrLen = len(arr)
		for i in range(arrLen):
			item = arr[i]
			if '{' in item or '}' in item:
				item = f"\"{item}\""
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
			elif i+1 == arrLen:
				output += item
			else:
				output += item + ', '
		#end for

		data = json.loads(output)
		return data
	#end define

	def Result2Dict(self, result):
		rawAny = False
		data = dict()
		tabSpaces = 2
		parenElementsList = list()
		lines = result.split('\n')
		for line in lines:
			firstSpacesCount = self.GetFirstSpacesCount(line)
			deep = firstSpacesCount // tabSpaces
			line = line.lstrip()
			if "raw@Any" in line:
				rawAny = True
			if rawAny == True and ')' in line:
				rawAny = False
			if line[:2] == "x{" and rawAny == False:
				continue
			if deep == 0:
				data[line] = dict()
				parenElementsList = [line]
			else:
				buff = data
				parenElementsList = parenElementsList[:deep]
				for item in parenElementsList:
					buff = buff[item]
				buff[line] = dict()
				parenElementsList.append(line)
			#end if
		#end for
		return data
	#end define

	def GetFirstSpacesCount(self, line):
		result = 0
		for item in line:
			if item == ' ':
				result += 1
			else:
				break
		#end for
		return result
	#end define

	def GetVarFromDict(self, data, search):
		arr = search.split('.')
		search2 = arr.pop()
		for search in arr:
			data = self.GetItemFromDict(data, search)
		text = self.GetKeyFromDict(data, search2)
		result = self.GetVar(text, search2)
		try:
			result = int(result)
		except: pass
		return result
	#end define

	def GetVar(self, text, search):
		if search is None or text is None:
			return
		if search not in text:
			return
		text = text[text.find(search) + len(search):]
		if text[0] in [':', '=', ' ']:
			text = text[1:]
		search2 = ')'
		if search2 in text:
			text = text[:text.find(search2)]
		search2 = ' '
		if search2 in text:
			text = text[:text.find(search2)]
		return text
	#end define

	def GetKeyFromDict(self, data, search):
		if data is None:
			return None
		for key, item in data.items():
			if search in key:
				return key
			#end if
		#end for
		return None
	#end define

	def GetItemFromDict(self, data, search):
		if data is None:
			return None
		for key, item in data.items():
			if search in key:
				return item
			#end if
		#end for
		return None
	#end define

	def AddBookmark(self, bookmark):
		if "bookmarks" not in self.local.db:
			self.local.db["bookmarks"] = list()
		#end if
		self.local.db["bookmarks"].append(bookmark)
		self.local.save()
	#end define

	def GetBookmarks(self):
		bookmarks = self.local.db.get("bookmarks")
		if bookmarks is not None:
			for bookmark in bookmarks:
				self.WriteBookmarkData(bookmark)
		return bookmarks
	#end define

	def DeleteBookmark(self, name):
		bookmarks = self.local.db.get("bookmarks")
		for bookmark in bookmarks:
			bookmark_name = bookmark.get("name")
			if name == bookmark_name:
				bookmarks.remove(bookmark)
				self.local.save()
				return
		raise Exception("DeleteBookmark error: Bookmark not found")
	#end define

	def WriteBookmarkData(self, bookmark):
		addr = bookmark.get("addr")
		account = self.GetAccount(addr)
		if account.status == "empty":
			data = "empty"
		else:
			data = account.balance
		bookmark["data"] = data
	#end define

	def offers_gc(self, save_offers):
		current_offers = self.GetOffers()
		current_offers_hashes = [offer.get("hash") for offer in current_offers]
		for offer_hash, offer in list(save_offers.items()):
			if offer_hash not in current_offers_hashes:
				if isinstance(offer, list):
					param_id = offer[1]
					if param_id is not None and offer[0] != self.calculate_offer_pseudohash(offer_hash, param_id):
						# param has been changed so no need to keep anymore
						save_offers.pop(offer_hash)
				else:  # old version of offer in db
					save_offers.pop(offer_hash)
		return save_offers

	def GetSaveOffers(self):
		bname = "saveOffers"
		save_offers = self.local.db.get(bname)
		if save_offers is None or isinstance(save_offers, list):
			save_offers = dict()
			self.local.db[bname] = save_offers
		self.offers_gc(save_offers)
		return save_offers
	#end define

	def add_save_offer(self, offer):
		offer_hash = offer.get("hash")
		offer_pseudohash = offer.get("pseudohash")
		save_offers = self.GetSaveOffers()
		if offer_hash not in save_offers:
			save_offers[offer_hash] = [offer_pseudohash, offer.get('config', {}).get("id")]
			self.local.save()
	#end define

	def GetVotedComplaints(self, complaints: dict):
		result = {}
		validator_index = self.GetValidatorIndex()
		for chash, complaint in complaints.items():
			voted_validators = complaint.get("votedValidators")
			if validator_index in voted_validators:
				result[chash] = complaint
		return result
	#end define

	def get_destination_addr(self, destination):
		if self.IsAddrB64(destination):
			pass
		elif self.IsAddrFull(destination):
			destination = self.AddrFull2AddrB64(destination)
		else:
			wallets_name_list = self.GetWalletsNameList()
			if destination in wallets_name_list:
				wallet = self.GetLocalWallet(destination)
				destination = wallet.addrB64
		return destination
	# end define

	def AddrFull2AddrB64(self, addrFull, bounceable=True):
		if addrFull is None or "None" in addrFull:
			return
		testnet = self.IsTestnet()
		buff = addrFull.split(':')
		workchain = int(buff[0])
		addr = buff[1]
		if len(addr) != 64:
			raise Exception("AddrFull2AddrB64 error: Invalid length of hexadecimal address")
		#end if

		# Create base64 address
		b = bytearray(36)
		b[0] = 0x51 - bounceable * 0x40 + testnet * 0x80
		b[1] = workchain % 256
		b[2:34] = bytearray.fromhex(addr)
		buff = bytes(b[:34])
		crc = crc16.xmodem(buff)
		b[34] = crc >> 8
		b[35] = crc & 0xff
		result = base64.b64encode(b)
		result = result.decode()
		result = result.replace('+', '-')
		result = result.replace('/', '_')
		return result
	#end define

	def ParseAddrB64(self, addrB64):
		# Get buffer
		fname = addrB64
		buff = self.GetFunctionBuffer(fname, timeout=1)
		if buff:
			return buff
		#end if

		buff = addrB64.replace('-', '+')
		buff = buff.replace('_', '/')
		buff = buff.encode()
		b = base64.b64decode(buff)
		testnet_int = (b[0] & 0x80)
		if testnet_int == 0:
			testnet = False
		else:
			testnet = True
		bounceable_int = (b[0] & 0x40)
		if bounceable_int != 0:
			bounceable = False
		else:
			bounceable = True
		networkTestnet = self.IsTestnet()
		if testnet != networkTestnet:
			text = f"ParseAddrB64 warning: testnet flag do not match. Addr: {testnet}, Network: {networkTestnet}"
			self.local.add_log(text, "warning")
		#end if

		# get wc and addr
		workchain_bytes = b[1:2]
		addr_bytes = b[2:34]
		crc_bytes = b[34:36]
		crc_data = bytes(b[:34])
		crc = int.from_bytes(crc_bytes, "big")
		check_crc = crc16.xmodem(crc_data)
		if crc != check_crc:
			raise Exception("ParseAddrB64 error: crc do not match")
		#end if

		workchain = int.from_bytes(workchain_bytes, "big", signed=True)
		addr = addr_bytes.hex()

		# Set buffer
		data = (workchain, addr, bounceable)
		self.SetFunctionBuffer(fname, data)
		return data
	#end define

	def ParseAddrFull(self, addrFull):
		buff = addrFull.split(':')
		workchain = int(buff[0])
		addr = buff[1]
		addrBytes = bytes.fromhex(addr)
		if len(addrBytes) != 32:
			raise Exception("ParseAddrFull error: addrBytes is not 32 bytes")
		return workchain, addr
	#end define

	def ParseInputAddr(self, inputAddr):
		if self.IsAddrB64(inputAddr):
			workchain, addr, bounceable = self.ParseAddrB64(inputAddr)
			return workchain, addr
		elif self.IsAddrFull(inputAddr):
			workchain, addr = self.ParseAddrFull(inputAddr)
			return workchain, addr
		else:
			raise Exception(f"ParseInputAddr error: input address is not a adress: {inputAddr}")
	#end define

	def IsBounceableAddrB64(self, inputAddr):
		bounceable = None
		try:
			workchain, addr, bounceable = self.ParseAddrB64(inputAddr)
		except: pass
		return bounceable
	#en define

	def GetNetLoadAvg(self, statistics=None):
		if statistics is None:
			statistics = self.local.db.get("statistics")
		if statistics:
			netLoadAvg = statistics.get("netLoadAvg")
		else:
			netLoadAvg = [-1, -1, -1]
		return netLoadAvg
	#end define

	def GetTpsAvg(self, statistics=None):
		if statistics is None:
			statistics = self.local.db.get("statistics")
		if statistics:
			tpsAvg = statistics.get("tpsAvg")
		else:
			tpsAvg = [-1, -1, -1]
		return tpsAvg
	#end define

	def GetStatistics(self, name, statistics=None):
		if statistics is None:
			statistics = self.local.db.get("statistics")
		if statistics:
			data = statistics.get(name)
		else:
			data = [-1, -1, -1]
		return data
	#end define

	def GetSettings(self, name):
		# self.local.load_db()
		result = self.local.db.get(name)
		return result
	#end define

	def SetSettings(self, name, data):
		try:
			data = json.loads(data)
		except: pass
		self.local.db[name] = data
		self.local.save()
	#end define

	def migrate_to_modes(self):
		usePool = self.local.db.get('usePool')
		if usePool is not None:
			if usePool:
				self.enable_mode('nominator-pool')
			self.local.db.pop('usePool')

		useController = self.local.db.get('useController')
		if useController is not None:
			if useController:
				self.enable_mode('liquid-staking')
			self.local.db.pop('useController')
		self.local.save()

	def rollback_modes(self):
		self.local.db['usePool'] = self.get_mode_value('nominator-pool')
		self.local.db['useController'] = self.get_mode_value('liquid-staking')
		self.local.db.pop('modes')
		self.local.save()

	def get_modes(self):
		current_modes = self.local.db.get('modes', {})
		if 'modes' not in self.local.db:
			self.local.db['modes'] = current_modes
			self.migrate_to_modes()
		for name, mode in MODES.items():
			if name not in current_modes:
				current_modes[name] = mode.default_value  # assign default mode value
		return current_modes

	def check_enable_mode(self, name):
		if name == 'liteserver':
			if self.using_validator():
				raise Exception(f'Cannot enable liteserver mode while validator mode is enabled. '
								f'Use `disable_mode validator` first.')
		if name == 'validator':
			if self.using_liteserver():
				raise Exception(f'Cannot enable validator mode while liteserver mode is enabled. '
								f'Use `disable_mode liteserver` first.')

	def enable_mode(self, name):
		if name not in MODES:
			raise Exception(f'Unknown module name: {name}. Available modes: {", ".join(MODES)}')
		self.check_enable_mode(name)
		current_modes = self.get_modes()
		current_modes[name] = True
		self.local.save()

	def disable_mode(self, name):
		current_modes = self.get_modes()
		if name not in current_modes:
			raise Exception(f'Unknown module name: {name}. Available modes: {", ".join(MODES)}')
		current_modes[name] = False
		self.local.save()

	def get_mode_value(self, name):
		current_modes = self.get_modes()
		if name not in current_modes:
			raise Exception(f'No mode named {name} found in current modes: {current_modes}')
		return current_modes[name]

	def using_nominator_pool(self):
		return self.get_mode_value('nominator-pool')

	def using_single_nominator(self):
		return self.get_mode_value('single-nominator')

	def using_liquid_staking(self):
		return self.get_mode_value('liquid-staking')

	def using_pool(self) -> bool:
		return self.using_nominator_pool() or self.using_single_nominator()

	def using_validator(self):
		return self.get_mode_value('validator')

	def using_liteserver(self):
		return self.get_mode_value('liteserver')

	def Tlb2Json(self, text):
		# Заменить скобки
		start = 0
		end = len(text)
		if '=' in text:
			start = text.find('=')+1
		if "x{" in text:
			end = text.find("x{")
		text = text[start:end]
		text = text.strip()
		text = text.replace('(', '{')
		text = text.replace(')', '}')

		# Добавить кавычки к строкам (1 этап)
		buff = text
		buff = buff.replace('\r', ' ')
		buff = buff.replace('\n', ' ')
		buff = buff.replace('\t', ' ')
		buff = buff.replace('{', ' ')
		buff = buff.replace('}', ' ')
		buff = buff.replace(':', ' ')

		# Добавить кавычки к строкам (2 этап)
		buff2 = ""
		itemList = list()
		for item in list(buff):
			if item == ' ':
				if len(buff2) > 0:
					itemList.append(buff2)
					buff2 = ""
				itemList.append(item)
			else:
				buff2 += item
		#end for

		# Добавить кавычки к строкам (3 этап)
		i = 0
		for item in itemList:
			l = len(item)
			if item == ' ':
				pass
			elif item.isdigit() is False:
				c = '"'
				item2 = c + item + c
				text = text[:i] + item2 + text[i+l:]
				i += 2
			#end if
			i += l
		#end for

		# Обозначить тип объекта
		text = text.replace('{"', '{"_":"')

		# Расставить запятые
		while True:
			try:
				data = json.loads(text)
				break
			except json.JSONDecodeError as err:
				if "Expecting ',' delimiter" in err.msg:
					text = text[:err.pos] + ',' + text[err.pos:]
				elif "Expecting property name enclosed in double quotes" in err.msg:
					text = text[:err.pos] + '"_":' + text[err.pos:]
				else:
					raise err
		#end while

		return data
	#end define

	def SignShardOverlayCert(self, adnl, pubkey):
		self.local.add_log("start SignShardOverlayCert function", "debug")
		fileName = self.tempDir + pubkey + ".cert"
		cmd = "signshardoverlaycert {workchain} {shardprefix} {pubkey} {expireat} {maxsize} {outfile}"
		cmd = cmd.format(workchain=-1, shardprefix=-9223372036854775808, pubkey=pubkey, expireat=172800, maxsize=8192, outfile=fileName)
		result = self.validatorConsole.Run(cmd)
		if "saved certificate" not in result:
			raise Exception("SignShardOverlayCert error: " + result)
		#end if

		file = open(fileName, 'rb')
		data = file.read()
		file.close()
		cert = base64.b64encode(data).decode("utf-8")

		destHex = "0:" + adnl
		destAddr = self.AddrFull2AddrB64(destHex, bounceable=False)
		wallet = self.GetValidatorWallet(mode="vote")
		flags = ["--comment", cert]
		self.MoveCoins(wallet, destAddr, 0.001, flags=flags)
	#end define

	def ImportShardOverlayCert(self):
		self.local.add_log("start ImportShardOverlayCert function", "debug")
		adnlAddr = self.GetAdnlAddr()
		pubkey = self.GetPubKey(adnlAddr)
		adnl = pubkey # adnl = adnlAddr
		fileName = self.tempDir + pubkey + ".cert"

		cert = None
		addrFull = "0:" + adnl
		addr = self.AddrFull2AddrB64(addrFull)
		account = self.GetAccount(addr)
		history = self.GetAccountHistory(account, 10)
		vwl = self.GetValidatorsWalletsList()
		for message in history:
			srcAddrFull = f"{message.srcWorkchain}:{message.srcAddr}"
			srcAddrFull = self.AddrFull2AddrB64(srcAddrFull)
			if srcAddrFull not in vwl:
				continue
			comment = message.comment
			buff = comment.encode("utf-8")
			cert = base64.b64decode(buff)
			break
		#end for

		# Check certificate
		if cert is None:
			self.local.add_log("ImportShardOverlayCert warning: certificate not found", "warning")
			return
		#end if

		file = open(fileName, 'wb')
		file.write(cert)
		file.close()

		self.ImportCertificate(pubkey, fileName)
	#end define

	def ImportCertificate(self, pubkey, fileName):
		self.local.add_log("start ImportCertificate function", "debug")
		cmd = "importshardoverlaycert {workchain} {shardprefix} {pubkey} {certfile}"
		cmd = cmd.format(workchain=-1, shardprefix=-9223372036854775808, pubkey=pubkey, certfile=fileName)
		result = self.validatorConsole.Run(cmd)
	#end define

	def GetValidatorsWalletsList(self):
		result = list()
		vl = self.GetValidatorsList(fast=True)
		for item in vl:
			walletAddr = item["walletAddr"]
			result.append(walletAddr)
		return result
	#end define

	def DownloadContract(self, url, branch=None):
		self.local.add_log("start DownloadContract function", "debug")
		buff = url.split('/')
		gitPath = self.contractsDir + buff[-1] + '/'

		args = ["git", "clone", url]
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.contractsDir, timeout=30)

		if branch is not None:
			args = ["git", "checkout", branch]
			process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=gitPath, timeout=3)
		#end if

		if not os.path.isfile(gitPath + "build.sh"):
			return
		if not os.path.isfile("/usr/bin/func"):
			return
		#	file = open("/usr/bin/func", 'wt')
		#	file.write("/usr/bin/ton/crypto/func $@")
		#	file.close()
		#end if

		os.makedirs(gitPath + "build", exist_ok=True)
		args = ["bash", "build.sh"]
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=gitPath, timeout=30)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			raise Exception(err)
		#end if
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

	def GetLocalPool(self, poolName):
		self.local.add_log("start GetLocalPool function", "debug")
		if poolName is None:
			return None
		filePath = self.poolsDir + poolName

		# Create pool object
		pool = Pool(poolName, filePath)
		if os.path.isfile(pool.addrFilePath) == False:
			raise Exception(f"GetLocalPool error: Address file not found: {pool.addrFilePath}")
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

	def GetPools(self):
		self.local.add_log("start GetPools function", "debug")
		pools = list()
		poolsNameList = self.GetPoolsNameList()
		for poolName in poolsNameList:
			pool = self.GetLocalPool(poolName)
			pools.append(pool)
		return pools
	#end define

	def get_pool(self):
		pools = self.GetPools()
		for pool in pools:
			if self.is_pool_ready_to_stake(pool):
				return pool
		raise Exception("Validator pool not found or not ready")
	#end define

	def get_pool_last_sent_stake_time(self, addrB64):
		pool_data = self.GetPoolData(addrB64)
		return pool_data["stakeAt"]
	#end define

	def is_pool_ready_to_stake(self, pool: Pool):
		addr = pool.addrB64
		account = self.GetAccount(addr)
		is_single_nominator = self.is_account_single_nominator(account)
		if self.using_single_nominator() and not is_single_nominator:
			return False
		try:  # check that account balance is enough for stake
			stake = self.GetStake(account)
			if not stake:
				raise Exception(f'Stake is {stake}')
		except Exception as e:
			self.local.add_log(f"Failed to get stake for pool {addr}: {e}", "debug")
			return False
		now = get_timestamp()
		config15 = self.GetConfig15()
		last_sent_stake_time = self.get_pool_last_sent_stake_time(addr)
		stake_freeze_delay = config15["validatorsElectedFor"] + config15["stakeHeldFor"]
		result = last_sent_stake_time + stake_freeze_delay < now
		print(f"{addr}: {result}. {last_sent_stake_time}, {stake_freeze_delay}, {now}")
		return result
	#end define

	def is_account_single_nominator(self, account: Account):
		account_version = self.GetVersionFromCodeHash(account.codeHash)
		return account_version is not None and 'spool' in account_version
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

	def GetLiquidPoolAddr(self):
		liquid_pool_addr = self.local.db.get("liquid_pool_addr")
		if liquid_pool_addr is None:
			raise Exception("GetLiquidPoolAddr error: liquid_pool_addr not set")
		return liquid_pool_addr
	#end define

	def GetControllerAddress(self, controller_id):
		wallet = self.GetValidatorWallet()
		addr_hash = HexAddr2Dec(wallet.addr)
		liquid_pool_addr = self.GetLiquidPoolAddr()
		cmd = f"runmethodfull {liquid_pool_addr} get_controller_address_legacy {controller_id} {wallet.workchain} {addr_hash}"
		result = self.liteClient.Run(cmd)
		buff = self.Result2List(result)
		wc = buff[0]
		addr_hash = Dec2HexAddr(buff[1])
		addrFull = f"{wc}:{addr_hash}"
		controllerAddr = self.AddrFull2AddrB64(addrFull)
		return controllerAddr
	#end define

	def CheckController(self, controllerAddr):
		self.local.add_log("start CheckController function", "debug")
		controllerData = self.GetControllerData(controllerAddr)
		using_controllers = self.local.db.get("using_controllers", list())
		if controllerData is None:
			raise Exception(f"CheckController error: controller not initialized. Use new_controllers")
		if controllerData["approved"] != -1:
			raise Exception(f"CheckController error: controller not approved: {controllerAddr}")
		if controllerAddr not in using_controllers:
			raise Exception("CheckController error: controller is not up to date. Use new_controllers")
	#end define

	def GetControllers(self):
		self.local.add_log("start GetControllers function", "debug")
		controller0 = self.GetControllerAddress(controller_id=0)
		controller1 = self.GetControllerAddress(controller_id=1)
		controllers = [controller0, controller1]
		return controllers
	#end define

	def GetController(self, mode):
		controllers = self.GetControllers()
		for controllerAddr in controllers:
			if mode == "stake" and self.IsControllerReadyToStake(controllerAddr):
				return controllerAddr
			if mode == "vote" and self.IsControllerReadyToVote(controllerAddr):
				return controllerAddr
		raise Exception("Validator controller not found or not ready")
	#end define

	def GetControllerRequiredBalanceForLoan(self, controllerAddr, credit, interest):
		cmd = f"runmethodfull {controllerAddr} required_balance_for_loan {credit} {interest}"
		result = self.liteClient.Run(cmd)
		data = self.Result2List(result)
		if data is None:
			return
		min_amount = data[0]
		validator_amount = data[1]
		return min_amount, validator_amount
	#end define

	def IsControllerReadyToStake(self, addrB64):
		stop_controllers_list = self.local.db.get("stop_controllers_list")
		if stop_controllers_list is not None and addrB64 in stop_controllers_list:
			return False
		now = get_timestamp()
		config15 = self.GetConfig15()
		controllerData = self.GetControllerData(addrB64)
		if controllerData is None:
			raise Exception(f"IsControllerReadyToStake error: controller not initialized. Use new_controllers")
		lastSentStakeTime = controllerData["stake_at"]
		stakeFreezeDelay = config15["validatorsElectedFor"] + config15["stakeHeldFor"]
		result = lastSentStakeTime + stakeFreezeDelay < now
		print(f"{addrB64}: {result}. {lastSentStakeTime}, {stakeFreezeDelay}, {now}")
		return result
	#end define

	def IsControllerReadyToVote(self, addrB64):
		vwl = self.GetValidatorsWalletsList()
		result = addrB64 in vwl
		return result
	#end define

	def GetControllerData(self, controllerAddr):
		cmd = f"runmethodfull {controllerAddr} get_validator_controller_data"
		result = self.liteClient.Run(cmd)
		data = self.Result2List(result)
		if data is None:
			return
		result_vars = ["state", "halted", "approved", "stake_amount_sent", "stake_at", "saved_validator_set_hash", "validator_set_changes_count", "validator_set_change_time", "stake_held_for", "borrowed_amount", "borrowing_time"]
		controllerData = dict()
		for name in result_vars:
			controllerData[name] = data.pop(0)
		return controllerData
	#end define

	def CreateLoanRequest(self, controllerAddr):
		self.local.add_log("start CreateLoanRequest function", "debug")
		min_loan = self.local.db.get("min_loan", 41000)
		max_loan = self.local.db.get("max_loan", 43000)
		max_interest_percent = self.local.db.get("max_interest_percent", 1.5)
		max_interest = int(max_interest_percent/100*16777216)

		# Проверить наличие действующего кредита
		controllerData = self.GetControllerData(controllerAddr)
		if controllerData["borrowed_amount"] > 0:
			self.local.add_log("CreateLoanRequest warning: past loan found", "warning")
			return
		#end define

		# Проверить наличие средств у ликвидного пула
		if self.CalculateLoanAmount(min_loan, max_loan, max_interest) == '-0x1':
			raise Exception("CreateLoanRequest error: The liquid pool cannot issue the required amount of credit")
		#end if

		# Проверить хватает ли ставки валидатора
		min_amount, validator_amount = self.GetControllerRequiredBalanceForLoan(controllerAddr, max_loan, max_interest)
		if min_amount > validator_amount:
			raise Exception("CreateLoanRequest error: Validator stake is too low. Use deposit_to_controller")
		#end if

		wallet = self.GetValidatorWallet()
		fiftScript = self.contractsDir + "jetton_pool/fift-scripts/generate-loan-request.fif"
		resultFilePath = self.tempDir + self.nodeName + wallet.name + "_loan_request.boc"
		args = [fiftScript, min_loan, max_loan, max_interest, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, controllerAddr, 1.01)
		self.SendFile(resultFilePath, wallet)
		self.WaitLoan(controllerAddr)
	#end define

	def CalculateLoanAmount(self, min_loan, max_loan, max_interest):
		data = dict()
		data["address"] = self.GetLiquidPoolAddr()
		data["method"] = "calculate_loan_amount"
		data["stack"] = [
			["num", min_loan*10**9],
			["num", max_loan*10**9],
			["num", max_interest],
		]
		print(f"CalculateLoanAmount data: {data}")

		url = "http://127.0.0.1:8801/runGetMethod"
		res = requests.post(url, json=data)
		res_data = res.json()
		if res_data.get("ok") is False:
			error = res_data.get("error")
			raise Exception(error)
		result = res_data.get("result").get("stack").pop().pop()
		return result
	#end define

	def WaitLoan(self, controllerAddr):
		self.local.add_log("start WaitLoan function", "debug")
		for i in range(10):
			time.sleep(3)
			controllerData = self.GetControllerData(controllerAddr)
			if controllerData["borrowed_amount"] != 0:
				return
		raise Exception("WaitLoan error: time out")
	#end define

	def ReturnUnusedLoan(self, controllerAddr):
		self.local.add_log("start ReturnUnusedLoan function", "debug")
		wallet = self.GetValidatorWallet()
		fileName = self.contractsDir + "jetton_pool/fift-scripts/return_unused_loan.boc"
		resultFilePath = self.SignBocWithWallet(wallet, fileName, controllerAddr, 1.05)
		self.SendFile(resultFilePath, wallet)
	#end define

	def WithdrawFromController(self, controllerAddr, amount=None):
		controllerData = self.GetControllerData(controllerAddr)
		if controllerData["state"] == 0:
			self.WithdrawFromControllerProcess(controllerAddr, amount)
		else:
			self.PendWithdrawFromController(controllerAddr, amount)
	#end define

	def WithdrawFromControllerProcess(self, controllerAddr, amount):
		if amount is None:
			account = self.GetAccount(controllerAddr)
			amount = account.balance-10.1
		if int(amount) < 3:
			return
		#end if

		self.local.add_log("start WithdrawFromControllerProcess function", "debug")
		wallet = self.GetValidatorWallet()
		fiftScript = self.contractsDir + "jetton_pool/fift-scripts/withdraw-controller.fif"
		resultFilePath = self.tempDir + self.nodeName + wallet.name + "_withdraw_request.boc"
		args = [fiftScript, amount, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, controllerAddr, 1.06)
		self.SendFile(resultFilePath, wallet)
	#end define

	def PendWithdrawFromController(self, controllerAddr, amount):
		self.local.add_log("start PendWithdrawFromController function", "debug")
		controllerPendingWithdraws = self.GetControllerPendingWithdraws()
		controllerPendingWithdraws[controllerAddr] = amount
		self.local.save()
	#end define

	def HandleControllerPendingWithdraw(self, controllerPendingWithdraws, controllerAddr):
		amount = controllerPendingWithdraws.get(controllerAddr)
		self.WithdrawFromControllerProcess(controllerAddr, amount)
		controllerPendingWithdraws.pop(controllerAddr)
	#end define

	def GetControllerPendingWithdraws(self):
		bname = "controllerPendingWithdraws"
		controllerPendingWithdraws = self.local.db.get(bname)
		if controllerPendingWithdraws is None:
			controllerPendingWithdraws = dict()
			self.local.db[bname] = controllerPendingWithdraws
		return controllerPendingWithdraws
	#end define

	def SignElectionRequestWithController(self, controllerAddr, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor, stake):
		self.local.add_log("start SignElectionRequestWithController function", "debug")
		fileName = self.tempDir + str(startWorkTime) + "_validator-query.boc"
		fiftScript = self.contractsDir + "jetton_pool/fift-scripts/controller-elect-signed.fif"
		args = [fiftScript, controllerAddr, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName, stake]
		self.local.add_log(f"SignElectionRequestWithController args: {args}", "debug")
		result = self.fift.Run(args)
		self.local.add_log(f"SignElectionRequestWithController result: {result}", "debug")
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName
	#end define

	def ControllersUpdateValidatorSet(self):
		self.local.add_log("start ControllersUpdateValidatorSet function", "debug")
		using_controllers = self.local.db.get("using_controllers")
		user_controllers = self.local.db.get("user_controllers", list())
		old_controllers = self.local.db.get("old_controllers", list())
		for controller in using_controllers + user_controllers + old_controllers:
			self.ControllerUpdateValidatorSet(controller)
	#end define

	def ControllerUpdateValidatorSet(self, controllerAddr):
		self.local.add_log("start ControllerUpdateValidatorSet function", "debug")
		wallet = self.GetValidatorWallet()
		controllers = self.GetControllers()
		controllerData = self.GetControllerData(controllerAddr)
		if controllerData is None:
			return
		#end if

		timeNow = int(time.time())
		config34 = self.GetConfig34()
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.GetReturnedStake(fullElectorAddr, controllerAddr)
		controllerPendingWithdraws = self.GetControllerPendingWithdraws()
		if (controllerData["state"] == 3 and
			controllerData["validator_set_changes_count"] < 2 and
			controllerData["validator_set_change_time"] < config34["startWorkTime"]):
			self.ControllerUpdateValidatorSetProcess(controllerAddr, wallet)
			controllerData = self.GetControllerData(controllerAddr)
		if (returnedStake > 0 and
			controllerData["state"] == 3 and
			controllerData["validator_set_changes_count"] >= 2 and
			timeNow - controllerData["validator_set_change_time"] > controllerData["stake_held_for"] + 60):
			self.ControllerRecoverStake(controllerAddr)
			controllerData = self.GetControllerData(controllerAddr)
		if (controllerData["state"] == 0 and
			controllerData["borrowed_amount"] > 0 and
			config34["startWorkTime"] > controllerData["borrowing_time"]):
			self.ReturnUnusedLoan(controllerAddr)
		if (controllerData["state"] == 0 and controllerAddr in controllerPendingWithdraws):
			self.HandleControllerPendingWithdraw(controllerPendingWithdraws, controllerAddr)
		if controllerAddr not in controllers:
			self.WithdrawFromController(controllerAddr)
	#end define

	def ControllerUpdateValidatorSetProcess(self, controllerAddr, wallet):
		self.local.add_log("start ControllerUpdateValidatorSetProcess function", "debug")
		fileName = self.contractsDir + "jetton_pool/fift-scripts/update_validator_hash.boc"
		resultFilePath = self.SignBocWithWallet(wallet, fileName, controllerAddr, 1.07)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("ControllerUpdateValidatorSetProcess completed")
	#end define

	def ControllerRecoverStake(self, controllerAddr):
		wallet = self.GetValidatorWallet()
		self.local.add_log("start ControllerRecoverStake function", "debug")
		fileName = self.contractsDir + "jetton_pool/fift-scripts/recover_stake.boc"
		resultFilePath = self.SignBocWithWallet(wallet, fileName, controllerAddr, 1.04)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("ControllerRecoverStake completed")
	#end define

	def get_custom_overlays(self):
		if 'custom_overlays' not in self.local.db:
			self.local.db['custom_overlays'] = {}
		return self.local.db['custom_overlays']

	def set_custom_overlay(self, name: str, config: dict):
		overlays = self.get_custom_overlays()
		overlays[name] = config
		self.local.save()

	def delete_custom_overlay(self, name: str):
		del self.local.db['custom_overlays'][name]
		self.local.save()

	def set_collator_config(self, location: str):
		self.local.db['collator_config'] = location
		self.local.save()

	def get_collator_config_location(self):
		default = 'https://raw.githubusercontent.com/ton-blockchain/ton-blockchain.github.io/main/default_collator_options.json'
		location = self.local.db.get('collator_config', default)
		if location is None:
			location = default
		return location

	def GetNetworkName(self):
		data = self.local.read_db(self.liteClient.configPath)
		mainnet_zero_state_root_hash = "F6OpKZKqvqeFp6CQmFomXNMfMj2EnaUSOXN+Mh+wVWk="
		testnet_zero_state_root_hash = "gj+B8wb/AmlPk1z1AhVI484rhrUpgSr2oSFIh56VoSg="
		if data.validator.zero_state.root_hash == mainnet_zero_state_root_hash:
			return "mainnet"
		elif data.validator.zero_state.root_hash == testnet_zero_state_root_hash:
			return "testnet"
		else:
			return "unknown"
	#end define

	def GetFunctionBuffer(self, name, timeout=10):
		timestamp = get_timestamp()
		buff = self.local.buffer.get(name)
		if buff is None:
			return
		buffTime = buff.get("time")
		diffTime = timestamp - buffTime
		if diffTime > timeout:
			return
		data = buff.get("data")
		return data
	#end define

	def SetFunctionBuffer(self, name, data):
		buff = dict()
		buff["time"] = get_timestamp()
		buff["data"] = data
		self.local.buffer[name] = buff
	#end define

	def IsTestnet(self):
		networkName = self.GetNetworkName()
		if networkName == "testnet":
			return True
		else:
			return False
	#end define

	def IsAddr(self, addr):
		isAddrB64 = self.IsAddrB64(addr)
		isAddrFull = self.IsAddrFull(addr)
		if isAddrB64 or isAddrFull:
			return True
		return False
	#end define

	def IsAddrB64(self, addr):
		try:
			self.ParseAddrB64(addr)
			return True
		except: pass
		return False
	#end define

	def IsAddrFull(self, addr):
		try:
			self.ParseAddrFull(addr)
			return True
		except: pass
		return False
	#end define

	def IsHash(self, inputHash):
		hashBytes = bytes.fromhex(inputHash)
		if len(hashBytes) != 32:
			return False
		return True
	#end define
#end class


def Dec2HexAddr(dec):
	h = dec2hex(dec)
	hu = h.upper()
	h64 = hu.rjust(64, "0")
	return h64
#end define

def HexAddr2Dec(h):
	d = int(h, 16)
	return d
#end define
