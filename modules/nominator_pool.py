import os

from mypylib.mypylib import color_print
from modules.pool import PoolModule
from mytoncore.models import Pool
from mytonctrl.argtypes import TonAddress
from mypyconsole.command_parser import Annotated, Arg

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mytoncore.mytoncore import MyTonCore


class NominatorPoolModule(PoolModule):

    description = 'Standard nominator pool - DEPRECATED'
    default_value = False

    @classmethod
    def check_enable(cls, ton: "MyTonCore"):
        ton.local.add_log("nominator-pool (v1) mode is deprecated, use nominator-pool-v2 for new pools", "warning")

    def do_create_pool(self, pool_name, validator_reward_share_percent, max_nominators_count, min_validator_stake,
                       min_nominator_stake):
        self.ton.local.add_log("start CreatePool function", "debug")
        validator_reward_share = int(validator_reward_share_percent * 100)

        self.check_download_pool_contract_scripts()

        file_path = self.ton.poolsDir + pool_name
        if os.path.isfile(file_path + ".addr"):
            self.ton.local.add_log("CreatePool warning: Pool already exists: " + file_path, "warning")
            return

        fift_script = self.ton.contractsDir + "nominator-pool/func/new-pool.fif"
        wallet = self.ton.GetValidatorWallet()
        args = [fift_script, wallet.addrB64, validator_reward_share, max_nominators_count, min_validator_stake,
                min_nominator_stake, file_path]
        result = self.ton.fift.run(args)
        if "Saved pool" not in result:
            raise Exception("CreatePool error: " + result)

        pools = self.ton.GetPools()
        new_pool = self.ton.GetLocalPool(pool_name)
        for pool in pools:
            if pool.name != new_pool.name and pool.addrB64 == new_pool.addrB64:
                new_pool.delete()
                raise Exception("CreatePool error: Pool with the same parameters already exists.")

    def new_pool(
        self,
        pool_name: str,
        validator_reward_share_percent: Annotated[float, Arg(help="validator's share of the reward, in percent")],
        max_nominators_count: int,
        min_validator_stake: Annotated[int, Arg(help="in TON")],
        min_nominator_stake: Annotated[int, Arg(help="in TON")],
    ) -> None:
        self.do_create_pool(pool_name, validator_reward_share_percent, max_nominators_count, min_validator_stake, min_nominator_stake)
        color_print("NewPool - {green}OK{endc}")

    def do_activate_pool(self, pool: Pool, ex=True):
        self.ton.local.add_log("start ActivatePool function", "debug")
        account = self.ton.GetAccount(pool.addrB64)
        if account.status == "empty":
            raise Exception("do_activate_pool error: account status is empty")
        elif account.status == "active":
            self.local.add_log("do_activate_pool warning: account status is active", "warning")
        else:
            validator_wallet = self.ton.GetValidatorWallet()
            self.ton.check_account_active(validator_wallet.addrB64)
            self.ton.SendFile(pool.bocFilePath, timeout=False, remove=False)

    def activate_pool(self, pool_name: str) -> None:
        pool = self.ton.GetLocalPool(pool_name)
        self.do_activate_pool(pool)
        color_print("ActivatePool - {green}OK{endc}")

    def update_validator_set(self, pool_addr: TonAddress) -> None:
        wallet = self.ton.GetValidatorWallet()
        self.ton.PoolUpdateValidatorSet(pool_addr, wallet)
        color_print("UpdateValidatorSet - {green}OK{endc}")

    def do_deposit_to_pool(self, pool_addr, amount):
        wallet = self.ton.GetValidatorWallet()
        bocPath = self.ton.local.my_temp_dir + wallet.name + "validator-deposit-query.boc"
        fiftScript = self.ton.contractsDir + "nominator-pool/func/validator-deposit.fif"
        args = [fiftScript, bocPath]
        self.ton.fift.run(args)
        resultFilePath = self.ton.SignBocWithWallet(wallet, bocPath, pool_addr, amount)
        self.ton.SendFile(resultFilePath, wallet)

    def deposit_to_pool(self, pool_addr: TonAddress, amount: float) -> None:
        self.do_deposit_to_pool(pool_addr, amount)
        color_print("DepositToPool - {green}OK{endc}")

    def do_withdraw_from_pool(self, pool_addr, amount):
        pool_data = self.ton.GetPoolData(pool_addr)
        if pool_data["state"] == 0:
            self.ton.WithdrawFromPoolProcess(pool_addr, amount)
        else:
            self.ton.PendWithdrawFromPool(pool_addr, amount)

    def withdraw_from_pool(self, pool_addr: TonAddress, amount: float) -> None:
        self.do_withdraw_from_pool(pool_addr, amount)
        color_print("WithdrawFromPool - {green}OK{endc}")

    def add_console_commands(self, console):
        console.add_command("new_pool", self.new_pool)
        console.add_command("activate_pool", self.activate_pool)
        console.add_command("update_validator_set", self.update_validator_set)
        console.add_command("withdraw_from_pool", self.withdraw_from_pool)
        console.add_command("deposit_to_pool", self.deposit_to_pool)
