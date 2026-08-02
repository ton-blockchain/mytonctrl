from __future__ import annotations

import os
import base64
import time
import json
import hashlib
import struct
import typing
from dataclasses import asdict
from typing import Union, Any

import psutil
import subprocess
import requests
from fastcrc import crc16

from modules import MODES
from mytoncore.stats_collector import StatsCollector
from mytoncore.utils import (
    b642hex,
    xhex2hex,
    ng2g,
    get_package_resource_path,
    raw_addr_to_b64,
	nano_ton_to_ton,
	dec2hex
)
from mytoncore.output import (
	get_cell_body,
	lc_result_to_list,
	tlb_to_json,
	get_var_from_text,
	get_var_from_dict,
	get_int_from_dict,
	get_item_from_dict,
	get_key_from_dict, get_var_from_worker_output,
)
from mytoncore.clients import Fift, LiteClient, ValidatorConsole
from mytoncore.models import (
    Config,
    Paths,
    ValidatorConfigExt,
    Wallet,
    Account,
    Block,
    Transaction,
    Message,
    Pool,
    Config15,
    ElectionsParticipant,
    Config17,
    CacheResult,
    BlockHead,
    WorkchainConfig,
)

from mypylib.mypylib import (
	parse,
	get_timestamp,
	Dict, int2ip, MyPyClass,
	parse_int_forced
)
from mytoncore.vm_stack import parse_result_stack, parse_remote_result_stack


