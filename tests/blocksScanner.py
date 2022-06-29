#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import sys
sys.path.append("/usr/src/mytonctrl/")
from mypylib.mypylib import bcolors, Sleep
from mytoncore import MyTonCore, TonBlocksScanner

def NewBlockReaction(block):
	print(f"{bcolors.green} block: {bcolors.endc} {block}")
#end define

def NewTransReaction(trans):
	print(f"{bcolors.magenta} trans: {bcolors.endc} {trans}")
#end define

def NewMessageReaction(message):
	print(f"{bcolors.yellow} message: {bcolors.endc} {message}")
#end define


ton = MyTonCore()
scanner = TonBlocksScanner(ton, nbr=NewBlockReaction, ntr=NewTransReaction, nmr=NewMessageReaction)
scanner.Run()
Sleep()