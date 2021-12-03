#!/usr/bin/env python3
# -*- coding: utf_8 -*-l

from sys import path
path.append("/usr/src/mytonctrl/")
from mytoncore import *

Local = MyPyClass(__file__)
ton = MyTonCore()


def Init():
	wallets = list()
	Local.buffer["wallets"] = wallets
	walletsNameList = ton.GetWalletsNameList()
	
	# Create tests wallet
	testsWalletName = "tests_hwallet"
	testsWallet = ton.CreateHighWallet(testsWalletName)

	# Check tests wallet balance
	account = ton.GetAccount(testsWallet.addr)
	local.AddLog("wallet: {addr}, status: {status}, balance: {balance}".format(addr=testsWallet.addr, status=account.status, balance=account.balance))
	if account.balance == 0:
		raise Exception(testsWallet.name + " wallet balance is empty.")
	if account.status == "uninit":
		ton.SendFile(testsWallet.bocFilePath, testsWallet)

	# Create wallets
	for i in range(load):
		walletName = testsWalletName
		if walletName not in walletsNameList:
			wallet = ton.CreateHighWallet(walletName, i)
		else:
			wallet = ton.GetLocalWallet(walletName, "hw", i)
		wallets.append(wallet)
	#end for

	# Fill up wallets
	buff_wallet = None
	buff_seqno = None
	destList = list()
	for wallet in wallets:
		wallet.account = ton.GetAccount(wallet.addr)
		need = 20 - wallet.account.balance
		if need > 10:
			destList.append([wallet.addr_init, need])
		elif need < -10:
			need = need * -1
			buff_wallet = wallet
			buff_wallet.oldseqno = ton.GetSeqno(wallet)
			ton.MoveGramsFromHW(wallet, [[testsWallet.addr, need]], wait=False)
			Local.AddLog(testsWallet.name + " <<< " + str(wallet.subwallet))
	if buff_wallet:
		ton.WaitTransaction(buff_wallet)
	#end for

	# Move grams from highload wallet
	ton.MoveGramsFromHW(testsWallet, destList)

	# Activate wallets
	for wallet in wallets:
		if wallet.account.status == "uninit":
			wallet.oldseqno = ton.GetSeqno(wallet)
			ton.SendFile(wallet.bocFilePath)
		Local.AddLog(str(wallet.subwallet) + " - OK")
	ton.WaitTransaction(wallets[-1])
#end define

def Work():
	wallets = Local.buffer["wallets"]
	destList = list()
	for i in range(load):
		destList.append([wallets[i].addr, 0.1])
	for wallet in wallets:
		wallet.oldseqno = ton.GetSeqno(wallet)
		ton.MoveGramsFromHW(wallet, destList, wait=False)
		Local.AddLog(str(wallet.subwallet) + " " + wallet.addr + " >>> ")
	ton.WaitTransaction(wallets[-1])
#end define

def General():
	Init()
	while True:
		time.sleep(1)
		Work()
		Local.AddLog("Work - OK")
	#end while
#end define



###
### Start test
###
Local = MyPyClass(__file__)
Local.db["config"]["logLevel"] = "info"
Local.Run()

ton = MyTonCore()
local.db["config"]["logLevel"] = "info"
load = 10

Local.StartCycle(General, sec=1)
while True:
	time.sleep(60)
	hour_str = time.strftime("%H")
	hour = int(hour_str)
	load = hour * 4
#end while
