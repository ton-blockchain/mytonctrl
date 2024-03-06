import os

from mypylib.mypylib import color_print
from mytonctrl.modules.pool import PoolModule


class NominatorPoolModule(PoolModule):

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
        self.ton.CreatePool(pool_name, validator_reward_share_percent, max_nominators_count, min_validator_stake, min_nominator_stake)
        color_print("NewPool - {green}OK{endc}")

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
        self.ton.ActivatePool(pool)
        color_print("ActivatePool - {green}OK{endc}")

    def deposit_to_pool(self, args):
        try:
            poll_addr = args[0]
            amount = float(args[1])
        except:
            color_print("{red}Bad args. Usage:{endc} deposit_to_pool <pool-addr> <amount>")
            return
        self.ton.DepositToPool(poll_addr, amount)
        color_print("DepositToPool - {green}OK{endc}")

    def withdraw_from_pool(self, args):
        try:
            pool_addr = args[0]
            amount = float(args[1])
        except:
            color_print("{red}Bad args. Usage:{endc} withdraw_from_pool <pool-addr> <amount>")
            return
        self.ton.WithdrawFromPool(pool_addr, amount)
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


