#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import sys
import time
sys.path.append("/usr/src/mytonctrl/")
from mypylib.mypylib import bcolors, Sleep
from mytoncore import MyTonCore
from mypylib.mypylib import MyPyClass

ton = MyTonCore()
local = MyPyClass(__file__)

def TestMoveCoins(wallet, dest, coins, **kwargs):
	start = time.time()
	ton.MoveCoins(wallet, dest, coins, timeout=600, **kwargs)
	end = time.time()
	diff = int(end - start)
	local.AddLog(f"{wallet.addrB64} -> {dest}, diff: {diff}")
#end define

def Init():
	vnum = local.buffer.get("vnum")
	wallet1 = ton.CreateWallet(f"test{vnum+1}", workchain=0, version="v1")
	wallet2 = ton.CreateWallet(f"test{vnum+2}", workchain=0, version="v2")
	wallet3 = ton.CreateWallet(f"test{vnum+3}", workchain=0, version="v3")
	local.buffer["vnum"] += 3
	ton.ActivateWallet(wallet1)
	ton.ActivateWallet(wallet2)
	ton.ActivateWallet(wallet3)
	return wallet1, wallet2, wallet3
#end define

def Test(wallet1, wallet2, wallet3):
	TestMoveCoins(wallet1, wallet1.addrB64, 1.01)
	TestMoveCoins(wallet2, wallet2.addrB64, 1.02)
	TestMoveCoins(wallet3, wallet3.addrB64, 1.03)

	TestMoveCoins(wallet1, wallet2.addrB64, 1.04)
	TestMoveCoins(wallet2, wallet3.addrB64, 1.05)
	TestMoveCoins(wallet3, wallet1.addrB64, 1.06)

	TestMoveCoins(wallet1, wallet1.addrB64, 1.07, flags=["--comment", "1.07"])
	TestMoveCoins(wallet2, wallet2.addrB64, 1.08, flags=["--comment", "1.08"])
	TestMoveCoins(wallet3, wallet3.addrB64, 1.09, flags=["--comment", "1.09"])
#end define




local.Run()
local.buffer["vnum"] = 0
wallet1, wallet2, wallet3 = Init()
wallet4, wallet5, wallet6 = Init()
wallet7, wallet8, wallet9 = Init()
local.StartCycle(Test, sec=1, name="Test1", args=(wallet1, wallet2, wallet3))
local.StartCycle(Test, sec=1, name="Test2", args=(wallet4, wallet5, wallet6))
local.StartCycle(Test, sec=1, name="Test3", args=(wallet7, wallet8, wallet9))
Sleep()











