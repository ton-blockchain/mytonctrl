import os

from mypylib.mypylib import color_print, print_table
from modules.module import MtcModule
from mytonctrl.console_cmd import add_command, check_usage_one_arg, check_usage_two_args


class PoolModule(MtcModule):

    description = 'Basic pools functions.'
    default_value = False

    def print_pools_list(self, args):
        table = list()
        table += [["Name", "Status", "Balance", "Version", "Address"]]
        data = self.ton.GetPools()
        if len(data) == 0:
            print("No data")
            return
        for pool in data:
            account = self.ton.GetAccount(pool.addrB64)
            addr = pool.addrB64
            if account.status != "active":
                addr = pool.addrB64_init
            version = self.ton.GetVersionFromCodeHash(account.codeHash)
            table += [[pool.name, account.status, account.balance, version, addr]]
        print_table(table)

    def delete_pool(self, args):
        if not check_usage_one_arg("delete_pool", args):
            return
        pool_name = args[0]
        pool = self.ton.GetLocalPool(pool_name)
        pool.delete()
        color_print("DeletePool - {green}OK{endc}")

    def do_import_pool(self, pool_name, addr_b64):
        self.check_download_pool_contract_scripts()
        addr_bytes = self.ton.addr_b64_to_bytes(addr_b64)
        pool_path = self.ton.poolsDir + pool_name
        with open(pool_path + ".addr", 'wb') as file:
            file.write(addr_bytes)

    def import_pool(self, args):
        if not check_usage_two_args("import_pool", args):
            return
        pool_name = args[0]
        pool_addr = args[1]
        self.do_import_pool(pool_name, pool_addr)
        color_print("import_pool - {green}OK{endc}")

    def check_download_pool_contract_scripts(self):
        contract_path = self.ton.contractsDir + "nominator-pool/"
        if not os.path.isdir(contract_path):
            self.ton.DownloadContract("https://github.com/ton-blockchain/nominator-pool")

    def add_console_commands(self, console):
        add_command(self.local, console, "pools_list", self.print_pools_list)
        add_command(self.local, console, "delete_pool", self.delete_pool)
        add_command(self.local, console, "import_pool", self.import_pool)
