import os
import time

from mypylib.mypylib import color_print
from modules.pool import PoolModule


class NominatorPoolModule(PoolModule):

    description = 'Standard nominator pools.'
    default_value = False

    def do_create_pool(self, pool_name, validator_reward_share_percent, max_nominators_count, min_validator_stake,
                       min_nominator_stake):
        self.ton.local.add_log("start CreatePool function", "debug")
        validator_reward_share = int(validator_reward_share_percent * 100)

        self.check_download_pool_contract_scripts()

        file_path = self.ton.poolsDir + pool_name
        if os.path.isfile(file_path + ".addr"):
            self.ton.local.add_log("CreatePool warning: Pool already exists: " + file_path, "warning")
            return
        # end if

        fift_script = self.ton.contractsDir + "nominator-pool/func/new-pool.fif"
        wallet = self.ton.GetValidatorWallet()
        args = [fift_script, wallet.addrB64, validator_reward_share, max_nominators_count, min_validator_stake,
                min_nominator_stake, file_path]
        result = self.ton.fift.Run(args)
        if "Saved pool" not in result:
            raise Exception("CreatePool error: " + result)
        # end if

        pools = self.ton.GetPools()
        new_pool = self.ton.GetLocalPool(pool_name)
        for pool in pools:
            if pool.name != new_pool.name and pool.addrB64 == new_pool.addrB64:
                new_pool.Delete()
                raise Exception("CreatePool error: Pool with the same parameters already exists.")
        # end for
    # end define

    def new_pool(self, args):
        try:
            pool_name = args[0]
            validator_reward_share_percent = float(args[1])
            max_nominators_count = int(args[2])
            min_validator_stake = int(args[3])
            min_nominator_stake = int(args[4])
        except:
            color_print("{red}Bad args. Usage:{endc} new_pool <pool-name> <validator-reward-share-percent> <max-nominators-count> <min-validator-stake> <min-nominator-stake>")
            return
        self.do_create_pool(pool_name, validator_reward_share_percent, max_nominators_count, min_validator_stake, min_nominator_stake)
        color_print("NewPool - {green}OK{endc}")

    def do_activate_pool(self, pool, ex=True):
        self.ton.local.add_log("start ActivatePool function", "debug")
        for i in range(10):
            time.sleep(3)
            account = self.ton.GetAccount(pool.addrB64)
            if account.balance > 0:
                self.ton.SendFile(pool.bocFilePath, pool, timeout=False)
                return
        if ex:
            raise Exception("ActivatePool error: time out")

    def activate_pool(self, args):
        try:
            pool_name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} activate_pool <pool-name>")
            return
        pool = self.ton.GetLocalPool(pool_name)
        if not os.path.isfile(pool.bocFilePath):
            self.local.add_log(f"Pool {pool_name} already activated", "warning")
            return
        self.do_activate_pool(pool)
        color_print("ActivatePool - {green}OK{endc}")

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

    def update_validator_set(self, args):
        try:
            pool_addr = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} update_validator_set <pool-addr>")
            return
        wallet = self.ton.GetValidatorWallet()
        self.ton.PoolUpdateValidatorSet(pool_addr, wallet)
        color_print("UpdateValidatorSet - {green}OK{endc}")

    def add_console_commands(self, console):
        console.AddItem("new_pool", self.new_pool, self.local.translate("new_pool_cmd"))
        console.AddItem("activate_pool", self.activate_pool, self.local.translate("activate_pool_cmd"))
        console.AddItem("deposit_to_pool", self.deposit_to_pool, self.local.translate("deposit_to_pool_cmd"))
        console.AddItem("withdraw_from_pool", self.withdraw_from_pool, self.local.translate("withdraw_from_pool_cmd"))
        console.AddItem("update_validator_set", self.update_validator_set, self.local.translate("update_validator_set_cmd"))


