#!/usr/bin/env python3
# -*- coding: utf_8 -*-l

from fastcrc import crc16
import struct
import random
import hashlib
import requests
import re
from mypylib.mypylib import *
from custom_overlays import custom_overlays

local = MyPyClass(__file__)

class LiteClient:
	def __init__(self):
		self.appPath = None
		self.configPath = None
		self.pubkeyPath = None
		self.addr = None
		self.ton = None # magic
	#end define

	def Run(self, cmd, **kwargs):
		index = kwargs.get("index")
		liteclient_timeout = local.db.liteclient_timeout if local.db.liteclient_timeout else 3
		timeout = kwargs.get("timeout", liteclient_timeout)
		useLocalLiteServer = kwargs.get("useLocalLiteServer", True)
		validatorStatus = self.ton.GetValidatorStatus()
		validatorOutOfSync = validatorStatus.get("outOfSync")
		args = [self.appPath, "--global-config", self.configPath, "--verbosity", "0", "--cmd", cmd]
		if index is not None:
			index = str(index)
			args += ["-i", index]
		elif useLocalLiteServer and self.pubkeyPath and validatorOutOfSync < 20:
			args = [self.appPath, "--addr", self.addr, "--pub", self.pubkeyPath, "--verbosity", "0", "--cmd", cmd]
		else:
			liteServers = local.db.get("liteServers")
			if liteServers is not None and len(liteServers):
				index = random.choice(liteServers)
				index = str(index)
				args += ["-i", index]
		#end if

		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			local.add_log("args: {args}".format(args=args), "error")
			raise Exception("LiteClient error: {err}".format(err=err))
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

	def Run(self, cmd, **kwargs):
		console_timeout = local.db.console_timeout if local.db.console_timeout else 3
		timeout = kwargs.get("timeout", console_timeout)
		if self.appPath is None or self.privKeyPath is None or self.pubKeyPath is None:
			raise Exception("ValidatorConsole error: Validator console is not settings")
		args = [self.appPath, "-k", self.privKeyPath, "-p", self.pubKeyPath, "-a", self.addr, "-v", "0", "--cmd", cmd]
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			local.add_log("args: {args}".format(args=args), "error")
			raise Exception("ValidatorConsole error: {err}".format(err=err))
		return output
	#end define
#end class

class Fift:
	def __init__(self):
		self.appPath = None
		self.libsPath = None
		self.smartcontsPath = None
	#end define

	def Run(self, args, **kwargs):
		fift_timeout = local.db.fift_timeout if local.db.fift_timeout else 3
		timeout = kwargs.get("timeout", fift_timeout)
		for i in range(len(args)):
			args[i] = str(args[i])
		includePath = self.libsPath + ':' + self.smartcontsPath
		args = [self.appPath, "-I", includePath, "-s"] + args
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			local.add_log("args: {args}".format(args=args), "error")
			raise Exception("Fift error: {err}".format(err=err))
		return output
	#end define
#end class

class Wallet:
	def __init__(self, name, path, version):
		self.name = name
		self.path = path
		self.addrFilePath = f"{path}.addr"
		self.privFilePath = f"{path}.pk"
		self.bocFilePath = f"{path}-query.boc"
		self.addrFull = None
		self.workchain = None
		self.addr = None
		self.addrB64 = None
		self.addrB64_init = None
		self.oldseqno = None
		self.account = None
		self.subwallet = None
		self.version = version
	#end define

	def Delete(self):
		os.remove(self.addrFilePath)
		os.remove(self.privFilePath)
	#end define
#end class

class Account:
	def __init__(self, workchain, addr):
		self.workchain = workchain
		self.addr = addr
		self.addrB64 = None
		self.addrFull = None
		self.status = "empty"
		self.balance = 0
		self.lt = None
		self.hash = None
		self.codeHash = None
	#end define
#end class

class Domain(dict):
	def __init__(self):
		self["name"] = None
		self["adnlAddr"] = None
		self["walletName"] = None
	#end define
#end class

class Block():
	def __init__(self, str=None):
		self.workchain = None
		self.shardchain = None
		self.seqno = None
		self.rootHash = None
		self.fileHash = None
		self.ParsBlock(str)
	#end define

	def ParsBlock(self, str):
		if str is None:
			return
		buff = str.split(':')
		self.rootHash = buff[1]
		self.fileHash = buff[2]
		buff = buff[0]
		buff = buff.replace('(', '')
		buff = buff.replace(')', '')
		buff = buff.split(',')
		self.workchain = int(buff[0])
		self.shardchain = buff[1]
		self.seqno = int(buff[2])
	#end define

	def __str__(self):
		result = f"({self.workchain},{self.shardchain},{self.seqno}):{self.rootHash}:{self.fileHash}"
		return result
	#end define

	def __repr__(self):
		return self.__str__()
	#end define

	def __eq__(self, other):
		if other is None:
			return False
		return self.rootHash == other.rootHash and self.fileHash == other.fileHash
	#end define
#end class

class Trans():
	def __init__(self, block, addr=None, lt=None, hash=None):
		self.block = block
		self.addr = addr
		self.lt = lt
		self.hash = hash
	#end define

	def __str__(self):
		return str(self.__dict__)
	#end define

	def __repr__(self):
		return self.__str__()
	#end define

	def __eq__(self, other):
		if other is None:
			return False
		return self.hash == other.hash
	#end define
#end class

class Message():
	def __init__(self):
		self.trans = None
		self.type = None
		self.time = None
		self.srcWorkchain = None
		self.destWorkchain = None
		self.srcAddr = None
		self.destAddr = None
		self.value = None
		self.body = None
		self.comment = None
		self.ihr_fee = None
		self.fwd_fee = None
		self.total_fees = None
		self.ihr_disabled = None
	#end define

	def GetFullAddr(self, workchain, addr):
		if addr is None:
			return
		return f"{workchain}:{addr}"
	#end define

	def __str__(self):
		return str(self.__dict__)
	#end define

	def __repr__(self):
		return self.__str__()
	#end define

	def __eq__(self, other):
		if other is None:
			return False
		return self.hash == other.hash
	#end define
#end class

class Pool:
	def __init__(self, name, path):
		self.name = name
		self.path = path
		self.addrFilePath = f"{path}.addr"
		self.bocFilePath = f"{path}-query.boc"
		self.addrFull = None
		self.workchain = None
		self.addr = None
		self.addrB64 = None
		self.addrB64_init = None
		self.account = None
	#end define

	def Delete(self):
		os.remove(self.addrFilePath)
	#end define
#end class

