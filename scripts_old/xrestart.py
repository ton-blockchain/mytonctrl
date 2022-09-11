import os
import sys
import pwd
import time
import threading
import subprocess

def Xguard():
	timestamp = int(sys.argv[1])
	args = sys.argv[2:]
	while True:
		time.sleep(1)
		timenow = int(time.time())
		if timenow > timestamp:
			Xcmd(args)
			print("exit")
			sys.exit(0)
#end define

def Xcmd(inputArgs):
	print("inputArgs:", inputArgs)
	
	# stop validator
	args = ["systemctl", "stop", "validator"]
	subprocess.run(args)
	
	file = open("/etc/systemd/system/validator.service", 'rt')
	text = file.read()
	file.close()
	lines = text.split('\n')
	
	for line in lines:
		if "ExecStart" not in line:
			continue
		ExecStart = line.replace("ExecStart = ", '')
		args = ExecStart.split(' ')
		print("ExecStart args:", args)
		args += inputArgs
	#end for

	pw_record = pwd.getpwnam("validator")
	user_uid = pw_record.pw_uid
	user_gid = pw_record.pw_gid
	
	# start with args
	print("args:", args)
	process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=demote(user_uid, user_gid))
	process.wait()
	text = process.stdout.read().decode()
	print("text:", text)
	
	# Exit program
	sys.exit(0)
#end define

def demote(user_uid, user_gid):
	def result():
		os.setgid(user_gid)
		os.setuid(user_uid)
		os.system("ulimit -n 1")
		os.system("ulimit -u 1")
		os.system("ulimit -l 1")
	return result
#end define


###
### Start of the program
###

if __name__ == "__main__":
	Xguard()
#end if
