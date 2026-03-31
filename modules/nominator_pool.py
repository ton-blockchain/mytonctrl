import os

from mypylib.mypylib import color_print
from modules.pool import PoolModule
from mytonctrl.console_cmd import add_command, check_usage_one_arg, check_usage_two_args, check_usage_args_len


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

    def new_pool(self, args):
        if not check_usage_args_len("new_pool", args, 5):
            return
        pool_name = args[0]
        try:
            validator_reward_share_percent = float(args[1])
            max_nominators_count = int(args[2])
            min_validator_stake = int(args[3])
            min_nominator_stake = int(args[4])
        except ValueError:
            color_print("{red}Bad args types. validator_reward_share_percent=float, counts/stakes=int{endc}")
            return
        self.do_create_pool(pool_name, validator_reward_share_percent, max_nominators_count, min_validator_stake, min_nominator_stake)
        color_print("NewPool - {green}OK{endc}")

    def do_activate_pool(self, pool, ex=True):
        self.ton.local.add_log("start ActivatePool function", "debug")
        account = self.ton.GetAccount(pool.addrB64)
        if account.status == "empty":
            raise Exception("do_activate_pool error: account status is empty")
        elif account.status == "active":
            self.local.add_log("do_activate_pool warning: account status is active", "warning")
        else:
            validator_wallet = self.ton.GetValidatorWallet()
            self.ton.check_account_active(validator_wallet.addrB64)
            self.ton.SendFile(pool.bocFilePath, pool, timeout=False, remove=False)
    #end define

    def activate_pool(self, args):
        if not check_usage_one_arg("activate_pool", args):
            return
        pool_name = args[0]
        pool = self.ton.GetLocalPool(pool_name)
        self.do_activate_pool(pool)
        color_print("ActivatePool - {green}OK{endc}")

    def update_validator_set(self, args):
        if not check_usage_one_arg("update_validator_set", args):
            return
        pool_addr = args[0]
        wallet = self.ton.GetValidatorWallet()
        self.ton.PoolUpdateValidatorSet(pool_addr, wallet)
        color_print("UpdateValidatorSet - {green}OK{endc}")

    def do_deposit_to_pool(self, pool_addr, amount):
        wallet = self.ton.GetValidatorWallet()
        bocPath = self.ton.local.my_temp_dir + wallet.name + "validator-deposit-query.boc"
        fiftScript = self.ton.contractsDir + "nominator-pool/func/validator-deposit.fif"
        args = [fiftScript, bocPath]
        self.ton.fift.Run(args)
        resultFilePath = self.ton.SignBocWithWallet(wallet, bocPath, pool_addr, amount)
        self.ton.SendFile(resultFilePath, wallet)

    def deposit_to_pool(self, args):
        if not check_usage_two_args("deposit_to_pool", args):
            return
        pool_addr = args[0]
        try:
            amount = float(args[1])
        except ValueError:
            color_print("{red}Amount must be a number{endc}")
            return
        self.do_deposit_to_pool(pool_addr, amount)
        color_print("DepositToPool - {green}OK{endc}")

    def do_withdraw_from_pool(self, pool_addr, amount):
        pool_data = self.ton.GetPoolData(pool_addr)
        if pool_data["state"] == 0:
            self.ton.WithdrawFromPoolProcess(pool_addr, amount)
        else:
            self.ton.PendWithdrawFromPool(pool_addr, amount)

    def withdraw_from_pool(self, args):
        if not check_usage_two_args("withdraw_from_pool", args):
            return
        pool_addr = args[0]
        try:
            amount = float(args[1])
        except ValueError:
            color_print("{red}Amount must be a number{endc}")
            return
        self.do_withdraw_from_pool(pool_addr, amount)
        color_print("WithdrawFromPool - {green}OK{endc}")

    def add_console_commands(self, console):
        add_command(self.local, console, "new_pool", self.new_pool)
        add_command(self.local, console, "activate_pool", self.activate_pool)
        add_command(self.local, console, "update_validator_set", self.update_validator_set)
        add_command(self.local, console, "withdraw_from_pool", self.withdraw_from_pool)
        add_command(self.local, console, "deposit_to_pool", self.deposit_to_pool)
