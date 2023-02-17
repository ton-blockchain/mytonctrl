import random
import subprocess


class LiteClient:
	def __init__(self, local):
		self.local = local
		self.appPath = None
		self.configPath = None
		self.pubkeyPath = None
		self.addr = None
		self.ton = None # magic
	#end define

	def Run(self, cmd, **kwargs):
		index = kwargs.get("index")
		timeout = kwargs.get("timeout", 3)
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
			liteServers = self.local.db.get("liteServers")
			if liteServers is not None and len(liteServers):
				index = random.choice(liteServers)
				index = str(index)
				args += ["-i", index]
		#end if

		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			self.local.AddLog("args: {args}".format(args=args), "error")
			raise Exception("LiteClient error: {err}".format(err=err))
		return output
	#end define
#end class
