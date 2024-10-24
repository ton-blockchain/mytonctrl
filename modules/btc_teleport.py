import os
import subprocess

import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import run_as_root


class BtcTeleportModule(MtcModule):

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.workdir = os.path.abspath(self.ton.local.buffer.my_work_dir + '../btc_teleport')
        self.keystore_path = self.workdir + '/keystore'
        self.repo_name = 'ton-teleport-btc-oracle'
        self.src_dir = self.workdir + f'/{self.repo_name}'

    def create_env_file(self):
        env_path = self.src_dir + '/.env'
        if os.path.exists(env_path):
            return

        text = f"""
STANDALONE=0
TON_CENTER_V2_ENDPOINT=http://127.0.0.1:8801
COORDINATOR=EQDIEVARwkn6_4qNWeDlHwT40kzJBGIzKo4vcqRSvDUUS6bT
VALIDATOR_SERVER_ADDRESS={self.ton.validatorConsole.addr}
KEYSTORE_DIR={self.keystore_path}
SERVER_PUBLIC_KEY_PATH={self.ton.validatorConsole.pubKeyPath}
CLIENT_PRIVATE_KEY_PATH={self.ton.validatorConsole.privKeyPath}
VALIDATOR_ENGINE_CONSOLE_PATH={self.ton.validatorConsole.appPath}
"""
        with open(env_path, 'w') as f:
            f.write(text)

    def install(self):
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport.sh')
        subprocess.run(["bash", script_path, "-s", self.workdir, "-r", self.repo_name])

    def init(self, reinstall=False):
        if os.path.exists(self.src_dir) and not reinstall:
            return
        os.makedirs(self.keystore_path, exist_ok=True)
        os.makedirs(self.workdir, exist_ok=True)
        self.install()
        self.create_env_file()

    def add_console_commands(self, console):
        pass
