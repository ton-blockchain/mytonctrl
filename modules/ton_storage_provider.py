#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import json
import psutil
import requests

from mypylib.mypylib import bcolors, color_print, Dict
from modules.module import MtcModule
from mytonctrl.utils import GetColorInt, GetColorStatus
from mytoninstaller.config import GetConfig

class TonStorageProviderModule(MtcModule):
	description = ''
	default_value = False

	def activate_ton_storage_provider(self, args):
		wallet_name = "provider_wallet_001"
		wallet = self.ton.GetLocalWallet(wallet_name)
		account = self.ton.GetAccount(wallet.addrB64)
		if account.status == "active":
			color_print("activate_ton_storage_provider - {green}Already activated{endc}")
			#return
		self.ton.ActivateWallet(wallet)
		destination = "0:7777777777777777777777777777777777777777777777777777777777777777"
		#ton_storage = self.ton.GetSettings("ton_storage")
		mytoncore_db = self.ton.local.db
		comment = f"tsp-{mytoncore_db.ton_storage.provider.pubkey}"
		flags = ["-n", "-C", comment]
		self.ton.MoveCoins(wallet, destination, 0.01, flags=flags)
		color_print("activate_ton_storage_provider - {green}OK{endc}")
	#end define

	def get_provider_api_data(self, mytoncore_db):
		local_api_url = f"http://127.0.0.1:{mytoncore_db.ton_storage.api_port}/api/v1/list"
		resp = requests.get(local_api_url, timeout=3)
		if resp.status_code != 200:
			raise Exception(f"Failed to get provider api data from {local_api_url}")
		return Dict(resp.json())
	#end define

	def get_provider_config(self, provider_config_parh):
		ton_storage_provider_config = GetConfig(path=provider_config_parh)
		return ton_storage_provider_config
	#end define

	def get_provider_used_space(self, provider_api_data):
		used_space = 0
		used_space_mb = 0
		for bag in provider_api_data.bags:
			used_space += bag.size
		if used_space != 0:
			used_space_mb = int(used_space / 1024 / 1024)
		return used_space_mb
	#end define

	def print_status(self):
		mytoncore_db = self.ton.local.db
		provider_config_parh = mytoncore_db.ton_storage.provider.config_path
		if mytoncore_db.provider_wallet_name == None:
			raise Exception("TonStorageProviderModule.print_status error: mytoncore_db.provider_wallet_name is None")
		#end if

		provider_wallet = self.ton.GetLocalWallet(mytoncore_db.provider_wallet_name)
		if provider_wallet == None:
			raise Exception("TonStorageProviderModule.print_status error: provider_wallet is None")
		#end if

		provider_account = self.ton.GetAccount(provider_wallet.addrB64)
		provider_api_data = self.get_provider_api_data(mytoncore_db)
		provider_bags_number = len(provider_api_data.bags)
		provider_config = self.get_provider_config(provider_config_parh)
		provider_space = Dict()
		provider_space.total = provider_config.Storages[0].SpaceToProvideMegabytes
		provider_space.used = self.get_provider_used_space(provider_api_data)
		provider_space.free = provider_space.total - provider_space.used
		provider_space.percent = round(provider_space.used / provider_space.total, 1)
		drive_space = psutil.disk_usage(provider_config_parh)
		drive_space_used = int(drive_space.used / 1024 / 1024 / 1024)
		drive_space_total = int(drive_space.total / 1024 / 1024 / 1024)

		provider_wallet_addr = bcolors.yellow_text(provider_wallet.addrB64)
		provider_pubkey = bcolors.yellow_text(mytoncore_db.ton_storage.provider.pubkey)
		provider_wallet_balance = bcolors.green_text(provider_account.balance)
		provider_bags_number = bcolors.green_text(provider_bags_number)
		provider_space_used = bcolors.green_text(provider_space.used)
		provider_space_total = bcolors.yellow_text(provider_space.total)
		provider_space_percent = GetColorInt(provider_space.percent, 90, logic="less", ending="%")
		drive_space_used = bcolors.green_text(drive_space_used)
		drive_space_total = bcolors.yellow_text(drive_space_total)
		drive_space_percent = GetColorInt(drive_space.percent, 90, logic="less", ending="%")

		provider_wallet_addr_text = self.local.translate("provider_wallet_addr").format(provider_wallet_addr)
		provider_pubkey_text = self.local.translate("provider_pubkey").format(provider_pubkey)
		provider_wallet_balance_text = self.local.translate("provider_wallet_balance").format(provider_wallet_balance)
		provider_bags_number_text = self.local.translate("provider_bags_number").format(provider_bags_number)
		provider_space_text = self.local.translate("provider_space").format(provider_space_used, provider_space_total, provider_space_percent)
		drive_space_text = self.local.translate("drive_space").format(drive_space_used, drive_space_total, drive_space_percent)

		color_print(self.local.translate("ton_storage_provider_status_head"))
		print(provider_wallet_addr_text)
		print(provider_pubkey_text)
		print(provider_wallet_balance_text)
		print(provider_bags_number_text)
		print(provider_space_text)
		print(drive_space_text)
		print()
	#end define

	def add_console_commands(self, console):
		console.AddItem("activate_ton_storage_provider", self.activate_ton_storage_provider, self.local.translate("activate_ton_storage_provider_cmd"))
	#end define