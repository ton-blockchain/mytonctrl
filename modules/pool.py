import os

from mypylib.mypylib import color_print, print_table
from modules.module import MtcModule


class PoolModule(MtcModule):

    description = 'Basic pools functions.'
    default_value = False

    def print_pools_list(self, args):
        table = list()
        table += [["Name", "Status", "Balance", "Version", "Address"]]
        data = self.ton.GetPools()
        if data is None or len(data) == 0:
            print("No data")
            return
        for pool in data:
            account = self.ton.GetAccount(pool.addrB64)
            if account.status != "active":
                pool.addrB64 = pool.addrB64_init
            version = self.ton.GetVersionFromCodeHash(account.codeHash)
            table += [[pool.name, account.status, account.balance, version, pool.addrB64]]
        print_table(table)

    def delete_pool(self, args):
        try:
            pool_name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} delete_pool <pool-name>")
            return
        pool = self.ton.GetLocalPool(pool_name)
        pool.Delete()
        color_print("DeletePool - {green}OK{endc}")
    # end define

    def do_import_pool(self, pool_name, addr_b64):
        self.check_download_pool_contract_scripts()
        addr_bytes = self.ton.addr_b64_to_bytes(addr_b64)
        pool_path = self.ton.poolsDir + pool_name
        with open(pool_path + ".addr", 'wb') as file:
            file.write(addr_bytes)
    # end define

    def import_pool(self, args):
        try:
            pool_name = args[0]
            pool_addr = args[1]
        except:
            color_print("{red}Bad args. Usage:{endc} import_pool <pool-name> <pool-addr>")
            return
        self.do_import_pool(pool_name, pool_addr)
        color_print("import_pool - {green}OK{endc}")

    def check_download_pool_contract_scripts(self):
        contract_path = self.ton.contractsDir + "nominator-pool/"
        if not os.path.isdir(contract_path):
            self.ton.DownloadContract("https://github.com/ton-blockchain/nominator-pool")

    def do_deposit_to_pool(self, pool_addr, amount):
        wallet = self.ton.GetValidatorWallet()
        bocPath = self.ton.local.buffer.my_temp_dir + wallet.name + "validator-deposit-query.boc"
        fiftScript = self.ton.contractsDir + "nominator-pool/func/validator-deposit.fif"
        args = [fiftScript, bocPath]
        result = self.ton.fift.Run(args)
        resultFilePath = self.ton.SignBocWithWallet(wallet, bocPath, pool_addr, amount)
        self.ton.SendFile(resultFilePath, wallet)

    def deposit_to_pool(self, args):
        try:
            poll_addr = args[0]
            amount = float(args[1])
        except:
            color_print("{red}Bad args. Usage:{endc} deposit_to_pool <pool-addr> <amount>")
            return
        self.do_deposit_to_pool(poll_addr, amount)
        color_print("DepositToPool - {green}OK{endc}")

    def do_withdraw_from_pool(self, pool_addr, amount):
        pool_data = self.ton.GetPoolData(pool_addr)
        if pool_data["state"] == 0:
            self.ton.WithdrawFromPoolProcess(pool_addr, amount)
        else:
            self.ton.PendWithdrawFromPool(pool_addr, amount)

    def withdraw_from_pool(self, args):
        try:
            pool_addr = args[0]
            amount = float(args[1])
        except:
            color_print("{red}Bad args. Usage:{endc} withdraw_from_pool <pool-addr> <amount>")
            return
        self.do_withdraw_from_pool(pool_addr, amount)
        color_print("WithdrawFromPool - {green}OK{endc}")

    def add_console_commands(self, console):
        console.AddItem("pools_list", self.print_pools_list, self.local.translate("pools_list_cmd"))
        console.AddItem("delete_pool", self.delete_pool, self.local.translate("delete_pool_cmd"))
        console.AddItem("import_pool", self.import_pool, self.local.translate("import_pool_cmd"))
        console.AddItem("deposit_to_pool", self.deposit_to_pool, self.local.translate("deposit_to_pool_cmd"))
        console.AddItem("withdraw_from_pool", self.withdraw_from_pool, self.local.translate("withdraw_from_pool_cmd"))
