from __future__ import annotations

from mypylib.mypylib import Dict, ip2int
from mytoncore.utils import hex2b64

import os
import sys
import json

from mytoninstaller.config import get_own_ip, GetConfig
from mytoninstaller.utils import get_pubkey_file_short_id


def find_keyring_id(keyring: list[str], pubkey_path: str) -> str | None:
	short_id = get_pubkey_file_short_id(pubkey_path)
	for item in keyring:
		if item.upper() == short_id:
			return hex2b64(item)
	return None


def dangerous_recovery_validator_config_file(keyring_dir: str, mconfig_path: str, ton_db_dir: str):
	# Get keys from keyring
	keys: list[str] = []
	keyring = os.listdir(keyring_dir)
	for item in keyring:
		b64String = hex2b64(item)
		keys.append(b64String)

	# Create config object
	vconfig = Dict()
	vconfig["@type"] = "engine.validator.config"
	vconfig.out_port = 3278

	# Create addrs object
	buff = Dict()
	buff["@type"] = "engine.addr"
	buff.ip = ip2int(get_own_ip())
	buff.port = None
	buff.categories = [0, 1, 2, 3]
	buff.priority_categories = []
	vconfig.addrs = [buff]

	# Get liteserver fragment
	mconfig = GetConfig(path=mconfig_path)
	lkey = mconfig.liteClient.liteServer.pubkeyPath
	lport = mconfig.liteClient.liteServer.port

	# Search lite server priv key
	ls_id = find_keyring_id(keyring, lkey)
	if ls_id is not None:
		keys.remove(ls_id)

	# Create LS object
	buff = Dict()
	buff["@type"] = "engine.liteServer"
	buff.id = ls_id
	buff.port = lport
	vconfig.liteservers = [buff]

	# Get validator-console fragment
	ckey = mconfig.validatorConsole.pubKeyPath
	addr = mconfig.validatorConsole.addr
	buff = addr.split(':')
	cport = int(buff[1])

	# Search validator-console priv key
	vcId = find_keyring_id(keyring, ckey)
	if vcId is not None:
		keys.remove(vcId)

	# Create VC object
	buff = Dict()
	buff2 = Dict()
	buff["@type"] = "engine.controlInterface"
	buff.id = vcId
	buff.port = cport
	buff2["@type"] = "engine.controlProcess"
	buff2.id = None
	buff2.permissions = 15
	buff.allowed = buff2
	vconfig.control = [buff]

	# Get dht fragment
	dhtS = None
	files = os.listdir(ton_db_dir)
	for item in files:
		if item[:3] == "dht":
			dhtS = item[4:]
			dhtS = dhtS.replace('_', '/')
			dhtS = dhtS.replace('-', '+')
			break

	# Get ght from keys
	dhtId = None
	for item in keys:
		if dhtS and dhtS in item:
			dhtId = item
			keys.remove(dhtId)

	# Create dht object
	buff = Dict()
	buff["@type"] = "engine.dht"
	buff.id = dhtId
	vconfig.dht = [buff]

	# Create adnl object
	adnl2 = Dict()
	adnl2["@type"] = "engine.adnl"
	adnl2.id = dhtId
	adnl2.category = 0

	# Create adnl object
	adnlId = hex2b64(mconfig["adnlAddr"])
	keys.remove(adnlId)
	adnl3 = Dict()
	adnl3["@type"] = "engine.adnl"
	adnl3.id = adnlId
	adnl3.category = 0

	# Create adnl object
	adnl1 = Dict()
	adnl1["@type"] = "engine.adnl"
	adnl1.id = keys.pop(0)
	adnl1.category = 1

	vconfig.adnl = [adnl1, adnl2, adnl3]

	# Get dumps from tmp
	dumps = list()
	dumpsDir = "/tmp/mytoncore/"
	dumpsList = os.listdir(dumpsDir)
	os.chdir(dumpsDir)
	sorted(dumpsList, key=os.path.getmtime)
	for item in dumpsList:
		if "ElectionEntry.json" in item:
			dumps.append(item)

	# Create validators object
	validators = list()

	# Read dump file
	while len(keys) > 0:
		dumpPath = dumps.pop()
		file = open(dumpPath, 'rt')
		data = file.read()
		file.close()
		dump = json.loads(data)
		vkey = hex2b64(dump["validatorKey"])
		temp_key = Dict()
		temp_key["@type"] = "engine.validatorTempKey"
		temp_key.key = vkey
		temp_key.expire_at = dump["endWorkTime"]
		adnl_addr = Dict()
		adnl_addr["@type"] = "engine.validatorAdnlAddress"
		adnl_addr.id = adnlId
		adnl_addr.expire_at = dump["endWorkTime"]

		# Create validator object
		validator = Dict()
		validator["@type"] = "engine.validator"
		validator.id = vkey
		validator.temp_keys = [temp_key]
		validator.adnl_addrs = [adnl_addr]
		validator.election_date = dump["startWorkTime"]
		validator.expire_at = dump["endWorkTime"]
		if vkey in keys:
			validators.append(validator)
			keys.remove(vkey)

	# Add validators object to vconfig
	vconfig.validators = validators

	print("vconfig:", json.dumps(vconfig, indent=4))
	print("keys:", keys)


if __name__ == '__main__':
	if len(sys.argv) != 4:
		sys.exit("usage: drvcf.py <keyring_dir> <mconfig_path> <ton_db_dir>")
	dangerous_recovery_validator_config_file(sys.argv[1], sys.argv[2], sys.argv[3])
