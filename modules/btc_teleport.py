import os
import subprocess

import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import run_as_root, color_print


class BtcTeleportModule(MtcModule):

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.keystore_path = self.ton.local.buffer.my_work_dir + '/btc_oracle_keystore'
        self.repo_name = 'ton-teleport-btc-periphery'
        self.src_dir = '/usr/src/' + f'/{self.repo_name}'
        self.bin_dir = self.src_dir + '/out'

    def create_local_file(self):
        from mytoninstaller.mytoninstaller import CreateLocalConfigFile
        CreateLocalConfigFile(self.local, [])

    def create_env_file(self, reinit=False):
        env_path = self.bin_dir + '/.env'
        if os.path.exists(env_path) and not reinit:
            return
        self.create_local_file()
        config_path = "/usr/bin/ton/local.config.json"
        if not os.path.exists(config_path):
            config_path = 'https://ton.org/global-config.json'
            warning_text = f"""
WARNING: Could not create local config file. Using global config file ({config_path}).
Please try to create local config file (`mytonctrl <<< "installer clcf"`) and update its path in {env_path} and restart 
btc teleport service (`systemctl restart btc_teleport`) or contact validators support. 
"""
            self.local.add_log(warning_text, 'warning')
        text = f"""
COMMON_TON_CONFIG={config_path}
COMMON_TON_CONTRACT_COORDINATOR=EQD43RtdAQ_Y8nl86SqzxjlL_-rAvdZiBDk_s7OTF-oRxmwo
ORACLE_STANDALONE_MODE=false
ORACLE_KEYSTORE_PATH={self.keystore_path}
ORACLE_VALIDATOR_ENGINE_CONSOLE_PATH={self.ton.validatorConsole.appPath}
ORACLE_SERVER_PUBLIC_KEY_PATH={self.ton.validatorConsole.pubKeyPath}
ORACLE_CLIENT_PRIVATE_KEY_PATH={self.ton.validatorConsole.privKeyPath}
ORACLE_VALIDATOR_SERVER_ADDR={self.ton.validatorConsole.addr}
API_CALL_TIMEOUT=30
LOG_FILE=/var/log/btc_teleport/btc_teleport.log
"""
        with open(env_path, 'w') as f:
            f.write(text)

    def add_daemon(self):
        start = f'{self.bin_dir}/oracle'
        script_path = pkg_resources.resource_filename('mytoninstaller', 'scripts/add2systemd.sh')
        user = os.environ.get("USER", "root")
        run_as_root(['bash', script_path, '-n', 'btc_teleport', '-u', user, '-g', user, '-s', start, '-w', self.bin_dir])

    def install(self, branch):
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport1.sh')
        exit_code = run_as_root(["bash", script_path, "-s", '/usr/src', "-r", self.repo_name, "-b", branch])
        if exit_code != 0:
            raise Exception('Failed to install btc_teleport')
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport2.sh')
        subprocess.run(["bash", script_path, "-s", self.src_dir])

    def init(self, reinstall=False, branch: str = 'master'):
        if os.path.exists(self.src_dir) and not reinstall:
            return
        self.local.add_log('Installing btc_teleport', 'info')
        os.makedirs(self.keystore_path, mode=0o700, exist_ok=True)
        self.install(branch)
        self.create_env_file()
        self.add_daemon()
        self.local.add_log('Installed btc_teleport', 'info')

    @staticmethod
    def run_remove_btc_teleport(args):
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/remove_btc_teleport.sh')
        return run_as_root(["bash", script_path] + args)

    def remove_btc_teleport(self, args: list):
        if len(args) > 1:
            color_print("{red}Bad args. Usage:{endc} remove_btc_teleport [--force]")
            return
        if '--force' not in args:
            if -1 < self.ton.GetValidatorIndex() < self.ton.GetConfig34()['mainValidators']:
                self.local.add_log('You can not remove btc_teleport on working masterchain validator', 'error')
                return
        exit_code = self.run_remove_btc_teleport(["-s", self.src_dir, "-k", self.keystore_path])
        if exit_code != 0:
            raise Exception('Failed to remove btc_teleport')
        self.local.add_log('Removed btc_teleport', 'info')

    def add_console_commands(self, console):
        console.AddItem("remove_btc_teleport", self.remove_btc_teleport, self.local.translate("remove_btc_teleport_cmd"))
