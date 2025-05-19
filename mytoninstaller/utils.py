import base64
import json
import time
import subprocess

import requests
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

def disable_service(local, service_name: str):
	local.add_log(f"Disable {service_name} service", "debug")
	args = ["systemctl", "disable", service_name]
	subprocess.run(args)

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


def is_testnet(local):
	testnet_zero_state_root_hash = "gj+B8wb/AmlPk1z1AhVI484rhrUpgSr2oSFIh56VoSg="
	with open(local.buffer.global_config_path) as f:
		config = json.load(f)
	if config['validator']['zero_state']['root_hash'] == testnet_zero_state_root_hash:
		return True
	return False


def get_block_from_toncenter(local, workchain: int, shard: int = -9223372036854775808, seqno: int = None, utime: int = None):
	url = f'https://toncenter.com/api/v2/lookupBlock?workchain={workchain}&shard={shard}'
	if is_testnet(local):
		url = url.replace('toncenter.com', 'testnet.toncenter.com')
	if seqno:
		url += f'&seqno={seqno}'
	if utime:
		url += f'&unixtime={utime}'
	local.add_log(f"Requesting block information from {url}", "debug")
	resp = requests.get(url)
	if resp.status_code != 200:
		local.add_log(f"Toncenter API returned status code {resp.status_code}", "error")
		raise Exception(f"Toncenter API request failed: {resp.text}")
	data = resp.json()
	if not data['ok']:
		local.add_log(f"Toncenter API returned error: {data.get('error', 'Unknown error')}", "error")
		raise Exception(f"Toncenter API returned error: {data.get('error', 'Unknown error')}")
	return data['result']
