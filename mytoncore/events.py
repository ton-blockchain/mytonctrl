from mypylib import MyPyClass

from mytoncore.mytoncore import MyTonCore


def run_event(local: MyPyClass, event_name: str):
    if event_name == "enableVC":
        enable_vc_event(local)
    elif event_name.startswith("enable_mode"):
        enable_mode(local, event_name)
    elif event_name == "enable_btc_teleport":
        enable_btc_teleport(local)
    elif event_name.startswith("setup_collator"):
        setup_collator(local, event_name)
    else:
        raise Exception("Unknown event name")
    local.exit()


def enable_vc_event(local: MyPyClass):
    local.add_log("start EnableVcEvent function", "debug")
    ton = MyTonCore(local)
    wallet = ton.CreateWallet("validator_wallet_001", -1)
    assert wallet is not None
    local.db["validatorWalletName"] = wallet.name
    adnl_addr = ton.CreateNewKey()
    assert adnl_addr is not None
    ton.add_adnl_addr(adnl_addr)
    local.db["adnlAddr"] = adnl_addr
    local.save()


def enable_mode(local: MyPyClass, event_name: str):
    ton = MyTonCore(local)
    mode = event_name.split("_")[-1]
    if mode in ("liteserver", "collator"):
        ton.disable_mode("validator")
    ton.enable_mode(mode)


def enable_btc_teleport(local: MyPyClass):
    local.add_log("start enable_btc_teleport function", "debug")
    ton = MyTonCore(local)
    if not ton.using_validator():
        local.add_log("Skip installing BTC Teleport as node is not a validator", "info")
        return
    from modules.btc_teleport import BtcTeleportModule

    BtcTeleportModule(ton, local).init(reinstall=True)


def setup_collator(local: MyPyClass, event_name: str):
    local.add_log("start setup_collator function", "debug")
    ton = MyTonCore(local)
    from modules.collator import CollatorModule

    shards = event_name.split("_")[2:]
    CollatorModule(ton, local).setup_collator(shards)
