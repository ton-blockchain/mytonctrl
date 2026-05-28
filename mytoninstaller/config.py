import json
import re
import subprocess
import requests
import base64

from mypylib import MyPyClass
from mytoninstaller.context import InstallerContext

from mytoninstaller.utils import get_ed25519_pubkey_text
from mypylib.mypylib import ip2int, Dict


defaultLocalConfigPath = "/usr/bin/ton/local.config.json"


def GetConfig(**kwargs):
	path = kwargs.get("path")
	file = open(path, 'rt')
	text = file.read()
	file.close()
	config = Dict(json.loads(text))
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


def backup_config(local, config_path):
	backup_path = f"{config_path}.backup"
	local.add_log(f"Backup config file '{config_path}' to '{backup_path}'", "debug")
	args = ["cp", config_path, backup_path]
	subprocess.run(args)
#end define


def BackupMconfig(local: MyPyClass, ctx: InstallerContext):
	local.add_log("Backup mytoncore config file 'mytoncore.db' to 'mytoncore.db.backup'", "debug")
	mconfig_path = ctx.mconfig_path
	backupPath = mconfig_path + ".backup"
	args = ["cp", mconfig_path, backupPath]
	subprocess.run(args)
#end define


def CreateLocalConfig(local: MyPyClass, ctx: InstallerContext, initBlock: str, localConfigPath: str = defaultLocalConfigPath):
	# dirty hack, but GetInitBlock() function uses the same technique
	from mytoncore.utils import hex2base64

	# read global config file
	file = open("/usr/bin/ton/global.config.json", 'rt')
	text = file.read()
	data = json.loads(text)
	file.close()

	# edit config
	liteServerConfig = GetLiteServerConfig(local, ctx)
	data["liteservers"] = [liteServerConfig]
	data["validator"]["init_block"]["seqno"] = initBlock["seqno"]
	data["validator"]["init_block"]["root_hash"] = hex2base64(initBlock["rootHash"])
	data["validator"]["init_block"]["file_hash"] = hex2base64(initBlock["fileHash"])
	text = json.dumps(data, indent=4)

	# write local config file
	file = open(localConfigPath, 'wt')
	file.write(text)
	file.close()

	print("Local config file created:", localConfigPath)
#end define


def get_own_ip():
	pat = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
	requests.packages.urllib3.util.connection.HAS_IPV6 = False
	ip = requests.get("https://ifconfig.me/ip", timeout=3).text
	if not pat.fullmatch(ip):
		ip = requests.get("https://ipinfo.io/ip", timeout=3).text
		if not pat.fullmatch(ip):
			raise Exception('Cannot get own IP address')
	return ip
#end define


def GetLiteServerConfig(local: MyPyClass, ctx: InstallerContext):
	keys_dir = ctx.paths.keys_dir
	liteserver_key = keys_dir + "liteserver"
	liteserver_pubkey = liteserver_key + ".pub"
	result = Dict()
	file = open(liteserver_pubkey, 'rb')
	data = file.read()
	file.close()
	key = base64.b64encode(data[4:])
	ip = get_own_ip()
	mconfig = GetConfig(path=ctx.mconfig_path)
	result.ip = ip2int(ip)
	result.port = mconfig.liteClient.liteServer.port
	result.id = Dict()
	result.id["@type"]= "pub.ed25519"
	result.id.key= key.decode()
	return result
#end define

def get_ls_proxy_config(local):
	ls_proxy_config_path = "/var/ls_proxy/ls-proxy-config.json"
	ls_proxy_config = GetConfig(path=ls_proxy_config_path)
	ip = get_own_ip()
	port = ls_proxy_config.ListenAddr.split(':')[1]
	privkey_text = ls_proxy_config.Clients[0].PrivateKey

	result = Dict()
	result.ip = ip2int(ip)
	result.port = port
	result.id = Dict()
	result.id["@type"]= "pub.ed25519"
	result.id.key= get_ed25519_pubkey_text(privkey_text)
	return result
#end define