class MyTonCore():
	def __init__(self):
		self.walletsDir = None
		self.dbFile = None
		self.contractsDir = None
		self.poolsDir = None
		self.tempDir = None
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
		os.makedirs(self.contractsDir, exist_ok=True)
		os.makedirs(self.poolsDir, exist_ok=True)
	#end define

	def Refresh(self):
		if self.dbFile:
			local.load_db(self.dbFile)
		#end if

		if not self.walletsDir:
			self.walletsDir = local.buffer.my_work_dir + "wallets/"
		self.contractsDir = local.buffer.my_work_dir + "contracts/"
		self.poolsDir = local.buffer.my_work_dir + "pools/"
		self.tempDir = local.buffer.my_temp_dir

		self.nodeName = local.db.get("nodeName")
		if self.nodeName is None:
			self.nodeName=""
		else:
			self.nodeName = self.nodeName + "_"

		liteClient = local.db.get("liteClient")
		if liteClient is not None:
			self.liteClient.ton = self # magic
			self.liteClient.appPath = liteClient["appPath"]
			self.liteClient.configPath = liteClient["configPath"]
			liteServer = liteClient.get("liteServer")
			if liteServer is not None:
				self.liteClient.pubkeyPath = liteServer["pubkeyPath"]
				self.liteClient.addr = "{0}:{1}".format(liteServer["ip"], liteServer["port"])
		#end if

		validatorConsole = local.db.get("validatorConsole")
		if validatorConsole is not None:
			self.validatorConsole.appPath = validatorConsole["appPath"]
			self.validatorConsole.privKeyPath = validatorConsole["privKeyPath"]
			self.validatorConsole.pubKeyPath = validatorConsole["pubKeyPath"]
			self.validatorConsole.addr = validatorConsole["addr"]
		#end if

		fift = local.db.get("fift")
		if fift is not None:
			self.fift.appPath = fift["appPath"]
			self.fift.libsPath = fift["libsPath"]
			self.fift.smartcontsPath = fift["smartcontsPath"]
		#end if

		# Check config file
		self.CheckConfigFile(fift, liteClient)
	#end define

	def CheckConfigFile(self, fift, liteClient):
		mconfig_path = local.buffer.db_path
		backup_path = mconfig_path + ".backup"
		if fift is None or liteClient is None:
			local.add_log("The config file is broken", "warning")
			print(f"local.db: {local.db}")
			if os.path.isfile(backup_path):
				local.add_log("Restoring the configuration file", "info")
				args = ["cp", backup_path, mconfig_path]
				subprocess.run(args)
				self.Refresh()
		elif os.path.isfile(backup_path) == False:
			local.add_log("Create backup config file", "info")
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
		local.add_log("start GetSeqno function", "debug")
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
		#local.add_log("start GetAccount function", "debug")
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
		local.add_log("start GetAccountHistory function", "debug")
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

	def GetDomainAddr(self, domainName):
		cmd = "dnsresolve {domainName} -1".format(domainName=domainName)
		result = self.liteClient.Run(cmd)
		if "not found" in result:
			raise Exception("GetDomainAddr error: domain \"{domainName}\" not found".format(domainName=domainName))
		resolver = parse(result, "next resolver", '\n')
		buff = resolver.replace(' ', '')
		buffList = buff.split('=')
		fullHexAddr = buffList[0]
		addr = buffList[1]
		return addr
	#end define

	def GetDomainEndTime(self, domainName):
		local.add_log("start GetDomainEndTime function", "debug")
		buff = domainName.split('.')
		subdomain = buff.pop(0)
		dnsDomain = ".".join(buff)
		dnsAddr = self.GetDomainAddr(dnsDomain)

		cmd = "runmethodfull {addr} getexpiration \"{subdomain}\"".format(addr=dnsAddr, subdomain=subdomain)
		result = self.liteClient.Run(cmd)
		result = parse(result, "result:", '\n')
		result = parse(result, "[", "]")
		result = result.replace(' ', '')
		result = int(result)
		return result
	#end define

	def GetDomainAdnlAddr(self, domainName):
		local.add_log("start GetDomainAdnlAddr function", "debug")
		cmd = "dnsresolve {domainName} 1".format(domainName=domainName)
		result = self.liteClient.Run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "adnl address" in line:
				adnlAddr = parse(line, "=", "\n")
				adnlAddr = adnlAddr.replace(' ', '')
				adnlAddr = adnlAddr
				return adnlAddr
	#end define

	def GetLocalWallet(self, walletName, version=None, subwallet=None):
		local.add_log("start GetLocalWallet function", "debug")
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
		local.add_log("start GetWalletFromFile function", "debug")
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
		local.add_log("start GetHighWalletFromFile function", "debug")
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
	#end define

	def WalletVersion2Wallet(self, wallet):
		local.add_log("start WalletVersion2Wallet function", "debug")
		if wallet.version is not None:
			return
		walletsVersionList = self.GetWalletsVersionList()
		account = self.GetAccount(wallet.addrB64)
		version = walletsVersionList.get(wallet.addrB64)
		if version is None:
			version = self.GetWalletVersionFromHash(account.codeHash)
		if version is None:
			local.add_log("Wallet version not found: " + wallet.addrB64, "warning")
			return
		#end if

		self.SetWalletVersion(wallet.addrB64, version)
		wallet.version = version
	#end define

	def SetWalletVersion(self, addrB64, version):
		walletsVersionList = self.GetWalletsVersionList()
		walletsVersionList[addrB64] = version
		local.save()
	#end define

	def GetWalletVersionFromHash(self, inputHash):
		local.add_log("start GetWalletVersionFromHash function", "debug")
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
		for version, hash in arr.items():
			if hash == inputHash:
				return version
		#end for
	#end define

	def GetWalletsVersionList(self):
		bname = "walletsVersionList"
		walletsVersionList = local.db.get(bname)
		if walletsVersionList is None:
			walletsVersionList = dict()
			local.db[bname] = walletsVersionList
		return walletsVersionList
	#end define

	def GetFullConfigAddr(self):
		# Get buffer
		bname = "fullConfigAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		local.add_log("start GetFullConfigAddr function", "debug")
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
		local.add_log("start GetFullElectorAddr function", "debug")
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

		local.add_log("start GetFullMinterAddr function", "debug")
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

		local.add_log("start GetFullDnsRootAddr function", "debug")
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

		local.add_log("start GetActiveElectionId function", "debug")
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
		local.add_log("start GetValidatorsElectedFor function", "debug")
		config15 = self.GetConfig15()
		return config15["validatorsElectedFor"]
	#end define

	def GetMinStake(self):
		local.add_log("start GetMinStake function", "debug")
		config17 = self.GetConfig17()
		return config17["minStake"]
	#end define

	def GetRootWorkchainEnabledTime(self):
		local.add_log("start GetRootWorkchainEnabledTime function", "debug")
		config12 = self.GetConfig(12)
		enabledTime = config12["workchains"]["root"]["node"]["value"]["enabled_since"]
		return enabledTime
	#end define

	def GetTotalValidators(self):
		local.add_log("start GetTotalValidators function", "debug")
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
		bname = "validatorStatus"
		buff = self.GetFunctionBuffer(bname)
		if buff:
			return buff
		#end if

		# local.add_log("start GetValidatorStatus function", "debug")
		validatorStatus = dict()
		try:
			validatorStatus["isWorking"] = True
			result = self.validatorConsole.Run("getstats")
			validatorStatus["unixtime"] = int(parse(result, "unixtime", '\n'))
			validatorStatus["masterchainblocktime"] = int(parse(result, "masterchainblocktime", '\n'))
			validatorStatus["stateserializermasterchainseqno"] = int(parse(result, "stateserializermasterchainseqno", '\n'))
			validatorStatus["shardclientmasterchainseqno"] = int(parse(result, "shardclientmasterchainseqno", '\n'))
			buff = parse(result, "masterchainblock", '\n')
			validatorStatus["masterchainblock"] = self.GVS_GetItemFromBuff(buff)
			buff = parse(result, "gcmasterchainblock", '\n')
			validatorStatus["gcmasterchainblock"] = self.GVS_GetItemFromBuff(buff)
			buff = parse(result, "keymasterchainblock", '\n')
			validatorStatus["keymasterchainblock"] = self.GVS_GetItemFromBuff(buff)
			buff = parse(result, "rotatemasterchainblock", '\n')
			validatorStatus["rotatemasterchainblock"] = self.GVS_GetItemFromBuff(buff)
			validatorStatus["transNum"] = local.buffer.get("transNum", -1)
			validatorStatus["blocksNum"] = local.buffer.get("blocksNum", -1)
			validatorStatus["masterBlocksNum"] = local.buffer.get("masterBlocksNum", -1)
		except Exception as ex:
			local.add_log(f"GetValidatorStatus warning: {ex}", "warning")
			validatorStatus["isWorking"] = False
			validatorStatus["unixtime"] = get_timestamp()
			validatorStatus["masterchainblocktime"] = 0
		validatorStatus["outOfSync"] = validatorStatus["unixtime"] - validatorStatus["masterchainblocktime"]

		# Set buffer
		self.SetFunctionBuffer(bname, validatorStatus)
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

	def GetConfig(self, configId):
		# Get buffer
		bname = "config" + str(configId)
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		text = "start GetConfig function ({})".format(configId)
		local.add_log(text, "debug")
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

		local.add_log("start GetConfig32 function", "debug")
		config32 = dict()
		result = self.liteClient.Run("getconfig 32")
		config32["totalValidators"] = int(parse(result, "total:", ' '))
		config32["startWorkTime"] = int(parse(result, "utime_since:", ' '))
		config32["endWorkTime"] = int(parse(result, "utime_until:", ' '))
		lines = result.split('\n')
		validators = list()
		for line in lines:
			if "public_key:" in line:
				validatorAdnlAddr = parse(line, "adnl_addr:x", ')')
				pubkey = parse(line, "pubkey:x", ')')
				if config32["totalValidators"] > 1:
					validatorWeight = int(parse(line, "weight:", ' '))
				else:
					validatorWeight = int(parse(line, "weight:", ')'))
				buff = dict()
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

		local.add_log("start GetConfig34 function", "debug")
		config34 = dict()
		result = self.liteClient.Run("getconfig 34")
		config34["totalValidators"] = int(parse(result, "total:", ' '))
		config34["startWorkTime"] = int(parse(result, "utime_since:", ' '))
		config34["endWorkTime"] = int(parse(result, "utime_until:", ' '))
		config34["totalWeight"] = int(parse(result, "total_weight:", ' '))
		lines = result.split('\n')
		validators = list()
		for line in lines:
			if "public_key:" in line:
				validatorAdnlAddr = parse(line, "adnl_addr:x", ')')
				pubkey = parse(line, "pubkey:x", ')')
				if config34["totalValidators"] > 1:
					validatorWeight = int(parse(line, "weight:", ' '))
				else:
					validatorWeight = int(parse(line, "weight:", ')'))
				buff = dict()
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

		local.add_log("start GetConfig36 function", "debug")
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
		local.add_log("start CreateNewKey function", "debug")
		result = self.validatorConsole.Run("newkey")
		key = parse(result, "created new key ", '\n')
		return key
	#end define

	def GetPubKeyBase64(self, key):
		local.add_log("start GetPubKeyBase64 function", "debug")
		result = self.validatorConsole.Run("exportpub " + key)
		validatorPubkey_b64 = parse(result, "got public key: ", '\n')
		return validatorPubkey_b64
	#end define

	def GetPubKey(self, key):
		local.add_log("start GetPubKey function", "debug")
		pubkey_b64 = self.GetPubKeyBase64(key)
		buff = pubkey_b64.encode("utf-8")
		buff = base64.b64decode(buff)
		buff = buff[4:]
		pubkey_hex = buff.hex()
		pubkey_hex = pubkey_hex.upper()
		return pubkey_hex
	#end define

	def AddKeyToValidator(self, key, startWorkTime, endWorkTime):
		local.add_log("start AddKeyToValidator function", "debug")
		output = False
		cmd = "addpermkey {key} {startWorkTime} {endWorkTime}".format(key=key, startWorkTime=startWorkTime, endWorkTime=endWorkTime)
		result = self.validatorConsole.Run(cmd)
		if ("success" in result):
			output = True
		return output
	#end define

	def AddKeyToTemp(self, key, endWorkTime):
		local.add_log("start AddKeyToTemp function", "debug")
		output = False
		result = self.validatorConsole.Run("addtempkey {key} {key} {endWorkTime}".format(key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output
	#end define

	def AddAdnlAddrToValidator(self, adnlAddr):
		local.add_log("start AddAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.Run("addadnl {adnlAddr} 0".format(adnlAddr=adnlAddr))
		if ("success" in result):
			output = True
		return output
	#end define

	def GetAdnlAddr(self):
		adnlAddr = local.db.get("adnlAddr")
		return adnlAddr
	#end define

	def AttachAdnlAddrToValidator(self, adnlAddr, key, endWorkTime):
		local.add_log("start AttachAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.Run("addvalidatoraddr {key} {adnlAddr} {endWorkTime}".format(adnlAddr=adnlAddr, key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output
	#end define

	def CreateConfigProposalRequest(self, offerHash, validatorIndex):
		local.add_log("start CreateConfigProposalRequest function", "debug")
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

	def CreateComplaintRequest(self, electionId , complaintHash, validatorIndex):
		local.add_log("start CreateComplaintRequest function", "debug")
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

	def PrepareComplaint(self, electionId, inputFileName):
		local.add_log("start PrepareComplaint function", "debug")
		fileName = self.tempDir + "complaint-msg-body.boc"
		args = ["envelope-complaint.fif", electionId, inputFileName, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", ')')
		return fileName
	#end define

	def CreateElectionRequest(self, wallet, startWorkTime, adnlAddr, maxFactor):
		local.add_log("start CreateElectionRequest function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-to-sign.bin"
		args = ["validator-elect-req.fif", wallet.addrB64, startWorkTime, maxFactor, adnlAddr, fileName]
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
		local.add_log("start GetValidatorSignature function", "debug")
		cmd = "sign {validatorKey} {var1}".format(validatorKey=validatorKey, var1=var1)
		result = self.validatorConsole.Run(cmd)
		validatorSignature = parse(result, "got signature ", '\n')
		return validatorSignature
	#end define

	def SignElectionRequestWithValidator(self, wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor):
		local.add_log("start SignElectionRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-query.boc"
		args = ["validator-elect-signed.fif", wallet.addrB64, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName
	#end define

	def SignBocWithWallet(self, wallet, bocPath, dest, coins, **kwargs):
		local.add_log("start SignBocWithWallet function", "debug")
		flags = kwargs.get("flags", list())
		subwalletDefault = 698983191 + wallet.workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwalletDefault)

		# Balance checking
		account = self.GetAccount(wallet.addrB64)
		if account.balance < coins + 0.1:
			raise Exception("Wallet balance is less than requested coins")
		#end if
		
		# Bounceable checking
		destAccount = self.GetAccount(dest)
		bounceable = self.IsBounceableAddrB64(dest)
		if bounceable == False and destAccount.status == "active":
			flags += ["-b"]
			text = "Find non-bounceable flag, but destination account already active. Using bounceable flag"
			local.add_log(text, "warning")
		elif "-n" not in flags and bounceable == True and destAccount.status != "active":
			raise Exception("Find bounceable flag, but destination account is not active. Use non-bounceable address or flag -n")
		#end if

		seqno = self.GetSeqno(wallet)
		resultFilePath = self.tempDir + self.nodeName + wallet.name + "_wallet-query"
		if "v1" in wallet.version:
			fiftScript = "wallet.fif"
			args = [fiftScript, wallet.path, dest, seqno, coins, "-B", bocPath, resultFilePath]
		elif "v2" in wallet.version:
			fiftScript = "wallet-v2.fif"
			args = [fiftScript, wallet.path, dest, seqno, coins, "-B", bocPath, resultFilePath]
		elif "v3" in wallet.version:
			fiftScript = "wallet-v3.fif"
			args = [fiftScript, wallet.path, dest, subwallet, seqno, coins, "-B", bocPath, resultFilePath]
		if flags:
			args += flags
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", ")")
		return resultFilePath
	#end define

	def SendFile(self, filePath, wallet=None, **kwargs):
		local.add_log("start SendFile function: " + filePath, "debug")
		timeout = kwargs.get("timeout", 30)
		remove = kwargs.get("remove", True)
		duplicateSendfile = local.db.get("duplicateSendfile", True)
		if not os.path.isfile(filePath):
			raise Exception("SendFile error: no such file '{filePath}'".format(filePath=filePath))
		if timeout and wallet:
			wallet.oldseqno = self.GetSeqno(wallet)
		self.liteClient.Run("sendfile " + filePath)
		if duplicateSendfile:
			try:
				self.liteClient.Run("sendfile " + filePath, useLocalLiteServer=False)
				self.liteClient.Run("sendfile " + filePath, useLocalLiteServer=False)
			except Exception as e:
				local.add_log('failed to send file via liteclient: ' + str(e), 'info')
			self.send_boc_toncenter(filePath)
		if timeout and wallet:
			self.WaitTransaction(wallet, timeout)
		if remove == True:
			os.remove(filePath)
	#end define

	def send_boc_toncenter(self, file_path: str):
		local.add_log('Start send_boc_toncenter function: ' + file_path, 'debug')
		with open(file_path, "rb") as f:
			boc = f.read()
			boc_b64 = base64.b64encode(boc).decode("utf-8")
		data = {"boc": boc_b64}
		if self.GetNetworkName() == 'testnet':
			url = 'https://testnet.toncenter.com/api/v2/sendBoc'
		else:
			url = 'https://toncenter.com/api/v2/sendBoc'
		result = requests.post(url=url, json=data)
		if result.status_code != 200:
			local.add_log(f'Failed to send boc to toncenter: {result.content}', 'info')
			return False
		local.add_log('Sent boc to toncenter', 'info')
		return True

	def WaitTransaction(self, wallet, timeout=30):
		local.add_log("start WaitTransaction function", "debug")
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
		local.add_log("start GetReturnedStake function", "debug")
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
		local.add_log("start ProcessRecoverStake function", "debug")
		resultFilePath = self.tempDir + self.nodeName + "recover-query"
		args = ["recover-stake.fif", resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath
	#end define

	def GetStake(self, account, args=None):
		stake = local.db.get("stake")
		usePool = local.db.get("usePool")
		stakePercent = local.db.get("stakePercent", 99)
		vconfig = self.GetValidatorConfig()
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
				local.add_log("Specified stake must be a percentage or whole number", "error")
				return

			# Limit stake to maximum available amount minus 10 (for transaction fees)
			if stake > account.balance - 10:
				stake = account.balance - 10
		#end if

		if stake is None and usePool:
			stake = account.balance - 20
		if stake is None:
			sp = stakePercent / 100
			if sp > 1 or sp < 0:
				local.add_log("Wrong stakePercent value. Using default stake.", "warning")
			elif len(vconfig.validators) == 0:
				stake = int(account.balance*sp/2)
			elif len(vconfig.validators) > 0:
				stake = int(account.balance*sp)
		#end if

		# Check if we have enough coins
		if stake > config17["maxStake"]:
			text = "Stake is greater than the maximum value. Will be used the maximum stake."
			local.add_log(text, "warning")
			stake = config17["maxStake"]
		if config17["minStake"] > stake:
			text = "Stake less than the minimum stake. Minimum stake: {minStake}".format(minStake=config17["minStake"])
			#local.add_log(text, "error")
			raise Exception(text)
		if stake > account.balance:
			text = "Don't have enough coins. stake: {stake}, account balance: {balance}".format(stake=stake, balance=account.balance)
			#local.add_log(text, "error")
			raise Exception(text)
		#end if

		return stake
	#end define

	def GetMaxFactor(self):
		# Either use defined maxFactor, or set maximal allowed by config17
		maxFactor = local.db.get("maxFactor")
		if maxFactor is None:
			config17 = self.GetConfig17()
			maxFactor = config17["maxStakeFactor"] / 65536
		maxFactor = round(maxFactor, 1)
		return maxFactor
	#end define

	def GetValidatorWallet(self, mode="stake"):
		local.add_log("start GetValidatorWallet function", "debug")
		walletName = local.db.get("validatorWalletName")
		wallet = self.GetLocalWallet(walletName)
		return wallet
	#end define

	def ElectionEntry(self, args=None):
		usePool = local.db.get("usePool")
		wallet = self.GetValidatorWallet()
		addrB64 = wallet.addrB64
		if wallet is None:
			raise Exception("Validator wallet not found")
		#end if

		if usePool:
			pool = self.GetPool(mode="stake")
			addrB64 = pool.addrB64
		#end if

		local.add_log("start ElectionEntry function", "debug")
		# Check if validator is not synchronized
		validatorStatus = self.GetValidatorStatus()
		validatorOutOfSync = validatorStatus.get("outOfSync")
		if validatorOutOfSync > 60:
			local.add_log("Validator is not synchronized", "error")
			return
		#end if

		# Get startWorkTime and endWorkTime
		fullElectorAddr = self.GetFullElectorAddr()
		startWorkTime = self.GetActiveElectionId(fullElectorAddr)

		# Check if elections started
		if (startWorkTime == 0):
			local.add_log("Elections have not yet begun", "info")
			return
		#end if

		# Get ADNL address
		adnlAddr = self.GetAdnlAddr()

		# Check wether it is too early to participate
		if "participateBeforeEnd" in local.db:
			now = time.time()
			if (startWorkTime - now) > local.db["participateBeforeEnd"] and \
			   (now + local.db["periods"]["elections"]) < startWorkTime:
				return
		# Check if election entry already completed
		entries = self.GetElectionEntries()
		if adnlAddr in entries:
			local.add_log("Elections entry already completed", "info")
			return
		#end if

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
		self.AttachAdnlAddrToValidator(adnlAddr, validatorKey, endWorkTime)

		# Get max factor
		maxFactor = self.GetMaxFactor()

		# Create fift's. Continue with pool or walet
		if usePool:
			var1 = self.CreateElectionRequest(pool, startWorkTime, adnlAddr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validatorKey, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithPoolWithValidator(pool, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor, stake)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, pool.addrB64, 1.3)
			self.SendFile(resultFilePath, wallet)
		else:
			var1 = self.CreateElectionRequest(wallet, startWorkTime, adnlAddr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validatorKey, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithValidator(wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, stake)
			self.SendFile(resultFilePath, wallet)
		#end if

		# Save vars to json file
		self.SaveElectionVarsToJsonFile(wallet=wallet, account=account, stake=stake, maxFactor=maxFactor, fullElectorAddr=fullElectorAddr, startWorkTime=startWorkTime, validatorsElectedFor=validatorsElectedFor, endWorkTime=endWorkTime, validatorKey=validatorKey, validatorPubkey_b64=validatorPubkey_b64, adnlAddr=adnlAddr, var1=var1, validatorSignature=validatorSignature, validatorPubkey=validatorPubkey)

		local.add_log("ElectionEntry completed. Start work time: " + str(startWorkTime))
	#end define

	def GetValidatorKeyByTime(self, startWorkTime, endWorkTime):
		local.add_log("start GetValidatorKeyByTime function", "debug")
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

		local.add_log("start RecoverStake function", "debug")
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.GetReturnedStake(fullElectorAddr, wallet.addrB64)
		if returnedStake == 0:
			local.add_log("You have nothing on the return stake", "debug")
			return
		#end if

		resultFilePath = self.ProcessRecoverStake()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, 1)
		self.SendFile(resultFilePath, wallet)
		local.add_log("RecoverStake completed")
	#end define

	def PoolRecoverStake(self, poolAddr):
		wallet = self.GetValidatorWallet()
		if wallet is None:
			raise Exception("Validator wallet not found")
		#end if

		local.add_log("start PoolRecoverStake function", "debug")
		resultFilePath = self.PoolProcessRecoverStake()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 1.2)
		self.SendFile(resultFilePath, wallet)
		local.add_log("PoolRecoverStake completed")
	#end define

	def PoolsUpdateValidatorSet(self):
		local.add_log("start PoolsUpdateValidatorSet function", "debug")
		wallet = self.GetValidatorWallet()
		pools = self.GetPools()
		for pool in pools:
			self.PoolUpdateValidatorSet(pool, wallet)
	#end define

	def PoolUpdateValidatorSet(self, pool, wallet):
		local.add_log("start PoolUpdateValidatorSet function", "debug")
		poolAddr = pool.addrB64
		poolData = self.GetPoolData(poolAddr)
		if poolData is None:
			return
		#en if

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
		if (poolData["state"] == 0 and self.HasPoolWithdrawRequests(pool)):
			self.PoolWithdrawRequests(pool, wallet)
			poolData = self.GetPoolData(poolAddr)
		if (poolData["state"] == 0 and poolAddr in pendingWithdraws):
			self.HandlePendingWithdraw(pendingWithdraws, poolAddr)
	#end define

	def PoolProcessUpdateValidatorSet(self, poolAddr, wallet):
		local.add_log("start PoolProcessUpdateValidatorSet function", "debug")
		resultFilePath = self.tempDir + "pool-update-validator-set-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/update-validator-set.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 1.1)
		self.SendFile(resultFilePath, wallet)
		local.add_log("PoolProcessUpdateValidatorSet completed")
	#end define

	def PoolWithdrawRequests(self, pool, wallet):
		local.add_log("start PoolWithdrawRequests function", "debug")
		resultFilePath = self.PoolProcessWihtdrawRequests()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, pool.addrB64, 10)
		self.SendFile(resultFilePath, wallet)
		local.add_log("PoolWithdrawRequests completed")
	#end define

	def PoolProcessWihtdrawRequests(self):
		local.add_log("start PoolProcessWihtdrawRequests function", "debug")
		resultFilePath = self.tempDir + "pool-withdraw-requests-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/process-withdraw-requests.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath
	#end define

	def HasPoolWithdrawRequests(self, pool):
		cmd = f"runmethodfull {pool.addrB64} has_withdraw_requests"
		result = self.liteClient.Run(cmd)
		buff = self.Result2List(result)
		data = int(buff[0])
		if data == -1:
			return True
		else:
			return False
	#end define

	def SaveElectionVarsToJsonFile(self, **kwargs):
		local.add_log("start SaveElectionVarsToJsonFile function", "debug")
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
		local.add_log("start CreateWallet function", "debug")
		subwalletDefault = 698983191 + workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwalletDefault)
		walletPath = self.walletsDir + name
		if os.path.isfile(walletPath + ".pk") and "v3" not in version:
			local.add_log("CreateWallet error: Wallet already exists: " + name, "warning")
		else:
			if "v1" in version:
				fiftScript = "new-wallet.fif"
				args = [fiftScript, workchain, walletPath]
			if "v2" in version:
				fiftScript = "new-wallet-v2.fif"
				args = [fiftScript, workchain, walletPath]
			if "v3" in version:
				fiftScript = "new-wallet-v3.fif"
				args = [fiftScript, workchain, subwallet, walletPath]
			result = self.fift.Run(args)
			if "Creating new" not in result:
				raise Exception("CreateWallet error")
			#end if
		wallet = self.GetLocalWallet(name, version)
		self.SetWalletVersion(wallet.addrB64, version)
		return wallet
	#end define

	def CreateHighWallet(self, name, **kwargs):
		workchain = kwargs.get("workchain", 0)
		subwalletDefault = 698983191 + workchain # 0x29A9A317 + workchain
		subwallet = kwargs.get("subwallet", subwalletDefault)
		version = kwargs.get("version", "hv1")
		local.add_log("start CreateHighWallet function", "debug")
		walletPath = self.walletsDir + name
		if os.path.isfile(walletPath + ".pk") and os.path.isfile(walletPath + str(subwallet) + ".addr"):
			local.add_log("CreateHighWallet error: Wallet already exists: " + name + str(subwallet), "warning")
		else:
			args = ["new-highload-wallet.fif", workchain, subwallet, walletPath]
			result = self.fift.Run(args)
			if "Creating new high-load wallet" not in result:
				raise Exception("CreateHighWallet error")
			#end if
		hwallet = self.GetLocalWallet(name, version, subwallet)
		self.SetWalletVersion(hwallet.addrB64, version)
		return hwallet
	#end define

	def ActivateWallet(self, wallet):
		local.add_log("start ActivateWallet function", "debug")
		account = self.GetAccount(wallet.addrB64)
		if account.status == "empty":
			raise Exception("ActivateWallet error: account status is empty")
		elif account.status == "active":
			local.add_log("ActivateWallet warning: account status is active", "warning")
		else:
			self.SendFile(wallet.bocFilePath, wallet, remove=False)
	#end define

	def ImportWallet(self, addrB64, key):
		workchain, addr, bounceable = self.ParseAddrB64(addrB64)
		workchain_bytes = int.to_bytes(workchain, 4, "big", signed=True)
		addr_bytes = bytes.fromhex(addr)
		key_bytes = base64.b64decode(key)

		walletName = self.GenerateWalletName()
		walletPath = self.walletsDir + walletName
		file = open(walletPath + ".addr", 'wb')
		file.write(addr_bytes + workchain_bytes)
		file.close()

		file = open(walletPath + ".pk", 'wb')
		file.write(key_bytes)
		file.close()

		return walletName
	#end define

	def ExportWallet(self, walletName):
		wallet = self.GetLocalWallet(walletName)

		file = open(wallet.privFilePath, 'rb')
		data = file.read()
		file.close()
		key = base64.b64encode(data).decode("utf-8")

		return wallet.addrB64, key
	#end define

	def GetWalletsNameList(self):
		local.add_log("start GetWalletsNameList function", "debug")
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

	def GetWallets(self):
		local.add_log("start GetWallets function", "debug")
		wallets = list()
		walletsNameList = self.GetWalletsNameList()
		for walletName in walletsNameList:
			wallet = self.GetLocalWallet(walletName)
			wallets.append(wallet)
		return wallets
	#end define

	def GenerateWalletName(self):
		local.add_log("start GenerateWalletName function", "debug")
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

	def WalletsCheck(self):
		local.add_log("start WalletsCheck function", "debug")
		wallets = self.GetWallets()
		for wallet in wallets:
			if os.path.isfile(wallet.bocFilePath):
				account = self.GetAccount(wallet.addrB64)
				if account.balance > 0:
					self.SendFile(wallet.bocFilePath, wallet)
	#end define

	def GetValidatorConfig(self):
		#local.add_log("start GetValidatorConfig function", "debug")
		result = self.validatorConsole.Run("getconfig")
		text = parse(result, "---------", "--------")
		vconfig = json.loads(text)
		return Dict(vconfig)
	#end define
	
	def GetOverlaysStats(self):
		local.add_log("start GetOverlaysStats function", "debug")
		resultFilePath = local.buffer.my_temp_dir + "getoverlaysstats.json"
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

	def MoveCoins(self, wallet, dest, coins, **kwargs):
		local.add_log("start MoveCoins function", "debug")
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
		if account.balance < coins + 0.1:
			raise Exception("Wallet balance is less than requested coins")
		if account.status != "active":
			raise Exception("Wallet account is uninitialized")
		#end if
		
		# Bounceable checking
		destAccount = self.GetAccount(dest)
		bounceable = self.IsBounceableAddrB64(dest)
		if bounceable == False and destAccount.status == "active":
			flags += ["-b"]
			text = "Find non-bounceable flag, but destination account already active. Using bounceable flag"
			local.add_log(text, "warning")
		elif "-n" not in flags and bounceable == True and destAccount.status != "active":
			raise Exception("Find bounceable flag, but destination account is not active. Use non-bounceable address or flag -n")
		#end if

		seqno = self.GetSeqno(wallet)
		resultFilePath = local.buffer.my_temp_dir + wallet.name + "_wallet-query"
		if "v1" in wallet.version:
			fiftScript = "wallet.fif"
			args = [fiftScript, wallet.path, dest, seqno, coins, "-m", mode, resultFilePath]
		elif "v2" in wallet.version:
			fiftScript = "wallet-v2.fif"
			args = [fiftScript, wallet.path, dest, seqno, coins, "-m", mode, resultFilePath]
		elif "v3" in wallet.version:
			fiftScript = "wallet-v3.fif"
			args = [fiftScript, wallet.path, dest, subwallet, seqno, coins, "-m", mode, resultFilePath]
		if flags:
			args += flags
		result = self.fift.Run(args)
		savedFilePath = parse(result, "Saved to file ", ")")
		self.SendFile(savedFilePath, wallet, timeout=timeout)
	#end define

	def MoveCoinsThroughProxy(self, wallet, dest, coins):
		local.add_log("start MoveCoinsThroughProxy function", "debug")
		wallet1 = self.CreateWallet("proxy_wallet1", 0)
		wallet2 = self.CreateWallet("proxy_wallet2", 0)
		self.MoveCoins(wallet, wallet1.addrB64_init, coins)
		self.ActivateWallet(wallet1)
		self.MoveCoins(wallet1, wallet2.addrB64_init, "alld")
		self.ActivateWallet(wallet2)
		self.MoveCoins(wallet2, dest, "alld", flags=["-n"])
		wallet1.Delete()
		wallet2.Delete()
	#end define

	def MoveCoinsFromHW(self, wallet, destList, **kwargs):
		local.add_log("start MoveCoinsFromHW function", "debug")
		flags = kwargs.get("flags")
		timeout = kwargs.get("timeout", 30)

		if len(destList) == 0:
			local.add_log("MoveCoinsFromHW warning: destList is empty, break function", "warning")
			return
		#end if

		orderFilePath = local.buffer.my_temp_dir + wallet.name + "_order.txt"
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
		resultFilePath = local.buffer.my_temp_dir + wallet.name + "_wallet-query"
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
		local.add_log("start GetElectionEntries function", "debug")
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
		saveElections = local.db.get("saveElections")
		if saveElections is None:
			saveElections = dict()
			local.db["saveElections"] = saveElections
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

	def GetOffers(self):
		local.add_log("start GetOffers function", "debug")
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
			item = dict()
			item["config"] = dict()
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
			config_val = self.GetConfig(param_id)
			pseudohash_bytes = hash.encode() + json.dumps(config_val, sort_keys=True).encode()
			item["pseudohash"] = hashlib.sha256(pseudohash_bytes).hexdigest()
			offers.append(item)
		#end for
		return offers
	#end define

	def GetOfferDiff(self, offerHash):
		local.add_log("start GetOfferDiff function", "debug")
		offer = self.GetOffer(offerHash)
		configId = offer["config"]["id"]
		configValue = offer["config"]["value"]

		if '{' in configValue or '}' in configValue:
			start = configValue.find('{') + 1
			end = configValue.find('}')
			configValue = configValue[start:end]
		#end if

		args = [self.liteClient.appPath, "--global-config", self.liteClient.configPath, "--verbosity", "0"]
		process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		time.sleep(1)

		fullConfigAddr = self.GetFullConfigAddr()
		cmd = "runmethodfull {fullConfigAddr} list_proposals".format(fullConfigAddr=fullConfigAddr)
		process.stdin.write(cmd.encode() + b'\n')
		process.stdin.flush()
		time.sleep(1)

		cmd = "dumpcellas ConfigParam{configId} {configValue}".format(configId=configId, configValue=configValue)
		process.stdin.write(cmd.encode() + b'\n')
		process.stdin.flush()
		time.sleep(1)

		process.terminate()
		text = process.stdout.read().decode()

		lines = text.split('\n')
		b = len(lines)
		for i in range(b):
			line = lines[i]
			if "dumping cells as values of TLB type" in line:
				a = i + 2
				break
		#end for

		for i in range(a, b):
			line = lines[i]
			if '(' in line:
				start = i
				break
		#end for

		for i in range(a, b):
			line = lines[i]
			if '>' in line:
				end = i
				break
		#end for

		buff = lines[start:end]
		text = "".join(buff)
		newData = self.Tlb2Json(text)
		newFileName = self.tempDir + "data1diff"
		file = open(newFileName, 'wt')
		newText = json.dumps(newData, indent=2)
		file.write(newText)
		file.close()

		oldData = self.GetConfig(configId)
		oldFileName = self.tempDir + "data2diff"
		file = open(oldFileName, 'wt')
		oldText = json.dumps(oldData, indent=2)
		file.write(oldText)
		file.close()

		print(oldText)
		args = ["diff", "--color", oldFileName, newFileName]
		subprocess.run(args)
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
		local.add_log("start GetComplaints function", "debug")
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
			complaints[pseudohash] = item
		#end for

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
		saveComplaints = local.db.get("saveComplaints")
		if saveComplaints is None:
			saveComplaints = dict()
			local.db["saveComplaints"] = saveComplaints
		buff = saveComplaints.copy()
		for key, item in buff.items():
			diffTime = timestamp - int(key)
			if diffTime > 604800:
				saveComplaints.pop(key)
		return saveComplaints
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
		local.add_log("start GetComplaintsNumber function", "debug")
		result = dict()
		complaints = self.GetComplaints()
		votedComplaints = self.GetVotedComplaints()
		buff = 0
		for key, item in complaints.items():
			pubkey = item.get("pubkey")
			electionId = item.get("electionId")
			pseudohash = pubkey + str(electionId)
			if pseudohash in votedComplaints:
				continue
			buff += 1
		result["all"] = len(complaints)
		result["new"] = buff
		return result
	#end define

	def GetComplaint(self, electionId, complaintHash):
		local.add_log("start GetComplaint function", "debug")
		complaints = self.GetComplaints(electionId)
		for key, item in complaints.items():
			if complaintHash == item.get("hash"):
				return item
		raise Exception("GetComplaint error: complaint not found.")
	#end define

	def SignProposalVoteRequestWithValidator(self, offerHash, validatorIndex, validatorPubkey_b64, validatorSignature):
		local.add_log("start SignProposalVoteRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + "proposal_vote-msg-body.boc"
		args = ["config-proposal-vote-signed.fif", "-i", validatorIndex, offerHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
		return fileName
	#end define

	def SignComplaintVoteRequestWithValidator(self, complaintHash, electionId, validatorIndex, validatorPubkey_b64, validatorSignature):
		local.add_log("start SignComplaintRequestWithValidator function", "debug")
		fileName = self.tempDir + "complaint_vote-msg-body.boc"
		args = ["complaint-vote-signed.fif", validatorIndex, electionId, complaintHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.Run(args)
		fileName = parse(result, "Saved to file ", '\n')
		return fileName
	#end define

	def VoteOffer(self, offerHash):
		local.add_log("start VoteOffer function", "debug")
		fullConfigAddr = self.GetFullConfigAddr()
		wallet = self.GetValidatorWallet(mode="vote")
		validatorKey = self.GetValidatorKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)
		validatorIndex = self.GetValidatorIndex()
		offer = self.GetOffer(offerHash)
		if validatorIndex in offer.get("votedValidators"):
			local.add_log("Proposal already has been voted", "debug")
			return
		self.AddSaveOffer(offer)
		var1 = self.CreateConfigProposalRequest(offerHash, validatorIndex)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		resultFilePath = self.SignProposalVoteRequestWithValidator(offerHash, validatorIndex, validatorPubkey_b64, validatorSignature)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullConfigAddr, 1.5)
		self.SendFile(resultFilePath, wallet)
	#end define

	def VoteComplaint(self, electionId, complaintHash):
		local.add_log("start VoteComplaint function", "debug")
		complaintHash = int(complaintHash)
		fullElectorAddr = self.GetFullElectorAddr()
		wallet = self.GetValidatorWallet(mode="vote")
		validatorKey = self.GetValidatorKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)
		validatorIndex = self.GetValidatorIndex()
		complaint = self.GetComplaint(electionId, complaintHash)
		votedValidators = complaint.get("votedValidators")
		pubkey = complaint.get("pubkey")
		if validatorIndex in votedValidators:
			local.add_log("Complaint already has been voted", "info")
			return
		var1 = self.CreateComplaintRequest(electionId, complaintHash, validatorIndex)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		resultFilePath = self.SignComplaintVoteRequestWithValidator(complaintHash, electionId, validatorIndex, validatorPubkey_b64, validatorSignature)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, 1.5)
		self.SendFile(resultFilePath, wallet)
		self.AddVotedComplaints(complaint)
	#end define

	def SaveComplaints(self, electionId):
		local.add_log("start SaveComplaints function", "debug")
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

	def CheckComplaint(self, filePath):
		local.add_log("start CheckComplaint function", "debug")
		cmd = "loadproofcheck {filePath}".format(filePath=filePath)
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

	def GetOnlineValidators(self):
		onlineValidators = list()
		validators = self.GetValidatorsList()
		for validator in validators:
			online = validator.get("online")
			if online is True:
				onlineValidators.append(validator)
		if len(onlineValidators) == 0:
			onlineValidators = None
		return onlineValidators
	#end define

	def GetValidatorsLoad(self, start, end, saveCompFiles=False):
		# Get buffer
		bname = f"validatorsLoad{start}{end}"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if

		text = "start GetValidatorsLoad function ({}, {})".format(start, end)
		local.add_log(text, "debug")
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

	def GetValidatorsList(self, past=False):
		# Get buffer
		bname = "validatorsList" + str(past)
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff
		#end if
		
		timestamp = get_timestamp()
		end = timestamp - 60
		start = end - 2000
		config = self.GetConfig34()
		if past:
			config = self.GetConfig32()
			start = config.get("startWorkTime")
			end = config.get("endWorkTime") - 60
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
			if saveElectionEntries and adnlAddr in saveElectionEntries:
				validator["walletAddr"] = saveElectionEntries[adnlAddr]["walletAddr"]
		#end for
		
		# Set buffer
		self.SetFunctionBuffer(bname, validators)
		return validators
	#end define

	def find_myself_in_el(self):
		save_elections = self.GetSaveElections()
		my_adnl = self.GetAdnlAddr()
		for election_id, election in save_elections.items():
			for adnl in election:
				if adnl == my_adnl:
					return True
		return False
	#end define

	def CheckValidators(self, start, end):
		local.add_log("start CheckValidators function", "debug")
		electionId = start
		complaints = self.GetComplaints(electionId)
		data = self.GetValidatorsLoad(start, end, saveCompFiles=True)
		fullElectorAddr = self.GetFullElectorAddr()
		wallet = self.GetValidatorWallet(mode="vote")

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
			if pseudohash in complaints:
				continue
			# Create complaint
			fileName = self.PrepareComplaint(electionId, fileName)
			fileName = self.SignBocWithWallet(wallet, fileName, fullElectorAddr, 300)
			self.SendFile(fileName, wallet)
			local.add_log("var1: {}, var2: {}, pubkey: {}, election_id: {}".format(var1, var2, pubkey, electionId), "debug")
	#end define

	def GetOffer(self, offerHash):
		local.add_log("start GetOffer function", "debug")
		offers = self.GetOffers()
		for offer in offers:
			if offerHash == offer.get("hash"):
				return offer
		raise Exception("GetOffer error: offer not found.")
	#end define

	def GetOffersNumber(self):
		local.add_log("start GetOffersNumber function", "debug")
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
		local.add_log("GetValidatorIndex warning: index not found.", "warning")
		return -1
	#end define

	def GetValidatorEfficiency(self, adnlAddr=None):
		local.add_log("start GetValidatorEfficiency function", "debug")
		validators = self.GetValidatorsList()
		if adnlAddr is None:
			adnlAddr = self.GetAdnlAddr()
		for validator in validators:
			searchAdnlAddr = validator.get("adnlAddr")
			if adnlAddr == searchAdnlAddr:
				efficiency = validator.get("efficiency")
				return efficiency
		local.add_log("GetValidatorEfficiency warning: efficiency not found.", "warning")
	#end define

	def GetDbUsage(self):
		path = "/var/ton-work/db"
		data = psutil.disk_usage(path)
		return data.percent
	#end define

	def GetDbSize(self, exceptions="log"):
		local.add_log("start GetDbSize function", "debug")
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
	
	def GetDomainFromAuction(self, walletName, addr):
		wallet = self.GetLocalWallet(walletName)
		bocPath = local.buffer.my_temp_dir + "get_dns_data.boc"
		bocData = bytes.fromhex("b5ee9c7241010101000e0000182fcb26a20000000000000000f36cae4d")
		with open(bocPath, 'wb') as file:
			file.write(bocData)
		resultFilePath = self.SignBocWithWallet(wallet, bocPath, addr, 0.1)
		self.SendFile(resultFilePath, wallet)
	#end define

	def NewDomain(self, domain):
		local.add_log("start NewDomain function", "debug")
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

		fileName = self.tempDir + "dns-msg-body.boc"
		args = ["auto-dns.fif", dnsAddr, "add", subdomain, expireInSec, "owner", wallet.addrB64, "cat", catId, "adnl", domain["adnlAddr"], "-o", fileName]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", ')')
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, dnsAddr, 1.7)
		self.SendFile(resultFilePath, wallet)
		self.AddDomain(domain)
	#end define

	def AddDomain(self, domain):
		if "domains" not in local.db:
			local.db["domains"] = list()
		#end if
		local.db["domains"].append(domain)
		local.save()
	#end define

	def GetDomains(self):
		domains = local.db.get("domains", list())
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
				local.save()
				return
		raise Exception("DeleteDomain error: Domain not found")
	#end define

	def GetAutoTransferRules(self):
		autoTransferRules = local.db.get("autoTransferRules")
		if autoTransferRules is None:
			autoTransferRules = list()
			local.db["autoTransferRules"] = autoTransferRules
		return autoTransferRules
	#end define

	def AddAutoTransferRule(self, rule):
		autoTransferRules = self.GetAutoTransferRules()
		autoTransferRules.append(rule)
		local.save()
	#end define

	def AddBookmark(self, bookmark):
		if "bookmarks" not in local.db:
			local.db["bookmarks"] = list()
		#end if
		local.db["bookmarks"].append(bookmark)
		local.save()
	#end define

	def GetBookmarks(self):
		bookmarks = local.db.get("bookmarks")
		if bookmarks is not None:
			for bookmark in bookmarks:
				self.WriteBookmarkData(bookmark)
		return bookmarks
	#end define

	def GetBookmarkAddr(self, type, name):
		bookmarks = local.db.get("bookmarks", list())
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
				local.save()
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
				data = timestamp2datetime(endTime, "%d.%m.%Y")
		else:
			data = "null"
		bookmark["data"] = data
	#end define

	def GetSaveOffers(self):
		bname = "saveOffers"
		saveOffers = local.db.get(bname)
		if saveOffers is None or isinstance(saveOffers, list):
			saveOffers = dict()
			local.db[bname] = saveOffers
		return saveOffers
	#end define

	def AddSaveOffer(self, offer):
		offerHash = offer.get("hash")
		offerPseudohash = offer.get("pseudohash")
		saveOffers = self.GetSaveOffers()
		if offerHash not in saveOffers:
			saveOffers[offerHash] = offerPseudohash
			local.save()
	#end define

	def GetVotedComplaints(self):
		bname = "votedComplaints"
		votedComplaints = local.db.get(bname)
		if votedComplaints is None:
			votedComplaints = dict()
			local.db[bname] = votedComplaints
		return votedComplaints
	#end define

	def AddVotedComplaints(self, complaint):
		pseudohash = complaint.get("pseudohash")
		votedComplaints = self.GetVotedComplaints()
		if pseudohash not in votedComplaints:
			votedComplaints[pseudohash] = complaint
			local.save()
	#end define

	def GetDestinationAddr(self, destination):
		if self.IsAddrB64(destination):
			pass
		elif self.IsAddrFull(destination):
			destination = self.AddrFull2AddrB64(destination)
		else:
			walletsNameList = self.GetWalletsNameList()
			if destination in walletsNameList:
				wallet = self.GetLocalWallet(destination)
				destination = wallet.addrB64
		return destination
	#end define

	def AddrFull2AddrB64(self, addrFull, bounceable=True):
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
			local.add_log(text, "warning")
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
			statistics = local.db.get("statistics")
		if statistics:
			netLoadAvg = statistics.get("netLoadAvg")
		else:
			netLoadAvg = [-1, -1, -1]
		return netLoadAvg
	#end define

	def GetTpsAvg(self, statistics=None):
		if statistics is None:
			statistics = local.db.get("statistics")
		if statistics:
			tpsAvg = statistics.get("tpsAvg")
		else:
			tpsAvg = [-1, -1, -1]
		return tpsAvg
	#end define

	def GetStatistics(self, name, statistics=None):
		if statistics is None:
			statistics = local.db.get("statistics")
		if statistics:
			data = statistics.get(name)
		else:
			data = [-1, -1, -1]
		return data
	#end define

	def GetSettings(self, name):
		#local.load_db()
		result = local.db.get(name)
		return result
	#end define

	def SetSettings(self, name, data):
		try:
			data = json.loads(data)
		except: pass
		local.db[name] = data
		local.save()
	#end define

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
		local.add_log("start SignShardOverlayCert function", "debug")
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
		local.add_log("start ImportShardOverlayCert function", "debug")
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
			local.add_log("ImportShardOverlayCert warning: certificate not found", "warning")
			return
		#end if

		file = open(fileName, 'wb')
		file.write(cert)
		file.close()

		self.ImportCertificate(pubkey, fileName)
	#end define

	def ImportCertificate(self, pubkey, fileName):
		local.add_log("start ImportCertificate function", "debug")
		cmd = "importshardoverlaycert {workchain} {shardprefix} {pubkey} {certfile}"
		cmd = cmd.format(workchain=-1, shardprefix=-9223372036854775808, pubkey=pubkey, certfile=fileName)
		result = self.validatorConsole.Run(cmd)
	#end define

	def GetValidatorsWalletsList(self):
		result = list()
		vl = self.GetValidatorsList()
		for item in vl:
			walletAddr = item["walletAddr"]
			result.append(walletAddr)
		return result
	#end define

	def DownloadContract(self, url, branch=None):
		local.add_log("start DownloadContract function", "debug")
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

	def CreatePool(self, poolName, validatorRewardSharePercent, maxNominatorsCount, minValidatorStake, minNominatorStake):
		local.add_log("start CreatePool function", "debug")
		validatorRewardShare = int(validatorRewardSharePercent * 100)
		contractPath = self.contractsDir + "nominator-pool/"
		if not os.path.isdir(contractPath):
			self.DownloadContract("https://github.com/ton-blockchain/nominator-pool")
		#end if

		filePath = self.poolsDir + poolName
		if os.path.isfile(filePath + ".addr"):
			local.add_log("CreatePool warning: Pool already exists: " + filePath, "warning")
			return
		#end if

		fiftScript = self.contractsDir + "nominator-pool/func/new-pool.fif"
		wallet = self.GetValidatorWallet()
		args = [fiftScript, wallet.addrB64, validatorRewardShare, maxNominatorsCount, minValidatorStake, minNominatorStake, filePath]
		result = self.fift.Run(args)
		if "Saved pool" not in result:
			raise Exception("CreatePool error: " + result)
		#end if
		
		pools = self.GetPools()
		newPool = self.GetLocalPool(poolName)
		for pool in pools:
			if pool.name != newPool.name and pool.addrB64 == newPool.addrB64:
				newPool.Delete()
				raise Exception("CreatePool error: Pool with the same parameters already exists.")
		#end for
	#end define

	def ActivatePool(self, pool, ex=True):
		local.add_log("start ActivatePool function", "debug")
		for i in range(10):
			time.sleep(3)
			account = self.GetAccount(pool.addrB64)
			if account.balance > 0:
				self.SendFile(pool.bocFilePath, pool, timeout=False)
				return
		if ex:
			raise Exception("ActivatePool error: time out")
	#end define

	def DepositToPool(self, walletName, poolAddr, amount):
		wallet = self.GetLocalWallet(walletName)
		bocPath = local.buffer.my_temp_dir + wallet.name + "validator-deposit-query.boc"
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
		local.add_log("start WithdrawFromPoolProcess function", "debug")
		wallet = self.GetValidatorWallet()
		bocPath = local.buffer.my_temp_dir + wallet.name + "validator-withdraw-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/validator-withdraw.fif"
		args = [fiftScript, amount, bocPath]
		result = self.fift.Run(args)
		resultFilePath = self.SignBocWithWallet(wallet, bocPath, poolAddr, 1.35)
		self.SendFile(resultFilePath, wallet)
	#end define
	
	def PendWithdrawFromPool(self, poolAddr, amount):
		local.add_log("start PendWithdrawFromPool function", "debug")
		pendingWithdraws = self.GetPendingWithdraws()
		pendingWithdraws[poolAddr] = amount
		local.save()
	#end define
	
	def HandlePendingWithdraw(self, pendingWithdraws, poolAddr):
		amount = pendingWithdraws.get(poolAddr)
		self.WithdrawFromPoolProcess(poolAddr, amount)
		pendingWithdraws.pop(poolAddr)
	#end define
	
	def GetPendingWithdraws(self):
		bname = "pendingWithdraws"
		pendingWithdraws = local.db.get(bname)
		if pendingWithdraws is None:
			pendingWithdraws = dict()
			local.db[bname] = pendingWithdraws
		return pendingWithdraws
	#end define

	def SignElectionRequestWithPoolWithValidator(self, pool, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor, stake):
		local.add_log("start SignElectionRequestWithPoolWithValidator function", "debug")
		fileName = self.tempDir + str(startWorkTime) + "_validator-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/validator-elect-signed.fif"
		args = [fiftScript, pool.addrB64, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName, stake]
		result = self.fift.Run(args)
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName
	#end define

	def PoolProcessRecoverStake(self):
		local.add_log("start PoolProcessRecoverStake function", "debug")
		resultFilePath = self.tempDir + "recover-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/recover-stake.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.Run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath
	#end define

	def GetLocalPool(self, poolName):
		local.add_log("start GetLocalPool function", "debug")
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
		local.add_log("start GetPoolsNameList function", "debug")
		poolsNameList = list()
		for fileName in os.listdir(self.poolsDir):
			if fileName.endswith(".addr"):
				fileName = fileName[:fileName.rfind('.')]
				poolsNameList.append(fileName)
		poolsNameList.sort()
		return poolsNameList
	#end define

	def GetPools(self):
		local.add_log("start GetPools function", "debug")
		pools = list()
		poolsNameList = self.GetPoolsNameList()
		for poolName in poolsNameList:
			pool = self.GetLocalPool(poolName)
			pools.append(pool)
		return pools
	#end define

	def GetPool(self, mode):
		pools = self.GetPools()
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
		local.add_log("start GetPoolData function", "debug")
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

	def get_custom_overlays(self):
		if 'custom_overlays' not in local.db:
			local.db['custom_overlays'] = {}
		return local.db['custom_overlays']

	def set_custom_overlay(self, name: str, config: dict):
		overlays = self.get_custom_overlays()
		overlays[name] = config
		local.save()

	def delete_custom_overlay(self, name: str):
		del local.db['custom_overlays'][name]
		local.save()

	def GetNetworkName(self):
		mainnetValidatorsElectedFor = 65536
		mainnetZerostateRootHash = "x55B13F6D0E1D0C34C9C2160F6F918E92D82BF9DDCF8DE2E4C94A3FDF39D15446"
		config12 = self.GetConfig(12)
		config15 = self.GetConfig15()
		validatorsElectedFor = config15["validatorsElectedFor"]
		zerostateRootHash = config12["workchains"]["root"]["node"]["value"]["zerostate_root_hash"]
		if (zerostateRootHash == mainnetZerostateRootHash and
			validatorsElectedFor == mainnetValidatorsElectedFor):
			return "mainnet"
		else:
			return "testnet"
	#end define
	
	def GetFunctionBuffer(self, name, timeout=10):
		timestamp = get_timestamp()
		buff = local.buffer.get(name)
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
		local.buffer[name] = buff
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

def ng2g(ng):
	if ng is None:
		return
	return int(ng)/10**9
#end define

def Init():
	# Event reaction
	if ("-e" in sys.argv):
		x = sys.argv.index("-e")
		eventName = sys.argv[x+1]
		Event(eventName)
	#end if

	local.run()

	# statistics
	local.buffer.blocksData = dict()
	local.buffer.transData = dict()
	local.buffer.network = [None]*15*6
	local.buffer.diskio = [None]*15*6

	# scan blocks
	local.buffer.masterBlocksList = list()
	local.buffer.prevShardsBlock = dict()
	local.buffer.blocksNum = 0
	local.buffer.transNum = 0
#end define

def Event(eventName):
	if eventName == "enableVC":
		EnableVcEvent()
	elif eventName == "validator down":
		ValidatorDownEvent()
	local.exit()
#end define

def EnableVcEvent():
	local.add_log("start EnableVcEvent function", "debug")
	# Создать новый кошелек для валидатора
	ton = MyTonCore()
	wallet = ton.CreateWallet("validator_wallet_001", -1)
	local.db["validatorWalletName"] = wallet.name

	# Создать новый ADNL адрес для валидатора
	adnlAddr = ton.CreateNewKey()
	ton.AddAdnlAddrToValidator(adnlAddr)
	local.db["adnlAddr"] = adnlAddr

	# Сохранить
	local.save()
#end define

def ValidatorDownEvent():
	local.add_log("start ValidatorDownEvent function", "debug")
	local.add_log("Validator is down", "error")
#end define

def Elections(ton):
	usePool = local.db.get("usePool")
	if usePool == True:
		ton.PoolsUpdateValidatorSet()
		ton.RecoverStake()
		ton.ElectionEntry()
	else:
		ton.RecoverStake()
		ton.ElectionEntry()
#end define

def Statistics():
	ReadNetworkData()
	SaveNetworkStatistics()
	#ReadTransData(scanner)
	SaveTransStatistics()
	ReadDiskData()
	SaveDiskStatistics()
#end define

def ReadDiskData():
	timestamp = get_timestamp()
	disks = GetDisksList()
	buff = psutil.disk_io_counters(perdisk=True)
	data = dict()
	for name in disks:
		data[name] = dict()
		data[name]["timestamp"] = timestamp
		data[name]["busyTime"] = buff[name].busy_time
		data[name]["readBytes"] = buff[name].read_bytes
		data[name]["writeBytes"] = buff[name].write_bytes
		data[name]["readCount"] = buff[name].read_count
		data[name]["writeCount"] = buff[name].write_count
	#end for

	local.buffer.diskio.pop(0)
	local.buffer.diskio.append(data)
#end define

def SaveDiskStatistics():
	data = local.buffer.diskio
	data = data[::-1]
	zerodata = data[0]
	buff1 = data[1*6-1]
	buff5 = data[5*6-1]
	buff15 = data[15*6-1]
	if buff5 is None:
		buff5 = buff1
	if buff15 is None:
		buff15 = buff5
	#end if

	disksLoadAvg = dict()
	disksLoadPercentAvg = dict()
	iopsAvg = dict()
	disks = GetDisksList()
	for name in disks:
		if zerodata[name]["busyTime"] == 0:
			continue
		diskLoad1, diskLoadPercent1, iops1 = CalculateDiskStatistics(zerodata, buff1, name)
		diskLoad5, diskLoadPercent5, iops5 = CalculateDiskStatistics(zerodata, buff5, name)
		diskLoad15, diskLoadPercent15, iops15 = CalculateDiskStatistics(zerodata, buff15, name)
		disksLoadAvg[name] = [diskLoad1, diskLoad5, diskLoad15]
		disksLoadPercentAvg[name] = [diskLoadPercent1, diskLoadPercent5, diskLoadPercent15]
		iopsAvg[name] = [iops1, iops5, iops15]
	#end fore

	# save statistics
	statistics = local.db.get("statistics", dict())
	statistics["disksLoadAvg"] = disksLoadAvg
	statistics["disksLoadPercentAvg"] = disksLoadPercentAvg
	statistics["iopsAvg"] = iopsAvg
	local.db["statistics"] = statistics
#end define

def CalculateDiskStatistics(zerodata, data, name):
	if data is None:
		return None, None, None
	data = data[name]
	zerodata = zerodata[name]
	timeDiff = zerodata["timestamp"] - data["timestamp"]
	busyTimeDiff = zerodata["busyTime"] - data["busyTime"]
	diskReadDiff = zerodata["readBytes"] - data["readBytes"]
	diskWriteDiff = zerodata["writeBytes"] - data["writeBytes"]
	diskReadCountDiff = zerodata["readCount"] - data["readCount"]
	diskWriteCountDiff = zerodata["writeCount"] - data["writeCount"]
	diskLoadPercent = busyTimeDiff /1000 /timeDiff *100 # /1000 - to second, *100 - to percent
	diskLoadPercent = round(diskLoadPercent, 2)
	diskRead = diskReadDiff /timeDiff
	diskWrite = diskWriteDiff /timeDiff
	diskReadCount = diskReadCountDiff /timeDiff
	diskWriteCount = diskWriteCountDiff /timeDiff
	diskLoad = b2mb(diskRead + diskWrite)
	iops = round(diskReadCount + diskWriteCount, 2)
	return diskLoad, diskLoadPercent, iops
#end define

def GetDisksList():
	data = list()
	buff = os.listdir("/sys/block/")
	for item in buff:
		if "loop" in item:
			continue
		data.append(item)
	#end for
	data.sort()
	return data
#end define

def ReadNetworkData():
	timestamp = get_timestamp()
	interfaceName = get_internet_interface_name()
	buff = psutil.net_io_counters(pernic=True)
	buff = buff[interfaceName]
	data = dict()
	data["timestamp"] = timestamp
	data["bytesRecv"] = buff.bytes_recv
	data["bytesSent"] = buff.bytes_sent
	data["packetsSent"] = buff.packets_sent
	data["packetsRecv"] = buff.packets_recv

	local.buffer.network.pop(0)
	local.buffer.network.append(data)
#end define

def SaveNetworkStatistics():
	data = local.buffer.network
	data = data[::-1]
	zerodata = data[0]
	buff1 = data[1*6-1]
	buff5 = data[5*6-1]
	buff15 = data[15*6-1]
	if buff5 is None:
		buff5 = buff1
	if buff15 is None:
		buff15 = buff5
	#end if

	netLoadAvg = dict()
	ppsAvg = dict()
	networkLoadAvg1, ppsAvg1 = CalculateNetworkStatistics(zerodata, buff1)
	networkLoadAvg5, ppsAvg5 = CalculateNetworkStatistics(zerodata, buff5)
	networkLoadAvg15, ppsAvg15 = CalculateNetworkStatistics(zerodata, buff15)
	netLoadAvg = [networkLoadAvg1, networkLoadAvg5, networkLoadAvg15]
	ppsAvg = [ppsAvg1, ppsAvg5, ppsAvg15]

	# save statistics
	statistics = local.db.get("statistics", dict())
	statistics["netLoadAvg"] = netLoadAvg
	statistics["ppsAvg"] = ppsAvg
	local.db["statistics"] = statistics
#end define

def CalculateNetworkStatistics(zerodata, data):
	if data is None:
		return None, None
	timeDiff = zerodata["timestamp"] - data["timestamp"]
	bytesRecvDiff = zerodata["bytesRecv"] - data["bytesRecv"]
	bytesSentDiff = zerodata["bytesSent"] - data["bytesSent"]
	packetsRecvDiff = zerodata["packetsRecv"] - data["packetsRecv"]
	packetsSentDiff = zerodata["packetsSent"] - data["packetsSent"]
	bitesRecvAvg = bytesRecvDiff /timeDiff *8
	bitesSentAvg = bytesSentDiff /timeDiff *8
	packetsRecvAvg = packetsRecvDiff /timeDiff
	packetsSentAvg = packetsSentDiff /timeDiff
	netLoadAvg = b2mb(bitesRecvAvg + bitesSentAvg)
	ppsAvg = round(packetsRecvAvg + packetsSentAvg, 2)
	return netLoadAvg, ppsAvg
#end define

def ReadTransData(scanner):
	transData = local.buffer.transData
	SetToTimeData(transData, scanner.transNum)
	ShortTimeData(transData)
#end define

def SetToTimeData(timeDataList, data):
	timenow = int(time.time())
	timeDataList[timenow] = data
#end define

def ShortTimeData(data, max=120, diff=20):
	if len(data) < max:
		return
	buff = data.copy()
	data.clear()
	keys = sorted(buff.keys(), reverse=True)
	for item in keys[:max-diff]:
		data[item] = buff[item]
#end define

def SaveTransStatistics():
	tps1 = GetTps(60)
	tps5 = GetTps(60*5)
	tps15 = GetTps(60*15)

	# save statistics
	statistics = local.db.get("statistics", dict())
	statistics["tpsAvg"] = [tps1, tps5, tps15]
	local.db["statistics"] = statistics
#end define

def GetDataPerSecond(data, timediff):
	if len(data) == 0:
		return
	timenow = sorted(data.keys())[-1]
	now = data.get(timenow)
	prev = GetItemFromTimeData(data, timenow-timediff)
	if prev is None:
		return
	diff = now - prev
	result = diff / timediff
	result = round(result, 2)
	return result
#end define

def GetItemFromTimeData(data, timeneed):
	if timeneed in data:
		result = data.get(timeneed)
	else:
		result = data[min(data.keys(), key=lambda k: abs(k-timeneed))]
	return result
#end define


def GetTps(timediff):
	data = local.buffer.transData
	tps = GetDataPerSecond(data, timediff)
	return tps
#end define

def GetBps(timediff):
	data = local.buffer.blocksData
	bps = GetDataPerSecond(data, timediff)
	return bps
#end define

def GetBlockTimeAvg(timediff):
	bps = GetBps(timediff)
	if bps is None or bps == 0:
		return
	result = 1/bps
	result = round(result, 2)
	return result
#end define

def Offers(ton):
	saveOffers = ton.GetSaveOffers()
	offers = ton.GetOffers()
	for offer in offers:
		offerHash = offer.get("hash")
		offerPseudohash = offer.get("pseudohash")
		saveOfferPseudohash = saveOffers.get(offerHash)
		if offerPseudohash == saveOfferPseudohash:
			ton.VoteOffer(offerHash)
#end define

def Domains(ton):
	pass
#end define

def GetUname():
	data = os.uname()
	result = dict(zip('sysname nodename release version machine'.split(), data))
	result.pop("nodename")
	return result
#end define

def GetMemoryInfo():
	result = dict()
	data = psutil.virtual_memory()
	result["total"] = round(data.total / 10**9, 2)
	result["usage"] = round(data.used / 10**9, 2)
	result["usagePercent"] = data.percent
	return result
#end define

def GetSwapInfo():
	result = dict()
	data = psutil.swap_memory()
	result["total"] = round(data.total / 10**9, 2)
	result["usage"] = round(data.used / 10**9, 2)
	result["usagePercent"] = data.percent
	return result
#end define


def parse_db_stats(path: str):
	with open(path) as f:
		lines = f.readlines()
	result = {}
	for line in lines:
		s = line.strip().split(maxsplit=1)
		items = re.findall(r"(\S+)\s:\s(\S+)", s[1])
		if len(items) == 1:
			item = items[0]
			if float(item[1]) > 0:
				result[s[0]] = float(item[1])
		else:
			if any(float(v) > 0 for k, v in items):
				result[s[0]] = {}
				result[s[0]] = {k: float(v) for k, v in items}
	return result
# end define


def get_db_stats():
    result = {
        'rocksdb': {
            'ok': True,
            'message': '',
            'data': {}
        },
        'celldb': {
            'ok': True,
            'message': '',
            'data': {}
        },
    }
    rocksdb_stats_path = '/var/ton-work/db/db_stats.txt'
    celldb_stats_path = '/var/ton-work/db/celldb/db_stats.txt'
    if os.path.exists(rocksdb_stats_path):
        try:
            result['rocksdb']['data'] = parse_db_stats(rocksdb_stats_path)
        except Exception as e:
            result['rocksdb']['ok'] = False
            result['rocksdb']['message'] = f'failed to fetch db stats: {e}'
    else:
        result['rocksdb']['ok'] = False
        result['rocksdb']['message'] = 'db stats file is not exists'
    # end if

    if os.path.exists(celldb_stats_path):
        try:
            result['celldb']['data'] = parse_db_stats(celldb_stats_path)
        except Exception as e:
            result['celldb']['ok'] = False
            result['celldb']['message'] = f'failed to fetch db stats: {e}'
    else:
        result['celldb']['ok'] = False
        result['celldb']['message'] = 'db stats file is not exists'
    # end if

    return result
# end define


def GetValidatorProcessInfo():
	pid = get_service_pid("validator")
	if pid == None or pid == 0:
		return
	p = psutil.Process(pid)
	mem = p.memory_info()
	result = dict()
	result["cpuPercent"] = p.cpu_percent()
	memory = dict()
	memory["rss"] = mem.rss
	memory["vms"] = mem.vms
	memory["shared"] = mem.shared
	memory["text"] = mem.text
	memory["lib"] = mem.lib
	memory["data"] = mem.data
	memory["dirty"] = mem.dirty
	result["memory"] = memory
	#io = p.io_counters() # Permission denied: '/proc/{pid}/io'
	return result
#end define

def Telemetry(ton):
	sendTelemetry = local.db.get("sendTelemetry")
	if sendTelemetry is not True:
		return
	#end if

	# Get validator status
	data = dict()
	data["adnlAddr"] = ton.GetAdnlAddr()
	data["validatorStatus"] = ton.GetValidatorStatus()
	data["cpuNumber"] = psutil.cpu_count()
	data["cpuLoad"] = get_load_avg()
	data["netLoad"] = ton.GetStatistics("netLoadAvg")
	data["tps"] = ton.GetStatistics("tpsAvg")
	data["disksLoad"] = ton.GetStatistics("disksLoadAvg")
	data["disksLoadPercent"] = ton.GetStatistics("disksLoadPercentAvg")
	data["iops"] = ton.GetStatistics("iopsAvg")
	data["pps"] = ton.GetStatistics("ppsAvg")
	data["dbUsage"] = ton.GetDbUsage()
	data["memory"] = GetMemoryInfo()
	data["swap"] = GetSwapInfo()
	data["uname"] = GetUname()
	data["vprocess"] = GetValidatorProcessInfo()
	data["dbStats"] = get_db_stats()
	elections = local.try_function(ton.GetElectionEntries)
	complaints = local.try_function(ton.GetComplaints)

	# Get git hashes
	gitHashes = dict()
	gitHashes["mytonctrl"] = get_git_hash("/usr/src/mytonctrl")
	gitHashes["validator"] = GetBinGitHash("/usr/bin/ton/validator-engine/validator-engine")
	data["gitHashes"] = gitHashes
	data["stake"] = local.db.get("stake")
	
	# Get validator config
	vconfig = ton.GetValidatorConfig()
	data["fullnode_adnl"] = vconfig.fullnode

	# Send data to toncenter server
	liteUrl_default = "https://telemetry.toncenter.com/report_status"
	liteUrl = local.db.get("telemetryLiteUrl", liteUrl_default)
	output = json.dumps(data)
	resp = requests.post(liteUrl, data=output, timeout=3)
#end define

def GetBinGitHash(path, short=False):
	if not os.path.isfile(path):
		return
	args = [path, "--version"]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	if "build information" not in output:
		return
	buff = output.split(' ')
	start = buff.index("Commit:") + 1
	result = buff[start].replace(',', '')
	if short is True:
		result = result[:7]
	return result
#end define

def OverlayTelemetry(ton):
	sendTelemetry = local.db.get("sendTelemetry")
	if sendTelemetry is not True:
		return
	#end if

	# Get validator status
	data = dict()
	data["adnlAddr"] = ton.GetAdnlAddr()
	data["overlaysStats"] = ton.GetOverlaysStats()

	# Send data to toncenter server
	overlayUrl_default = "https://telemetry.toncenter.com/report_overlays"
	overlayUrl = local.db.get("overlayTelemetryUrl", overlayUrl_default)
	output = json.dumps(data)
	resp = requests.post(overlayUrl, data=output, timeout=3)
#end define

def Complaints(ton):
	validatorIndex = ton.GetValidatorIndex()
	if validatorIndex < 0:
		return
	#end if

	# Voting for complaints
	config32 = ton.GetConfig32()
	electionId = config32.get("startWorkTime")
	complaintsHashes = ton.SaveComplaints(electionId)
	complaints = ton.GetComplaints(electionId)
	for key, item in complaints.items():
		complaintHash = item.get("hash")
		complaintHash_hex = Dec2HexAddr(complaintHash)
		if complaintHash_hex in complaintsHashes:
			ton.VoteComplaint(electionId, complaintHash)
#end define

def Slashing(ton):
	isSlashing = local.db.get("isSlashing")
	if isSlashing is not True:
		return
	#end if

	# Creating complaints
	slash_time = local.buffer.slash_time
	config32 = ton.GetConfig32()
	start = config32.get("startWorkTime")
	end = config32.get("endWorkTime")
	local.add_log("slash_time {}, start {}, end {}".format(slash_time, start, end), "debug")
	if slash_time != start:
		end -= 60
		ton.CheckValidators(start, end)
		local.buffer.slash_time = start
#end define

def ScanLiteServers(ton):
	# Считать список серверов
	filePath = ton.liteClient.configPath
	file = open(filePath, 'rt')
	text = file.read()
	file.close()
	data = json.loads(text)

	# Пройтись по серверам
	result = list()
	liteservers = data.get("liteservers")
	for index in range(len(liteservers)):
		try:
			ton.liteClient.Run("last", index=index)
			result.append(index)
		except: pass
	#end for

	# Записать данные в базу
	local.db["liteServers"] = result
#end define

def General():
	local.add_log("start General function", "debug")
	ton = MyTonCore()

	# Запустить потоки
	local.start_cycle(Elections, sec=600, args=(ton, ))
	local.start_cycle(Statistics, sec=10)
	local.start_cycle(Offers, sec=600, args=(ton, ))
	local.start_cycle(Complaints, sec=600, args=(ton, ))
	local.start_cycle(Slashing, sec=600, args=(ton, ))
	local.start_cycle(Domains, sec=600, args=(ton, ))
	local.start_cycle(Telemetry, sec=60, args=(ton, ))
	local.start_cycle(OverlayTelemetry, sec=7200, args=(ton, ))
	local.start_cycle(ScanLiteServers, sec=60, args=(ton,))
	local.start_cycle(custom_overlays, sec=60, args=(local, ton,))
	thr_sleep()
#end define

def Dec2HexAddr(dec):
	h = dec2hex(dec)
	hu = h.upper()
	h64 = hu.rjust(64, "0")
	return h64
#end define

def xhex2hex(x):
	try:
		b = x[1:]
		h = b.lower()
		return h
	except:
		return None
#end define

def hex2base64(h):
	b = bytes.fromhex(h)
	b64 = base64.b64encode(b)
	s = b64.decode("utf-8")
	return s
#end define




###
### Start of the program
###

if __name__ == "__main__":
	Init()
	General()
#end if
