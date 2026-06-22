from __future__ import annotations

import base64
import os
import json
import tempfile
from typing import final, TypedDict, Callable

import requests

from mypylib.mypylib import MyPyClass, run_as_root, color_print, ip2int
from mypyconsole.mypyconsole import MyPyConsole
from mytoncore.models import BlockHead, Paths
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import get_package_resource_path
from mytonctrl.utils import get_current_user

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
		console.add_item("status", self._print_status, "Print TON component status")
		console.add_item("set_node_argument", self._set_node_argument, "Set node argument", "<arg_name> [arg_value1] [arg_value2] [-d (to delete)]")
		console.add_item("enable", self.enable, "Enable some function", "<mode_name>")
		console.add_item("plsc", self._print_ls_config, "Print lite-server config")
		console.add_item("clcf", self.create_local_config_file, "Create lite-server config file", "[path]")
		console.add_item("print_ls_proxy_config", self._print_ls_proxy_config, "Print ls-proxy config")
		console.add_item("drvcf", self._drvcf, "Dangerous recovery validator config file")
		console.add_item("ton_storage_list", self.ton_storage_list, "Print result of /list method at Ton Storage API")

	def _print_status(self, _: list[str]):
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

	def _set_node_argument(self, args: list[str]):
		if len(args) < 1:
			color_print("{red}Bad args. Usage:{endc} set_node_argument <arg-name> [arg-value] [-d (to delete)].\n"
						"Examples: 'set_node_argument --archive-ttl 86400' or 'set_node_argument --archive-ttl -d' or 'set_node_argument -M' or 'set_node_argument --add-shard 0:2000000000000000 0:a000000000000000'")
			return
		set_node_argument(args)

	def enable(self, args: list[str]):
		if len(args) < 1:
			color_print("{red}Bad args. Usage:{endc} enable <mode-name>")
			return
		name = args[0]
		if name == "DS":
			with get_package_resource_path('mytoninstaller.scripts', 'dht_server.py') as script_path:
				run_as_root(['python3', str(script_path), self._validator_user, str(self._paths.ton_bin), str(self._paths.global_config_path)])
		elif name == "THA":
			self.create_local_config_file([])
			self.enable_ton_http_api(update=True)
		elif name == "LSP":
			user = get_current_user()
			with get_package_resource_path('mytoninstaller.scripts', 'ls_proxy.py') as script_path:
				run_as_root(['python3', str(script_path), user, self.mconfig_path, str(self._paths.src_dir)])
		elif name == "TS":
			user = get_current_user()
			with get_package_resource_path('mytoninstaller.scripts', 'ton_storage.py') as script_path:
				run_as_root(['python3', str(script_path), user, self.mconfig_path, str(self._paths.global_config_path), str(self._paths.src_dir)])
		else:
			color_print("{red}Bad args{endc}")
			print("'DS' - DHT-Server")
			print("'THA' - ton-http-api")
			print("'LSP' - ls-proxy")
			print("'TS' - ton-storage")

	def _drvcf(self, _: list[str]):
		with get_package_resource_path('mytoninstaller.scripts', 'drvcf.py') as script_path:
			run_as_root(['python3', str(script_path), str(self._paths.keyring_dir), self.mconfig_path, str(self._paths.ton_db)])

	def ton_storage_list(self, args: list[str]):
		if len(args) > 0:
			api_port = int(args[0])
		else:
			api_port = get_ton_storage_port(self.local)
			if api_port is None:
				raise Exception('Failed to get Ton Storage API port and port was not provided. Use ton_storage_list [api_port]')
		data = requests.get(f"http://127.0.0.1:{api_port}" + '/api/v1/list', timeout=3)
		if data.status_code != 200:
			raise Exception(f'Failed to get Ton Storage list: {data.text}')
		print(json.dumps(data.json(), indent=4))

	def enable_ton_http_api(self, update: bool = False):
		try:
			if update or not tha_exists():
				self.do_enable_ton_http_api()
		except Exception as e:
			self.local.add_log(f"Error in enable_ton_http_api: {e}", "warning")
			pass

	def do_enable_ton_http_api(self):
		self.local.add_log("start do_enable_ton_http_api function", "debug")
		if not os.path.exists(self._paths.local_config_path):
			self.create_local_config_file([])
		user = get_current_user()
		with get_package_resource_path('mytoninstaller.scripts',
		                               'ton_http_api_installer.sh') as ton_http_api_installer_path:
			exit_code = run_as_root(["bash", str(ton_http_api_installer_path), "-u", user, "-b", str(self._paths.ton_bin), "-c", str(self._paths.local_config_path)])
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

	def create_local_config_file(self, args: list[str]):
		path = args[0] if len(args) > 0 else str(self._paths.local_config_path)
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

	def _print_ls_config(self, _: list[str]):
		print(json.dumps(self._get_ls_config(), indent=4))

	def _print_ls_proxy_config(self, _: list[str]):
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
