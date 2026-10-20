from __future__ import annotations

import base64
import os
from typing import Optional, Union

from modules.module import MtcModule
from mypyconsole.mypyconsole import UsageError
from mypylib.mypylib import color_print, print_table, parse
from mytoncore.models import Wallet
from mytoncore.utils import wallet_v3_subwallet_id
from mytonctrl.argtypes import TonAddress, WalletVersion, coins_amount
from mypyconsole.command_parser import Annotated, Arg

_Destination = Annotated[str, Arg(help="address or bookmark name")]
_CoinsAmount = Annotated[
    Union[float, str],
    Arg(type=coins_amount, help="TON amount, or all (the whole balance) / alld (the whole balance, then destroy the wallet)"),
]


class WalletModule(MtcModule):

    description = ''
    default_value = False

    def generate_wallet_name(self):
        self.local.add_log("start GenerateWalletName function", "debug")
        index = 1
        index_str = str(index).rjust(3, '0')
        wallet_prefix = "wallet_"
        index_list = list()
        wallet_name = wallet_prefix + index_str
        wallets_name_list = self.ton.GetWalletsNameList()
        if wallet_name in wallets_name_list:
            for item in wallets_name_list:
                if item.startswith(wallet_prefix):
                    try:
                        index = item[item.rfind('_') + 1:]
                        index = int(index)
                        index_list.append(index)
                    except Exception:
                        pass
            index = max(index_list) + 1
            index_str = str(index).rjust(3, '0')
            wallet_name = wallet_prefix + index_str
        while (
            os.path.lexists(self.ton.walletsDir + wallet_name + ".addr")
            or os.path.lexists(self.ton.walletsDir + wallet_name + ".pk")
        ):
            index += 1
            index_str = str(index).rjust(3, '0')
            wallet_name = wallet_prefix + index_str
        return wallet_name

    def create_new_wallet(
        self,
        workchain_id: Optional[int] = None,
        wallet_name: Optional[str] = None,
        version: WalletVersion = "v1",
    ) -> None:
        if workchain_id is None and wallet_name is None:
            wallet_name = self.generate_wallet_name()
            workchain_id = 0
        elif workchain_id is None or wallet_name is None:
            raise UsageError("workchain_id and wallet_name must be given together")
        wallet = self.create_wallet(wallet_name, workchain_id, version)
        table = list()
        table += [["Name", "Workchain", "Address"]]
        table += [[wallet.name, wallet.workchain, wallet.addrB64_init]]
        print_table(table)

    def _wallets_check(self):
        self.local.add_log("start WalletsCheck function", "debug")
        wallets = self.get_wallets()
        for wallet in wallets:
            if os.path.isfile(wallet.bocFilePath):
                account = self.ton.GetAccount(wallet.addrB64)
                if account.balance > 0:
                    wallet.seqno = 0
                    self.ton.SendFile(wallet.bocFilePath, wallet)

    def do_activate_wallet(self, wallet: Wallet):
        account = self.ton.GetAccount(wallet.addrB64)
        if account.status == "empty":
            raise Exception("ActivateWallet error: account status is empty")
        elif account.status == "active":
            self.local.add_log("ActivateWallet warning: account status is active", "warning")
        else:
            wallet.seqno = 0
            self.ton.SendFile(wallet.bocFilePath, wallet, remove=False)

    def activate_wallet(self, wallet_name: Optional[str] = None, *, all_: bool = False) -> None:
        if wallet_name is not None and all_:
            raise UsageError("argument --all: not allowed with argument wallet_name")
        if all_:
            self._wallets_check()
        elif wallet_name is not None:
            wallet = self.ton.GetLocalWallet(wallet_name)
            self.do_activate_wallet(wallet)
        else:
            raise UsageError("one of the arguments wallet_name --all is required")
        color_print("ActivateWallet - {green}OK{endc}")

    def get_wallets(self):
        self.local.add_log("start GetWallets function", "debug")
        wallets = list()
        wallets_name_list = self.ton.GetWalletsNameList()
        for walletName in wallets_name_list:
            wallet = self.ton.GetLocalWallet(walletName)
            wallets.append(wallet)
        return wallets

    def print_wallets_list(self) -> None:
        table = list()
        table += [["Name", "Status", "Balance", "Ver", "Wch", "Address"]]
        data = self.get_wallets()
        if data is None or len(data) == 0:
            print("No data")
            return
        for wallet in data:
            account = self.ton.GetAccount(wallet.addrB64)
            addr = wallet.addrB64
            if account.status != "active":
                addr = wallet.addrB64_init
            table += [[wallet.name, account.status, account.balance, wallet.version, wallet.workchain, addr]]
        print_table(table)

    def do_import_wallet(self, addr_b64, key):
        addr_bytes = self.ton.addr_b64_to_bytes(addr_b64)
        pk_bytes = base64.b64decode(key)
        wallet_name = self.generate_wallet_name()
        wallet_path = self.ton.walletsDir + wallet_name
        addr_path = wallet_path + ".addr"
        pk_path = wallet_path + ".pk"
        with open(addr_path, 'xb') as file:
            file.write(addr_bytes)
        try:
            pk_fd = os.open(pk_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except Exception:
            os.remove(addr_path)
            raise
        try:
            os.fchmod(pk_fd, 0o600)
            pk_file = os.fdopen(pk_fd, 'wb')
            pk_fd = None
            with pk_file:
                pk_file.write(pk_bytes)
        except Exception:
            if pk_fd is not None:
                os.close(pk_fd)
            os.remove(pk_path)
            os.remove(addr_path)
            raise
        return wallet_name

    def import_wallet(self, wallet_addr: TonAddress, wallet_secret_key: str) -> None:
        name = self.do_import_wallet(wallet_addr, wallet_secret_key)
        print("Wallet name:", name)

    def set_wallet_version(self, wallet_addr: TonAddress, wallet_version: WalletVersion) -> None:
        self.ton.SetWalletVersion(wallet_addr, wallet_version)
        color_print("SetWalletVersion - {green}OK{endc}")

    def do_export_wallet(self, wallet_name):
        wallet = self.ton.GetLocalWallet(wallet_name)
        with open(wallet.privFilePath, 'rb') as file:
            data = file.read()
        key = base64.b64encode(data).decode("utf-8")
        return wallet.addrB64, key

    def export_wallet(self, wallet_name: str) -> None:
        addr, key = self.do_export_wallet(wallet_name)
        print("Wallet name:", wallet_name)
        print("Address:", addr)
        print("Secret key:", key)

    def delete_wallet(self, wallet_name: str) -> None:
        if input("Are you sure you want to delete this wallet (yes/no): ") != "yes":
            print("Cancel wallet deletion")
            return
        wallet = self.ton.GetLocalWallet(wallet_name)
        wallet.delete()
        color_print("DeleteWallet - {green}OK{endc}")

    @staticmethod
    def get_new_wallet_fift_args(version: str, workchain: int, wallet_path: str) -> list[str]:
        if version.startswith("v1"):
            fift_script = "new-wallet.fif"
            args = [fift_script, workchain, wallet_path]
        elif version.startswith("v2"):
            fift_script = "new-wallet-v2.fif"
            args = [fift_script, workchain, wallet_path]
        elif version.startswith("v3"):
            fift_script = "new-wallet-v3.fif"
            args = [fift_script, workchain, wallet_v3_subwallet_id(workchain), wallet_path]
        else:
            raise Exception(f"get_wallet_fift error: fift script for `{version}` not found")
        return list(map(str, args))

    def create_wallet(self, name: str, workchain: int = 0, version: str = "v1") -> Wallet:
        wallet_path = self.ton.walletsDir + name
        if os.path.isfile(wallet_path + ".pk") and not version.startswith("v3"):
            self.local.add_log("CreateWallet error: Wallet already exists: " + name, "warning")
        else:
            fift_args = self.get_new_wallet_fift_args(version, workchain=workchain, wallet_path=wallet_path)
            result = self.ton.fift.run(fift_args)
            if "Creating new" not in result:
                raise Exception(f"CreateWallet error: {result}")
        wallet = self.ton.GetLocalWallet(name, version)
        self.ton.SetWalletVersion(wallet.addrB64, version)
        return wallet

    def do_move_coins(self, wallet: Wallet, dest: str, coins: float | str, flags: list | None = None, timeout: int = 30):
        if flags is None:
            flags = []
        version = wallet.version or ""
        if coins == "all":
            mode = 130
            coins = 0
        elif coins == "alld":
            mode = 160
            coins = 0
        else:
            coins = float(coins)
            mode = 3

        account = self.ton.GetAccount(wallet.addrB64)
        self.ton.check_account_balance(account, coins + 0.1)
        self.ton.check_account_active(account)

        dest_account = self.ton.GetAccount(dest)
        bounceable = self.ton.IsBounceableAddrB64(dest)
        if not bounceable and dest_account.status == "active":
            flags += ["-b"]
            text = "Find non-bounceable flag, but destination account already active. Using bounceable flag"
            self.local.add_log(text, "warning")
        elif "-n" not in flags and bounceable and dest_account.status != "active":
            raise Exception(
                "Find bounceable flag, but destination account is not active. Use non-bounceable address or flag -n")

        seqno = str(self.ton.get_seqno(wallet))
        result_file_path = self.local.my_temp_dir + wallet.name + "_wallet-query"
        if version.startswith("v1"):
            fift_script = "wallet.fif"
            args = [fift_script, wallet.path, dest, seqno, str(coins), "-m", str(mode), result_file_path]
        elif version.startswith("v2"):
            fift_script = "wallet-v2.fif"
            args = [fift_script, wallet.path, dest, seqno, str(coins), "-m", str(mode), result_file_path]
        elif version.startswith("v3"):
            fift_script = "wallet-v3.fif"
            subwallet = str(wallet_v3_subwallet_id(wallet.workchain))
            args = [fift_script, wallet.path, dest, subwallet, seqno, str(coins), "-m", str(mode), result_file_path]
        else:
            raise Exception(f"MoveCoins error: Wallet version {wallet.version!r} is not supported")
        if flags:
            args += flags
        result = self.ton.fift.run(args)
        saved_file_path = parse(result, "Saved to file ", ")")
        if not saved_file_path:
            raise Exception(f"Fift script did not save boc: {result}")
        self.ton.SendFile(saved_file_path, wallet, timeout=timeout)

    def move_coins(
        self,
        wallet_name: str,
        destination: _Destination,
        amount: _CoinsAmount,
        *,
        no_bounce: Annotated[bool, Arg("-n", help="clear the bounce flag")] = False,
        force_bounce: Annotated[bool, Arg("-b", help="force the bounce flag")] = False,
        comment: Annotated[Optional[str], Arg("-C", help="text comment of the transfer")] = None,
        timeout: Annotated[Optional[int], Arg("-t", help="message expiration timeout, seconds")] = None,
        mode: Annotated[Optional[int], Arg("-m", help="SENDRAWMSG mode 0..255, overrides the one derived from amount")] = None,
        body: Annotated[Optional[str], Arg("-B", help="file with the BoC of the message body")] = None,
        with_init: Annotated[Optional[str], Arg("-I", help="file with the StateInit BoC, forwarded as is")] = None,
    ) -> None:
        flags: list[str] = []
        if no_bounce:
            flags.append("-n")
        if force_bounce:
            flags.append("-b")
        for flag, value in (("-C", comment), ("-t", timeout), ("-m", mode), ("-B", body), ("-I", with_init)):
            if value is not None:
                flags += [flag, str(value)]
        wallet = self.ton.GetLocalWallet(wallet_name)
        destination = self.ton.get_destination_addr(destination)
        self.do_move_coins(wallet, destination, amount, flags=flags)
        color_print("MoveCoins - {green}OK{endc}")

    def do_move_coins_through_proxy(self, wallet, dest, coins):
        self.local.add_log("start MoveCoinsThroughProxy function", "debug")
        wallet1 = self.create_wallet("proxy_wallet1", 0)
        wallet2 = self.create_wallet("proxy_wallet2", 0)
        self.do_move_coins(wallet, wallet1.addrB64_init, coins)
        self.do_activate_wallet(wallet1)
        self.do_move_coins(wallet1, wallet2.addrB64_init, "alld")
        self.do_activate_wallet(wallet2)
        self.do_move_coins(wallet2, dest, "alld", flags=["-n"])
        wallet1.delete()
        wallet2.delete()

    def move_coins_through_proxy(
        self,
        wallet_name: str,
        destination: _Destination,
        amount: _CoinsAmount,
    ) -> None:
        wallet = self.ton.GetLocalWallet(wallet_name)
        destination = self.ton.get_destination_addr(destination)
        self.do_move_coins_through_proxy(wallet, destination, amount)
        color_print("MoveCoinsThroughProxy - {green}OK{endc}")

    def add_console_commands(self, console):
        console.add_command("nw", self.create_new_wallet)
        console.add_command("aw", self.activate_wallet)
        console.add_command("wl", self.print_wallets_list)
        console.add_command("iw", self.import_wallet)
        console.add_command("swv", self.set_wallet_version)
        console.add_command("ew", self.export_wallet)
        console.add_command("dw", self.delete_wallet)
        console.add_command("mg", self.move_coins)
        console.add_command("mgtp", self.move_coins_through_proxy)
