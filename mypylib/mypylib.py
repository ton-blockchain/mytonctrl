from __future__ import annotations

import os
import re
import shutil
import sys
import grp
import time
import json
import zlib
import signal
import base64
import psutil
import struct
import socket
import hashlib
import platform
import requests
import threading
import subprocess
import datetime as date_time_library
from types import FrameType
from typing import Any, Callable, Literal, Mapping, Sequence
from urllib.request import urlopen
from urllib.error import URLError

INFO = "info"
WARNING = "warning"
ERROR = "error"
DEBUG = "debug"

Callback = Callable[..., Any]


class Dict(dict):

	def __init__(self, *args: Mapping[str, Any], **kwargs: Any) -> None:
		for item in args:
			self._parse_dict(item)
		self._parse_dict(kwargs)

	def _parse_dict(self, d: Mapping[str, Any]) -> None:
		for key, value in d.items():
			if type(value) in [dict, Dict]:
				value = Dict(value)
			if type(value) == list:
				value = self._parse_list(value)
			self[key] = value

	def _parse_list(self, lst: list[Any]) -> list[Any]:
		result = list()
		for value in lst:
			if type(value) in [dict, Dict]:
				value = Dict(value)
			result.append(value)
		return result

	def __getitem__(self, key: str) -> Any:
		return super().__getitem__(key)

	def get(self, key: str, default: Any = None) -> Any:
		return super().get(key, default)

	def __setattr__(self, key: str, value: Any) -> None:
		self[key] = value

	def __getattr__(self, key: str) -> Any:
		return self.get(key)


class bcolors:
	'''This class is designed to display text in color format'''
	red = "\033[31m"
	green = "\033[32m"
	yellow = "\033[33m"
	blue = "\033[34m"
	magenta = "\033[35m"
	cyan = "\033[36m"
	endc = "\033[0m"
	bold = "\033[1m"
	underline = "\033[4m"
	default = "\033[39m"

	DEBUG = magenta
	INFO = blue
	OKGREEN = green
	WARNING = yellow
	ERROR = red
	ENDC = endc
	BOLD = bold
	UNDERLINE = underline

	@staticmethod
	def get_args(*args: Any) -> str:
		text = ""
		for item in args:
			if item is None:
				continue
			text += str(item)
		return text
	#end define

	@staticmethod
	def magenta_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.magenta + text + bcolors.endc
		return text
	#end define

	@staticmethod
	def blue_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.blue + text + bcolors.endc
		return text
	#end define

	@staticmethod
	def green_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.green + text + bcolors.endc
		return text
	#end define

	@staticmethod
	def yellow_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.yellow + text + bcolors.endc
		return text
	#end define

	@staticmethod
	def red_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.red + text + bcolors.endc
		return text
	#end define

	@staticmethod
	def bold_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.bold + text + bcolors.endc
		return text
	#end define

	@staticmethod
	def underline_text(*args: Any) -> str:
		text = bcolors.get_args(*args)
		text = bcolors.underline + text + bcolors.endc
		return text
	#end define

	colors = {"red": red, "green": green, "yellow": yellow, "blue": blue, "magenta": magenta, "cyan": cyan,
			  "endc": endc, "bold": bold, "underline": underline}
#end class


