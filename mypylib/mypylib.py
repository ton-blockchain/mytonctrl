from __future__ import annotations

import logging
import os
import shutil
import sys
import time
import json
import fcntl
import signal
import psutil
import struct
import socket
import platform
import threading
import traceback
import subprocess
from contextlib import contextmanager
from types import FrameType
from typing import Any, Callable, Mapping, Sequence

from mypylib.colors import bcolors
from mypylib.logger import (
    ERROR,
    INFO,
    get_logger,
    level_for_mode,
)

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
			if isinstance(value, list):
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


class MyPyClass:
	def __init__(self, file: str) -> None:
		self.working: bool = True
		self.file: str = file
		self.db: Dict = Dict()
		self.db.config = Dict()

		self.old_db = Dict()

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

		self.logger: logging.Logger = get_logger(self.my_name)

		self.load_db()
		self.set_default_config()

		# Remove old log file
		if self.db.config.isDeleteOldLogFile and os.path.isfile(self.log_file_name):
			os.remove(self.log_file_name)

		# Catch the shutdown signal
		signal.signal(signal.SIGINT, self.exit)
		signal.signal(signal.SIGTERM, self.exit)

	def run(self) -> None:
		# Start only one process (exit if process exist)
		if self.db.config.isStartOnlyOneProcess:
			self.start_only_one_process()

		# Start other threads
		if self.db.config.isLocaldbSaving is True:
			self.start_cycle(self.save_db, sec=1)

		# Logging the start of the program
		self.add_log(f"Start program `{self.my_path}`", "debug")

	def set_default_config(self):
		if self.db.config.logLevel is None:
			self.db.config.logLevel = INFO  # info || debug
		if self.db.config.isLimitLogFile is None:
			self.db.config.isLimitLogFile = True
		if self.db.config.isDeleteOldLogFile is None:
			self.db.config.isDeleteOldLogFile = False
		if self.db.config.isStartOnlyOneProcess is None:
			self.db.config.isStartOnlyOneProcess = True
		if self.db.config.isLocaldbSaving is None:
			self.db.config.isLocaldbSaving = False
		if self.db.config.isWritingLogFile is None:
			self.db.config.isWritingLogFile = True
		if self.db.config.logFileSizeLines is None:
			self.db.config.logFileSizeLines = 16384

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
			except Exception:
				full_process_name = ""
			if full_process_name.find(self.my_full_name) > -1:
				print("The process is already running")
				sys.exit(1)
		self.write_pid()

	def write_pid(self):
		pid = os.getpid()
		pid_str = str(pid)
		pid_file_path = self.pid_file_path
		with open(pid_file_path, 'w') as file:
			file.write(pid_str)

	def get_my_full_name(self):
		'''return "test.py"'''
		my_path = self.get_my_path()
		my_full_name = my_path[my_path.rfind('/') + 1:]
		if len(my_full_name) == 0:
			my_full_name = "empty"
		return my_full_name

	def get_my_name(self):
		my_full_name = self.get_my_full_name()
		my_name = my_full_name[:my_full_name.rfind('.')]
		return my_name

	def get_my_path(self):
		'''return "/some_dir/test.py"'''
		my_path = os.path.abspath(self.file)
		return my_path

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

	def check_root_permission(self):
		process = subprocess.run(["touch", "/checkpermission"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		if process.returncode == 0:
			subprocess.run(["rm", "/checkpermission"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			result = True
		else:
			result = False
		return result

	def add_log(self, input_text: str, mode: str = INFO) -> None:
		self.logger.log(level_for_mode(mode), str(input_text))

	def exit(self, signum: int | None = None, frame: FrameType | None = None) -> None:
		self.working = False
		if os.path.isfile(self.pid_file_path):
			os.remove(self.pid_file_path)
		self.save()
		sys.exit(0)

	def read_file(self, path: str) -> str:
		with open(path, 'rt') as file:
			text = file.read()
		return text

	def write_file(self, path: str, text: str = "") -> None:
		with open(path, 'wt') as file:
			file.write(text)

	def read_db(self, db_path: str) -> Dict:
		err = None
		for i in range(10):
			try:
				return self.read_db_process(db_path)
			except Exception as ex:
				err = ex
				time.sleep(0.1)
		raise Exception(f"read_db error: {err}")

	def read_db_process(self, db_path: str) -> Dict:
		text = self.read_file(db_path)
		data = json.loads(text)
		return Dict(data)

	def write_db(self, data: Mapping[str, Any]) -> None:
		db_path = os.path.realpath(self.db_path)
		text = json.dumps(data, indent=4)
		with self.lock_file(db_path):
			self._write_file_atomic(db_path, text)

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

	@contextmanager
	def lock_file(self, path: str, timeout: float = 3.0):
		lock_path = path + ".lock"
		fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
		try:
			deadline = time.monotonic() + timeout
			while True:
				try:
					fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
					break
				except BlockingIOError:
					if time.monotonic() >= deadline:
						raise Exception(f"lock_file error: time out: {lock_path}")
					time.sleep(0.01)
			yield
		finally:
			os.close(fd)

	def merge_three_dicts(self, local_data, file_data, old_file_data):
		if (id(local_data) == id(file_data) or
			id(file_data) == id(old_file_data) or
			id(local_data) == id(old_file_data)):
			print(local_data.keys())
			print(file_data.keys())
			raise Exception("merge_three_dicts error: merge the same object")

		need_write_local_data = False
		if local_data == file_data and file_data == old_file_data:
			return need_write_local_data

		dict_keys = list()
		dict_keys += [key for key in local_data if key not in dict_keys]
		dict_keys += [key for key in file_data if key not in dict_keys]
		for key in dict_keys:
			buff = self.merge_three_dicts_process(key, local_data, file_data, old_file_data)
			if buff is True:
				need_write_local_data = True
		return need_write_local_data

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

	def mtdp_get_tmp(self, key, local_data, file_data, old_file_data):
		tmp = Dict()
		tmp.local_item = local_data.get(key)
		tmp.file_item = file_data.get(key)
		tmp.old_file_item = old_file_data.get(key)
		tmp.local_item_type = type(tmp.local_item)
		tmp.file_item_type = type(tmp.file_item)
		tmp.old_file_item_type = type(tmp.old_file_item)
		return tmp

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

	def save_db(self) -> None:
		file_data = self.read_db(self.db_path)
		need_write_local_data = self.merge_three_dicts(self.db, file_data, self.old_db)
		self.old_db = Dict(self.db)
		if need_write_local_data:
			self.write_db(self.db)

	def save(self) -> None:
		self.save_db()

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

	def try_function(self, func: Callback, args: Sequence[Any] | None = None, log_traceback: bool = False) -> Any:
		result = None
		try:
			if args is None:
				result = func()
			else:
				result = func(*args)
		except Exception as err:
			self.add_log(f"{func.__name__} error: {err}", ERROR)
			if log_traceback:
				self.add_log(traceback.format_exc(), ERROR)
		return result

	def start_thread(self, func: Callback, name: str | None = None, args: Sequence[Any] | None = None) -> None:
		if name is None:
			name = func.__name__
		if args is None:
			args = ()
		threading.Thread(target=func, name=name, args=args, daemon=True).start()
		self.add_log("Thread {name} started".format(name=name), "debug")

	def cycle(self, func: Callback, sec: float, args: Sequence[Any] | None) -> None:
		while self.working:
			self.try_function(func, args=args, log_traceback=True)
			time.sleep(sec)

	def start_cycle(self, func: Callback, sec: float, args: Sequence[Any] | None = None, name: str | None = None) -> None:
		if name is None:
			name = func.__name__
		self.start_thread(self.cycle, name=name, args=(func, sec, args))

	def init_translator(self, file_path: str | None = None) -> None:
		if file_path is None:
			file_path = self.db.translate_file_path
		assert file_path is not None
		with open(file_path, encoding="utf-8") as file:
			text = file.read()
		self.translate_dict = json.loads(text)

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

def parse(text: str | None, search: str | None, search2: str | None = None) -> str | None:
	if search is None or text is None:
		return None
	if search not in text:
		return None
	text = text[text.find(search) + len(search):]
	if search2 is not None and search2 in text:
		text = text[:text.find(search2)]
	return text

def parse_int_forced(text: str | None, search: str, search2: str | None = None) -> int:
	value = parse(text, search, search2)
	if value is None:
		raise ValueError(f"{search!r} not found in validator console output")
	return int(value)

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

def get_timestamp() -> int:
	return int(time.time())

def color_text(text: str) -> str:
	for cname in bcolors.colors:
		item = '{' + cname + '}'
		if item in text:
			text = text.replace(item, bcolors.colors[cname])
	return text

def color_print(text: str) -> None:
	text = color_text(text)
	print(text)

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

def ip2int(addr: str) -> int:
	return struct.unpack("!i", socket.inet_aton(addr))[0]

def int2ip(dec: int) -> str:
	return socket.inet_ntoa(struct.pack("!i", dec))
