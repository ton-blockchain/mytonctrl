import os

from modules.module import MtcModule

from mytonctrl.console_cmd import add_command
from mypylib.mypylib import run_as_root
from mytoncore.utils import get_package_resource_path


class BtcTeleportModule(MtcModule):

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.keystore_path = self.ton.local.my_work_dir + '/btc_oracle_keystore'
        self.repo_name = 'ton-teleport-btc-periphery'
        self.src_root = str(self.ton.get_paths().src_dir)
        self.src_dir = os.path.join(self.src_root, self.repo_name)

    @staticmethod
    def run_remove_btc_teleport(args):
        with get_package_resource_path('mytonctrl', 'scripts/remove_btc_teleport.sh') as script_path:
            return run_as_root(["bash", str(script_path)] + args)

    def remove_btc_teleport(self, _):
        exit_code = self.run_remove_btc_teleport(["-s", self.src_dir, "-k", self.keystore_path])
        if exit_code != 0:
            raise Exception('Failed to remove btc_teleport')
        self.local.add_log('Removed btc_teleport', 'info')

    def add_console_commands(self, console):
        add_command(self.local, console, "remove_btc_teleport", self.remove_btc_teleport)