class MyPyClass:
	def __init__(self, file: str) -> None:
		self.working: bool = True
		self.file: str = file
		self.db: Dict = Dict()
		self.db.config = Dict()

		self.old_db = Dict()
		self.log_list = list()
		self.thread_count: int | None = None
		self.thread_count_old: int | None = None
		self.memory_using: float | None = None
		self.free_space_memory: float | None = None

		self.buffer: Dict = Dict()

		self.my_name: str = self.get_my_name()
		self.my_full_name: str = self.get_my_full_name()
		self.my_path: str = self.get_my_path()
		self.my_work_dir: str = self.get_my_work_dir()
		self.my_temp_dir: str = self.get_my_temp_dir()
		self.log_file_name: str = self.my_work_dir + self.my_name + ".log"
		self.db_path: str = self.my_work_dir + self.my_name + ".db"
		self.pid_file_path: str = self.my_work_dir + self.my_name + ".pid"

		self.translate_dict: dict | None = None

		os.makedirs(self.my_work_dir, exist_ok=True)
		os.makedirs(self.my_temp_dir, exist_ok=True)

		self.load_db()
		self.set_default_config()

		# Remove old log file
		if self.db.config.isDeleteOldLogFile and os.path.isfile(self.log_file_name):
			os.remove(self.log_file_name)

		# Catch the shutdown signal
		signal.signal(signal.SIGINT, self.exit)
		signal.signal(signal.SIGTERM, self.exit)

	def start_service(self, service_name: str, sleep: int = 1) -> None:
		self.add_log(f"Start/restart {service_name} service", "debug")
		args = ["systemctl", "restart", service_name]
		subprocess.run(args)

		self.add_log(f"sleep {sleep} sec", "debug")
		time.sleep(sleep)
	# end define

	def stop_service(self, service_name: str) -> None:
		self.add_log(f"Stop {service_name} service", "debug")
		args = ["systemctl", "stop", service_name]
		subprocess.run(args)
	# end define

	def run(self) -> None:
		# Check args
		if "-ef" in sys.argv:
			file = open(os.devnull, 'w')
			sys.stdout = file
			sys.stderr = file
		if "-d" in sys.argv:
			self.fork_daemon()
		if "-s" in sys.argv:
			x = sys.argv.index("-s")
			file_path = sys.argv[x + 1]
			self.get_settings(file_path)
		if "--add2cron" in sys.argv:
			self.add_to_crone()

		# Start only one process (exit if process exist)
		if self.db.config.isStartOnlyOneProcess:
			self.start_only_one_process()
		#end if

		# Start other threads
		self.start_cycle(self.self_test, sec=1)
		if self.db.config.isWritingLogFile is True:
			self.start_cycle(self.write_log, sec=1)
		if self.db.config.isLocaldbSaving is True:
			self.start_cycle(self.save_db, sec=1)
		self.thread_count_old = threading.active_count()

		# Logging the start of the program
		self.add_log(f"Start program `{self.my_path}`")
	#end define

	def set_default_config(self):
		if self.db.config.logLevel is None:
			self.db.config.logLevel = INFO  # info || debug
		if self.db.config.isLimitLogFile is None:
			self.db.config.isLimitLogFile = True
		if self.db.config.isDeleteOldLogFile is None:
			self.db.config.isDeleteOldLogFile = False
		if self.db.config.isIgnorLogWarning is None:
			self.db.config.isIgnorLogWarning = False
		if self.db.config.isStartOnlyOneProcess is None:
			self.db.config.isStartOnlyOneProcess = True
		if self.db.config.memoryUsinglimit is None:
			self.db.config.memoryUsinglimit = 50
		if self.db.config.isLocaldbSaving is None:
			self.db.config.isLocaldbSaving = False
		if self.db.config.isWritingLogFile is None:
			self.db.config.isWritingLogFile = True
		if self.db.config.logFileSizeLines is None:
			self.db.config.logFileSizeLines = 16384
	#end define

	def start_only_one_process(self):
		pid_file_path = self.pid_file_path
		if os.path.isfile(pid_file_path):
			file = open(pid_file_path, 'r')
			pid_str = file.read()
			file.close()
			try:
				pid = int(pid_str)
				process = psutil.Process(pid)
				full_process_name = " ".join(process.cmdline())
			except:
				full_process_name = ""
			if full_process_name.find(self.my_full_name) > -1:
				print("The process is already running")
				sys.exit(1)
		#end if
		self.write_pid()
	#end define

	def write_pid(self):
		pid = os.getpid()
		pid_str = str(pid)
		pid_file_path = self.pid_file_path
		with open(pid_file_path, 'w') as file:
			file.write(pid_str)
	#end define

	def self_test(self):
		process = psutil.Process(os.getpid())
		memory_using = b2mb(process.memory_info().rss)
		free_space_memory = b2mb(psutil.virtual_memory().available)
		thread_count = threading.active_count()
		self.free_space_memory = free_space_memory
		self.memory_using = memory_using
		self.thread_count = thread_count
		if memory_using > self.db.config.memoryUsinglimit:
			self.db.config.memoryUsinglimit += 50
			self.add_log(f"Memory using: {memory_using}Mb, free: {free_space_memory}Mb", WARNING)
	#end define

	def print_self_testing_result(self):
		thread_count_old = self.thread_count_old
		thread_count_new = self.thread_count
		memory_using = self.memory_using
		free_space_memory = self.free_space_memory
		self.add_log(color_text("{blue}Self testing informatinon:{endc}"))
		self.add_log(f"Threads: {thread_count_new} -> {thread_count_old}")
		self.add_log(f"Memory using: {memory_using}Mb, free: {free_space_memory}Mb")
	#end define

	def get_thread_name(self):
		return threading.current_thread().name
	#end define

	def get_my_full_name(self):
		'''return "test.py"'''
		my_path = self.get_my_path()
		my_full_name = get_full_name_from_path(my_path)
		if len(my_full_name) == 0:
			my_full_name = "empty"
		return my_full_name
	#end define

	def get_my_name(self):
		my_full_name = self.get_my_full_name()
		my_name = my_full_name[:my_full_name.rfind('.')]
		return my_name
	#end define

	def get_my_path(self):
		'''return "/some_dir/test.py"'''
		my_path = os.path.abspath(self.file)
		return my_path
	#end define

	def get_my_work_dir(self):
		if self.check_root_permission():
			program_files_dir = "/usr/local/bin"
		else:
			program_files_dir = os.getenv("XDG_DATA_HOME")
			if not program_files_dir:
				user_home_dir = os.getenv("HOME")
				if user_home_dir is None:
					raise Exception("HOME environment variable is not set")
				program_files_dir = os.path.join(user_home_dir, ".local", "share")
		my_work_dir = os.path.join(program_files_dir, self.my_name, "")
		return my_work_dir

	def get_my_temp_dir(self):
		my_temp_dir = os.path.join("/tmp", self.my_name, "")
		return my_temp_dir

	def get_lang(self):
		lang = os.getenv("LANG", "en")
		if "ru" in lang:
			lang = "ru"
		else:
			lang = "en"
		return lang
	#end define

	def check_root_permission(self):
		process = subprocess.run(["touch", "/checkpermission"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		if process.returncode == 0:
			subprocess.run(["rm", "/checkpermission"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			result = True
		else:
			result = False
		return result
	#end define

	def add_log(self, input_text: str, mode=INFO):
		input_text = f"{input_text}"
		time_text = date_time_library.datetime.utcnow().strftime("%d.%m.%Y, %H:%M:%S.%f")[:-3]
		time_text = "{0} (UTC)".format(time_text).ljust(32, ' ')

		# Pass if set log level
		if self.db.config.logLevel != DEBUG and mode == DEBUG:
			return
		elif self.db.config.isIgnorLogWarning and mode == WARNING:
			return

		# Set color mode
		if mode == INFO:
			color_start = bcolors.INFO + bcolors.BOLD
		elif mode == WARNING:
			color_start = bcolors.WARNING + bcolors.BOLD
		elif mode == ERROR:
			color_start = bcolors.ERROR + bcolors.BOLD
		elif mode == DEBUG:
			color_start = bcolors.DEBUG + bcolors.BOLD
		else:
			color_start = bcolors.UNDERLINE + bcolors.BOLD
		mode_text = "{0}{1}{2}".format(color_start, "[{0}]".format(mode).ljust(10, ' '), bcolors.ENDC)

		# Set color thread
		if mode == ERROR:
			color_start = bcolors.ERROR + bcolors.BOLD
		else:
			color_start = bcolors.OKGREEN + bcolors.BOLD
		thread_text = "{0}{1}{2}".format(color_start, "<{0}>".format(self.get_thread_name()).ljust(14, ' '), bcolors.ENDC)
		log_text = mode_text + time_text + thread_text + input_text

		# Queue for recording
		self.log_list.append(log_text)

		# Print log text
		print(log_text)
	#end define

	def write_log(self):
		log_file_name = self.log_file_name

		with open(log_file_name, 'a') as file:
			while len(self.log_list) > 0:
				log_text = self.log_list.pop(0)
				file.write(log_text + '\n')
			#end while
		#end with

		# Control log size
		if self.db.config.isLimitLogFile is False:
			return
		log_size = self.db.config.logFileSizeLines or 16384
		allline = self.count_lines(log_file_name)
		if allline > log_size + 256:
			delline = allline - log_size
			f = open(log_file_name).readlines()
			i = 0
			while i < delline:
				f.pop(0)
				i = i + 1
			with open(log_file_name, 'w') as F:
				F.writelines(f)
	#end define

	def count_lines(self, filename, chunk_size=1 << 13):
		if not os.path.isfile(filename):
			return 0
		with open(filename) as file:
			return sum(chunk.count('\n')
				for chunk in iter(lambda: file.read(chunk_size), ''))
	#end define

	def dict_to_base64_with_compress(self, item):
		string = json.dumps(item)
		original = string.encode("utf-8")
		compressed = zlib.compress(original)
		b64 = base64.b64encode(compressed)
		data = b64.decode("utf-8")
		return data
	#end define

	def base64_to_dict_with_decompress(self, item):
		data = item.encode("utf-8")
		b64 = base64.b64decode(data)
		decompress = zlib.decompress(b64)
		original = decompress.decode("utf-8")
		data = json.loads(original)
		return data
	#end define

	def exit(self, signum: int | None = None, frame: FrameType | None = None) -> None:
		self.working = False
		if os.path.isfile(self.pid_file_path):
			os.remove(self.pid_file_path)
		self.save()
		sys.exit(0)
	#end define

	def read_file(self, path: str) -> str:
		with open(path, 'rt') as file:
			text = file.read()
		return text
	#end define

	def write_file(self, path: str, text: str = "") -> None:
		with open(path, 'wt') as file:
			file.write(text)
	#end define

	def read_db(self, db_path: str) -> Dict:
		err = None
		for i in range(10):
			try:
				return self.read_db_process(db_path)
			except Exception as ex:
				err = ex
				time.sleep(0.1)
		raise Exception(f"read_db error: {err}")
	#end define

	def read_db_process(self, db_path: str) -> Dict:
		text = self.read_file(db_path)
		data = json.loads(text)
		return Dict(data)
	#end define

	def write_db(self, data: Mapping[str, Any]) -> None:
		db_path = os.path.realpath(self.db_path)
		text = json.dumps(data, indent=4)
		self.lock_file(db_path)
		try:
			self._write_file_atomic(db_path, text)
		finally:
			self.unlock_file(db_path)

	def _write_file_atomic(self, path: str, text: str = "") -> None:
		tmp_path = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
		try:
			with open(tmp_path, 'wt') as file:
				file.write(text)
				file.flush()
			os.replace(tmp_path, path)
		finally:
			if os.path.isfile(tmp_path):
				try:
					os.remove(tmp_path)
				except OSError:
					pass

	def lock_file(self, path: str) -> None:
		pid_path = path + ".lock"
		for i in range(300):
			if os.path.isfile(pid_path):
				time.sleep(0.01)
			else:
				self.write_file(pid_path)
				return
		raise Exception("lock_file error: time out.")
	#end define

	def unlock_file(self, path: str) -> None:
		pid_path = path + ".lock"
		try:
			os.remove(pid_path)
		except:
			print("Wow. You are faster than me")
	#end define

	def merge_three_dicts(self, local_data, file_data, old_file_data):
		if (id(local_data) == id(file_data) or
			id(file_data) == id(old_file_data) or
			id(local_data) == id(old_file_data)):
			print(local_data.keys())
			print(file_data.keys())
			raise Exception(f"merge_three_dicts error: merge the same object")
		#end if

		need_write_local_data = False
		if local_data == file_data and file_data == old_file_data:
			return need_write_local_data
		#end if

		dict_keys = list()
		dict_keys += [key for key in local_data if key not in dict_keys]
		dict_keys += [key for key in file_data if key not in dict_keys]
		for key in dict_keys:
			buff = self.merge_three_dicts_process(key, local_data, file_data, old_file_data)
			if buff is True:
				need_write_local_data = True
		return need_write_local_data
	#end define

	def merge_three_dicts_process(self, key, local_data, file_data, old_file_data):
		need_write_local_data = False
		tmp = self.mtdp_get_tmp(key, local_data, file_data, old_file_data)
		if tmp.local_item != tmp.file_item and tmp.file_item == tmp.old_file_item:
			# find local change
			self.mtdp_flc(key, local_data, file_data, old_file_data)
			need_write_local_data = True
		elif tmp.file_item != tmp.old_file_item:
			# find config file change
			self.mtdp_fcfc(key, local_data, file_data, old_file_data)
		return need_write_local_data
	#end define

	def mtdp_get_tmp(self, key, local_data, file_data, old_file_data):
		tmp = Dict()
		tmp.local_item = local_data.get(key)
		tmp.file_item = file_data.get(key)
		tmp.old_file_item = old_file_data.get(key)
		tmp.local_item_type = type(tmp.local_item)
		tmp.file_item_type = type(tmp.file_item)
		tmp.old_file_item_type = type(tmp.old_file_item)
		return tmp
	#end define

	def mtdp_flc(self, key, local_data, file_data, old_file_data):
		dict_types = [dict, Dict]
		tmp = self.mtdp_get_tmp(key, local_data, file_data, old_file_data)
		if tmp.local_item_type in dict_types and tmp.file_item_type in dict_types and tmp.old_file_item_type in dict_types:
			self.merge_three_dicts(tmp.local_item, tmp.file_item, tmp.old_file_item)
		elif tmp.local_item is None:
			#print(f"find local change {key} -> {tmp.local_item}")
			pass
		elif tmp.local_item_type not in dict_types:
			#print(f"find local change {key}: {tmp.old_file_item} -> {tmp.local_item}")
			pass
		elif tmp.local_item_type in dict_types:
			#print(f"find local change {key}: {tmp.old_file_item} -> {tmp.local_item}")
			pass
		else:
			raise Exception(f"mtdp_flc error: {key} -> {tmp.local_item_type}, {tmp.file_item_type}, {tmp.old_file_item_type}")
	#end define

	def mtdp_fcfc(self, key, local_data, file_data, old_file_data):
		dict_types = [dict, Dict]
		tmp = self.mtdp_get_tmp(key, local_data, file_data, old_file_data)
		if tmp.local_item_type in dict_types and tmp.file_item_type in dict_types and tmp.old_file_item_type in dict_types:
			self.merge_three_dicts(tmp.local_item, tmp.file_item, tmp.old_file_item)
		elif tmp.file_item is None:
			#print(f"find config file change {key} -> {tmp.file_item}")
			local_data.pop(key)
		elif tmp.file_item_type not in dict_types:
			#print(f"find config file change {key}: {tmp.old_file_item} -> {tmp.file_item}")
			local_data[key] = tmp.file_item
		elif tmp.file_item_type in dict_types:
			#print(f"find config file change {key}: {tmp.old_file_item} -> {tmp.file_item}")
			local_data[key] = Dict(tmp.file_item)
		else:
			raise Exception(f"mtdp_fcfc error: {key} -> {tmp.local_item_type}, {tmp.file_item_type}, {tmp.old_file_item_type}")
	#end define

	def save_db(self) -> None:
		file_data = self.read_db(self.db_path)
		need_write_local_data = self.merge_three_dicts(self.db, file_data, self.old_db)
		self.old_db = Dict(self.db)
		if need_write_local_data:
			self.write_db(self.db)
	#end define

	def save(self) -> None:
		self.save_db()
		self.write_log()
	#end define

	def load_db(self, db_path: str | None = None) -> bool:
		result = False
		if db_path is None:
			db_path = self.db_path
		if not os.path.isfile(db_path):
			self.write_db(self.db)
		try:
			file_data = self.read_db(db_path)
			self.db = Dict(file_data)
			self.old_db = Dict(file_data)
			self.set_default_config()
			result = True
		except Exception as err:
			self.add_log(f"load_db error: {err}", ERROR)
		return result
	#end define

	def get_settings(self, file_path: str) -> None:
		try:
			with open(file_path) as file:
				text = file.read()
			self.db = Dict(json.loads(text))
			self.save_db()
			print("get setting successful: " + file_path)
			self.exit()
		except Exception as err:
			self.add_log(f"get_settings error: {err}", WARNING)
	#end define

	def get_python3_path(self) -> str:
		python3_path = "/usr/bin/python3"
		if platform.system() == "OpenBSD":
			python3_path = "/usr/local/bin/python3"
		return python3_path
	#end define

	def fork_daemon(self) -> None:
		my_path = self.my_path
		python3_path = self.get_python3_path()
		cmd = " ".join([python3_path, my_path, "-ef", '&'])
		os.system(cmd)
		print("daemon start: " + my_path)
		self.exit()
	#end define

	def add_to_crone(self) -> None:
		python3_path = self.get_python3_path()
		cron_text = f"@reboot {python3_path} \"{self.my_path}\" -d\n"
		os.system("crontab -l > mycron")
		with open("mycron", 'a') as file:
			file.write(cron_text)
		os.system("crontab mycron && rm mycron")
		print("add to cron successful: " + cron_text)
		self.exit()
	#end define

	def try_function(self, func: Callback, args: Sequence[Any] | None = None) -> Any:
		result = None
		try:
			if args is None:
				result = func()
			else:
				result = func(*args)
		except Exception as err:
			self.add_log(f"{func.__name__} error: {err}", ERROR)
		return result
	#end define

	def start_thread(self, func: Callback, name: str | None = None, args: Sequence[Any] | None = None) -> None:
		if name is None:
			name = func.__name__
		if args is None:
			threading.Thread(target=func, name=name, daemon=True).start()
		else:
			threading.Thread(target=func, name=name, args=args, daemon=True).start()
		self.add_log("Thread {name} started".format(name=name), "debug")
	#end define

	def cycle(self, func: Callback, sec: float, args: Sequence[Any] | None) -> None:
		while self.working:
			self.try_function(func, args=args)
			time.sleep(sec)
	#end define

	def start_cycle(self, func: Callback, sec: float, args: Sequence[Any] | None = None, name: str | None = None) -> None:
		if name is None:
			name = func.__name__
		self.start_thread(self.cycle, name=name, args=(func, sec, args))
	#end define

	def init_translator(self, file_path: str | None = None) -> None:
		if file_path is None:
			file_path = self.db.translate_file_path
		assert file_path is not None
		with open(file_path, encoding="utf-8") as file:
			text = file.read()
		self.translate_dict = json.loads(text)
	#end define

	def translate(self, text: str) -> str:
		if self.translate_dict is None:
			return text
		lang = self.get_lang()
		text_list = text.split(' ')
		for item in text_list:
			sitem = self.translate_dict.get(item)
			if sitem is None:
				continue
			ritem = sitem.get(lang)
			if ritem is not None:
				text = text.replace(item, ritem)
		return text
	#end define
#end class

def get_hash_md5(file_name: str) -> str:
	blocksize = 65536
	hasher = hashlib.md5()
	with open(file_name, 'rb') as file:
		buf = file.read(blocksize)
		while len(buf) > 0:
			hasher.update(buf)
			buf = file.read(blocksize)
	return hasher.hexdigest()
#end define

def parse(text: str | None, search: str | None, search2: str | None = None) -> str | None:
	if search is None or text is None:
		return None
	if search not in text:
		return None
	text = text[text.find(search) + len(search):]
	if search2 is not None and search2 in text:
		text = text[:text.find(search2)]
	return text
#end define

def get_request(url: str) -> str:
	link = urlopen(url)
	data = link.read()
	text = data.decode("utf-8")
	return text
#end define

def b2mb(item: int | str) -> float:
	return round(int(item) / 1000 / 1000, 2)
#end define

def search_file_in_dir(path: str, file_name: str) -> str | None:
	result = None
	for entry in os.scandir(path):
		if entry.name.startswith('.'):
			continue
		if entry.is_dir():
			buff = search_file_in_dir(entry.path, file_name)
			if buff is not None:
				result = buff
				break
		elif entry.is_file():
			if entry.name == file_name:
				result = entry.path
				break
	return result
#end define

def search_dir_in_dir(path: str, dir_name: str) -> str | None:
	result = None
	for entry in os.scandir(path):
		if entry.name.startswith('.'):
			continue
		if entry.is_dir():
			if entry.name == dir_name:
				result = entry.path
				break
			buff = search_dir_in_dir(entry.path, dir_name)
			if buff is not None:
				result = buff
				break
	return result
#end define

def get_dir_from_path(path: str) -> str:
	return path[:path.rfind('/') + 1]
#end define

def get_full_name_from_path(path: str) -> str:
	return path[path.rfind('/') + 1:]
#end define

def print_table(arr: Sequence[Sequence[Any]]) -> None:
	buff = dict()
	for i in range(len(arr[0])):
		buff[i] = list()
		for item in arr:
			buff[i].append(len(str(item[i])))
	for item in arr:
		for i in range(len(arr[0])):
			index = max(buff[i]) + 2
			ptext = str(item[i]).ljust(index)
			if item == arr[0]:
				ptext = bcolors.blue_text(ptext)
				ptext = bcolors.bold_text(ptext)
			print(ptext, end='')
		print()
#end define

def get_timestamp() -> int:
	return int(time.time())
#end define

def color_text(text: str) -> str:
	for cname in bcolors.colors:
		item = '{' + cname + '}'
		if item in text:
			text = text.replace(item, bcolors.colors[cname])
	return text
#end define

def color_print(text: str) -> None:
	text = color_text(text)
	print(text)
#end define

def get_load_avg() -> list[float]:
	psys = platform.system()
	if psys in ["FreeBSD", "Darwin", "OpenBSD"]:
		loadavg = subprocess.check_output(["sysctl", "-n", "vm.loadavg"]).decode('utf-8')
		if psys != "OpenBSD":
			m = re.match(r"{ (\d+\.\d+) (\d+\.\d+) (\d+\.\d+).+", loadavg)
		else:
			m = re.match(r"(\d+\.\d+) (\d+\.\d+) (\d+\.\d+)", loadavg)
		if m:
			loadavg_arr = [m.group(1), m.group(2), m.group(3)]
		else:
			loadavg_arr = ["0.00", "0.00", "0.00"]
	else:
		file = open("/proc/loadavg")
		loadavg = file.read()
		file.close()
		loadavg_arr = loadavg.split(' ')

	return [float(item) for item in loadavg_arr[:3]]

def get_internet_interface_name() -> str:
	if platform.system() == "OpenBSD":
		cmd = "ifconfig egress"
		text = subprocess.getoutput(cmd)
		lines = text.split('\n')
		items = lines[0].split(' ')
		interface_name = items[0][:-1]
	else:
		cmd = "ip --json route"
		text = subprocess.getoutput(cmd)
		try:
			arr = json.loads(text)
			interface_name = arr[0]["dev"]
		except:
			lines = text.split('\n')
			items = lines[0].split(' ')
			buff = items.index("dev")
			interface_name = items[buff + 1]
	return interface_name
#end define

def thr_sleep() -> None:
	while True:
		time.sleep(10)
#end define

def timestamp2datetime(timestamp: int | float, format: str = "%d.%m.%Y %H:%M:%S") -> str:
	datetime = time.localtime(timestamp)
	result = time.strftime(format, datetime)
	return result
#end define

def timeago(timestamp: int | date_time_library.datetime | Literal[False] = False) -> str:
	"""
	Get a datetime object or a int() Epoch timestamp and return a
	pretty string like 'an hour ago', 'Yesterday', '3 months ago',
	'just now', etc
	"""
	now = date_time_library.datetime.now()
	diff = date_time_library.timedelta(0)
	if type(timestamp) is int:
		diff = now - date_time_library.datetime.fromtimestamp(timestamp)
	elif isinstance(timestamp, date_time_library.datetime):
		diff = now - timestamp
	elif not timestamp:
		diff = now - now
	second_diff = diff.seconds
	day_diff = diff.days

	if day_diff < 0:
		return ''

	if day_diff == 0:
		if second_diff < 10:
			return "just now"
		if second_diff < 60:
			return str(second_diff) + " seconds ago"
		if second_diff < 120:
			return "a minute ago"
		if second_diff < 3600:
			return str(second_diff // 60) + " minutes ago"
		if second_diff < 7200:
			return "an hour ago"
		if second_diff < 86400:
			return str(second_diff // 3600) + " hours ago"
	if day_diff < 31:
		return str(day_diff) + " days ago"
	if day_diff < 365:
		return str(day_diff // 30) + " months ago"
	return str(day_diff // 365) + " years ago"
#end define

def time2human(diff: int | float) -> str:
	dt = date_time_library.timedelta(seconds=diff)
	if dt.days < 0:
		return ''

	if dt.days == 0:
		if dt.seconds < 60:
			return str(dt.seconds) + " seconds"
		if dt.seconds < 3600:
			return str(dt.seconds // 60) + " minutes"
		if dt.seconds < 86400:
			return str(dt.seconds // 3600) + " hours"
	return str(dt.days) + " days"
#end define

def dec2hex(dec: int) -> str:
	h = hex(dec)[2:]
	if len(h) % 2 > 0:
		h = '0' + h
	return h
#end define

def hex2dec(h: str) -> int:
	return int(h, base=16)
#end define

def run_as_root(args: list[str]) -> int:
	psys = platform.system()
	if os.geteuid() != 0:
		if psys == "Linux":
			if shutil.which("sudo"):
				args = ["sudo", "-s"] + args
			else:
				print("Enter root password")
				args = ["su", "-c"] + [" ".join(args)]
		elif psys == "OpenBSD":
			args = ["doas"] + args
		else:
			raise Exception(f"run_as_root error: the system is not supported: {psys}")
	exit_code = subprocess.call(args)
	return exit_code
#end define

def get_username() -> str | None:
	user = os.getenv("USER")
	return user
#end define

def add2systemd(**kwargs):
	name = kwargs.get("name")
	start = kwargs.get("start")
	pre = kwargs.get("pre")
	post = kwargs.get("post", "/bin/echo service down")
	user = kwargs.get("user", "root")
	group = kwargs.get("group", user)
	workdir = kwargs.get("workdir")
	force = kwargs.get("force")
	pversion = platform.version()
	psys = platform.system()
	path = "/etc/systemd/system/{name}.service".format(name=name)

	if psys == "OpenBSD":
		path = "/etc/rc.d/{name}".format(name=name)
	if name is None or start is None:
		raise Exception("Bad args. Need 'name' and 'start'.")
	if os.path.isfile(path):
		if force == True:
			print("Unit exist, force rewrite")
		else:
			print("Unit exist.")
			return
	#end if

	text = f"""
[Unit]
Description = {name} service. Created by https://github.com/igroman787/mypylib.
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

	file = open(path, 'wt')
	file.write(text)
	file.close()

	# Изменить права
	args = ["chmod", "664", path]
	subprocess.run(args)

	# Разрешить запуск
	args = ["chmod", "+x", path]
	subprocess.run(args)

	if psys != "OpenBSD":
		# Перезапустить systemd
		args = ["systemctl", "daemon-reload"]
		subprocess.run(args)
	#end if

	# Включить автозапуск
	if psys == "OpenBSD":
		args = ["rcctl", "enable", name]
	else:
		args = ["systemctl", "enable", name]
	subprocess.run(args)
#end define

def ip2int(addr: str) -> int:
	return struct.unpack("!i", socket.inet_aton(addr))[0]
#end define

def int2ip(dec: int) -> str:
	return socket.inet_ntoa(struct.pack("!i", dec))
#end define

def get_service_status(name: str) -> bool:
	status = False
	psys = platform.system()
	if psys == "OpenBSD":
		result = os.system(f"rcctl check {name}")
	else:
		result = os.system(f"systemctl is-active --quiet {name}")
	if result == 0:
		status = True
	return status
#end define

def get_service_uptime(name: str) -> int | None:
	property = "ExecMainStartTimestampMonotonic"
	args = ["systemctl", "show", name, "--property=" + property]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	start_timestamp_monotonic = parse(output, f"{property}=", '\n') or 0
	start_timestamp_monotonic = int(start_timestamp_monotonic) / 10 ** 6
	boot_timestamp = psutil.boot_time()
	time_now = time.time()
	start_timestamp = boot_timestamp + start_timestamp_monotonic
	uptime = int(time_now - start_timestamp)
	return uptime
#end define

def get_service_pid(name: str) -> int | None:
	property = "MainPID"
	args = ["systemctl", "show", name, "--property=" + property]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	pid_text = parse(output, f"{property}=", '\n')
	if pid_text is None:
		return None
	pid = int(pid_text)
	return pid
#end define

def get_git_hash(git_path: str, short: bool = False) -> str | None:
	args = ["git", "rev-parse", "HEAD"]
	if short is True:
		args.insert(2, '--short')
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=git_path,
							timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	buff = output.split('\n')
	return buff[0]
#end define

def get_git_url(git_path: str) -> str | None:
	args = ["git", "remote", "-v"]
	output = ""
	try:
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
								cwd=git_path, timeout=3)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
	except Exception as ex:
		err = str(ex)
	if len(err) > 0:
		return None
	lines = output.split('\n')
	url = None
	for line in lines:
		if "origin" in line:
			buff = line.split()
			url = buff[1]
	#end if
	return url
#end define

def get_git_author_and_repo(git_path: str) -> tuple[str | None, str | None]:
	author = None
	repo = None
	url = get_git_url(git_path)
	if url is not None:
		buff = url.split('/')
		if len(buff) == 5:
			author = buff[3]
			repo = buff[4]
			repo = repo.split('.')
			repo = repo[0]
	return author, repo
#end define

def get_git_last_remote_commit(git_path: str, branch: str = "master") -> str | None:
	author, repo = get_git_author_and_repo(git_path)
	if author is None or repo is None:
		return
	url = f"https://api.github.com/repos/{author}/{repo}/branches/{branch}"
	sha = None
	try:
		text = get_request(url)
		data = json.loads(text)
		sha = data["commit"]["sha"]
	except URLError:
		pass
	return sha
#end define

def get_git_branch(git_path: str) -> str | None:
	args = ["git", "branch", "-v"]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=git_path,
							timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return None
	lines = output.split('\n')
	branch = None
	for line in lines:
		if "*" in line:
			buff = line.split()
			branch = buff[1]
	#end if
	return branch
#end define

def check_git_update(git_path: str) -> bool | None:
	branch = get_git_branch(git_path)
	if branch is None:
		return None
	new_hash = get_git_last_remote_commit(git_path, branch)
	old_hash = get_git_hash(git_path)
	result = False
	if old_hash != new_hash:
		result = True
	if old_hash is None or new_hash is None:
		result = None
	return result
#end define

def read_config_from_file(config_path: str) -> Dict:
	file = open(config_path, 'rt')
	text = file.read()
	file.close()
	config = Dict(json.loads(text))
	return config
#end define


def write_config_to_file(config_path: str, data: Mapping[str, Any]) -> None:
	text = json.dumps(data, indent=4)
	file = open(config_path, 'wt')
	file.write(text)
	file.close()
#end define
