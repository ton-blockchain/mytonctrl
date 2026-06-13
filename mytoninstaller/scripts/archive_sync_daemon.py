#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import shutil
import subprocess
import time

import requests

from mypylib.mypylib import MyPyClass, Dict, parse, get_service_status
from mytoninstaller.mytoninstaller import Refresh
from mytoninstaller.config import GetConfig, SetConfig
from mytoninstaller.utils import start_service, stop_service, is_testnet
from mytoncore.validator_console import ValidatorConsole
from mytoninstaller.archive_blocks import download_bag


IMPORT_DIR = "/var/ton-work/db/import/"
DOWNLOADS_PATH = "/var/ton-work/ts-downloads/"
BAGS_PER_RESTART = 100  # рестарт ноды каждые N bags


def get_service_user(service, default):
	# Читать User= из systemd unit файла сервиса
	try:
		result = subprocess.run(
			["systemctl", "cat", service],
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3
		)
		output = result.stdout.decode("utf-8")
		user = parse(output, "User = ", '\n') or parse(output, "User=", '\n')
		if user:
			return user.strip()
	except Exception:
		pass
	return default
#end define


def get_mtc_user():
	return get_service_user("mytoncore.service", "ubuntu")
#end define


def get_validator_user():
	return get_service_user("validator.service", "validator")
#end define


def setup_validator_console(local):
	# Настройка validatorConsole из mconfig — точно как в mytoncore.py::Refresh()
	mconfig_path = local.buffer.mconfig_path
	mconfig = GetConfig(path=mconfig_path)
	vc_cfg = mconfig.get("validatorConsole")
	if vc_cfg is None:
		return None
	vc = ValidatorConsole(local)
	vc.appPath = vc_cfg["appPath"]
	vc.privKeyPath = vc_cfg["privKeyPath"]
	vc.pubKeyPath = vc_cfg["pubKeyPath"]
	vc.addr = vc_cfg["addr"]
	return vc
#end define


def get_block_seqno(buff):
	# Парсинг seqno из строки блока вида (-1,8000000000000000,seqno):rootHash:fileHash
	# Логика идентична MyTonCore.GVS_GetItemFromBuff
	buff2 = buff.split(':')[0]
	buff2 = buff2.replace(' ', '').replace('(', '').replace(')', '')
	return int(buff2.split(',')[2])
#end define


def is_synced(local, vc):
	# VC недоступна — нода ещё стартует, не считаем синхронизированной
	if vc is None:
		return False
	try:
		result = vc.Run("getstats")
		unixtime = int(parse(result, "unixtime", '\n'))
		masterchainblocktime = int(parse(result, "masterchainblocktime", '\n'))
		masterchainblock = get_block_seqno(parse(result, "masterchainblock", '\n'))
		shardclientmasterchainseqno = int(parse(result, "shardclientmasterchainseqno", '\n'))
		masterchain_out_of_sync = unixtime - masterchainblocktime
		shardchain_out_of_sync = masterchainblock - shardclientmasterchainseqno
		out_of_sync = max(masterchain_out_of_sync, shardchain_out_of_sync)
		return out_of_sync < 20
	except Exception as ex:
		local.add_log(f"is_synced error: {ex}", "debug")
		return False
#end define


def get_node_seqno(local, vc):
	# Получить текущий seqno ноды из VC
	if vc is None:
		return None
	try:
		result = vc.Run("getstats")
		return int(parse(result, "shardclientmasterchainseqno", '\n'))
	except Exception as ex:
		local.add_log(f"get_node_seqno error: {ex}", "warning")
		return None
#end define


def get_import_max_seqno():
	# Максимальный seqno из файлов уже лежащих в import/ (формат X.SEQNO.Y)
	max_seqno = 0
	if not os.path.isdir(IMPORT_DIR):
		return max_seqno
	for fname in os.listdir(IMPORT_DIR):
		try:
			seqno = int(fname.split('.')[1])
			if seqno > max_seqno:
				max_seqno = seqno
		except Exception:
			pass
	return max_seqno
#end define


def fetch_bags(local):
	# Загрузить список bags из индекса (5 попыток как в settings.py)
	url = 'https://archival-dump.ton.org/index/mainnet.json'
	if is_testnet(local):
		url = 'https://archival-dump.ton.org/index/testnet.json'
	#end if

	for _ in range(5):
		try:
			return requests.get(url, timeout=3).json().get('blocks', [])
		except Exception as ex:
			local.add_log(f"fetch_bags: failed: {ex}. Retrying", "error")
			time.sleep(10)
	#end for

	local.add_log("fetch_bags: failed after 5 attempts", "error")
	return None
#end define


def find_start_index(bags, start_seqno):
	# Найти индекс первого bag где bag['from'] > start_seqno
	for i, bag in enumerate(bags):
		if bag['from'] > start_seqno:
			return i
	return None
#end define


def keep_import_gc_active(local):
	# gc_import выключает себя когда import/ пуст — включаем обратно каждую итерацию
	# чтобы файлы которые нода уже импортировала своевременно чистились
	try:
		mconfig = GetConfig(path=local.buffer.mconfig_path)
		if not mconfig.get("importGc", False):
			mconfig.importGc = True
			SetConfig(path=local.buffer.mconfig_path, data=mconfig)
	except Exception as ex:
		local.add_log(f"keep_import_gc_active error: {ex}", "warning")
