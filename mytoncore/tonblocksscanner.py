import threading
import time

from mytoncore.models import Block


class TonBlocksScanner():
	def __init__(self, ton, **kwargs):
		self.ton = ton
		self.prevMasterBlock = None
		self.prevShardsBlock = dict()
		self.blocksNum = 0
		self.transNum = 0
		self.nbr = kwargs.get("nbr") #NewBlockReaction
		self.ntr = kwargs.get("ntr") #NewTransReaction
		self.nmr = kwargs.get("nmr") #NewMessageReaction
		self.local = kwargs.get("local")
		self.sync = kwargs.get("sync", False)
		self.delay = 0
		self.working = False
		self.closing = False
	#end define

	def Run(self):
		self.StartThread(self.ScanBlocks, args=())
		self.StartThread(self.ThreadBalancing, args=())
		self.StartThread(self.StatusReading, args=())
	#end define

	def StartThread(self, func, args):
		threading.Thread(target=func, args=args, name=func.__name__, daemon=True).start()
	#end define

	def StartWithMode(self, func, args):
		if self.sync:
			func(*args)
		else:
			self.StartThread(func, args)
	#end define
	
	def AddLog(self, text, type):
		if self.local:
			self.local.AddLog(text, type)
		else:
			print(text)
	#end define

	def Try(self, func, **kwargs):
		args = kwargs.get("args", tuple())
		for step in range(10):
			time.sleep(step)
			try:
				result = func(*args)
				return result
			except Exception as ex:
				err = ex
				text = f"{func.__name__} step: {step}, error: {err}"
				self.AddLog(text, "error")
		raise Exception(err)
	#end define

	def SetStartBlock(self, workchain, shardchain, seqno):
		workchainType = type(workchain)
		shardchainType = type(shardchain)
		seqnoType = type(seqno)
		if workchainType != int:
			raise Exception(f"SetStartBlock error: workchain type mast be int, not {workchainType}")
		if shardchainType != str:
			raise Exception(f"SetStartBlock error: shardchain type mast be str, not {shardchainType}")
		if seqnoType != int:
			raise Exception(f"SetStartBlock error: seqno type mast be int, not {seqnoType}")
		#end if

		block = Block()
		block.workchain = workchain
		block.shardchain = shardchain
		block.seqno = seqno
		if workchain == -1:
			self.prevMasterBlock = block
		else:
			self.SetShardPrevBlock(block)
		self.sync = True
	#end define

	def ThreadBalancing(self):
		while True:
			tnum = threading.active_count()
			if tnum > 100:
				self.delay += 0.1
			elif tnum > 50:
				self.delay += 0.01
			elif tnum < 50:
				self.delay -= 0.1
			elif tnum < 100:
				self.delay -= 0.01
			if self.delay < 0:
				self.delay = 0
			if self.closing is True:
				exit()
			time.sleep(0.1)
	#end define

	def StatusReading(self):
		while True:
			validatorStatus = self.ton.GetValidatorStatus()
			validatorOutOfSync = validatorStatus.get("outOfSync")
			if self.ton.liteClient.pubkeyPath is None:
				self.working = False
				self.closing = True
				text = "TonBlocksScanner error: local liteserver is not configured, stop thread."
				self.AddLog(text, "error")
				exit()
			if validatorOutOfSync > 20:
				self.working = False
				text = f"TonBlocksScanner warning: local liteserver is out of sync: {validatorOutOfSync}."
				self.AddLog(text, "warning")
			else:
				self.working = True
			time.sleep(10)
	#end define

	def ScanBlocks(self):
		while True:
			if self.working is True:
				self.ScanBlock()
			if self.closing is True:
				exit()
			time.sleep(1)
	#end define

	def ScanBlock(self):
		block = self.Try(self.ton.GetLastBlock)
		self.StartThread(self.SearchMissBlocks, args=(block, self.prevMasterBlock))
		if block != self.prevMasterBlock:
			self.StartWithMode(self.ReadBlock, args=(block,))
			self.prevMasterBlock = block
	#end define

	def ReadBlock(self, block):
		self.StartWithMode(self.NewBlockReaction, args=(block,))
		shards = self.Try(self.ton.GetShards, args=(block,))
		for shard in shards:
			self.StartThread(self.ReadShard, args=(shard,))
	#end define

	def ReadShard(self, shard):
		block = shard.get("block")
		prevBlock = self.GetShardPrevBlock(block.shardchain)
		self.StartThread(self.SearchMissBlocks, args=(block, prevBlock))
		if block != prevBlock:
			self.StartWithMode(self.NewBlockReaction, args=(block,))
			self.SetShardPrevBlock(block)
	#end define

	def SearchMissBlocks(self, block, prevBlock):
		if prevBlock is None:
			return
		diff = block.seqno - prevBlock.seqno
		#for i in range(1, diff):
		for i in range(diff-1, 0, -1):
			workchain = block.workchain
			shardchain = block.shardchain
			seqno = block.seqno - i
			self.StartWithMode(self.SearchBlock, args=(workchain, shardchain, seqno))
	#end define

	def SearchBlock(self, workchain, shardchain, seqno):
		if self.delay != 0:
			time.sleep(self.delay)
		block = self.Try(self.ton.GetBlock, args=(workchain, shardchain, seqno))
		self.StartWithMode(self.NewBlockReaction, args=(block,))
	#end define

	def GetShardPrevBlock(self, shardchain):
		prevBlock = self.prevShardsBlock.get(shardchain)
		return prevBlock
	#end define

	def SetShardPrevBlock(self, prevBlock):
		self.prevShardsBlock[prevBlock.shardchain] = prevBlock
	#end define

	def NewBlockReaction(self, block):
		#print(f"{bcolors.green} block: {bcolors.endc} {block}")
		self.blocksNum += 1
		if self.nbr:
			self.StartThread(self.nbr, args=(block,))
		transactions = self.Try(self.ton.GetTransactions, args=(block,))
		for trans in transactions:
			self.StartWithMode(self.NewTransReaction, args=(trans,))
	#end define

	def NewTransReaction(self, trans):
		#print(f"{bcolors.magenta} trans: {bcolors.endc} {self.transNum}", "debug")
		self.transNum += 1
		if self.ntr:
			self.StartThread(self.ntr, args=(trans,))
		messageList = self.Try(self.ton.GetTrans, args=(trans,))
		for message in messageList:
			self.NewMessageReaction(message)
	#end define

	def NewMessageReaction(self, message):
		if self.nmr:
			self.StartThread(self.nmr, args=(message,))
		#print(f"{bcolors.yellow} message: {bcolors.endc} {message}")
	#end define
#end class
