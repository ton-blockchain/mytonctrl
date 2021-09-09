#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import json
import base64
import getpass
import platform
import subprocess


def RunAsRoot(args):
	text = platform.version()
	if "Ubuntu" in text:
		args = ["sudo", "-s"] + args
	else:
		print("Enter root password")
		args = ["su", "-c"] + [" ".join(args)]
	process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	return output
#end define



user = getpass.getuser()
file1 = "/home/{user}/.local/share/mytoncore/mytoncore.db".format(user=user)
file2 = "/usr/local/bin/mytoncore/mytoncore.db"


if os.path.isfile(file1):
	mconfigPath = file1
elif os.path.isfile(file2):
	mconfigPath = file2
#end if

file = open(mconfigPath, 'rt')
mtext = file.read()
file.close()

text = """
vconfigPath = "/var/ton-work/db/config.json"
file = open(vconfigPath, 'rt')
vtext = file.read()
file.close()
print(vtext)
"""
file = open("tmp.py", 'wt')
file.write(text)
file.close()

args = ["python3", "tmp.py"]
vtext = RunAsRoot(args)

buffer = json.loads(vtext)
lsPort = buffer["liteservers"][0]["port"]
vcPort = buffer["control"][0]["port"]
dht = buffer["dht"][0]["id"]
fullnode = buffer["fullnode"]
adnls = buffer["adnl"]
for item in adnls:
	if item["id"] != dht and item["id"] != fullnode:
		adnl_id = item["id"]
		adnl = base64.b64decode(adnl_id).hex().upper()
#end for

data = json.loads(mtext)
data["fift"] = dict()
data["fift"]["appPath"] = "/usr/bin/ton/crypto/fift"
data["fift"]["libsPath"] = "/usr/src/ton/crypto/fift/lib"
data["fift"]["smartcontsPath"] = "/usr/src/ton/crypto/smartcont"

data["liteClient"] = dict()
data["liteClient"]["appPath"] = "/usr/bin/ton/lite-client/lite-client"
data["liteClient"]["configPath"] = "/usr/bin/ton/global.config.json"
data["liteClient"]["liteServer"] = dict()
data["liteClient"]["liteServer"]["pubkeyPath"] = "/usr/bin/ton/validator-engine-console/liteserver.pub"
data["liteClient"]["liteServer"]["ip"] = "127.0.0.1"
data["liteClient"]["liteServer"]["port"] = lsPort

data["validatorConsole"] = dict()
data["validatorConsole"]["appPath"] = "/usr/bin/ton/validator-engine-console/validator-engine-console"
data["validatorConsole"]["privKeyPath"] = "/usr/bin/ton/validator-engine-console/client"
data["validatorConsole"]["pubKeyPath"] = "/usr/bin/ton/validator-engine-console/server.pub"
data["validatorConsole"]["addr"] = "127.0.0.1:" + str(vcPort)

data["miner"] = dict()
data["miner"]["appPath"] = "/usr/bin/ton/crypto/pow-miner"

data["validatorWalletName"] = "validator_wallet_001"
data["adnlAddr"] = adnl

text = json.dumps(data, indent=4)
file = open(mconfigPath, 'wt')
file.write(text)
file.close()

