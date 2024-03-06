import os

from mypylib.mypylib import color_print
from mytonctrl.modules.pool import PoolModule


class SingleNominatorModule(PoolModule):

    def new_single_pool(self, args):
        try:
            pool_name = args[0]
            owner_address = args[1]
        except:
            color_print("{red}Bad args. Usage:{endc} new_single_pool <pool-name> <owner_address>")
            return
        self.ton.create_single_pool(pool_name, owner_address)
        color_print("new_single_pool - {green}OK{endc}")

    def activate_single_pool(self, args):
        try:
            pool_name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} activate_single_pool <pool-name>")
            return
        pool = self.ton.GetLocalPool(pool_name)
        if not os.path.isfile(pool.bocFilePath):
            self.local.add_log(f"Pool {pool_name} already activated", "warning")
            return
        self.ton.activate_single_pool(pool)
        color_print("activate_single_pool - {green}OK{endc}")

    def add_console_commands(self, console):
        console.AddItem("new_single_pool", self.new_single_pool, self.local.translate("new_single_pool_cmd"))
        console.AddItem("activate_single_pool", self.activate_single_pool, self.local.translate("activate_single_pool_cmd"))
