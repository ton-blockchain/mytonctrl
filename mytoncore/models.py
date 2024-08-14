import os


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
		self.hash = None
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
