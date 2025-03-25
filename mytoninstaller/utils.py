import base64
import json
import time
import subprocess
from nacl.signing import SigningKey


def GetInitBlock():
	from mypylib.mypylib import MyPyClass
	from mytoncore import MyTonCore

	mytoncore_local = MyPyClass('mytoncore.py')
	ton = MyTonCore(mytoncore_local)
	initBlock = ton.GetInitBlock()
	return initBlock
#end define

def start_service(local, service_name:str, sleep:int=1):
	local.add_log(f"Start/restart {service_name} service", "debug")
	args = ["systemctl", "restart", service_name]
	subprocess.run(args)

	local.add_log(f"sleep {sleep} sec", "debug")
	time.sleep(sleep)
#end define

def stop_service(local, service_name:str):
	local.add_log(f"Stop {service_name} service", "debug")
	args = ["systemctl", "stop", service_name]
	subprocess.run(args)
#end define

def StartValidator(local):
	start_service(local, "validator", sleep=10)
#end define

def StartMytoncore(local):
	start_service(local, "mytoncore")
#end define

def get_ed25519_pubkey_text(privkey_text):
	privkey = base64.b64decode(privkey_text)
	pubkey = get_ed25519_pubkey(privkey)
	pubkey_text = base64.b64encode(pubkey).decode("utf-8")
	return pubkey_text
#end define

def get_ed25519_pubkey(privkey):
	privkey_obj = SigningKey(privkey)
	pubkey = privkey_obj.verify_key.encode()
	return pubkey
#end define
