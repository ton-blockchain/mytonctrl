from modules.wallet import WalletModule
from modules.general import GeneralModule

from mypylib.mypylib import MyPyClass

from mytoncore.mytoncore import MyTonCore


def run_event(local: MyPyClass, event_name: str):
    if event_name.startswith("enableVC"):
        enable_vc_event(local, event_name)
    elif event_name.startswith("enable_mode"):
        enable_mode(local, event_name)
    elif event_name.startswith("setup_collator"):
        setup_collator(local, event_name)
    else:
        raise Exception("Unknown event name")
    local.exit()


def enable_vc_event(local: MyPyClass, event_name: str):
    local.add_log("start EnableVcEvent function", "debug")
    ton = MyTonCore(local)
    module = WalletModule(ton, local)
    wallet = module.create_wallet("validator_wallet_001", -1)
    assert wallet is not None
    local.db["validatorWalletName"] = wallet.name
    adnl_addr = ton.CreateNewKey()
    ton.add_adnl_addr(adnl_addr)
    local.db["adnlAddr"] = adnl_addr
    local.save()

    args = event_name.split("_")[1:]
    if args:
        module = GeneralModule(ton, local)
        module.set_quic_port(args)


def enable_mode(local: MyPyClass, event_name: str):
    ton = MyTonCore(local)
    mode = event_name.split("_")[-1]
    if mode in ("liteserver", "collator"):
        ton.disable_mode("validator")
    ton.enable_mode(mode)


def setup_collator(local: MyPyClass, event_name: str):
    local.add_log("start setup_collator function", "debug")
    ton = MyTonCore(local)
    from modules.collator import CollatorModule

    shards = event_name.split("_")[2:]
    CollatorModule(ton, local).setup_collator(shards)
