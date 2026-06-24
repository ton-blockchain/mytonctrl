from __future__ import annotations

import base64
import json
import os
import platform
import time
import subprocess
import typing

import requests
from nacl.signing import SigningKey

from mypylib import MyPyClass


def start_service(local, service_name:str, sleep:int=1):
	local.add_log(f"Start/restart {service_name} service", "debug")
	args = ["systemctl", "restart", service_name]
	subprocess.run(args)

	local.add_log(f"sleep {sleep} sec", "debug")
	time.sleep(sleep)

def stop_service(local, service_name:str):
	local.add_log(f"Stop {service_name} service", "debug")
	args = ["systemctl", "stop", service_name]
	subprocess.run(args)

def disable_service(local, service_name: str):
	local.add_log(f"Disable {service_name} service", "debug")
	args = ["systemctl", "disable", service_name]
	subprocess.run(args)

def StartValidator(local):
	start_service(local, "validator", sleep=10)

def StartMytoncore(local):
	start_service(local, "mytoncore")

def get_ed25519_pubkey_text(privkey_text):
	privkey = base64.b64decode(privkey_text)
	pubkey = get_ed25519_pubkey(privkey)
	pubkey_text = base64.b64encode(pubkey).decode("utf-8")
	return pubkey_text

def get_ed25519_pubkey(privkey):
	privkey_obj = SigningKey(privkey)
	pubkey = privkey_obj.verify_key.encode()
	return pubkey


def is_testnet(global_config_path: str):
	testnet_zero_state_root_hash = "gj+B8wb/AmlPk1z1AhVI484rhrUpgSr2oSFIh56VoSg="
	with open(global_config_path) as f:
		config = json.load(f)
	if config['validator']['zero_state']['root_hash'] == testnet_zero_state_root_hash:
		return True
	return False


def get_ton_storage_port(local: MyPyClass) -> typing.Optional[int]:
	p = subprocess.run(["systemctl", "cat", "ton_storage.service"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
					   timeout=3)
	if p.returncode != 0:
		local.add_log("Failed to get ton_storage.service", "error")
		return None
	output = p.stdout.decode()
	for line in output.splitlines():
		if line.startswith('ExecStart'):
			cmd = line.split()
			if '-api' not in cmd:
				local.add_log("Failed to find -api in ton_storage.service exec command", "error")
				return None
			return int(cmd[cmd.index('-api') + 1].split(':')[1])
	local.add_log("Failed to find ExecStart in ton_storage.service", "error")
	return None

def tha_exists():
	try:
		resp = requests.get('http://127.0.0.1:8801/healthcheck', timeout=3)
	except Exception:
		return False
	if resp.status_code == 200 and resp.text == '"OK"':
		return True
	return False


def add2systemd(
		*,
		name: str,
		user: str,
		start: str,
		pre: str | None = None,
		post: str = "/bin/echo service down",
		group: str | None = None,
		workdir: str | None = None,
		force: bool = False
) -> None:
	group = group or user
	pversion = platform.version()
	psys = platform.system()
	path = f"/etc/systemd/system/{name}.service"

	if psys == "OpenBSD":
		path = f"/etc/rc.d/{name}"
	if os.path.isfile(path):
		if force:
			print("Unit exist, force rewrite")
		else:
			print("Unit exist.")
			return

	text = f"""
[Unit]
Description = {name} service
After = network.target

[Service]
Type = simple
Restart = always
RestartSec = 30
ExecStart = {start}
{f"ExecStartPre = {pre}" if pre else '# ExecStartPre not set'}
ExecStopPost = {post}
User = {user}
Group = {group} 
{f"WorkingDirectory = {workdir}" if workdir else '# WorkingDirectory not set'}
LimitNOFILE = infinity
LimitNPROC = infinity
LimitMEMLOCK = infinity

[Install]
WantedBy = multi-user.target
"""

	if psys == "OpenBSD" and 'APRENDIENDODEJESUS' in pversion:
		text = f"""
#!/bin/ksh
servicio="{start}"
servicio_user="{user}"
servicio_timeout="3"

. /etc/rc.d/rc.subr

rc_cmd $1
"""

	with open(path, 'w') as f:
		f.write(text)

	subprocess.run(["chmod", "664", path])
	subprocess.run(["chmod", "+x", path])

	if psys != "OpenBSD":
		subprocess.run(["systemctl", "daemon-reload"])

	if psys == "OpenBSD":
		args = ["rcctl", "enable", name]
	else:
		args = ["systemctl", "enable", name]
	subprocess.run(args)
