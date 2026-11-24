from modules.wallet import WalletModule
from modules.general import GeneralModule

from mypylib.mypylib import MyPyClass

from mytoncore.mytoncore import MyTonCore
from mytonctrl.argtypes import tcp_port
from mytonctrl.utils import is_container


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
    container = is_container()
    if container and local.db.get("containerEnableVcComplete"):
        if not local.db.get("validatorWalletName") or not local.db.get("adnlAddr"):
            raise RuntimeError("Validator-console setup checkpoint is missing its wallet or ADNL identity")
        return
    wallet_name = local.db.get("validatorWalletName", "validator_wallet_001") if container else "validator_wallet_001"
    wallet = ton.GetLocalWallet(wallet_name) if container and local.db.get("validatorWalletName") else module.create_wallet(wallet_name, -1)
    assert wallet is not None
    local.db["validatorWalletName"] = wallet.name
    if container:
        local.save()
    adnl_addr = local.db.get("adnlAddr") if container else None
    if not adnl_addr:
        adnl_addr = ton.CreateNewKey()
        if container:
            # Persist the identity before attaching it so an interrupted retry reuses it.
            local.db["adnlAddr"] = adnl_addr
            local.save()
    added = ton.add_adnl_addr(adnl_addr)
    if container and not added:
        raise RuntimeError("Failed to add the validator ADNL address; its key was retained for retry")
    if not container:
        local.db["adnlAddr"] = adnl_addr
    local.save()

    args = event_name.split("_")[1:]
    if args:
        GeneralModule(ton, local).set_quic_port(tcp_port(args[0]))
    if container:
        local.db["containerEnableVcComplete"] = True
        local.save()


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

    CollatorModule(ton, local).setup_collator(adnl=None)