#end define


def check_disk_space():
	usage = shutil.disk_usage("/var")
	return usage.free > 5 * 1024 ** 3
#end define


def download_and_move(local, bag):
	bag_id = bag['bag']
	os.makedirs(DOWNLOADS_PATH, exist_ok=True)
	subprocess.run(["chmod", "o+wx", DOWNLOADS_PATH])

	local.add_log(f"Downloading bag {bag_id} blocks {bag['from']}-{bag['to']}", "info")
	if not download_bag(local, bag_id, DOWNLOADS_PATH):
		local.add_log(f"Failed to download bag {bag_id}", "error")
		return False
	#end if

	# mv -n bag/*/*/*  import/
	os.makedirs(IMPORT_DIR, exist_ok=True)
	bag_path = f"{DOWNLOADS_PATH}/{bag_id}"
	if not os.path.isdir(bag_path):
		local.add_log(f"Bag {bag_id} directory missing after download, skipping", "warning")
		return False
	#end if

	subprocess.run(f'mv -n {bag_path}/*/*/* {IMPORT_DIR}', shell=True)

	# chown как в FirstNodeSettings — файлы скачаны от root, нода запущена от vuser
	vuser = get_validator_user()
	subprocess.run(["chown", "-R", f"{vuser}:{vuser}", IMPORT_DIR])

	# Удалить скачанный bag
	subprocess.run(["rm", "-rf", bag_path])

	local.add_log(f"Bag {bag_id} done, blocks {bag['from']}-{bag['to']} moved to import/", "info")
	return True
#end define


def init_ton_storage(local):
	# Читаем ton_storage.api_port из mconfig, запускаем сервис один раз на всё время демона
	mconfig = GetConfig(path=local.buffer.mconfig_path)
	ts_cfg = mconfig.get("ton_storage")
	if ts_cfg is None:
		local.add_log("ton_storage not configured in mconfig, exiting", "error")
		return False
	#end if
	local.buffer.ton_storage = Dict()
	local.buffer.ton_storage.api_port = ts_cfg["api_port"]
	if not get_service_status("ton_storage"):
		start_service(local, "ton_storage", sleep=5)
	#end if
	return True
#end define


def resolve_start_index(local, vc, bags, last_bag_to):
	# При рефреше индекса — продолжаем точно с последнего скачанного bag
	# При первом запуске — откатываемся назад с запасом чтобы не пропустить блоки
	if last_bag_to is not None:
		start_seqno = last_bag_to
	else:
		node_seqno = get_node_seqno(local, vc) or 0
		import_seqno = get_import_max_seqno()
		start_seqno = max(0, max(node_seqno, import_seqno) - 30000)
	#end if
	local.add_log(f"Resolving start index: start_seqno={start_seqno}, last_bag_to={last_bag_to}", "info")
	return find_start_index(bags, start_seqno)
#end define


def main():
	local = MyPyClass(__file__)
	local.db.config.isStartOnlyOneProcess = True
	local.run()

	# Демон запускается от root, но local.buffer.user должен быть реальным пользователем mytoncore
	# Читаем User= из mytoncore.service — тогда Refresh() построит правильный mconfig_path
	local.buffer.user = get_mtc_user()
	Refresh(local)

	if not init_ton_storage(local):
		local.exit()
		return
	#end if

	bags = None         # список bags из индекса
	bag_index = None    # текущая позиция в списке
	last_bag_to = None  # bag['to'] последнего успешно скачанного bag
	bags_downloaded = 0 # счётчик скачанных bags с последнего рестарта ноды

	while local.working:
		try:
			vc = setup_validator_console(local)
			keep_import_gc_active(local)

			if is_synced(local, vc):
				local.add_log("Node is synced, disabling archive_sync", "info")
				subprocess.run(["systemctl", "disable", "--now", "archive_sync"])
				break
			#end if

			if bags is None:
				bags = fetch_bags(local)
				if bags is None:
					time.sleep(60)
					continue
				#end if
				bag_index = resolve_start_index(local, vc, bags, last_bag_to)
				if bag_index is None:
					local.add_log("No new bags available, sleeping 3600s", "info")
					bags = None
					time.sleep(3600)
					continue
				#end if
			#end if

			if not check_disk_space():
				local.add_log("Not enough disk space on /var (need > 5GB), sleeping 3600s", "warning")
				time.sleep(3600)
				continue
			#end if

			bag = bags[bag_index]
			ok = download_and_move(local, bag)
			if ok:
				last_bag_to = bag['to']
				bag_index += 1
				bags_downloaded += 1
				if bag_index >= len(bags):
					local.add_log("All bags downloaded, restarting validator to pick up import/", "info")
					start_service(local, "validator")
					bags_downloaded = 0
					bags = None
					time.sleep(3600)
				elif bags_downloaded % BAGS_PER_RESTART == 0:
					local.add_log(f"Downloaded {bags_downloaded} bags, restarting validator to pick up import/", "info")
					start_service(local, "validator")
				#end if
			else:
				local.add_log("download_and_move failed, will retry", "warning")
				time.sleep(30)
			#end if

		except Exception as ex:
			local.add_log(f"archive_sync error: {ex}", "error")
			time.sleep(30)
	#end while

	stop_service(local, "ton_storage")
#end define


if __name__ == '__main__':
	main()
