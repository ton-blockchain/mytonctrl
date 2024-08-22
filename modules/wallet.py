import base64
import os

from modules.module import MtcModule
from mypylib.mypylib import color_print, print_table


class WalletModule(MtcModule):

    description = ''
    default_value = False

    def create_new_wallet(self, args):
        version = "v1"
        try:
            if len(args) == 0:
                walletName = self.ton.GenerateWalletName()
                workchain = 0
            else:
                workchain = int(args[0])
                walletName = args[1]
            if len(args) > 2:
                version = args[2]
            if len(args) == 4:
                subwallet = int(args[3])
            else:
                subwallet = 698983191 + workchain  # 0x29A9A317 + workchain
        except:
            color_print("{red}Bad args. Usage:{endc} nw <workchain-id> <wallet-name> [<version> <subwallet>]")
            return
        wallet = self.ton.CreateWallet(walletName, workchain, version, subwallet=subwallet)
        table = list()
        table += [["Name", "Workchain", "Address"]]
        table += [[wallet.name, wallet.workchain, wallet.addrB64_init]]
        print_table(table)
    # end define

    def _wallets_check(self):
        self.local.add_log("start WalletsCheck function", "debug")
        wallets = self.get_wallets()
        for wallet in wallets:
            if os.path.isfile(wallet.bocFilePath):
                account = self.ton.GetAccount(wallet.addrB64)
                if account.balance > 0:
                    self.ton.SendFile(wallet.bocFilePath, wallet)
    # end define

    def activate_wallet(self, args):
        try:
            walletName = args[0]
        except Exception as err:
            walletName = "all"
        if walletName == "all":
            self._wallets_check()
        else:
            wallet = self.ton.GetLocalWallet(walletName)
            self.ton.ActivateWallet(wallet)
        color_print("ActivateWallet - {green}OK{endc}")
    # end define

    def get_wallets(self):
        self.local.add_log("start GetWallets function", "debug")
        wallets = list()
        wallets_name_list = self.ton.GetWalletsNameList()
        for walletName in wallets_name_list:
            wallet = self.ton.GetLocalWallet(walletName)
            wallets.append(wallet)
        return wallets
    # end define

    def print_wallets_list(self, args):
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
    # end define

    def do_import_wallet(self, addr_b64, key):
        addr_bytes = self.ton.addr_b64_to_bytes(addr_b64)
        pk_bytes = base64.b64decode(key)
        wallet_name = self.ton.GenerateWalletName()
        wallet_path = self.ton.walletsDir + wallet_name
        with open(wallet_path + ".addr", 'wb') as file:
            file.write(addr_bytes)
        with open(wallet_path + ".pk", 'wb') as file:
            file.write(pk_bytes)
        return wallet_name
    # end define

    def import_wallet(self, args):
        try:
            addr = args[0]
            key = args[1]
        except:
            color_print("{red}Bad args. Usage:{endc} iw <wallet-addr> <wallet-secret-key>")
            return
        name = self.do_import_wallet(addr, key)
        print("Wallet name:", name)
    # end define

    def set_wallet_version(self, args):
        try:
            addr = args[0]
            version = args[1]
        except:
            color_print("{red}Bad args. Usage:{endc} swv <wallet-addr> <wallet-version>")
            return
        self.ton.SetWalletVersion(addr, version)
        color_print("SetWalletVersion - {green}OK{endc}")
    # end define

    def do_export_wallet(self, wallet_name):
        wallet = self.ton.GetLocalWallet(wallet_name)
        with open(wallet.privFilePath, 'rb') as file:
            data = file.read()
        key = base64.b64encode(data).decode("utf-8")
        return wallet.addrB64, key
    # end define

    def export_wallet(self, args):
        try:
            name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} ew <wallet-name>")
            return
        addr, key = self.do_export_wallet(name)
        print("Wallet name:", name)
        print("Address:", addr)
        print("Secret key:", key)
    # end define

    def delete_wallet(self, args):
        try:
            wallet_name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} dw <wallet-name>")
            return
        if input("Are you sure you want to delete this wallet (yes/no): ") != "yes":
            print("Cancel wallet deletion")
            return
        wallet = self.ton.GetLocalWallet(wallet_name)
        wallet.Delete()
        color_print("DeleteWallet - {green}OK{endc}")
    # end define

    def move_coins(self, args):
        try:
            wallet_name = args[0]
            destination = args[1]
            amount = args[2]
            flags = args[3:]
        except:
            color_print("{red}Bad args. Usage:{endc} mg <wallet-name> <account-addr | bookmark-name> <amount>")
            return
        wallet = self.ton.GetLocalWallet(wallet_name)
        destination = self.ton.get_destination_addr(destination)
        self.ton.MoveCoins(wallet, destination, amount, flags=flags)
        color_print("MoveCoins - {green}OK{endc}")
    # end define

    def do_move_coins_through_proxy(self, wallet, dest, coins):
        self.local.add_log("start MoveCoinsThroughProxy function", "debug")
        wallet1 = self.ton.CreateWallet("proxy_wallet1", 0)
        wallet2 = self.ton.CreateWallet("proxy_wallet2", 0)
        self.ton.MoveCoins(wallet, wallet1.addrB64_init, coins)
        self.ton.ActivateWallet(wallet1)
        self.ton.MoveCoins(wallet1, wallet2.addrB64_init, "alld")
        self.ton.ActivateWallet(wallet2)
        self.ton.MoveCoins(wallet2, dest, "alld", flags=["-n"])
        wallet1.Delete()
        wallet2.Delete()
    # end define

    def move_coins_through_proxy(self, args):
        try:
            wallet_name = args[0]
            destination = args[1]
            amount = args[2]
        except:
            color_print("{red}Bad args. Usage:{endc} mgtp <wallet-name> <account-addr | bookmark-name> <amount>")
            return
        wallet = self.ton.GetLocalWallet(wallet_name)
        destination = self.ton.get_destination_addr(destination)
        self.do_move_coins_through_proxy(wallet, destination, amount)
        color_print("MoveCoinsThroughProxy - {green}OK{endc}")
    # end define

    def add_console_commands(self, console):
        console.AddItem("nw", self.create_new_wallet, self.local.translate("nw_cmd"))
        console.AddItem("aw", self.activate_wallet, self.local.translate("aw_cmd"))
        console.AddItem("wl", self.print_wallets_list, self.local.translate("wl_cmd"))
        console.AddItem("iw", self.import_wallet, self.local.translate("iw_cmd"))
        console.AddItem("swv", self.set_wallet_version, self.local.translate("swv_cmd"))
        console.AddItem("ew", self.export_wallet, self.local.translate("ex_cmd"))
        console.AddItem("dw", self.delete_wallet, self.local.translate("dw_cmd"))
        console.AddItem("mg", self.move_coins, self.local.translate("mg_cmd"))
        console.AddItem("mgtp", self.move_coins_through_proxy, self.local.translate("mgtp_cmd"))
