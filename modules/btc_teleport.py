import os
import subprocess

import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import run_as_root


class BtcTeleportModule(MtcModule):

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.keystore_path = self.ton.local.buffer.my_work_dir + '/btc_oracle_keystore'
        self.repo_name = 'ton-teleport-btc-periphery'
        self.src_dir = '/usr/src/' + f'/{self.repo_name}'
        self.bin_dir = self.src_dir + '/out'

    def create_env_file(self):
        env_path = self.bin_dir + '/.env'
        if os.path.exists(env_path):
            return

        text = f"""
COMMON_TON_CONFIG_URL=https://ton-blockchain.github.io/testnet-global.config.json
COMMON_TON_CONTRACT_COORDINATOR=EQAmHFjKpq3ecr3WqSY4w-qy6VHVVdjYH8kIRWq5xdwudIPC
ORACLE_STANDALONE_MODE=false
ORACLE_KEYSTORE_PATH={self.keystore_path}
ORACLE_VALIDATOR_ENGINE_CONSOLE_PATH={self.ton.validatorConsole.appPath}
ORACLE_SERVER_PUBLIC_KEY_PATH={self.ton.validatorConsole.pubKeyPath}
ORACLE_CLIENT_PRIVATE_KEY_PATH={self.ton.validatorConsole.privKeyPath}
ORACLE_VALIDATOR_SERVER_ADDR={self.ton.validatorConsole.addr}
"""
        with open(env_path, 'w') as f:
            f.write(text)

    def add_daemon(self):
        start = f'{self.bin_dir}/oracle'
        cmd = f'''import subprocess; import os; from mypylib.mypylib import add2systemd; add2systemd(name='btc_teleport', user=os.getlogin(), start='{start}', workdir='{self.bin_dir}'); subprocess.run(['systemctl', 'restart', 'btc_teleport'])'''
        run_as_root(['python3', '-c', cmd])

    def install(self):
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport1.sh')
        exit_code = run_as_root(["bash", script_path, "-s", '/usr/src', "-r", self.repo_name])
        if exit_code != 0:
            raise Exception('Failed to install btc_teleport')
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport2.sh')
        subprocess.run(["bash", script_path, "-s", self.src_dir])

    def init(self, reinstall=False):
        if os.path.exists(self.src_dir) and not reinstall:
            return
        self.local.add_log('Installing btc_teleport', 'info')
        os.makedirs(self.keystore_path, mode=0o700, exist_ok=True)
        self.install()
        self.create_env_file()
        self.add_daemon()
        self.local.add_log('Installed btc_teleport', 'info')

    def remove_btc_teleport(self, args: list):
        pass

    def add_console_commands(self, console):
        pass