class MyTonCore:
	def __init__(self, local: MyPyClass):
		self.local: MyPyClass = local
		self.nodeName: str = ""
		self.cache: dict[str, CacheResult] = {}

		self.walletsDir = self.local.my_work_dir + "wallets/"
		self.contractsDir = self.local.my_work_dir + "contracts/"
		self.poolsDir = self.local.my_work_dir + "pools/"
		self.tempDir = self.local.my_temp_dir

		os.makedirs(self.walletsDir, exist_ok=True)
		os.makedirs(self.contractsDir, exist_ok=True)
		os.makedirs(self.poolsDir, exist_ok=True)

		self._lite_client: LiteClient | None = None
		self._validator_console: ValidatorConsole | None = None
		self._fift: Fift | None = None

		mconfig_path = self.local.db_path
		backup_path = mconfig_path + ".backup"
		if self.local.db.get("liteClient") is None or self.local.db.get("fift") is None:
			self.restore_db_file(mconfig_path, backup_path)
		else:
			self.check_db_backup(backup_path)

		self.apply_db_settings()

	def apply_db_settings(self):
		lite_client_config = self.local.db.get("liteClient")
		fift_config = self.local.db.get("fift")
		vc_config = self.local.db.get("validatorConsole")

		self.nodeName = self.local.db.get("nodeName")
		if self.nodeName is None:
			self.nodeName=""
		else:
			self.nodeName = self.nodeName + "_"

		if lite_client_config is not None:
			ls_pubkey_path = None
			ls_addr = None
			ls_config = lite_client_config.get("liteServer")
			if ls_config is not None:
				ls_pubkey_path = ls_config["pubkeyPath"]
				ls_addr = f"{ls_config['ip']}:{ls_config['port']}"
			self._lite_client = LiteClient(
				self.local,
				lite_client_config["appPath"],
				lite_client_config["configPath"],
				ls_pubkey_path,
				ls_addr,
				self.GetValidatorStatus
			)

		if vc_config is not None:
			self._validator_console = ValidatorConsole(
				self.local, vc_config["appPath"], vc_config["privKeyPath"], vc_config["pubKeyPath"], vc_config["addr"]
			)

		if fift_config is not None:
			self._fift = Fift(self.local, fift_config["appPath"], fift_config["libsPath"], fift_config["smartcontsPath"])

	@property
	def liteClient(self) -> LiteClient:
		if self._lite_client is None:
			raise RuntimeError("LiteClient is not initialized")
		return self._lite_client

	@property
	def validatorConsole(self) -> ValidatorConsole:
		if self._validator_console is None:
			raise RuntimeError("ValidatorConsole is not initialized")
		return self._validator_console

	@property
	def fift(self) -> Fift:
		if self._fift is None:
			raise RuntimeError("Fift is not initialized")
		return self._fift

	def restore_db_file(self, mconfig_path: str, backup_path: str):
		self.local.add_log(f"Restoring db file {mconfig_path} from backup {backup_path}", "warning")
		print(f"self.local.db: {self.local.db}")
		if os.path.isfile(backup_path):
			self.local.add_log("Restoring the configuration file", "info")
			args = ["cp", backup_path, mconfig_path]
			subprocess.run(args)
			self.local.load_db(mconfig_path)
		else:
			self.local.add_log("Backup file not found", "error")

	def check_db_backup(self, backup_path: str):
		if not os.path.isfile(backup_path) or time.time() - os.path.getmtime(backup_path) > 3600:
			self.local.try_function(self.create_self_db_backup)

	def create_self_db_backup(self):
		self.local.add_log("Create backup config file", "info")
		mconfig_path = self.local.db_path
		backup_path = mconfig_path + ".backup"
		backup_tmp_path = backup_path + '.tmp'
		subprocess.run(["cp", mconfig_path, backup_tmp_path])
		try:
			with open(backup_tmp_path, "r") as file:
				json.load(file)
			os.rename(backup_tmp_path, backup_path)  # atomic opetation
		except Exception:
			self.local.add_log("Could not update backup, backup_tmp file is broken", "warning")
			os.remove(backup_tmp_path)

	def get_paths(self) -> Paths:
		paths = self.local.db.get("paths")
		if paths is None:
			return Paths()
		return Paths.from_dict(paths)

	def run_get_method(self, addr: str, method: str) -> list[str]:
		cmd = f"runmethodfull {addr} {method}"
		result = self.liteClient.run(cmd)
		return parse_result_stack(result)

	def run_get_method_local(self, addr: str, method: str, params: list | None = None) -> list[str]:
		cmd = f"runmethod {addr} {method}"
		if params:
			cmd += " " + " ".join(map(str, params))
		result = self.liteClient.run_local(cmd)
		return parse_remote_result_stack(result)

	def get_seqno(self, wallet: Wallet) -> int:
		seqno = int(self.run_get_method(wallet.addrB64, "seqno")[0])
		wallet.seqno = seqno
		self.local.add_log(f"got seqno {seqno} for {wallet.addrB64}", "debug")
		return seqno

	def GetAccount(self, inputAddr: str):
		#self.local.add_log("start GetAccount function", "debug")
		workchain, addr = self.ParseInputAddr(inputAddr)
		account = Account(workchain, addr)
		cmd = "getaccount {inputAddr}".format(inputAddr=inputAddr)
		result = self.liteClient.run(cmd)
		storage = get_var_from_worker_output(result, "storage")
		if storage is None:
			return account
		balance = get_var_from_worker_output(storage, "balance")
		grams = get_var_from_worker_output(balance, "grams")
		value = get_var_from_worker_output(grams, "value")
		state = get_var_from_worker_output(storage, "state")
		code_buff = get_var_from_worker_output(state, "code")
		code = get_var_from_worker_output(code_buff, "value")
		code_hash = None
		if code is not None:
			code = get_cell_body(code.split('\n'))
			code_bytes = bytes.fromhex(code)
			code_hash = hashlib.sha256(code_bytes).hexdigest()
		status = parse(state, "account_", '\n')
		if status is not None:
			account.status = status
		if value is not None:
			account.balance = nano_ton_to_ton(int(value))
		account.lt = parse(result, "lt = ", ' ')
		account.hash = parse(result, "hash = ", '\n')
		account.codeHash = code_hash
		return account

	def GetAccountHistory(self, account, limit) -> list[Message]:
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

	def LastTransDump(self, addr, lt, transHash, count=10):
		history: list[Message] = list()
		cmd = f"lasttransdump {addr} {lt} {transHash} {count}"
		result = self.liteClient.run(cmd)
		data = self.Result2Dict(result)
		prevTrans = get_key_from_dict(data, "previous transaction")
		prevTransLt = get_var_from_text(prevTrans, "lt")
		prevTransHash = get_var_from_text(prevTrans, "hash")
		for key, item in data.items():
			if "transaction #" not in key:
				continue
			block_str = parse(key, "from block ", ' ')
			if block_str is None:
				raise ValueError(f'Invalid transaction block: {key}')
			description = get_key_from_dict(item, "description")
			type = get_var_from_text(description, "trans_")
			time = get_int_from_dict(item, "time")
			#outmsg = get_int_from_dict(item, "outmsg_cnt")
			total_fees = get_int_from_dict(item, "total_fees.grams.value")
			messages = self.GetMessagesFromTransaction(item)
			tr = Transaction(block=Block.from_str(block_str), type=type, time=time, total_fees=ng2g(total_fees))
			history += self.parse_messages(messages, tr)
		return history, prevTransLt, prevTransHash

	def parse_messages(self, messages: list[dict[str, Any]], tr: Transaction) -> list[Message]:
		history = list()
		for data in messages:
			src_addr, dest_addr = None, None

			src_workchain = get_int_from_dict(data, "message.info.src.workchain_id")
			address = get_var_from_dict(data, "message.info.src.address")
			if address is not None:
				src_addr = xhex2hex(address)

			dest_workchain = get_int_from_dict(data, "message.info.dest.workchain_id")
			address = get_var_from_dict(data, "message.info.dest.address")
			if address is not None:
				dest_addr = xhex2hex(address)

			grams = get_int_from_dict(data, "message.info.value.grams.value")

			message = get_item_from_dict(data, "message")
			body = get_item_from_dict(message, "body")
			value = get_item_from_dict(body, "value")
			body = None
			if value is not None:
				body = get_cell_body(value) or None

			message = Message(
				transaction=tr,
				src_workchain=src_workchain,
				dest_workchain=dest_workchain,
				src_addr=src_addr,
				dest_addr=dest_addr,
				value=ng2g(grams),
				body=body,
			)
			history.append(message)
		return history

	def GetMessagesFromTransaction(self, data):
		result = list()
		for key, item in data.items():
			if ("inbound message" in key or
			"outbound message" in key):
				result.append(item)
		result.reverse()
		return result

	def GetLocalWallet(self, wallet_name: str, version=None, subwallet=None) -> Wallet:
		walletPath = self.walletsDir + wallet_name
		if version and "h" in version:
			wallet = self.GetHighWalletFromFile(walletPath, subwallet, version)
		else:
			wallet = self.GetWalletFromFile(walletPath, version)
		return wallet

	def GetWalletFromFile(self, filePath, version):
		# Check input args
		if (".addr" in filePath):
			filePath = filePath.replace(".addr", '')
		if (".pk" in filePath):
			filePath = filePath.replace(".pk", '')
		if not os.path.isfile(filePath + ".pk"):
			raise Exception("GetWalletFromFile error: Private key not found: " + filePath)

		# Create wallet object
		walletName = filePath[filePath.rfind('/')+1:]
		wallet = Wallet.from_file(walletName, filePath, version)
		self.WalletVersion2Wallet(wallet)
		return wallet

	def GetHighWalletFromFile(self, filePath, subwallet, version):
		# Check input args
		if (".addr" in filePath):
			filePath = filePath.replace(".addr", '')
		if (".pk" in filePath):
			filePath = filePath.replace(".pk", '')
		if not os.path.isfile(filePath + ".pk"):
			raise Exception("GetHighWalletFromFile error: Private key not found: " + filePath)

		# Create wallet object
		walletName = filePath[filePath.rfind('/')+1:]
		wallet = Wallet.from_file(walletName, filePath, version, subwallet)
		self.WalletVersion2Wallet(wallet)
		return wallet

	def WalletVersion2Wallet(self, wallet):
		if wallet.version is not None:
			return
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

	def SetWalletVersion(self, addrB64, version):
		walletsVersionList = self.GetWalletsVersionList()
		walletsVersionList[addrB64] = version
		self.local.save()

	def GetVersionFromCodeHash(self, inputHash):
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

	def GetWalletsVersionList(self):
		bname = "walletsVersionList"
		walletsVersionList = self.local.db.get(bname)
		if walletsVersionList is None:
			walletsVersionList = dict()
			self.local.db[bname] = walletsVersionList
		return walletsVersionList

	def GetFullConfigAddr(self):
		# Get buffer
		bname = "fullConfigAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff

		result = self.liteClient.run("getconfig 0")
		configAddr_hex = get_var_from_worker_output(result, "config_addr:x")
		fullConfigAddr = "-1:{configAddr_hex}".format(configAddr_hex=configAddr_hex)

		# Set buffer
		self.SetFunctionBuffer(bname, fullConfigAddr)
		return fullConfigAddr

	def GetFullElectorAddr(self):
		# Get buffer
		bname = "fullElectorAddr"
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff

		# Get data
		result = self.liteClient.run("getconfig 1")
		electorAddr_hex = get_var_from_worker_output(result, "elector_addr:x")
		fullElectorAddr = "-1:{electorAddr_hex}".format(electorAddr_hex=electorAddr_hex)

		# Set buffer
		self.SetFunctionBuffer(bname, fullElectorAddr)
		return fullElectorAddr

	def GetActiveElectionId(self, full_elector_addr: str) -> int:
		cmd = "runmethodfull {fullElectorAddr} active_election_id".format(fullElectorAddr=full_elector_addr)
		result = self.liteClient.run(cmd)
		activeElectionId = get_var_from_worker_output(result, "result")
		if activeElectionId is None:
			raise ValueError(f"result is not found: {result}")
		activeElectionId = activeElectionId.replace(' ', '')
		activeElectionId = parse(activeElectionId, '[', ']')
		if activeElectionId is None:
			raise ValueError(f"election id is not found: {result}")
		activeElectionId = int(activeElectionId)
		return activeElectionId

	def GetLastBlock(self):
		block = None
		cmd = "last"
		result = self.liteClient.run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "latest masterchain block" in line:
				buff = line.split(' ')
				block = Block.from_str(buff[7])
				break
		return block

	def GetInitBlock(self) -> BlockHead:
		block = self.GetLastBlock()
		cmd = f"gethead {block}"
		result = self.liteClient.run(cmd)
		seqno =  parse(result, "prev_key_block_seqno=", '\n')
		data = self.GetBlockHead(-1, 8000000000000000, seqno)
		return data

	def GetBlockHead(self, workchain, shardchain, seqno) -> BlockHead:
		block = self.GetBlock(workchain, shardchain, seqno)
		data: BlockHead = {"seqno": block.seqno, "rootHash": block.rootHash, "fileHash": block.fileHash}
		return data

	def GetBlock(self, workchain, shardchain, seqno):
		cmd = "byseqno {workchain}:{shardchain} {seqno}"
		cmd = cmd.format(workchain=workchain, shardchain=shardchain, seqno=seqno)
		result = self.liteClient.run(cmd)
		block_str =  parse(result, "block header of ", ' ')
		if block_str is None:
			raise ValueError(f"block is not found: {result}")
		block = Block.from_str(block_str)
		return block

	def GetShards(self, block=None):
		shards = list()
		if block:
			cmd = "allshards {block}".format(block=block)
		else:
			cmd = "allshards"
		result = self.liteClient.run(cmd)
		lines = result.split('\n')
		for line in lines:
			if "shard #" in line:
				buff = line.split(' ')
				shard_id = buff[1]
				shard_id = shard_id.replace('#', '')
				shard_block = Block.from_str(buff[3])
				shard = {"id": shard_id, "block": shard_block}
				shards.append(shard)
		return shards

	def GetShardsNumber(self, block=None):
		shards = self.GetShards(block)
		shardsNum = len(shards)
		return shardsNum

	def parse_stats_from_vc(self, output: str, result: dict):
		for line in output.split('\n'):
			if len(line.split('\t\t\t')) == 2:
				name, value = line.split('\t\t\t')  # https://github.com/ton-blockchain/ton/blob/master/validator-engine-console/validator-engine-console-query.cpp#L648
				if name not in result:
					result[name] = value

	def GetValidatorStatus(self, no_cache: bool = False) -> Dict:
		# Get buffer
		bname = "validator_status"
		buff = self.GetFunctionBuffer(bname)
		if buff and not no_cache:
			return buff

		self.local.add_log("start GetValidatorStatus function", "debug")
		status = Dict()
		result = None
		try:
			# Parse
			status.is_working = True
			result = self.validatorConsole.run("getstats")
			status.unixtime = parse_int_forced(result, "unixtime", '\n')
			status.masterchainblocktime = parse_int_forced(result, "masterchainblocktime", '\n')
			status.stateserializermasterchainseqno = parse_int_forced(result, "stateserializermasterchainseqno", '\n')
			status.shardclientmasterchainseqno = parse_int_forced(result, "shardclientmasterchainseqno", '\n')
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
			status.last_deleted_mc_state = parse_int_forced(result, "last_deleted_mc_state", '\n')
			state_serializer_enabled = parse(result, "stateserializerenabled", '\n')
			if state_serializer_enabled is not None:
				status.stateserializerenabled = state_serializer_enabled.strip() == "true"
			self.local.try_function(self.parse_stats_from_vc, args=[result, status])
			if 'active_validator_groups' in status:
				groups = status.active_validator_groups.split()  # master:1 shard:2
				status.validator_groups_master = int(groups[0].split(':')[1])
				status.validator_groups_shard = int(groups[1].split(':')[1])
		except Exception as ex:
			self.local.add_log(f"GetValidatorStatus warning: {ex}", "warning")
			status.is_working = False
			if result is not None:
				self.local.try_function(self.parse_stats_from_vc, args=[result, status])
		status.initial_sync = status.get("process.initial_sync")

		# old vars
		status.outOfSync = status.out_of_sync
		status.isWorking = status.is_working

		# Set buffer
		self.SetFunctionBuffer(bname, status)
		return status

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

	_Nested = typing.Dict[str, Union[str, int, "_Nested"]]
	def get_config(self, config_id: int) -> _Nested:
		bname = "config" + str(config_id)
		buff = self.GetFunctionBuffer(bname, timeout=10)
		if buff:
			return buff
		cmd = f"getconfig {config_id}"
		result = self.liteClient.run(cmd)
		text = result[result.find("ConfigParam"):]
		data = tlb_to_json(text)
		self.SetFunctionBuffer(bname, data)
		return data

	def get_basechain_config(self) -> WorkchainConfig:
		result = self.liteClient.run("getconfig 12")
		return WorkchainConfig.from_str(result)

	def get_root_workchain_enabled_time(self) -> int:
		enabled_time = self.get_basechain_config().enabled_since
		return enabled_time

	def get_config_15(self) -> Config15:
		result = self.liteClient.run("getconfig 15")
		return Config15.from_str(result)

	def get_config_17(self) -> Config17:
		result = self.liteClient.run("getconfig 17")
		return Config17.from_str(result)

	def get_config_32(self) -> Config:
		bname = "typed_config32"
		buff = self.GetFunctionBuffer(bname, timeout=10)
		if buff:
			return buff
		result = self.liteClient.run("getconfig 32")
		config32 = Config.from_str(result)
		self.SetFunctionBuffer(bname, config32)
		return config32

	def get_config_34(self, no_cache: bool = False) -> Config:
		bname = "typed_config34"
		buff = self.GetFunctionBuffer(bname, timeout=10)
		if buff and not no_cache:
			return buff
		result = self.liteClient.run("getconfig 34")
		config34 = Config.from_str(result)
		self.SetFunctionBuffer(bname, config34)
		return config34

	def get_config_36(self) -> Config | None:
		result = self.liteClient.run("getconfig 36")
		if 'ConfigParam(36) = (null)' in result:
			return None
		return Config.from_str(result)

	def CreateNewKey(self):
		self.local.add_log("start CreateNewKey function", "debug")
		result = self.validatorConsole.run("newkey")
		key = parse(result, "created new key ", '\n')
		if key is None:
			raise Exception(f"Failed to get new ket: {result}")
		return key

	def GetPubKeyBase64(self, key: str):
		self.local.add_log("start GetPubKeyBase64 function", "debug")
		result = self.validatorConsole.run("exportpub " + key)
		validatorPubkey_b64 = parse(result, "got public key: ", '\n')
		if validatorPubkey_b64 is None:
			raise Exception(f"Failed to get public key: {result}")
		return validatorPubkey_b64

	def get_clean_pubkey_hex(self, key: str):
		validator_pubkey_b64 = self.GetPubKeyBase64(key)
		return b642hex(validator_pubkey_b64)[8:].upper()  # skip magic prefix

	def AddKeyToValidator(self, key, startWorkTime, endWorkTime):
		self.local.add_log("start AddKeyToValidator function", "debug")
		output = False
		cmd = "addpermkey {key} {startWorkTime} {endWorkTime}".format(key=key, startWorkTime=startWorkTime, endWorkTime=endWorkTime)
		result = self.validatorConsole.run(cmd)
		if ("success" in result):
			output = True
		return output

	def AddKeyToTemp(self, key: str, endWorkTime: int):
		self.local.add_log("start AddKeyToTemp function", "debug")
		output = False
		result = self.validatorConsole.run("addtempkey {key} {key} {endWorkTime}".format(key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output

	def add_adnl_addr(self, adnl_addr: str, category: int = 0) -> bool:
		self.local.add_log(f"adding {adnl_addr} adnl addr category {category}", "debug")
		result = self.validatorConsole.run(f"addadnl {adnl_addr} {category}")
		return "success" in result

	def update_adnl_category(self, adnl_addr: str, category: int) -> bool:
		res = self.add_adnl_addr(adnl_addr=adnl_addr, category=category)
		if res:
			self.local.add_log(f"Changed category for {adnl_addr} ADNL address in validator config", "info")
			return True
		else:
			self.local.add_log(f"Failed to change category for {adnl_addr} ADNL address in validator config", "error")
			return False

	def GetAdnlAddr(self) -> str | None:
		adnlAddr = self.local.db.get("adnlAddr")
		return adnlAddr

	def AttachAdnlAddrToValidator(self, adnlAddr, key, endWorkTime):
		self.local.add_log("start AttachAdnlAddrToValidator function", "debug")
		output = False
		result = self.validatorConsole.run("addvalidatoraddr {key} {adnlAddr} {endWorkTime}".format(adnlAddr=adnlAddr, key=key, endWorkTime=endWorkTime))
		if ("success" in result):
			output = True
		return output

	def CreateConfigProposalRequest(self, offerHash, validatorIndex):
		self.local.add_log("start CreateConfigProposalRequest function", "debug")
		fileName = self.tempDir + self.nodeName + "proposal_validator-to-sign.req"
		args = ["config-proposal-vote-req.fif", "-i", validatorIndex, offerHash, fileName]
		result = self.fift.run(args)
		fileName = parse(result, "Saved to file ", '\n')
		resultList = result.split('\n')
		i = 0
		start_index = 0
		for item in resultList:
			if "Creating a request to vote for configuration proposal" in item:
				start_index = i
			i += 1
		var1 = resultList[start_index + 1]
		return var1

	def CreateComplaintRequest(self, electionId, complaintHash, validatorIndex):
		self.local.add_log("start CreateComplaintRequest function", "debug")
		fileName = self.tempDir + "complaint_validator-to-sign.req"
		args = ["complaint-vote-req.fif", validatorIndex, electionId, complaintHash, fileName]
		result = self.fift.run(args)
		fileName = parse(result, "Saved to file ", '\n')
		resultList = result.split('\n')
		i = 0
		start_index = 0
		for item in resultList:
			if "Creating a request to vote for complaint" in item:
				start_index = i
			i += 1
		var1 = resultList[start_index + 1]
		return var1

	def remove_proofs_from_complaint(self, input_file_name: str):
		self.local.add_log("start remove_proofs_from_complaint function", "debug")
		output_file_name = self.tempDir + "complaint-new.boc"
		with get_package_resource_path('mytoncore', 'complaints/remove-proofs-v2.fif') as fift_script:
			args = [fift_script, input_file_name, output_file_name]
			self.fift.run(args)
		return output_file_name


	def PrepareComplaint(self, electionId, inputFileName):
		self.local.add_log("start PrepareComplaint function", "debug")
		fileName = self.tempDir + "complaint-msg-body.boc"
		args = ["envelope-complaint.fif", electionId, inputFileName, fileName]
		result = self.fift.run(args)
		fileName = parse(result, "Saved to file ", ')')
		return fileName

	def CreateElectionRequest(self, addrB64, startWorkTime, adnlAddr, maxFactor):
		self.local.add_log("start CreateElectionRequest function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-to-sign.bin"
		args = ["validator-elect-req.fif", addrB64, startWorkTime, maxFactor, adnlAddr, fileName]
		result = self.fift.run(args)
		fileName = parse(result, "Saved to file ", '\n')
		resultList = result.split('\n')
		i = 0
		start_index = 0
		for item in resultList:
			if "Creating a request to participate in validator elections" in item:
				start_index = i
			i += 1
		var1 = resultList[start_index + 1]
		return var1

	def GetValidatorSignature(self, validatorKey, var1):
		self.local.add_log("start GetValidatorSignature function", "debug")
		cmd = "sign {validatorKey} {var1}".format(validatorKey=validatorKey, var1=var1)
		result = self.validatorConsole.run(cmd)
		validatorSignature = parse(result, "got signature ", '\n')
		return validatorSignature

	def SignElectionRequestWithValidator(self, wallet, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor):
		self.local.add_log("start SignElectionRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + str(startWorkTime) + "_validator-query.boc"
		args = ["validator-elect-signed.fif", wallet.addrB64, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.run(args)
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName

	def SignBocWithWallet(self, wallet: Wallet, boc_path, dest, coins, boc_mode: str = "--body"):
		self.local.add_log("start SignBocWithWallet function", "debug")
		flags = []

		# Balance checking
		account = self.GetAccount(wallet.addrB64)
		self.check_account_balance(account, coins + 0.1)

		# Bounceable checking
		destAccount = self.GetAccount(dest)
		bounceable = self.IsBounceableAddrB64(dest)
		if not bounceable and destAccount.status == "active":
			flags += ["--force-bounce"]
			text = "Find non-bounceable flag, but destination account already active. Using bounceable flag"
			self.local.add_log(text, "warning")
		elif "-n" not in flags and bounceable and destAccount.status != "active":
			raise Exception("Find bounceable flag, but destination account is not active. Use non-bounceable address or flag -n")

		seqno = str(self.get_seqno(wallet))
		result_file_path = self.tempDir + self.nodeName + wallet.name + "_wallet-query"
		if "v1" in wallet.version:
			fift_script = "wallet.fif"
			args = [fift_script, wallet.path, dest, seqno, coins, boc_mode, boc_path, result_file_path]
		elif "v2" in wallet.version:
			fift_script = "wallet-v2.fif"
			args = [fift_script, wallet.path, dest, seqno, coins, boc_mode, boc_path, result_file_path]
		elif "v3" in wallet.version:
			if wallet.subwallet is None:
				subwallet = str(698983191 + wallet.workchain)  # 0x29A9A317 + workchain
			else:
				subwallet = str(wallet.subwallet)
			fift_script = "wallet-v3.fif"
			args = [fift_script, wallet.path, dest, subwallet, seqno, coins, boc_mode, boc_path, result_file_path]
		else:
			raise Exception(f"SignBocWithWallet error: Wallet version '{wallet.version}' is not supported")
		if flags:
			args += flags
		result = self.fift.run(args)
		result_file_path = parse(result, "Saved to file ", ")")
		if not result_file_path:
			raise Exception(f"Failed to get file with boc: {result}")
		return result_file_path

	def SendFile(self, file_path: str, wallet: Wallet | None = None, timeout: int = 30, remove: bool = True):
		self.local.add_log("start SendFile function: " + file_path, "debug")
		duplicateSendfile = self.local.db.get("duplicateSendfile", True)
		telemetry = self.local.db.get("sendTelemetry", False)
		duplicateApi = self.local.db.get("duplicateApi", telemetry)
		if not os.path.isfile(file_path):
			raise Exception("SendFile error: no such file '{filePath}'".format(filePath=file_path))
		old_seqno = None
		if wallet:
			old_seqno = wallet.seqno
		self.liteClient.run("sendfile " + file_path)
		if duplicateSendfile:
			try:
				self.liteClient.run("sendfile " + file_path, use_local=False)
				self.liteClient.run("sendfile " + file_path, use_local=False)
			except Exception:
				pass
		if duplicateApi:
			try:
				self.send_boc_toncenter(file_path)
			except Exception as e:
				self.local.add_log(f'Failed to send file {file_path} to toncenter: {e}', 'warning')
		if timeout and wallet and old_seqno is not None:
			self.WaitTransaction(wallet, old_seqno, timeout)
		if remove:
			try:
				os.remove(file_path)
			except Exception as e:
				self.local.add_log(f'Failed to remove file {file_path}: {e}', 'warning')

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
		if url is None:
			return False
		result = requests.post(url=url, json=data, timeout=3)
		if result.status_code != 200:
			self.local.add_log(f'Failed to send boc to toncenter: {result.content}', 'info')
			return False
		self.local.add_log('Sent boc to toncenter', 'info')
		return True

	def WaitTransaction(self, wallet: Wallet, old_seqno: int, timeout: int = 30):
		self.local.add_log("start WaitTransaction function", "debug")
		timesleep = 3
		steps = timeout // timesleep
		for i in range(steps):
			time.sleep(timesleep)
			try:
				seqno = self.get_seqno(wallet)
			except Exception:
				self.local.add_log("WaitTransaction error: Can't get seqno", "warning")
				continue
			if seqno != old_seqno:
				self.local.add_log("WaitTransaction success", "info")
				return
		raise Exception("WaitTransaction error: time out")

	def get_returned_stake(self, full_elector_addr: str, input_addr: str) -> float:
		workchain, addr = self.ParseInputAddr(input_addr)
		cmd = f"runmethodfull {full_elector_addr} compute_returned_stake 0x{addr}"
		result = self.liteClient.run(cmd)
		stack = lc_result_to_list(result)
		if not isinstance(stack[0], int):
			raise TypeError(f'Got incorrect type: {stack}')
		returned_stake = nano_ton_to_ton(stack[0])
		return returned_stake

	def ProcessRecoverStake(self):
		self.local.add_log("start ProcessRecoverStake function", "debug")
		resultFilePath = self.tempDir + self.nodeName + "recover-query"
		args = ["recover-stake.fif", resultFilePath]
		result = self.fift.run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath

	def GetStake(self, account: Account):
		stake = self.local.db.get("stake")
		usePool = self.using_pool()
		useController = self.using_liquid_staking()
		stakePercent = self.local.db.get("stakePercent", 100)
		stake_no_split = self.local.db.get("stakeNoSplit", False)
		vconfig = self.GetValidatorConfig()
		config17 = self.get_config_17()

		is_single_nominator = self.is_account_single_nominator(account)

		if stake is None and usePool and not is_single_nominator:
			stake = account.balance - 20
		if stake is None and useController:
			stake = account.balance - 50
		if stake is None:
			sp = stakePercent / 100
			if sp > 1 or sp < 0:
				self.local.add_log("Wrong stakePercent value. Using default stake.", "warning")
				stakePercent = 100
				sp = 1
			if len(vconfig.validators) == 0 and not stake_no_split:
				stake = int(account.balance*sp/2)
				if stake < config17.min_stake:  # not enough funds to divide them by 2
					stake = int(account.balance*sp)
			else:
				stake = int(account.balance*sp)
			if stakePercent == 100:
				stake -= 20

		if stake is None:
			raise Exception("Failed to get stake")

		# Check if we have enough coins
		if stake > config17.max_stake:
			text = "Stake is greater than the maximum value. Will be used the maximum stake."
			self.local.add_log(text, "warning")
			stake = config17.max_stake
		if config17.min_stake > stake:
			text = "Stake less than the minimum stake. Minimum stake: {minStake}".format(minStake=config17.min_stake)
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
			config17 = self.get_config_17()
			maxFactor = config17.max_stake_factor / 65536
		maxFactor = round(maxFactor, 1)
		return maxFactor

	def GetValidatorWallet(self):
		wallet_name = self.local.db.get("validatorWalletName")
		if wallet_name is None:
			raise Exception("Validator wallet not configured: validatorWalletName not set")
		wallet = self.GetLocalWallet(wallet_name)
		return wallet

	def ElectionEntry(self):
		usePool = self.using_pool()
		useController = self.using_liquid_staking()
		wallet = self.GetValidatorWallet()
		if wallet is None:
			raise Exception("Validator wallet not found")
		addrB64 = wallet.addrB64

		self.local.add_log("start ElectionEntry function", "debug")
		# Check if validator is not synchronized
		validatorStatus = self.GetValidatorStatus()
		validatorOutOfSync = validatorStatus.get("outOfSync")
		if validatorOutOfSync > 60:
			self.local.add_log("Validator is not synchronized", "error")
			return

		# Get startWorkTime and endWorkTime
		fullElectorAddr = self.GetFullElectorAddr()
		startWorkTime = self.GetActiveElectionId(fullElectorAddr)

		# Check if elections started
		if (startWorkTime == 0):
			self.local.add_log("Elections have not yet begun", "info")
			return

		# Get ADNL address
		adnl_addr = self.GetAdnlAddr()
		if adnl_addr is None:
			raise Exception("Failed to get ADNL address")
		adnl_addr_bytes = bytes.fromhex(adnl_addr)

		# Check wether it is too early to participate
		if "participateBeforeEnd" in self.local.db:
			now = time.time()
			if (startWorkTime - now) > self.local.db["participateBeforeEnd"] and \
			   (now + self.local.db["periods"]["elections"]) < startWorkTime:
				return

		vconfig = self.GetValidatorConfig()

		have_adnl = False
		# Check if ADNL address is in the list
		for a in vconfig.adnl:
			if base64.b64decode(a.id) == adnl_addr_bytes:
				have_adnl = True
				break
		if not have_adnl:
			raise Exception('ADNL address is not found')

		validator_key = self.get_validator_key_by_time(startWorkTime, vconfig)
		if validator_key is not None:
			validator_pubkey_hex = self.get_clean_pubkey_hex(validator_key)
			# Check if election entry already completed
			entries = self.GetElectionEntries()
			if entries and validator_pubkey_hex in entries:
				self.local.add_log("Elections entry already completed", "info")
				return

		pool = None
		controllerAddr = None
		if usePool:
			pool = self.get_pool()
			if pool is None:
				raise Exception("Could not get pool with pool mode on")
			addrB64 = pool.addrB64
		elif useController:
			controllerAddr = self.GetController(mode="stake")
			self.CheckController(controllerAddr)
			self.CreateLoanRequest(controllerAddr)
			addrB64 = controllerAddr

		# Calculate stake
		account = self.GetAccount(addrB64)
		stake = self.GetStake(account)

		# Calculate endWorkTime
		validatorsElectedFor = self.get_config_15().validators_elected_for
		endWorkTime = startWorkTime + validatorsElectedFor + 300 # 300 sec - margin of seconds

		# Create keys
		if validator_key is None:
			validator_key = self.create_validator_key(startWorkTime, endWorkTime)
		validator_pubkey_b64  = self.GetPubKeyBase64(validator_key)
		self.AddKeyToTemp(validator_key, endWorkTime) # add one more time to ensure it is in temp keys

		# Attach ADNL addr to validator
		self.AttachAdnlAddrToValidator(adnl_addr, validator_key, endWorkTime)

		# Get max factor
		maxFactor = self.GetMaxFactor()

		# Create fift's. Continue with pool or walet
		if usePool:
			if pool is None:
				raise Exception("Could not get pool with pool mode on")
			var1 = self.CreateElectionRequest(pool.addrB64, startWorkTime, adnl_addr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validator_key, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithPoolWithValidator(pool, startWorkTime, adnl_addr, validator_pubkey_b64, validatorSignature, maxFactor, stake)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, pool.addrB64, 1.3)
			self.SendFile(resultFilePath, wallet)
		elif useController:
			if controllerAddr is None:
				raise Exception("Could not get controller with controller mode on")
			var1 = self.CreateElectionRequest(controllerAddr, startWorkTime, adnl_addr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validator_key, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithController(controllerAddr, startWorkTime, adnl_addr, validator_pubkey_b64, validatorSignature, maxFactor, stake)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, controllerAddr, 1.03)
			self.SendFile(resultFilePath, wallet)
		else:
			var1 = self.CreateElectionRequest(wallet.addrB64, startWorkTime, adnl_addr, maxFactor)
			validatorSignature = self.GetValidatorSignature(validator_key, var1)
			validatorPubkey, resultFilePath = self.SignElectionRequestWithValidator(wallet, startWorkTime, adnl_addr, validator_pubkey_b64, validatorSignature, maxFactor)

			# Send boc file to TON
			resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, stake)
			self.SendFile(resultFilePath, wallet)

		# Save vars to json file
		self.SaveElectionVarsToJsonFile(wallet=wallet, account=account, stake=stake, maxFactor=maxFactor, fullElectorAddr=fullElectorAddr, startWorkTime=startWorkTime, validatorsElectedFor=validatorsElectedFor, endWorkTime=endWorkTime, validatorKey=validator_key, validatorPubkey_b64=validator_pubkey_b64, adnlAddr=adnl_addr, var1=var1, validatorSignature=validatorSignature, validatorPubkey=validatorPubkey)
		self.local.add_log("ElectionEntry completed. Start work time: " + str(startWorkTime))

		self.clear_tmp()
		self.make_backup(startWorkTime)


	def clear_dir(self, dir_name):
		start = time.time()
		count = 0
		week_ago = 60 * 60 * 24 * 7
		for f in os.listdir(dir_name):
			ts = os.path.getmtime(os.path.join(dir_name, f))
			if ts < time.time() - week_ago:
				count += 1
				if os.path.isfile(os.path.join(dir_name, f)):
					os.remove(os.path.join(dir_name, f))
		self.local.add_log(f"Removed {count} old files from {dir_name} directory for {int(time.time() - start)} seconds", "info")

	def clear_tmp(self):
		self.clear_dir(self.tempDir)

	def make_backup(self, election_id: int):
		if not self.local.db.get("auto_backup"):
			return
		from modules.backups import BackupModule
		module = BackupModule(self, self.local)
		args = []
		name = f"/mytonctrl_backup_elid{election_id}.zip"
		backups_dir = self.tempDir + "/auto_backups"
		if self.local.db.get("auto_backup_path"):
			backups_dir = self.local.db.get("auto_backup_path")
		os.makedirs(backups_dir, exist_ok=True)
		args.append(backups_dir + name)
		self.clear_dir(backups_dir)
		exit_code = module.create_backup(args)
		if exit_code != 0:
			self.local.add_log(f"Backup failed with exit code {exit_code}", "error")
			# try one more time
			exit_code = module.create_backup(args)
			if exit_code != 0:
				self.local.add_log(f"Backup failed with exit code {exit_code}", "error")
		if exit_code == 0:
			self.local.add_log("Backup created successfully", "info")

	def get_validator_key_by_time(self, start_work_time: int, vconfig: Dict | None = None):
		if vconfig is None:
			vconfig = self.GetValidatorConfig()
		for item in vconfig.validators:
			if item.get("election_date") == start_work_time:
				validator_key = base64.b64decode(item.get("id")).hex().upper()
				return validator_key
		return None

	def create_validator_key(self, start_work_time: int, end_work_time: int):
		validator_key = self.CreateNewKey()
		self.AddKeyToValidator(validator_key, start_work_time, end_work_time)
		self.AddKeyToTemp(validator_key, end_work_time)
		return validator_key

	def RecoverStake(self):
		wallet = self.GetValidatorWallet()
		if wallet is None:
			raise Exception("Validator wallet not found")

		self.local.add_log("start RecoverStake function", "debug")
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.get_returned_stake(fullElectorAddr, wallet.addrB64)
		if returnedStake == 0:
			self.local.add_log("You have nothing on the return stake", "debug")
			return

		resultFilePath = self.ProcessRecoverStake()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, 1)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("RecoverStake completed")

	def PoolRecoverStake(self, poolAddr):
		wallet = self.GetValidatorWallet()
		if wallet is None:
			raise Exception("Validator wallet not found")

		self.local.add_log("start PoolRecoverStake function", "debug")
		resultFilePath = self.PoolProcessRecoverStake()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 1.2)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("PoolRecoverStake completed")

	def PoolsUpdateValidatorSet(self):
		self.local.add_log("start PoolsUpdateValidatorSet function", "debug")
		wallet = self.GetValidatorWallet()
		pools = self.GetPools()
		for pool in pools:
			try:
				self.PoolUpdateValidatorSet(pool.addrB64, wallet)
			except Exception as e:
				self.local.add_log(f"Error updating validator set for pool {pool.addrB64}: {e}", "error")
				continue

	def PoolUpdateValidatorSet(self, poolAddr, wallet):
		self.local.add_log("start PoolUpdateValidatorSet function", "debug")
		poolData = self.GetPoolData(poolAddr)

		timeNow = int(time.time())
		config34 = self.get_config_34()
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.get_returned_stake(fullElectorAddr, poolAddr)
		pendingWithdraws = self.GetPendingWithdraws()
		if (poolData["state"] == 2 and
			poolData["validatorSetChangesCount"] < 2 and
			poolData["validatorSetChangeTime"] < config34.start_work_time):
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

	def PoolProcessUpdateValidatorSet(self, poolAddr, wallet):
		self.local.add_log("start PoolProcessUpdateValidatorSet function", "debug")
		resultFilePath = self.tempDir + "pool-update-validator-set-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/update-validator-set.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 1.1)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("PoolProcessUpdateValidatorSet completed")

	def PoolWithdrawRequests(self, poolAddr, wallet):
		self.local.add_log("start PoolWithdrawRequests function", "debug")
		resultFilePath = self.PoolProcessWihtdrawRequests()
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, poolAddr, 10)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("PoolWithdrawRequests completed")

	def PoolProcessWihtdrawRequests(self):
		self.local.add_log("start PoolProcessWihtdrawRequests function", "debug")
		resultFilePath = self.tempDir + "pool-withdraw-requests-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/process-withdraw-requests.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath

	def HasPoolWithdrawRequests(self, poolAddr):
		cmd = f"runmethodfull {poolAddr} has_withdraw_requests"
		result = self.liteClient.run(cmd)
		buff = lc_result_to_list(result)
		data = int(buff[0])
		if data == -1:
			return True
		else:
			return False

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


	def addr_b64_to_bytes(self, addr_b64):
		workchain, addr, bounceable = self.ParseAddrB64(addr_b64)
		workchain_bytes = int.to_bytes(workchain, 4, "big", signed=True)
		addr_bytes = bytes.fromhex(addr)
		result = addr_bytes + workchain_bytes
		return result

	def GetWalletsNameList(self):
		self.local.add_log("start GetWalletsNameList function", "debug")
		walletsNameList: list[str] = []
		for fileName in os.listdir(self.walletsDir):
			if fileName.endswith(".addr"):
				fileName = fileName[:fileName.rfind('.')]
				pkFileName = self.walletsDir + fileName + ".pk"
				if os.path.isfile(pkFileName):
					walletsNameList.append(fileName)
		walletsNameList.sort()
		return walletsNameList

	def GetValidatorConfig(self):
		result = self.validatorConsole.run("getconfig")
		text = parse(result, "---------", "--------")
		if text is None:
			raise ValueError(f"Could not get validator config: {result}")
		vconfig = json.loads(text)
		return Dict(vconfig)

	def GetOverlaysStats(self):
		self.local.add_log("start GetOverlaysStats function", "debug")
		resultFilePath = self.local.my_temp_dir + "getoverlaysstats.json"
		result = self.validatorConsole.run(f"getoverlaysstatsjson {resultFilePath}")
		if "wrote stats" not in result:
			raise Exception(f"GetOverlaysStats error: {result}")
		file = open(resultFilePath)
		text = file.read()
		file.close()
		data = json.loads(text)
		return data

	def check_account_balance(self, account, coins):
		if not isinstance(account, Account):
			account = self.GetAccount(account)
		if account.balance < coins:
			raise Exception(f"Account {account.addrB64} balance is less than requested coins. Balance: {account.balance}, requested amount: {coins} (need {coins - account.balance} more)")

	def check_account_active(self, account):
		if not isinstance(account, Account):
			address = account
			account = self.GetAccount(account)
		else:
			address = account.addrB64
		if account.status != "active":
			raise Exception(f"Account {address} account is uninitialized")

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

	def GetElectionEntries(self, past: bool = False) -> dict[str, ElectionsParticipant] | None:
		if past:
			config34 = self.get_config_34()
			election_id = config34.start_work_time
			end = config34.end_work_time
			buff = end - election_id
			election_id = election_id - buff
			entries = self.get_saved_election_entries(election_id)
			return entries

		full_elector_addr = self.GetFullElectorAddr()
		election_id = self.GetActiveElectionId(full_elector_addr)
		if election_id == 0:
			return {}

		entries = {}

		# Get raw data
		self.local.add_log("start GetElectionEntries function", "debug")
		cmd = f"runmethodfull {full_elector_addr} participant_list_extended"
		result = self.liteClient.run(cmd)
		raw_election_entries = lc_result_to_list(result)
		election_entries = raw_election_entries[4]
		for entry in election_entries:
			if len(entry) == 0:
				continue

			# Create dict
			item = {
				"pubkey": Dec2HexAddr(entry[0]),
				"adnlAddr": Dec2HexAddr(entry[1][3]),
				"stake": ng2g(entry[1][0]),
				"maxFactor": round(entry[1][1] / 655.36) / 100.0,
				"walletAddr": raw_addr_to_b64("-1:" + Dec2HexAddr(entry[1][2]))
			}
			entries[item["pubkey"]] = item

		# Save elections
		saveElections = self._get_save_elections()
		saveElections[str(election_id)] = entries
		return entries

	def _get_save_elections(self) -> dict[str, dict[str, ElectionsParticipant]]:
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

	def get_saved_election_entries(self, election_id: int):
		saveElections = self._get_save_elections()
		result = saveElections.get(str(election_id))
		if result is not None:  # temp fix for migration period of cached past election entries. todo: remove this
			return {x['pubkey']: x for x in result.values()}
		return None

	def calculate_offer_pseudohash(self, offer_hash: str, param_id: int):
		config_val = self.get_config(param_id)
		pseudohash_bytes = offer_hash.encode() + json.dumps(config_val, sort_keys=True).encode()
		return hashlib.sha256(pseudohash_bytes).hexdigest()

	def GetOffers(self):
		fullConfigAddr = self.GetFullConfigAddr()
		# Get raw data
		cmd = "runmethodfull {fullConfigAddr} list_proposals".format(fullConfigAddr=fullConfigAddr)
		result = self.liteClient.run(cmd)
		rawOffers = lc_result_to_list(result)
		rawOffers = rawOffers[0]
		config34 = self.get_config_34()
		totalWeight = config34.total_weight

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
		return offers

	def GetComplaints(self, electionId: int | None = None, past: bool = False) -> dict[str, typing.Any] | None:
		# Get buffer
		bname = "complaints" + str(past)
		buff = self.GetFunctionBuffer(bname)
		if buff:
			return buff

		# Calculate complaints time
		complaints = dict()
		fullElectorAddr = self.GetFullElectorAddr()
		end = None
		if electionId is None:
			config32 = self.get_config_32()
			if config32 is None:
				raise Exception("No election id provided and could not get 32 config")
			electionId = config32.start_work_time
			end = config32.end_work_time
		if past:
			if end is None:
				raise Exception("Cannot compute past election id")
			electionId = electionId - (end - electionId)
			saveComplaints = self.GetSaveComplaints()
			complaints = saveComplaints.get(str(electionId))
			return complaints

		# Get raw data
		cmd = "runmethodfull {fullElectorAddr} list_complaints {electionId}".format(fullElectorAddr=fullElectorAddr, electionId=electionId)
		result = self.liteClient.run(cmd)
		rawComplaints = lc_result_to_list(result)
		rawComplaints = rawComplaints[0]
		config34 = self.get_config_34()
		totalWeight = config34.total_weight

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
			rewardAddr = raw_addr_to_b64(rewardAddr)
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

		# sort complaints by their creation time and hash
		complaints = dict(sorted(complaints.items(), key=lambda item: (item[1]["createdTime"], item[0])))

		# Set buffer
		self.SetFunctionBuffer(bname, complaints)

		# Save complaints
		if len(complaints) > 0:
			saveComplaints = self.GetSaveComplaints()
			saveComplaints[str(electionId)] = complaints
		return complaints

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

	def GetAdnlFromPubkey(self, inputPubkey):
		config32 = self.get_config_32()
		validators = config32.validators
		for validator in validators:
			adnl = validator.adnl_addr
			pubkey = validator.pubkey
			if pubkey == inputPubkey:
				return adnl

	def GetComplaintsNumber(self):
		result = dict()
		complaints = self.GetComplaints()
		if complaints is None:
			raise Exception("Failed to get complaints")
		voted_complaints = self.GetVotedComplaints(complaints)
		buff = 0
		for chash in complaints:
			if chash in voted_complaints:
				continue
			buff += 1
		result["all"] = len(complaints)
		result["new"] = buff
		return result

	def SignProposalVoteRequestWithValidator(self, offerHash, validatorIndex, validatorPubkey_b64, validatorSignature):
		self.local.add_log("start SignProposalVoteRequestWithValidator function", "debug")
		fileName = self.tempDir + self.nodeName + "proposal_vote-msg-body.boc"
		args = ["config-proposal-vote-signed.fif", "-i", validatorIndex, offerHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.run(args)
		fileName = parse(result, "Saved to file ", '\n')
		return fileName

	def SignComplaintVoteRequestWithValidator(self, complaintHash, electionId, validatorIndex, validatorPubkey_b64, validatorSignature):
		self.local.add_log("start SignComplaintRequestWithValidator function", "debug")
		fileName = self.tempDir + "complaint_vote-msg-body.boc"
		args = ["complaint-vote-signed.fif", validatorIndex, electionId, complaintHash, validatorPubkey_b64, validatorSignature, fileName]
		result = self.fift.run(args)
		fileName = parse(result, "Saved to file ", '\n')
		return fileName

	def VoteOffer(self, offer):
		self.local.add_log("start VoteOffer function", "debug")
		full_config_addr = self.GetFullConfigAddr()
		wallet = self.GetValidatorWallet()
		validator_key = self.GetValidatorKey()
		validator_pubkey_b64 = self.GetPubKeyBase64(validator_key)
		validator_index = self.GetValidatorIndex()
		offer_hash = offer.get("hash")
		if validator_index in offer.get("votedValidators"):
			self.local.add_log("Proposal already has been voted", "debug")
			return
		self.add_save_offer(offer)
		var1 = self.CreateConfigProposalRequest(offer_hash, validator_index)
		validator_signature = self.GetValidatorSignature(validator_key, var1)
		result_file_path = self.SignProposalVoteRequestWithValidator(offer_hash, validator_index, validator_pubkey_b64, validator_signature)
		result_file_path = self.SignBocWithWallet(wallet, result_file_path, full_config_addr, 1.5)
		self.SendFile(result_file_path, wallet, remove=False)

	def VoteComplaint(self, electionId, complaintHash):
		self.local.add_log("start VoteComplaint function", "debug")
		complaintHash = int(complaintHash)
		fullElectorAddr = self.GetFullElectorAddr()
		wallet = self.GetValidatorWallet()
		validatorKey = self.GetValidatorKey()
		validatorPubkey_b64 = self.GetPubKeyBase64(validatorKey)
		validatorIndex = self.GetValidatorIndex()
		var1 = self.CreateComplaintRequest(electionId, complaintHash, validatorIndex)
		validatorSignature = self.GetValidatorSignature(validatorKey, var1)
		resultFilePath = self.SignComplaintVoteRequestWithValidator(complaintHash, electionId, validatorIndex, validatorPubkey_b64, validatorSignature)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, fullElectorAddr, 1.5)
		self.SendFile(resultFilePath, wallet)

	def CheckComplaint(self, file_path: str):
		self.local.add_log("start CheckComplaint function", "debug")
		cmd = "loadproofcheck {filePath}".format(filePath=file_path)
		result = self.liteClient.run(cmd, timeout=30)
		lines = result.split('\n')
		ok = False
		for line in lines:
			if "COMPLAINT_VOTE_FOR" in line:
				buff = line.split('\t')
				ok_buff = buff[2]
				if ok_buff == "YES":
					ok = True
		return ok

	def get_valid_complaints(self, complaints: dict, election_id: int):
		self.local.add_log("start get_valid_complaints function", "debug")
		config32 = self.get_config_32()
		start = config32.start_work_time
		assert start == election_id, 'provided election_id != election_id from config32'
		end = config32.end_work_time
		validators_load = self.GetValidatorsLoad(start, end - 60, save_comp_files=True, v2=True)
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
								   f"start work time ({config32.start_work_time})", "info")
				continue

			exists = False
			vload = None
			for item in validators_load.values():
				if 'fileName' not in item:
					continue
				pubkey = item.get("pubkey")
				if pubkey is None:
					continue
				pseudohash = pubkey + str(election_id)
				if pseudohash == complaint['pseudohash']:
					exists = True
					vload = item
					break
			if vload is None:
				self.local.add_log(f"complaint {complaint['hash_hex']} declined: complaint info was not found: {validators_load}", "info")
				continue

			if not exists:
				self.local.add_log(f"complaint {complaint['hash_hex']} declined: complaint info was not found, probably it's wrong", "info")
				continue

			if vload["id"] >= config32.main_validators:
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

	def GetValidatorsLoad(self, start: int, end: int, save_comp_files: bool = False, v2: bool = False) -> dict:
		bname = f"validatorsLoad{start}{end}{save_comp_files}{v2}"
		timeout = 60
		cmd_suf = ""
		if v2:
			cmd_suf = "-v2"
			timeout = 3600
		buff = self.GetFunctionBuffer(bname, timeout=timeout)
		if buff:
			return buff
		text = "start GetValidatorsLoad function ({}, {})".format(start, end)
		self.local.add_log(text, "debug")
		if save_comp_files:
			filePrefix = self.tempDir + f"checkload_{start}_{end}"
		else:
			filePrefix = ""
		cmd = f"checkloadall{cmd_suf} {start} {end} {filePrefix}"
		result = self.liteClient.run(cmd, timeout=180 if v2 else 30)
		if 'total:' not in result:
			raise Exception(f"Failed to get validators load: {result}")
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
				if masterBlocksExpected > 0:  # show only masterchain efficiency for masterchain validator
					r = mr
				else:
					r = wr
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

		# Set buffer
		self.SetFunctionBuffer(bname, data)
		return data

	def GetValidatorsList(self, past: bool=False, fast: bool=False, start: int | None = None, end: int | None = None) -> list[ValidatorConfigExt]:
		# Get buffer
		bname = "validatorsList" + str(past) + str(start) + str(end)
		buff = self.GetFunctionBuffer(bname, timeout=60)
		if buff:
			return buff

		config = self.get_config_34()
		if end is None:
			timestamp = get_timestamp()
			end = timestamp - 60
		if start is None:
			if fast:
				start = max(end - 1000, config.start_work_time)
			else:
				start = config.start_work_time
		if past:
			config = self.get_config_32()
			start = config.start_work_time
			end = config.end_work_time - 60
			save_vl = self.GetSaveVl()
			start_str = str(start)
			if start_str in save_vl:
				return [ValidatorConfigExt.from_dict(entry) for entry in save_vl[start_str]]

		validators_load = self.GetValidatorsLoad(start, end)
		validators: list[ValidatorConfigExt] = []
		electionId = config.start_work_time
		saveElectionEntries = self.get_saved_election_entries(electionId)
		for vid in range(len(config.validators)):
			base = config.validators[vid]
			load = validators_load[vid]
			pubkey = base.pubkey
			wallet_addr, stake = None, None
			if saveElectionEntries and pubkey in saveElectionEntries:
				entry = saveElectionEntries[pubkey]
				wallet_addr = entry["walletAddr"]
				stake = entry.get("stake")
				stake = int(stake) if stake else None
			validator = ValidatorConfigExt(
				adnl_addr=base.adnl_addr,
				pubkey=base.pubkey,
				weight=base.weight,
				mr=load["mr"],
				wr=load["wr"],
				efficiency=load["efficiency"],
				online=load["online"],
				master_blocks_created=load["masterBlocksCreated"],
				master_blocks_expected=load["masterBlocksExpected"],
				blocks_created=load["masterBlocksCreated"] + load["workBlocksCreated"],
				blocks_expected=load["masterBlocksExpected"] + load["workBlocksExpected"],
				is_masterchain=vid < config.main_validators,
				wallet_addr=wallet_addr,
				stake=stake,
			)
			validators.append(validator)

		self.SetFunctionBuffer(bname, validators)
		if past:
			save_vl = self.GetSaveVl()
			save_vl[str(start)] = [asdict(v) for v in validators]
		return validators

	def CheckValidators(self, start: int, end: int):
		self.local.add_log("start CheckValidators function", "debug")
		electionId = start
		complaints = self.GetComplaints(electionId)
		if complaints is None:
			raise Exception(f"Failed to get complaints for round {start}-{end}")
		valid_complaints = self.get_valid_complaints(complaints, electionId)
		voted_complaints = self.GetVotedComplaints(complaints)
		voted_complaints_pseudohashes = [complaint['pseudohash'] for complaint in voted_complaints.values()]
		data = self.GetValidatorsLoad(start, end, save_comp_files=True, v2=True)
		fullElectorAddr = self.GetFullElectorAddr()
		wallet = self.GetValidatorWallet()
		config = self.get_config_32()

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
			if item['id'] >= config.main_validators:  # do not create complaints for non-masterchain validators
				continue
			# Create complaint
			fileName = self.remove_proofs_from_complaint(fileName)
			fileName = self.PrepareComplaint(electionId, fileName)
			fileName = self.SignBocWithWallet(wallet, fileName, fullElectorAddr, 300)
			self.SendFile(fileName, wallet)
			self.local.add_log("var1: {}, var2: {}, pubkey: {}, election_id: {}".format(var1, var2, pubkey, electionId), "debug")

	def GetOffer(self, offer_hash: str, offers: list | None = None):
		self.local.add_log("start GetOffer function", "debug")
		if offers is None:
			offers = self.GetOffers()
		for offer in offers:
			if offer_hash == offer.get("hash"):
				return offer
		raise Exception("GetOffer error: offer not found.")

	def GetOffersNumber(self):
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

	def GetValidatorIndex(self, adnlAddr=None):
		config34 = self.get_config_34()
		validators = config34.validators
		if adnlAddr is None:
			adnlAddr = self.GetAdnlAddr()
		index = 0
		for validator in validators:
			searchAdnlAddr = validator.adnl_addr
			if adnlAddr == searchAdnlAddr:
				return index
			index += 1
		return -1

	def GetDbUsage(self):
		path = self.get_paths().ton_db
		data = psutil.disk_usage(str(path))
		return data.percent

	def GetDbSize(self, exceptions="log"):
		exceptions = exceptions.split()
		totalSize = 0
		path = self.get_paths().ton_work
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

	def get_local_adnl_data(self):

		def int2ip(dec):
			import socket
			return socket.inet_ntoa(struct.pack("!i", dec))

		vconfig = self.GetValidatorConfig()

		data = {"host": int2ip(vconfig["addrs"][0]["ip"]), "port": vconfig["addrs"][0]["port"]}

		dht_id = vconfig["dht"][0]["id"]
		dht_id_hex = base64.b64decode(dht_id).hex().upper()

		result = self.validatorConsole.run(f"exportpub {dht_id_hex}")
		pubkey = parse(result, "got public key: ", "\n")
		if pubkey is not None:
			data["pubkey"] = base64.b64encode(base64.b64decode(pubkey)[4:]).decode()
		return data

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
			if rawAny and ')' in line:
				rawAny = False
			if line[:2] == "x{" and not rawAny:
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
		return data

	def GetFirstSpacesCount(self, line):
		result = 0
		for item in line:
			if item == ' ':
				result += 1
			else:
				break
		return result

	def AddBookmark(self, bookmark):
		if "bookmarks" not in self.local.db:
			self.local.db["bookmarks"] = list()
		self.local.db["bookmarks"].append(bookmark)
		self.local.save()

	def GetBookmarks(self):
		bookmarks = self.local.db.get("bookmarks")
		if bookmarks is not None:
			for bookmark in bookmarks:
				self.WriteBookmarkData(bookmark)
		return bookmarks

	def DeleteBookmark(self, name):
		bookmarks = self.local.db.get("bookmarks")
		for bookmark in bookmarks:
			bookmark_name = bookmark.get("name")
			if name == bookmark_name:
				bookmarks.remove(bookmark)
				self.local.save()
				return
		raise Exception("DeleteBookmark error: Bookmark not found")

	def WriteBookmarkData(self, bookmark):
		addr = bookmark.get("addr")
		account = self.GetAccount(addr)
		if account.status == "empty":
			data = "empty"
		else:
			data = account.balance
		bookmark["data"] = data

	def offers_gc(self, save_offers):
		current_offers = self.GetOffers()
		current_offers_hashes = [offer.get("hash") for offer in current_offers]
		for offer_hash, offer in list(save_offers.items()):
			if offer_hash not in current_offers_hashes:
				if isinstance(offer, list):
					param_id = offer[1]
					phash = self.calculate_offer_pseudohash(offer_hash, param_id)
					if param_id is not None and offer[0] != phash:
						# param has been changed so no need to keep anymore
						save_offers.pop(offer_hash)
						self.local.add_log(f"Removing offer {offer_hash} from save_offers. Saved phash: {offer[0]}, now phash: {phash}", "debug")
				else:  # old version of offer in db
					save_offers.pop(offer_hash)
		return save_offers

	def GetSaveOffers(self):
		bname = "saveOffers"
		save_offers = self.local.db.get(bname)
		if save_offers is None or isinstance(save_offers, list):
			save_offers = dict()
			self.local.db[bname] = save_offers
		return save_offers

	def add_save_offer(self, offer):
		offer_hash = offer.get("hash")
		offer_pseudohash = offer.get("pseudohash")
		save_offers = self.GetSaveOffers()
		if offer_hash not in save_offers:
			save_offers[offer_hash] = [offer_pseudohash, offer.get('config', {}).get("id")]
			self.local.save()

	def GetVotedComplaints(self, complaints: dict):
		result = {}
		validator_index = self.GetValidatorIndex()
		for chash, complaint in complaints.items():
			voted_validators = complaint.get("votedValidators")
			if validator_index in voted_validators:
				result[chash] = complaint
		return result

	def get_destination_addr(self, destination):
		if self.IsAddrB64(destination):
			pass
		elif self.IsAddrFull(destination):
			destination = raw_addr_to_b64(destination)
		else:
			wallets_name_list = self.GetWalletsNameList()
			if destination in wallets_name_list:
				wallet = self.GetLocalWallet(destination)
				destination = wallet.addrB64
		return destination

	def ParseAddrB64(self, addrB64):
		# Get buffer
		fname = addrB64
		buff = self.GetFunctionBuffer(fname, timeout=1)
		if buff:
			return buff

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

		# get wc and addr
		workchain_bytes = b[1:2]
		addr_bytes = b[2:34]
		crc_bytes = b[34:36]
		crc_data = bytes(b[:34])
		crc = int.from_bytes(crc_bytes, "big")
		check_crc = crc16.xmodem(crc_data)
		if crc != check_crc:
			raise Exception("ParseAddrB64 error: crc do not match")

		workchain = int.from_bytes(workchain_bytes, "big", signed=True)
		addr = addr_bytes.hex()

		# Set buffer
		data = (workchain, addr, bounceable)
		self.SetFunctionBuffer(fname, data)
		return data

	def ParseAddrFull(self, addrFull):
		buff = addrFull.split(':')
		workchain = int(buff[0])
		addr = buff[1]
		addrBytes = bytes.fromhex(addr)
		if len(addrBytes) != 32:
			raise Exception("ParseAddrFull error: addrBytes is not 32 bytes")
		return workchain, addr

	def ParseInputAddr(self, inputAddr):
		if self.IsAddrB64(inputAddr):
			workchain, addr, bounceable = self.ParseAddrB64(inputAddr)
			return workchain, addr
		elif self.IsAddrFull(inputAddr):
			workchain, addr = self.ParseAddrFull(inputAddr)
			return workchain, addr
		else:
			raise Exception(f"ParseInputAddr error: input address is not a adress: {inputAddr}")

	def IsBounceableAddrB64(self, inputAddr):
		bounceable = None
		try:
			workchain, addr, bounceable = self.ParseAddrB64(inputAddr)
		except Exception:
			pass
		return bounceable

	def GetStatistics(self, name: str, statistics: dict[str, list[int]] | None = None) -> list[int] | dict[str, list[int]] | None:
		if statistics is None:
			statistics = self.local.db.get("statistics")
		if statistics:
			data = statistics.get(name)
		else:
			data = [-1, -1, -1]
		return data

	def get_node_statistics(self):
		stats = self.local.db.get('statistics', {}).get('node')
		if stats is None:
			return {}
		return StatsCollector.parse_node_statistics(stats)

	def GetSettings(self, name):
		# self.local.load_db()
		result = self.local.db.get(name)
		return result

	def SetSettings(self, name, data):
		try:
			data = json.loads(data)
		except Exception:
			pass
		self.local.db[name] = data
		self.local.save()
		self.create_self_db_backup()

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

	def get_modes(self):
		current_modes = self.local.db.get('modes', {})
		if 'modes' not in self.local.db:
			self.local.db['modes'] = current_modes
			self.migrate_to_modes()
		for name, mode in MODES.items():
			if name not in current_modes:
				current_modes[name] = mode.default_value  # assign default mode value
		return current_modes

	def enable_mode(self, name: str):
		if name not in MODES:
			raise Exception(f'Unknown module name: {name}. Available modes: {", ".join(MODES)}')
		MODES[name].check_enable(self)
		current_modes = self.get_modes()
		current_modes[name] = True
		self.local.save()

	def disable_mode(self, name: str):
		current_modes = self.get_modes()
		if name not in current_modes:
			raise Exception(f'Unknown module name: {name}. Available modes: {", ".join(MODES)}')
		MODES[name](self, self.local).check_disable()
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

	def using_collator(self):
		return self.get_mode_value('collator')

	def get_node_mode(self):
		if self.using_validator():
			return 'VALIDATOR'
		elif self.using_liteserver():
			return 'LITESERVER'
		elif self.using_collator():
			return 'COLLATOR'

	def using_alert_bot(self):
		return self.get_mode_value('alert-bot')

	def using_prometheus(self):
		return self.get_mode_value('prometheus')

	def in_initial_sync(self):
		return self.local.db.get('initialSync', False)

	def set_initial_sync_off(self):
		self.local.db.pop('initialSync', None)
		self.local.save()

	def GetValidatorsWalletsList(self):
		result = list()
		vl = self.GetValidatorsList(fast=True)
		for item in vl:
			result.append(item.wallet_addr)
		return result

	def DownloadContract(self, url: str, branch: str | None = None):
		self.local.add_log("start DownloadContract function", "debug")
		buff = url.split('/')
		gitPath = self.contractsDir + buff[-1] + '/'

		args = ["git", "clone", url]
		subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.contractsDir, timeout=30)

		if branch is not None:
			args = ["git", "checkout", branch]
			subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=gitPath, timeout=3)


	def WithdrawFromPoolProcess(self, poolAddr, amount):
		self.local.add_log("start WithdrawFromPoolProcess function", "debug")
		wallet = self.GetValidatorWallet()
		bocPath = self.local.my_temp_dir + wallet.name + "validator-withdraw-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/validator-withdraw.fif"
		args = [fiftScript, amount, bocPath]
		self.fift.run(args)
		resultFilePath = self.SignBocWithWallet(wallet, bocPath, poolAddr, 1.35)
		self.SendFile(resultFilePath, wallet)

	def PendWithdrawFromPool(self, poolAddr, amount):
		self.local.add_log("start PendWithdrawFromPool function", "debug")
		pendingWithdraws = self.GetPendingWithdraws()
		pendingWithdraws[poolAddr] = amount
		self.local.save()

	def HandlePendingWithdraw(self, pendingWithdraws, poolAddr):
		amount = pendingWithdraws.pop(poolAddr)
		self.WithdrawFromPoolProcess(poolAddr, amount)

	def GetPendingWithdraws(self):
		bname = "pendingWithdraws"
		pendingWithdraws = self.local.db.get(bname)
		if pendingWithdraws is None:
			pendingWithdraws = dict()
			self.local.db[bname] = pendingWithdraws
		return pendingWithdraws

	def SignElectionRequestWithPoolWithValidator(self, pool, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor, stake):
		self.local.add_log("start SignElectionRequestWithPoolWithValidator function", "debug")
		fileName = self.tempDir + str(startWorkTime) + "_validator-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/validator-elect-signed.fif"
		args = [fiftScript, pool.addrB64, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName, stake]
		result = self.fift.run(args)
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName

	def PoolProcessRecoverStake(self):
		self.local.add_log("start PoolProcessRecoverStake function", "debug")
		resultFilePath = self.tempDir + "recover-query.boc"
		fiftScript = self.contractsDir + "nominator-pool/func/recover-stake.fif"
		args = [fiftScript, resultFilePath]
		result = self.fift.run(args)
		resultFilePath = parse(result, "Saved to file ", '\n')
		return resultFilePath

	def GetLocalPool(self, pool_name: str) -> Pool:
		self.local.add_log("start GetLocalPool function", "debug")
		file_path = self.poolsDir + pool_name
		pool = Pool.from_file(pool_name, file_path)
		if not os.path.isfile(pool.addrFilePath):
			raise Exception(f"GetLocalPool error: Address file not found: {pool.addrFilePath}")
		return pool

	def GetPoolsNameList(self) -> list[str]:
		self.local.add_log("start GetPoolsNameList function", "debug")
		poolsNameList = list()
		for fileName in os.listdir(self.poolsDir):
			if fileName.endswith(".addr"):
				fileName = fileName[:fileName.rfind('.')]
				poolsNameList.append(fileName)
		poolsNameList.sort()
		return poolsNameList

	def GetPools(self) -> list[Pool]:
		self.local.add_log("start GetPools function", "debug")
		pools = list()
		poolsNameList = self.GetPoolsNameList()
		for poolName in poolsNameList:
			pool = self.GetLocalPool(poolName)
			pools.append(pool)
		return pools

	def get_pool(self):
		pools = self.GetPools()
		for pool in pools:
			if self.is_pool_ready_to_stake(pool):
				return pool
		raise Exception("Validator pool not found or not ready")

	def get_pool_last_sent_stake_time(self, addrB64):
		pool_data = self.GetPoolData(addrB64)
		return pool_data["stakeAt"]

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
		config15 = self.get_config_15()
		last_sent_stake_time = self.get_pool_last_sent_stake_time(addr)
		stake_freeze_delay = config15.validators_elected_for + config15.stake_held_for
		result = last_sent_stake_time + stake_freeze_delay < now
		print(f"{addr}: {result}. {last_sent_stake_time}, {stake_freeze_delay}, {now}")
		return result

	def is_account_single_nominator(self, account: Account):
		account_version = self.GetVersionFromCodeHash(account.codeHash)
		return account_version is not None and 'spool' in account_version

	def GetPoolData(self, addrB64: str):
		self.local.add_log("start GetPoolData function", "debug")
		cmd = f"runmethodfull {addrB64} get_pool_data"
		result = self.liteClient.run(cmd)
		data = lc_result_to_list(result)
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

	def GetLiquidPoolAddr(self):
		liquid_pool_addr = self.local.db.get("liquid_pool_addr")
		if liquid_pool_addr is None:
			raise Exception("GetLiquidPoolAddr error: liquid_pool_addr not set")
		return liquid_pool_addr

	def GetControllerAddress(self, controller_id):
		wallet = self.GetValidatorWallet()
		addr_hash = int(wallet.addr, 16)
		liquid_pool_addr = self.GetLiquidPoolAddr()
		cmd = f"runmethodfull {liquid_pool_addr} get_controller_address_legacy {controller_id} {wallet.workchain} {addr_hash}"
		result = self.liteClient.run(cmd)
		buff = lc_result_to_list(result)
		wc = buff[0]
		addr_hash = Dec2HexAddr(buff[1])
		addrFull = f"{wc}:{addr_hash}"
		controllerAddr = raw_addr_to_b64(addrFull)
		return controllerAddr

	def CheckController(self, controllerAddr):
		self.local.add_log("start CheckController function", "debug")
		controllerData = self.GetControllerData(controllerAddr)
		using_controllers = self.local.db.get("using_controllers", list())
		if controllerData["approved"] != -1:
			raise Exception(f"CheckController error: controller not approved: {controllerAddr}")
		if controllerAddr not in using_controllers:
			raise Exception("CheckController error: controller is not up to date. Use new_controllers")

	def GetControllers(self):
		self.local.add_log("start GetControllers function", "debug")
		controller0 = self.GetControllerAddress(controller_id=0)
		controller1 = self.GetControllerAddress(controller_id=1)
		controllers = [controller0, controller1]
		return controllers

	def GetController(self, mode):
		controllers = self.GetControllers()
		for controllerAddr in controllers:
			if mode == "stake" and self.IsControllerReadyToStake(controllerAddr):
				return controllerAddr
			if mode == "vote" and self.IsControllerReadyToVote(controllerAddr):
				return controllerAddr
		raise Exception("Validator controller not found or not ready")

	def GetControllerRequiredBalanceForLoan(self, controller_addr: str, credit: int, interest: int) -> tuple[int, int]:
		cmd = f"runmethodfull {controller_addr} required_balance_for_loan {credit * 10 ** 9} {interest}"
		result = self.liteClient.run(cmd)
		data = lc_result_to_list(result)
		if not isinstance(data[0], int) or not isinstance(data[1], int):
			raise ValueError(f"Got incorrect value: {data}")
		min_amount = data[0]
		validator_amount = data[1]
		return min_amount, validator_amount

	def IsControllerReadyToStake(self, addrB64):
		stop_controllers_list = self.local.db.get("stop_controllers_list")
		if stop_controllers_list is not None and addrB64 in stop_controllers_list:
			return False
		now = get_timestamp()
		config15 = self.get_config_15()
		controllerData = self.GetControllerData(addrB64)
		lastSentStakeTime = controllerData["stake_at"]
		stakeFreezeDelay = config15.validators_elected_for + config15.stake_held_for
		result = lastSentStakeTime + stakeFreezeDelay < now
		print(f"{addrB64}: {result}. {lastSentStakeTime}, {stakeFreezeDelay}, {now}")
		return result

	def IsControllerReadyToVote(self, addrB64):
		vwl = self.GetValidatorsWalletsList()
		result = addrB64 in vwl
		return result

	def GetControllerData(self, controllerAddr: str):
		cmd = f"runmethodfull {controllerAddr} get_validator_controller_data"
		result = self.liteClient.run(cmd)
		data = lc_result_to_list(result)
		result_vars = ["state", "halted", "approved", "stake_amount_sent", "stake_at", "saved_validator_set_hash", "validator_set_changes_count", "validator_set_change_time", "stake_held_for", "borrowed_amount", "borrowing_time"]
		controllerData = dict()
		for name in result_vars:
			controllerData[name] = data.pop(0)
		return controllerData

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

		# Проверить наличие средств у ликвидного пула
		if self.calculate_loan_amount(min_loan, max_loan, max_interest) == -1:
			raise Exception("CreateLoanRequest error: The liquid pool cannot issue the required amount of credit")

		# Проверить хватает ли ставки валидатора
		min_amount, validator_amount = self.GetControllerRequiredBalanceForLoan(controllerAddr, max_loan, max_interest)
		if min_amount > validator_amount:
			self.local.add_log("CreateLoanRequest warning: Validator stake is too low. Use deposit_to_controller", "warning")

		wallet = self.GetValidatorWallet()
		fiftScript = self.contractsDir + "jetton_pool/fift-scripts/generate-loan-request.fif"
		resultFilePath = self.tempDir + self.nodeName + wallet.name + "_loan_request.boc"
		args = [fiftScript, min_loan, max_loan, max_interest, resultFilePath]
		self.fift.run(args)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, controllerAddr, 1.01)
		self.SendFile(resultFilePath, wallet)
		self.WaitLoan(controllerAddr)

	def calculate_loan_amount(self, min_loan: int, max_loan: int, max_interest: int) -> int:
		pool_addr = self.GetLiquidPoolAddr()
		params = [min_loan*10**9, max_loan*10**9, max_interest]
		try:
			result = self.run_get_method_local(pool_addr, "calculate_loan_amount", params)
			return int(result[-1])
		except Exception as e:
			self.local.add_log(f"Failed to calculate loan amount: {e}, params: {params}. Falling back to local ton-http-api", "warning")
			return self.calculate_loan_amount_tha(pool_addr, params)

	def calculate_loan_amount_tha(self, pool_addr: str, params: list) -> int:
		data = {
			"address": pool_addr,
			"method": "calculate_loan_amount",
			"stack": [["num", param] for param in params],
		}
		url = "http://127.0.0.1:8801/runGetMethod"
		res = requests.post(url, json=data, timeout=3)
		res_data = res.json()
		if res_data.get("ok") is False:
			error = res_data.get("error")
			raise Exception(error)
		result = res_data.get("result").get("stack").pop().pop()
		return int(result, 16)

	def WaitLoan(self, controllerAddr):
		self.local.add_log("start WaitLoan function", "debug")
		for i in range(10):
			time.sleep(3)
			controllerData = self.GetControllerData(controllerAddr)
			if controllerData["borrowed_amount"] != 0:
				return
		raise Exception("WaitLoan error: time out")

	def ReturnUnusedLoan(self, controllerAddr):
		self.local.add_log("start ReturnUnusedLoan function", "debug")
		wallet = self.GetValidatorWallet()
		fileName = self.contractsDir + "jetton_pool/fift-scripts/return_unused_loan.boc"
		resultFilePath = self.SignBocWithWallet(wallet, fileName, controllerAddr, 1.05)
		self.SendFile(resultFilePath, wallet)

	def WithdrawFromController(self, controllerAddr, amount=None):
		controllerData = self.GetControllerData(controllerAddr)
		if controllerData["state"] == 0:
			self.WithdrawFromControllerProcess(controllerAddr, amount)
		else:
			self.PendWithdrawFromController(controllerAddr, amount)

	def WithdrawFromControllerProcess(self, controllerAddr, amount):
		if amount is None:
			account = self.GetAccount(controllerAddr)
			amount = account.balance-10.1
		if int(amount) < 3:
			return

		self.local.add_log("start WithdrawFromControllerProcess function", "debug")
		wallet = self.GetValidatorWallet()
		fiftScript = self.contractsDir + "jetton_pool/fift-scripts/withdraw-controller.fif"
		resultFilePath = self.tempDir + self.nodeName + wallet.name + "_withdraw_request.boc"
		args = [fiftScript, amount, resultFilePath]
		self.fift.run(args)
		resultFilePath = self.SignBocWithWallet(wallet, resultFilePath, controllerAddr, 1.06)
		self.SendFile(resultFilePath, wallet)

	def PendWithdrawFromController(self, controllerAddr, amount):
		self.local.add_log("start PendWithdrawFromController function", "debug")
		controllerPendingWithdraws = self.GetControllerPendingWithdraws()
		controllerPendingWithdraws[controllerAddr] = amount
		self.local.save()

	def HandleControllerPendingWithdraw(self, controllerPendingWithdraws, controllerAddr):
		amount = controllerPendingWithdraws.get(controllerAddr)
		self.WithdrawFromControllerProcess(controllerAddr, amount)
		controllerPendingWithdraws.pop(controllerAddr)

	def GetControllerPendingWithdraws(self):
		bname = "controllerPendingWithdraws"
		controllerPendingWithdraws = self.local.db.get(bname)
		if controllerPendingWithdraws is None:
			controllerPendingWithdraws = dict()
			self.local.db[bname] = controllerPendingWithdraws
		return controllerPendingWithdraws

	def SignElectionRequestWithController(self, controllerAddr, startWorkTime, adnlAddr, validatorPubkey_b64, validatorSignature, maxFactor, stake):
		self.local.add_log("start SignElectionRequestWithController function", "debug")
		fileName = self.tempDir + str(startWorkTime) + "_validator-query.boc"
		fiftScript = self.contractsDir + "jetton_pool/fift-scripts/controller-elect-signed.fif"
		args = [fiftScript, controllerAddr, startWorkTime, maxFactor, adnlAddr, validatorPubkey_b64, validatorSignature, fileName, stake]
		self.local.add_log(f"SignElectionRequestWithController args: {args}", "debug")
		result = self.fift.run(args)
		self.local.add_log(f"SignElectionRequestWithController result: {result}", "debug")
		pubkey = parse(result, "validator public key ", '\n')
		fileName = parse(result, "Saved to file ", '\n')
		return pubkey, fileName

	def ControllersUpdateValidatorSet(self):
		self.local.add_log("start ControllersUpdateValidatorSet function", "debug")
		using_controllers = self.local.db.get("using_controllers")
		user_controllers = self.local.db.get("user_controllers", list())
		old_controllers = self.local.db.get("old_controllers", list())
		for controller in using_controllers + user_controllers + old_controllers:
			self.ControllerUpdateValidatorSet(controller)

	def ControllerUpdateValidatorSet(self, controllerAddr: str):
		self.local.add_log("start ControllerUpdateValidatorSet function", "debug")
		wallet = self.GetValidatorWallet()
		controllers = self.GetControllers()

		try:
			controllerData = self.GetControllerData(controllerAddr)
		except Exception:
			return

		timeNow = int(time.time())
		config34 = self.get_config_34()
		fullElectorAddr = self.GetFullElectorAddr()
		returnedStake = self.get_returned_stake(fullElectorAddr, controllerAddr)
		controllerPendingWithdraws = self.GetControllerPendingWithdraws()
		if (controllerData["state"] == 3 and
			controllerData["validator_set_changes_count"] < 2 and
			controllerData["validator_set_change_time"] < config34.start_work_time):
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
			config34.start_work_time > controllerData["borrowing_time"]):
			self.ReturnUnusedLoan(controllerAddr)
		if (controllerData["state"] == 0 and controllerAddr in controllerPendingWithdraws):
			self.HandleControllerPendingWithdraw(controllerPendingWithdraws, controllerAddr)
		if controllerAddr not in controllers:
			self.WithdrawFromController(controllerAddr)

	def ControllerUpdateValidatorSetProcess(self, controllerAddr, wallet):
		self.local.add_log("start ControllerUpdateValidatorSetProcess function", "debug")
		fileName = self.contractsDir + "jetton_pool/fift-scripts/update_validator_hash.boc"
		resultFilePath = self.SignBocWithWallet(wallet, fileName, controllerAddr, 1.07)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("ControllerUpdateValidatorSetProcess completed")

	def ControllerRecoverStake(self, controllerAddr):
		wallet = self.GetValidatorWallet()
		self.local.add_log("start ControllerRecoverStake function", "debug")
		fileName = self.contractsDir + "jetton_pool/fift-scripts/recover_stake.boc"
		resultFilePath = self.SignBocWithWallet(wallet, fileName, controllerAddr, 1.04)
		self.SendFile(resultFilePath, wallet)
		self.local.add_log("ControllerRecoverStake completed")

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
		data = self.local.read_db(self.liteClient.config_path)
		mainnet_zero_state_root_hash = "F6OpKZKqvqeFp6CQmFomXNMfMj2EnaUSOXN+Mh+wVWk="
		testnet_zero_state_root_hash = "gj+B8wb/AmlPk1z1AhVI484rhrUpgSr2oSFIh56VoSg="
		if data.validator.zero_state.root_hash == mainnet_zero_state_root_hash:
			return "mainnet"
		elif data.validator.zero_state.root_hash == testnet_zero_state_root_hash:
			return "testnet"
		else:
			return "unknown"

	def get_node_ip(self):
		try:
			config = self.GetValidatorConfig()
			return int2ip(config['addrs'][0]['ip'])
		except Exception:
			return None

	def get_validator_engine_ip(self):
		return self.validatorConsole.addr.split(':')[0]

	def GetFunctionBuffer(self, name: str, timeout: int | float = 10) -> Any | None:
		res = self.cache.get(name)
		if res is None:
			return None
		if get_timestamp() - res.time > timeout:
			return None
		return res.data

	def SetFunctionBuffer(self, name: str, data):
		self.cache[name] = CacheResult(
			time=get_timestamp(),
			data=data
		)

	def IsTestnet(self):
		networkName = self.GetNetworkName()
		if networkName == "testnet":
			return True
		else:
			return False

	def IsAddr(self, addr):
		isAddrB64 = self.IsAddrB64(addr)
		isAddrFull = self.IsAddrFull(addr)
		if isAddrB64 or isAddrFull:
			return True
		return False

	def IsAddrB64(self, addr):
		try:
			self.ParseAddrB64(addr)
			return True
		except Exception:
			pass
		return False

	def IsAddrFull(self, addr):
		try:
			self.ParseAddrFull(addr)
			return True
		except Exception:
			pass
		return False


def Dec2HexAddr(dec):
	h = dec2hex(dec)
	hu = h.upper()
	h64 = hu.rjust(64, "0")
	return h64
