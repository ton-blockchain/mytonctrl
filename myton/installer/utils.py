import base64
import json
import time
import subprocess


def GetInitBlock():
    from mytoncore import MyTonCore

    ton = MyTonCore(None)
    initBlock = ton.GetInitBlock()
    return initBlock
# end define


def StartValidator(local):
    # restart validator
    local.AddLog("Start/restart validator service", "debug")
    args = ["systemctl", "restart", "validator"]
    subprocess.run(args)

    # sleep 10 sec
    local.AddLog("sleep 10 sec", "debug")
    time.sleep(10)
# end define


def StartMytoncore(local):
    # restart mytoncore
    local.AddLog("Start/restart mytoncore service", "debug")
    args = ["systemctl", "restart", "mytoncore"]
    subprocess.run(args)
# end define
