import json
import re
import subprocess
import requests

from mypylib import MyPyClass
from mytoninstaller.context import InstallerContext

from mytoninstaller.utils import get_ed25519_pubkey_text
from mypylib.mypylib import ip2int, Dict


def GetConfig(path: str):
	with open(path, 'rt') as f:
		text = f.read()
	config = Dict(json.loads(text))
	return config


def SetConfig(path: str, data: Dict):
	text = json.dumps(data, indent=4)
	with open(path, 'wt') as f:
		f.write(text)

def backup_config(local: MyPyClass, config_path: str):
	backup_path = f"{config_path}.backup"
	local.add_log(f"Backup config file '{config_path}' to '{backup_path}'", "debug")
	args = ["cp", config_path, backup_path]
	subprocess.run(args)

def BackupMconfig(local: MyPyClass, ctx: InstallerContext):
	local.add_log("Backup mytoncore config file 'mytoncore.db' to 'mytoncore.db.backup'", "debug")
	mconfig_path = ctx.mconfig_path
	backupPath = mconfig_path + ".backup"
	args = ["cp", mconfig_path, backupPath]
	subprocess.run(args)
#end define

def get_own_ip():
	from urllib3.util import connection
	connection.HAS_IPV6 = False
	pat = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
	ip = requests.get("https://ifconfig.me/ip", timeout=3).text
	if not pat.fullmatch(ip):
		ip = requests.get("https://ipinfo.io/ip", timeout=3).text
		if not pat.fullmatch(ip):
			raise Exception('Cannot get own IP address')
	return ip
#end define


def get_ls_proxy_config():
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
