import subprocess


class Fift:
	def __init__(self, local):
		self.local = local
		self.appPath = None
		self.libsPath = None
		self.smartcontsPath = None
	#end define

	def Run(self, args, **kwargs):
		fift_timeout = self.local.db.fift_timeout if self.local.db.fift_timeout else 3
		timeout = kwargs.get("timeout", fift_timeout)
		for i in range(len(args)):
			args[i] = str(args[i])
		includePath = self.libsPath + ':' + self.smartcontsPath
		args = [self.appPath, "-I", includePath, "-s"] + args
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
		if len(err) > 0:
			self.local.add_log("args: {args}".format(args=args), "error")
			raise Exception("Fift error: {err}".format(err=err))
		return output
	#end define
#end class
