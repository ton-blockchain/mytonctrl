import json
import os
import time
from typing import Optional, Union

from mypylib.mypylib import color_print, print_table
from mytonctrl.argtypes import TonAddress
from mypyconsole.command_parser import Annotated, Arg

from modules.module import MtcModule


class ControllerModule(MtcModule):

    description = 'Liquid staking controllers.'
    default_value = False

    def do_create_controllers(self):
        new_controllers = self.ton.GetControllers()
        old_controllers = self.ton.local.db.get("using_controllers", list())
        if new_controllers == old_controllers:
            return

        self.ton.local.add_log("start CreateControllers function", "debug")
        wallet = self.ton.GetValidatorWallet()
        liquid_pool_addr = self.ton.GetLiquidPoolAddr()
        contract_path = self.ton.contractsDir + "jetton_pool/"
        if not os.path.isdir(contract_path):
            self.ton.DownloadContract("https://github.com/igroman787/jetton_pool")

        file_name0 = contract_path + "fift-scripts/deploy_controller0.boc"
        file_name1 = contract_path + "fift-scripts/deploy_controller1.boc"
        result_file_path0 = self.ton.SignBocWithWallet(wallet, file_name0, liquid_pool_addr, 1)
        self.ton.SendFile(result_file_path0, wallet)
        time.sleep(10)
        result_file_path1 = self.ton.SignBocWithWallet(wallet, file_name1, liquid_pool_addr, 1)
        self.ton.SendFile(result_file_path1, wallet)

        self.ton.local.db["old_controllers"] = old_controllers
        self.ton.local.db["using_controllers"] = new_controllers
        self.ton.local.save()

    def create_controllers(self) -> None:
        self.do_create_controllers()
        color_print("CreateControllers - {green}OK{endc}")

    def print_controllers_list(self) -> None:
        new_controllers = self.ton.GetControllers()
        using_controllers = self.ton.GetSettings("using_controllers")
        old_controllers = self.ton.GetSettings("old_controllers")
        user_controllers_list = self.ton.GetSettings("user_controllers_list")
        print("using controllers:")
        if using_controllers is not None:
            self.print_controllers_list_process(using_controllers)
        if new_controllers is not None and new_controllers != using_controllers:
            print()
            print("new controllers:")
            self.print_controllers_list_process(new_controllers)
        if old_controllers is not None and len(old_controllers) > 0:
            print()
            print("old controllers:")
            self.print_controllers_list_process(old_controllers)
        if user_controllers_list is not None and len(user_controllers_list) > 0:
            print()
            print("user controllers:")
            self.print_controllers_list_process(user_controllers_list)

    def print_controllers_list_process(self, controllers):
        table = list()
        table += [["Address", "Status", "Balance", "Approved", "State"]]
        for controllerAddr in controllers:
            account = self.ton.GetAccount(controllerAddr)
            try:
                controller_data = self.ton.GetControllerData(controllerAddr)
            except Exception:
                controller_data = None
            approved = True if controller_data and controller_data["approved"] == -1 else False
            state = controller_data["state"] if controller_data else None
            table += [[controllerAddr, account.status, account.balance, approved, state]]
        print_table(table)

    def get_controller_data(self, controller_addr: TonAddress) -> None:
        controller_data = self.ton.GetControllerData(controller_addr)
        print(json.dumps(controller_data, indent=4))

    def do_deposit_to_controller(self, controller_addr, amount):
        self.ton.local.add_log("start DepositToController function", "debug")
        wallet = self.ton.GetValidatorWallet()
        file_name = self.ton.contractsDir + "jetton_pool/fift-scripts/top-up.boc"
        result_file_path = self.ton.SignBocWithWallet(wallet, file_name, controller_addr, amount)
        self.ton.SendFile(result_file_path, wallet)

    def deposit_to_controller(
        self,
        controller_addr: TonAddress,
        amount: Annotated[float, Arg(help="amount in TON")],
    ) -> None:
        self.do_deposit_to_controller(controller_addr, amount)

    def withdraw_from_controller(
        self,
        controller_addr: TonAddress,
        amount: Annotated[Optional[str], Arg(help="amount in TON, default: the balance minus 10.1 TON")] = None,
    ) -> None:
        self.ton.WithdrawFromController(controller_addr, amount)

    def calculate_annual_controller_percentage(
        self,
        percent_per_round: Annotated[Optional[float], Arg(help="default: the max_interest_percent setting")] = None,
    ) -> None:
        percent: float = (
            percent_per_round
            if percent_per_round is not None
            else self.ton.local.db.get("max_interest_percent", 1.5)
        )
        config15 = self.ton.get_config_15()
        roundPeriod = config15.validators_elected_for
        rounds = 365 * 24 * 3600 / roundPeriod
        yearInterest = (1 + percent / 100) * rounds
        yearInterestPercent = round(yearInterest / 100, 2)
        print("roundPeriod", roundPeriod)
        print("rounds", rounds)
        print("percentPerRound", percent)
        print("yearInterest", yearInterest)
        print(f"yearInterestPercent: {yearInterestPercent}%")

    def controller_update_validator_set(self, controller_addr: TonAddress) -> None:
        self.ton.ControllerUpdateValidatorSet(controller_addr)
        color_print("ControllerUpdateValidatorSet - {green}OK{endc}")

    def do_stop_controller(self, controller_addr):
        stop_controllers_list = self.ton.local.db.get("stop_controllers_list")
        if stop_controllers_list is None:
            stop_controllers_list = list()
        if controller_addr not in stop_controllers_list:
            stop_controllers_list.append(controller_addr)
        self.ton.local.db["stop_controllers_list"] = stop_controllers_list

        user_controllers = self.ton.local.db.get("user_controllers")
        if user_controllers is not None and controller_addr in user_controllers:
            user_controllers.remove(controller_addr)
        self.ton.local.save()

    def stop_controller(self, controller_addr: TonAddress) -> None:
        self.do_stop_controller(controller_addr)
        color_print("StopController - {green}OK{endc}")

    def stop_and_withdraw_controller(
        self,
        controller_addr: TonAddress,
        amount: Annotated[Optional[str], Arg(help="amount in TON, default: the balance minus 10.1 TON")] = None,
    ) -> None:
        withdraw_amount: Union[str, float, None] = amount
        if withdraw_amount is None:
            account = self.ton.GetAccount(controller_addr)
            withdraw_amount = account.balance - 10.1
        self.do_stop_controller(controller_addr)
        self.ton.WithdrawFromController(controller_addr, withdraw_amount)
        color_print("StopAndWithdrawController - {green}OK{endc}")

    def do_add_controller(self, controller_addr):
        user_controllers = self.ton.local.db.get("user_controllers")
        if user_controllers is None:
            user_controllers = list()
        if controller_addr not in user_controllers:
            user_controllers.append(controller_addr)
        self.ton.local.db["user_controllers"] = user_controllers

        stop_controllers_list = self.ton.local.db.get("stop_controllers_list")
        if stop_controllers_list is not None and controller_addr in stop_controllers_list:
            stop_controllers_list.remove(controller_addr)
        self.ton.local.save()

    def add_controller(self, controller_addr: TonAddress) -> None:
        self.do_add_controller(controller_addr)
        color_print("AddController - {green}OK{endc}")

    def do_calculate_loan_amount_test(self):
        min_loan = self.ton.local.db.get("min_loan", 41000)
        max_loan = self.ton.local.db.get("max_loan", 43000)
        max_interest_percent = self.ton.local.db.get("max_interest_percent", 1.5)
        max_interest = int(max_interest_percent / 100 * 16777216)
        return self.ton.calculate_loan_amount(min_loan, max_loan, max_interest)

    def calculate_loan_amount_test(self) -> None:
        t = self.do_calculate_loan_amount_test()
        print(t)

    def add_console_commands(self, console):
        console.add_command("create_controllers", self.create_controllers)
        console.add_command("update_controllers", self.create_controllers)
        console.add_command("controllers_list", self.print_controllers_list)
        console.add_command("get_controller_data", self.get_controller_data)
        console.add_command("deposit_to_controller", self.deposit_to_controller)
        console.add_command("withdraw_from_controller", self.withdraw_from_controller)
        console.add_command("calculate_annual_controller_percentage", self.calculate_annual_controller_percentage)
        console.add_command("controller_update_validator_set", self.controller_update_validator_set)
        console.add_command("stop_controller", self.stop_controller)
        console.add_command("stop_and_withdraw_controller", self.stop_and_withdraw_controller)
        console.add_command("add_controller", self.add_controller)
        console.add_command("test_calculate_loan_amount", self.calculate_loan_amount_test)
