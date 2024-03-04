import json
from mypylib.mypylib import color_print, print_table

from ..utils import GetItemFromList
from .module import MtcModule


class ControllerModule(MtcModule):

    def create_controllers(self, args):
        self.ton.CreateControllers()
        color_print("CreateControllers - {green}OK{endc}")

    def print_controllers_list(self, args):
        new_controllers = self.ton.GetControllers()
        using_controllers = self.ton.GetSettings("using_controllers")
        old_controllers = self.ton.GetSettings("old_controllers")
        user_controllers_list = self.ton.GetSettings("user_controllers_list")
        print("using controllers:")
        self.print_controllers_list_process(using_controllers)
        if new_controllers != using_controllers:
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
            controllerData = self.ton.GetControllerData(controllerAddr)
            approved = True if controllerData and controllerData["approved"] == -1 else False
            state = controllerData["state"] if controllerData else None
            table += [[controllerAddr, account.status, account.balance, approved, state]]
        print_table(table)

    def get_controller_data(self, args):
        try:
            controller_addr = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} get_controller_data <controller-addr>")
            return
        controller_data = self.ton.GetControllerData(controller_addr)
        print(json.dumps(controller_data, indent=4))

    def deposit_to_controller(self, args):
        try:
            controller_addr = args[0]
            amount = float(args[1])
        except:
            color_print("{red}Bad args. Usage:{endc} deposit_to_controller <controller-addr> <amount>")
            return
        self.ton.DepositToController(controller_addr, amount)

    def withdraw_from_controller(self, args):
        try:
            controller_addr = args[0]
            amount = GetItemFromList(args, 1)
        except:
            color_print("{red}Bad args. Usage:{endc} withdraw_from_controller <controller-addr> [amount]")
            return
        self.ton.WithdrawFromController(controller_addr, amount)

    def calculate_annual_controller_percentage(self, args):
        try:
            percent_per_round = float(args[0])
        except:
            percent_per_round = self.ton.GetSettings("max_interest_percent")
        config15 = self.ton.GetConfig(15)
        roundPeriod = config15["validators_elected_for"]
        rounds = 365 * 24 * 3600 / roundPeriod
        yearInterest = (1 + percent_per_round / 100) * rounds
        yearInterestPercent = round(yearInterest / 100, 2)
        print("roundPeriod", roundPeriod)
        print("rounds", rounds)
        print("percentPerRound", percent_per_round)
        print("yearInterest", yearInterest)
        print(f"yearInterestPercent: {yearInterestPercent}%")

    def controller_update_validator_set(self, args):
        try:
            controller_addr = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} controller_update_validator_set <controller-addr>")
            return
        self.ton.ControllerUpdateValidatorSet(controller_addr)
        color_print("ControllerUpdateValidatorSet - {green}OK{endc}")

    def stop_controller(self, args):
        try:
            controller_addr = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} stop_controller <controller-addr>")
            return
        self.ton.StopController(controller_addr)
        color_print("StopController - {green}OK{endc}")

    def stop_and_withdraw_controller(self, args):
        try:
            controller_addr = args[0]
            amount = GetItemFromList(args, 1)
        except:
            color_print("{red}Bad args. Usage:{endc} stop_and_withdraw_controller <controller-addr> [amount]")
            return
        if amount is None:
            account = self.ton.GetAccount(controller_addr)
            amount = account.balance - 10.1
        self.ton.StopController(controller_addr)
        self.ton.WithdrawFromController(controller_addr, amount)
        color_print("StopAndWithdrawController - {green}OK{endc}")

    def add_controller(self, args):
        try:
            controller_addr = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} add_controller <controller-addr>")
            return
        self.ton.AddController(controller_addr)
        color_print("AddController - {green}OK{endc}")

    def check_liquid_pool(self, args):
        self.ton.CheckLiquidPool()
        color_print("CheckLiquidPool - {green}OK{endc}")

    def calculate_loan_amount_test(self, args):
        t = self.ton.CalculateLoanAmount_test()
        print(t)

    def add_console_commands(self, console):
        console.AddItem("create_controllers", self.create_controllers, self.local.translate("_"))
        console.AddItem("update_controllers", self.create_controllers, self.local.translate("_"))
        console.AddItem("controllers_list", self.print_controllers_list, self.local.translate("_"))
        console.AddItem("get_controller_data", self.get_controller_data, self.local.translate("_"))
        console.AddItem("deposit_to_controller", self.deposit_to_controller, self.local.translate("_"))
        console.AddItem("withdraw_from_controller", self.withdraw_from_controller, self.local.translate("_"))
        console.AddItem("calculate_annual_controller_percentage", self.calculate_annual_controller_percentage, self.local.translate("_"))
        console.AddItem("controller_update_validator_set", self.controller_update_validator_set, self.local.translate("_"))
        console.AddItem("stop_controller", self.stop_controller, self.local.translate("_"))
        console.AddItem("stop_and_withdraw_controller", self.stop_and_withdraw_controller, self.local.translate("_"))
        console.AddItem("add_controller", self.add_controller, self.local.translate("_"))
        console.AddItem("check_liquid_pool", self.check_liquid_pool, self.local.translate("_"))
        console.AddItem("test_calculate_loan_amount", self.calculate_loan_amount_test, self.local.translate("_"))
