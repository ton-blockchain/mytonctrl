import subprocess


class ValidatorConsole:
	def __init__(self, local):
		self.local = local
		self.appPath = None
		self.privKeyPath = None
		self.pubKeyPath = None
		self.addr = None
	#end define

	def Run(self, cmd, **kwargs):
		timeout = kwargs.get("timeout", 3)
		if self.appPath is None or self.privKeyPath is None or self.pubKeyPath is None:
			raise Exception("ValidatorConsole error: Validator console is not settings")
		args = [self.appPath, "-k", self.privKeyPath, "-p", self.pubKeyPath, "-a", self.addr, "-v", "0", "--cmd", cmd]
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			self.local.AddLog("args: {args}".format(args=args), "error")
			raise Exception("ValidatorConsole error: {err}".format(err=err))
		return output
	#end define
#end class
