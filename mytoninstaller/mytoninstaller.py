from __future__ import annotations

import base64
import os
import json
import sys
import tempfile
from typing import final, TypedDict, Callable, Literal, Optional

import requests

from mypylib.mypylib import MyPyClass, run_as_root, color_print, ip2int
from mypyconsole.mypyconsole import MyPyConsole, UsageError
from mytoncore.models import BlockHead, Paths
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import get_package_resource_path
from mypyconsole.command_parser import Annotated, Arg
from mytonctrl.utils import get_current_user, is_container

from mytoninstaller.config import get_ls_proxy_config, get_own_ip
from mytoninstaller.node_args import get_node_args, set_node_argument
from mytoninstaller.utils import get_ton_storage_port, tha_exists
from mytoncore.utils import b642hex


class LsData(TypedDict):
	pubkeyPath: str
	ip: str
	port: int


@final
class InstallerCtrl:

	def __init__(
			self,
			local: MyPyClass,
			mconfig_path: str,
			paths: Paths,
			ls_data: LsData | None,
			get_init_block: Callable[[], BlockHead] | None,
			console: MyPyConsole | None = None
	):
		self.local= local
		self.mconfig_path = mconfig_path
		self._paths = paths
		self._ls_data = ls_data
		self._validator_user = 'validator'
		self._get_init_block = get_init_block
		self._console_engine = console

	def run(self, cmd: str | None = None):
		if self._console_engine is None:
			raise ValueError("Console engine is not set")
		self.local.db.config.isStartOnlyOneProcess = False
		self.local.db.config.logLevel = "debug"
		self._console_engine.color = self._console_engine.RED
		self._add_console_commands(self._console_engine)
		if cmd:
			self._console_engine.run_cmd(cmd)
			return
		self._console_engine.run()

	def _add_console_commands(self, console: MyPyConsole):
		console.add_command("status", self._print_status, "Print TON component status")
		console.add_command("set_node_argument", self._set_node_argument, "Set node argument", forward_unknown=True)
		console.add_command("enable", self.enable, "Enable some function")
		console.add_command("plsc", self._print_ls_config, "Print lite-server config")
		console.add_command("clcf", self.create_local_config_file, "Create lite-server config file")
		console.add_command("print_ls_proxy_config", self._print_ls_proxy_config, "Print ls-proxy config")
		console.add_command("drvcf", self._drvcf, "Dangerous recovery validator config file")
		console.add_command("ton_storage_list", self.ton_storage_list, "Print result of /list method at Ton Storage API")


	def _print_status(self) -> None:
		keys_dir = self._paths.ton_keys
		server_key = keys_dir / "server"
		client_key = keys_dir / "client"
		liteserver_pubkey = keys_dir / "liteserver.pub"

		statuses = {
			'Full node status': os.path.isfile(self._paths.vconfig_path),
			'Mytoncore status': os.path.isfile(self.mconfig_path),
			'V.console status': os.path.isfile(server_key) or os.path.isfile(client_key),
			'Liteserver status': os.path.isfile(liteserver_pubkey)
		}

		color_print("{cyan}===[ Services status ]==={endc}")
		for item in statuses.items():
			status = '{green}enabled{endc}' if item[1] else '{red}disabled{endc}'
			color_print(f"{item[0]}: {status}")

		node_args = get_node_args()
		color_print("{cyan}===[ Node arguments ]==={endc}")
		for key, value in node_args.items():
			if len(value) == 0:
				print(f"{key}")
			for v in value:
				print(f"{key}: {v}")

	def _set_node_argument(self, *arg_name_and_values: str, delete: Annotated[bool, Arg("-d", help="delete the argument from the node command line")] = False) -> None:
		if not arg_name_and_values:
			raise UsageError("expected the node argument name, e.g. set_node_argument --archive-ttl 86400")
		args = list(arg_name_and_values)
		if delete:
			args.append("-d")
		set_node_argument(args)

	def enable(self, mode_name: Literal["DS", "THA", "LSP", "TS"]) -> None:
		if is_container() and mode_name in ("THA", "LSP"):
			raise RuntimeError(f"{mode_name} is installed separately in container deployments. The controller image does not install packages or compile add-ons.")
		if mode_name == "DS":
			with get_package_resource_path('mytoninstaller.scripts', 'dht_server.py') as script_path:
				run_as_root([sys.executable, str(script_path), self._validator_user, str(self._paths.ton_bin), str(self._paths.global_config_path)])
		elif mode_name == "THA":
			self.create_local_config_file()
			self.enable_ton_http_api(update=True)
		elif mode_name == "LSP":
			user = get_current_user()
			with get_package_resource_path('mytoninstaller.scripts', 'ls_proxy.py') as script_path:
				run_as_root([sys.executable, str(script_path), user, self.mconfig_path, str(self._paths.src_dir)])
		elif mode_name == "TS":
			user = get_current_user()
			with get_package_resource_path('mytoninstaller.scripts', 'ton_storage.py') as script_path:
				run_as_root([sys.executable, str(script_path), user, self.mconfig_path, str(self._paths.global_config_path), str(self._paths.src_dir)])

	def _drvcf(self) -> None:
		with get_package_resource_path('mytoninstaller.scripts', 'drvcf.py') as script_path:
			run_as_root([sys.executable, str(script_path), str(self._paths.keyring_dir), self.mconfig_path, str(self._paths.ton_db)])

	def ton_storage_list(self, api_port: Optional[int] = None) -> None:
		if api_port is None:
			api_port = get_ton_storage_port(self.local)
			if api_port is None:
				raise Exception('Failed to get Ton Storage API port and port was not provided. Use ton_storage_list [api_port]')
		data = requests.get(f"http://127.0.0.1:{api_port}" + '/api/v1/list', timeout=3)
		if data.status_code != 200:
			raise Exception(f'Failed to get Ton Storage list: {data.text}')
		print(json.dumps(data.json(), indent=4))

	def enable_ton_http_api(self, update: bool = False):
		if is_container():
			return
		try:
			if update or not tha_exists():
				self.do_enable_ton_http_api()
		except Exception as e:
			self.local.add_log(f"Error in enable_ton_http_api: {e}", "warning")
			pass

	def do_enable_ton_http_api(self):
		if is_container():
			raise RuntimeError("Run ton-http-api in a separate container; this controller image does not install or update it.")
		self.local.add_log("start do_enable_ton_http_api function", "debug")
		if not os.path.exists(self._paths.local_config_path):
			self.create_local_config_file()
		user = get_current_user()
		with get_package_resource_path('mytoninstaller.scripts',
		                               'ton_http_api_installer.sh') as ton_http_api_installer_path:
			exit_code = run_as_root(["bash", str(ton_http_api_installer_path), "-u", user, "-b", str(self._paths.ton_bin), "-c", str(self._paths.local_config_path), "-p", sys.executable])
		if exit_code == 0:
			text = "do_enable_ton_http_api - {green}OK{endc}"
		else:
			text = "do_enable_ton_http_api - {red}Error{endc}"
		color_print(text)

	def _get_ls_config(self):
		if self._ls_data is None:
			raise Exception("Liteserver data is not set")
		ls_ip = self._ls_data["ip"]
		if ls_ip == '127.0.0.1':
			ls_ip = get_own_ip()
		ip = ip2int(ls_ip)
		with open(self._ls_data["pubkeyPath"], 'rb') as f:
			data = f.read()
		key = base64.b64encode(data[4:])
		result = {
			"ip": ip,
			"port": self._ls_data["port"],
			"id": {
				"@type": "pub.ed25519",
				"key": key.decode()
			}
		}
		return result

	def create_local_config_file(self, path: Optional[str] = None) -> None:
		if path is None:
			path = str(self._paths.local_config_path)
		init_block: BlockHead | None = None
		if self._get_init_block is not None:
			try:
				init_block = self._get_init_block()
			except Exception as e:
				self.local.add_log(f"Failed to get init block: {e}", "warning")

		if init_block is None or init_block['rootHash'] is None:
			self.local.add_log("Failed to get recent init block. Using init block from global config.", "warning")
			with open(self._paths.global_config_path, 'r') as f:
				config = json.load(f)
			config_init_block = config['validator']['init_block']
			init_block = {"seqno": config_init_block['seqno'], "rootHash": b642hex(config_init_block['root_hash']), "fileHash": b642hex(config_init_block['file_hash'])}
		self._create_local_config(init_block, path)

	def _create_local_config(self, init_block: BlockHead, localConfigPath: str):
		from mytoncore.utils import hex2base64

		with open(self._paths.global_config_path, 'r') as f:
			data = json.loads(f.read())

		lite_server_config = self._get_ls_config()
		data["liteservers"] = [lite_server_config]
		data["validator"]["init_block"]["seqno"] = init_block["seqno"]
		data["validator"]["init_block"]["root_hash"] = hex2base64(init_block["rootHash"])
		data["validator"]["init_block"]["file_hash"] = hex2base64(init_block["fileHash"])
		text = json.dumps(data, indent=4)

		# write local config file
		try:
			with open(localConfigPath, 'wt') as file:
				file.write(text)
		except PermissionError:
			with tempfile.NamedTemporaryFile('wt', suffix='.json') as tmp_file:
				tmp_file.write(text)
				tmp_file.flush()
				exit_code = run_as_root(["install", "-m", "0644", tmp_file.name, localConfigPath])
			if exit_code != 0:
				message = f"Failed to create local config file {localConfigPath} as root (exit code {exit_code})."
				self.local.add_log(message, "error")
				raise RuntimeError(message)

		print("Local config file created:", localConfigPath)

	def _print_ls_config(self) -> None:
		print(json.dumps(self._get_ls_config(), indent=4))

	def _print_ls_proxy_config(self) -> None:
		print(json.dumps(get_ls_proxy_config(), indent=4))

	@classmethod
	def from_ton(cls, ton: MyTonCore):
		local = MyPyClass(__file__)
		console = MyPyConsole(local, name="MyTonInstaller")
		return cls(local,
				   mconfig_path=ton.local.db_path,
				   paths=ton.get_paths(),
				   ls_data=ton.local.db.get("liteClient", {}).get("liteServer"),
				   get_init_block=ton.GetInitBlock,
				   console=console,
		           )
