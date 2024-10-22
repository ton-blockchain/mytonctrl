import os
import subprocess

import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import add2systemd
from mytoninstaller.utils import start_service


class BtcTeleportModule(MtcModule):

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.keystore_path = os.path.abspath(self.ton.local.buffer.my_work_dir + '../btc_teleport/keystore/')
        os.makedirs(self.keystore_path, exist_ok=True)
        self.src_dir = '/usr/src/ton-teleport-btc-oracle/'

    def create_env_file(self):
        env_path = self.src_dir + '.env'
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

    @staticmethod
    def install_sources():
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport.sh')
        subprocess.run("bash", script_path)

    def add_daemon(self):
        add2systemd(name="btc_teleport", user=os.getlogin(), start="bun start", workdir=self.src_dir)
        start_service(self.local, "btc_teleport")

    def init(self):
        self.install_sources()
        self.create_env_file()
        self.add_daemon()

    def add_console_commands(self, console):
        pass
