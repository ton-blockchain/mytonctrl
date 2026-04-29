import os

from mypylib.mypylib import color_print
from modules.pool import PoolModule
from mytoncore.utils import get_package_resource_path
from mytonctrl.console_cmd import add_command, check_usage_two_args, check_usage_one_arg


class SingleNominatorModule(PoolModule):

    description = 'Orbs\'s single nominator pools.'
    default_value = False

    def do_create_single_pool(self, pool_name, owner_address):
        self.ton.local.add_log("start create_single_pool function", "debug")

        self.check_download_pool_contract_scripts()

        file_path = self.ton.poolsDir + pool_name
        if os.path.isfile(file_path + ".addr"):
            self.ton.local.add_log("create_single_pool warning: Pool already exists: " + file_path, "warning")
            return

        validator_wallet = self.ton.GetValidatorWallet()
        with get_package_resource_path('mytoncore', 'contracts/single-nominator-pool/init.fif') as fift_script:
            with get_package_resource_path('mytoncore', 'contracts/single-nominator-pool/single-nominator-code.hex') as code_boc:
                args = [fift_script, code_boc, owner_address, validator_wallet.addrB64, file_path]
                result = self.ton.fift.run(args)
        if "Saved single nominator pool" not in result:
            raise Exception("create_single_pool error: " + result)

        pools = self.ton.GetPools()
        new_pool = self.ton.GetLocalPool(pool_name)
        for pool in pools:
            if pool.name != new_pool.name and pool.addrB64 == new_pool.addrB64:
                new_pool.Delete()
                raise Exception("create_single_pool error: Pool with the same parameters already exists.")

    def new_single_pool(self, args):
        if not check_usage_two_args("new_single_pool", args):
            return
        pool_name = args[0]
        owner_address = args[1]
        self.do_create_single_pool(pool_name, owner_address)
        color_print("new_single_pool - {green}OK{endc}")

    def do_activate_single_pool(self, pool):
        self.local.add_log("start activate_single_pool function", "debug")
        boc_mode = "--with-init"
        validator_wallet = self.ton.GetValidatorWallet()
        self.ton.check_account_active(validator_wallet.addrB64)
        result_file_path = self.ton.SignBocWithWallet(validator_wallet, pool.bocFilePath, pool.addrB64_init, 1, boc_mode=boc_mode)
        self.ton.SendFile(result_file_path, validator_wallet)

    def activate_single_pool(self, args):
        if not check_usage_one_arg("activate_single_pool", args):
            return
        pool_name = args[0]
        pool = self.ton.GetLocalPool(pool_name)
        if not os.path.isfile(pool.bocFilePath):
            self.local.add_log(f"Pool {pool_name} already activated", "warning")
            return
        self.do_activate_single_pool(pool)
        color_print("activate_single_pool - {green}OK{endc}")

    def withdraw_from_single_pool(self, args):
        if not check_usage_two_args("withdraw_from_single_pool", args):
            return
        pool_addr = args[0]
        amount = float(args[1])
        self.ton.WithdrawFromPoolProcess(pool_addr, amount)
        color_print("withdraw_from_single_pool - {green}OK{endc}")

    def add_console_commands(self, console):
        add_command(self.local, console, "new_single_pool", self.new_single_pool)
        add_command(self.local, console, "activate_single_pool", self.activate_single_pool)
        add_command(self.local, console, "withdraw_from_single_pool", self.withdraw_from_single_pool)
