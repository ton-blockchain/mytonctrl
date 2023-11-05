import base64
import json
import time
import subprocess


def GetInitBlock():
    from mypylib.mypylib import MyPyClass
    from mytoncore import MyTonCore

    mytoncore_local = MyPyClass('mytoncore.py')
    ton = MyTonCore(mytoncore_local)
    initBlock = ton.GetInitBlock()
    return initBlock
# end define


def StartValidator(local):
    # restart validator
    local.add_log("Start/restart validator service", "debug")
    args = ["systemctl", "restart", "validator"]
    subprocess.run(args)

    # sleep 10 sec
    local.add_log("sleep 10 sec", "debug")
    time.sleep(10)
# end define


def StartMytoncore(local):
    # restart mytoncore
    local.add_log("Start/restart mytoncore service", "debug")
    args = ["systemctl", "restart", "mytoncore"]
    subprocess.run(args)
# end define
