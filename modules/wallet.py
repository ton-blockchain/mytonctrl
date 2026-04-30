from __future__ import annotations

import base64
import os

from modules.module import MtcModule
from mypylib.mypylib import color_print, print_table, parse
from mytoncore.models import Wallet
from mytonctrl.console_cmd import (check_usage_no_args, check_usage_one_arg, check_usage_two_args,
    add_command, check_usage_args_len, check_usage_args_min_len, check_usage_args_lens
)


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
        return wallet_name

    def create_new_wallet(self, args):
        if not check_usage_args_lens("nw", args, [0, 2, 3, 4]):
            return
        version = "v1"
        if len(args) == 0:
            wallet_name = self.generate_wallet_name()
            workchain = 0
        else:
            workchain = int(args[0])
            wallet_name = args[1]
        if len(args) > 2:
            version = args[2]
        if len(args) == 4:
            subwallet = int(args[3])
        else:
            subwallet = 698983191 + workchain  # 0x29A9A317 + workchain
        wallet = self.create_wallet(wallet_name, workchain, version, subwallet=subwallet)
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

    def activate_wallet(self, args):
        if not check_usage_one_arg("aw", args):
            return
        wallet_name = args[0]
        if wallet_name == "--all":
            self._wallets_check()
        else:
            wallet = self.ton.GetLocalWallet(wallet_name)
            self.do_activate_wallet(wallet)
        color_print("ActivateWallet - {green}OK{endc}")

    def get_wallets(self):
        self.local.add_log("start GetWallets function", "debug")
        wallets = list()
        wallets_name_list = self.ton.GetWalletsNameList()
        for walletName in wallets_name_list:
            wallet = self.ton.GetLocalWallet(walletName)
            wallets.append(wallet)
        return wallets

    def print_wallets_list(self, args):
        if not check_usage_no_args("wl", args):
            return
        table = list()
        table += [["Name", "Status", "Balance", "Ver", "Wch", "Address"]]
        data = self.get_wallets()
        if data is None or len(data) == 0:
            print("No data")
            return
        for wallet in data:
            account = self.ton.GetAccount(wallet.addrB64)
            if account.status != "active":
                wallet.addrB64 = wallet.addrB64_init
            table += [[wallet.name, account.status, account.balance, wallet.version, wallet.workchain, wallet.addrB64]]
        print_table(table)

    def do_import_wallet(self, addr_b64, key):
        addr_bytes = self.ton.addr_b64_to_bytes(addr_b64)
        pk_bytes = base64.b64decode(key)
        wallet_name = self.generate_wallet_name()
        wallet_path = self.ton.walletsDir + wallet_name
        with open(wallet_path + ".addr", 'wb') as file:
            file.write(addr_bytes)
        with open(wallet_path + ".pk", 'wb') as file:
            file.write(pk_bytes)
        return wallet_name

    def import_wallet(self, args):
        if not check_usage_two_args("iw", args):
            return
        addr, key = args[0], args[1]
        name = self.do_import_wallet(addr, key)
        print("Wallet name:", name)

    def set_wallet_version(self, args):
        if not check_usage_two_args("swv", args):
            return
        addr, version = args[0], args[1]
        self.ton.SetWalletVersion(addr, version)
        color_print("SetWalletVersion - {green}OK{endc}")

    def do_export_wallet(self, wallet_name):
        wallet = self.ton.GetLocalWallet(wallet_name)
        with open(wallet.privFilePath, 'rb') as file:
            data = file.read()
        key = base64.b64encode(data).decode("utf-8")
        return wallet.addrB64, key

    def export_wallet(self, args):
        if not check_usage_one_arg("ew", args):
            return
        name = args[0]
        addr, key = self.do_export_wallet(name)
        print("Wallet name:", name)
        print("Address:", addr)
        print("Secret key:", key)

    def delete_wallet(self, args):
        if not check_usage_one_arg("dw", args):
            return
        wallet_name = args[0]
        if input("Are you sure you want to delete this wallet (yes/no): ") != "yes":
            print("Cancel wallet deletion")
            return
        wallet = self.ton.GetLocalWallet(wallet_name)
        wallet.Delete()
        color_print("DeleteWallet - {green}OK{endc}")

    @staticmethod
    def get_new_wallet_fift_args(version: str, workchain: int, wallet_path: str, subwallet: int) -> list[str]:
        if "v1" in version:
            fift_script = "new-wallet.fif"
            args = [fift_script, workchain, wallet_path]
        elif "v2" in version:
            fift_script = "new-wallet-v2.fif"
            args = [fift_script, workchain, wallet_path]
        elif "v3" in version:
            fift_script = "new-wallet-v3.fif"
            args = [fift_script, workchain, subwallet, wallet_path]
        else:
            raise Exception(f"get_wallet_fift error: fift script for `{version}` not found")
        return list(map(str, args))

    def _get_wallet_id(self, wallet: Wallet):
        subwallet = 698983191 + wallet.workchain  # 0x29A9A317 + workchain
        try:
            subwallet = self.ton.run_get_method(wallet.addrB64, "wallet_id")[0]
        except Exception as e:
            self.local.add_log(f"Error getting wallet id: {e}", "error")
        return int(subwallet)

    def create_wallet(self, name: str, workchain: int = 0, version: str = "v1", subwallet: int | None = None) -> Wallet:
        subwallet_default = 698983191 + workchain  # 0x29A9A317 + workchain
        if subwallet is None:
            subwallet = subwallet_default
        wallet_path = self.ton.walletsDir + name
        if os.path.isfile(wallet_path + ".pk") and "v3" not in version:
            self.local.add_log("CreateWallet error: Wallet already exists: " + name, "warning")
        else:
            fift_args = self.get_new_wallet_fift_args(version, workchain=workchain,
                                                      wallet_path=wallet_path, subwallet=subwallet)
            result = self.ton.fift.run(fift_args)
            if "Creating new" not in result:
                raise Exception(f"CreateWallet error: {result}")
        wallet = self.ton.GetLocalWallet(name, version)
        self.ton.SetWalletVersion(wallet.addrB64, version)
        return wallet

    def do_move_coins(self, wallet: Wallet, dest: str, coins: float | str, flags: list | None = None, timeout: int = 30, subwallet: int | None = None):
        if flags is None:
            flags = []
        if "v3" in wallet.version and subwallet is None:
            subwallet = self._get_wallet_id(wallet)
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
        if "v1" in wallet.version:
            fift_script = "wallet.fif"
            args = [fift_script, wallet.path, dest, seqno, str(coins), "-m", str(mode), result_file_path]
        elif "v2" in wallet.version:
            fift_script = "wallet-v2.fif"
            args = [fift_script, wallet.path, dest, seqno, str(coins), "-m", str(mode), result_file_path]
        elif "v3" in wallet.version:
            fift_script = "wallet-v3.fif"
            args = [fift_script, wallet.path, dest, str(subwallet), seqno, str(coins), "-m", str(mode), result_file_path]
        else:
            raise Exception(f"MoveCoins error: Wallet version '{wallet.version}' is not supported")
        if flags:
            args += flags
        result = self.ton.fift.run(args)
        saved_file_path = parse(result, "Saved to file ", ")")
        if not saved_file_path:
            raise Exception(f"Fift script did not save boc: {result}")
        self.ton.SendFile(saved_file_path, wallet, timeout=timeout)

    def move_coins(self, args):
        if not check_usage_args_min_len("mg", args, 3):
            return
        wallet_name, destination, amount = args[0], args[1], args[2]
        flags = args[3:]
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
        wallet1.Delete()
        wallet2.Delete()

    def move_coins_through_proxy(self, args):
        if not check_usage_args_len("mgtp", args, 3):
            return
        wallet_name, destination, amount = args[0], args[1], args[2]
        wallet = self.ton.GetLocalWallet(wallet_name)
        destination = self.ton.get_destination_addr(destination)
        self.do_move_coins_through_proxy(wallet, destination, amount)
        color_print("MoveCoinsThroughProxy - {green}OK{endc}")

    def add_console_commands(self, console):
        add_command(self.local, console, "nw", self.create_new_wallet)
        add_command(self.local, console, "aw", self.activate_wallet)
        add_command(self.local, console, "wl", self.print_wallets_list)
        add_command(self.local, console, "iw", self.import_wallet)
        add_command(self.local, console, "swv", self.set_wallet_version)
        add_command(self.local, console, "ew", self.export_wallet)
        add_command(self.local, console, "dw", self.delete_wallet)
        add_command(self.local, console, "mg", self.move_coins)
        add_command(self.local, console, "mgtp", self.move_coins_through_proxy)
