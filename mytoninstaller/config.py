import os
import json
import subprocess
import requests
import base64

from mytoncore.utils import hex2b64, dict2b64
from mytoninstaller.utils import StartMytoncore, GetInitBlock
from mypylib.mypylib import ip2int


defaultLocalConfigPath = "/usr/bin/ton/local.config.json"


def GetConfig(**kwargs):
	path = kwargs.get("path")
	file = open(path, 'rt')
	text = file.read()
	file.close()
	config = json.loads(text)
	return config
#end define


def SetConfig(**kwargs):
	path = kwargs.get("path")
	data = kwargs.get("data")

	# write config
	text = json.dumps(data, indent=4)
	file = open(path, 'wt')
	file.write(text)
	file.close()
#end define


def BackupVconfig(local):
	local.AddLog("Backup validator config file 'config.json' to 'config.json.backup'", "debug")
	vconfigPath = local.buffer["vconfigPath"]
	backupPath = vconfigPath + ".backup"
	args = ["cp", vconfigPath, backupPath]
	subprocess.run(args)
#end define


def BackupMconfig(local):
	local.AddLog("Backup mytoncore config file 'mytoncore.db' to 'mytoncore.db.backup'", "debug")
	mconfigPath = local.buffer["mconfigPath"]
	backupPath = mconfigPath + ".backup"
	args = ["cp", mconfigPath, backupPath]
	subprocess.run(args)
#end define


def GetPortsFromVconfig(local):
	vconfigPath = local.buffer["vconfigPath"]

	# read vconfig
	local.AddLog("read vconfig", "debug")
	vconfig = GetConfig(path=vconfigPath)

	# read mconfig
	local.AddLog("read mconfig", "debug")
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)

	# edit mytoncore config file
	local.AddLog("edit mytoncore config file", "debug")
	mconfig["liteClient"]["liteServer"]["port"] = mconfig["liteservers"][0]["port"]
	mconfig["validatorConsole"]["addr"] = "127.0.0.1:{}".format(mconfig["control"][0]["port"])

	# write mconfig
	local.AddLog("write mconfig", "debug")
	SetConfig(path=mconfigPath, data=mconfig)

	# restart mytoncore
	StartMytoncore(local)
#end define


def CreateLocalConfig(local, initBlock, localConfigPath=defaultLocalConfigPath):
	# dirty hack, but GetInitBlock() function uses the same technique
	from mytoncore import hex2base64

	# read global config file
	file = open("/usr/bin/ton/global.config.json", 'rt')
	text = file.read()
	data = json.loads(text)
	file.close()

	# edit config
	liteServerConfig = GetLiteServerConfig(local)
	data["liteservers"] = [liteServerConfig]
	data["validator"]["init_block"]["seqno"] = initBlock["seqno"]
	data["validator"]["init_block"]["root_hash"] = hex2base64(initBlock["rootHash"])
	data["validator"]["init_block"]["file_hash"] = hex2base64(initBlock["fileHash"])
	text = json.dumps(data, indent=4)

	# write local config file
	file = open(localConfigPath, 'wt')
	file.write(text)
	file.close()

	# chown
	user = local.buffer["user"]
	args = ["chown", "-R", user + ':' + user, localConfigPath]

	print("Local config file created:", localConfigPath)
#end define


def GetLiteServerConfig(local):
	keysDir = local.buffer["keysDir"]
	liteserver_key = keysDir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"
	result = dict()
	file = open(liteserver_pubkey, 'rb')
	data = file.read()
	file.close()
	key = base64.b64encode(data[4:])
	ip = requests.get("https://ifconfig.me").text
	mconfigPath = local.buffer["mconfigPath"]
	mconfig = GetConfig(path=mconfigPath)
	liteClient = mconfig.get("liteClient")
	liteServer = liteClient.get("liteServer")
	result["ip"] = ip2int(ip)
	result["port"] = liteServer.get("port")
	result["id"] = dict()
	result["id"]["@type"]= "pub.ed25519"
	result["id"]["key"]= key.decode()
	return result
#end define
