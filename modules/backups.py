import os
import shutil
import subprocess
import time
from typing import Optional

from modules.module import MtcModule
from mytonctrl.console_cmd import add_command, check_usage_args_min_max_len
from mypylib.mypylib import color_print, ip2int, run_as_root, parse
from mytoncore.utils import get_package_resource_path
from mytonctrl.utils import get_current_user, pop_user_from_args
from mytoninstaller.config import get_own_ip


class BackupModule(MtcModule):

    def create_keyring(self, dir_name: str):
        keyring_dir = dir_name + '/keyring'
        self.ton.validatorConsole.Run(f'exportallprivatekeys {keyring_dir}')

    def create_tmp_ton_dir(self):
        result = self.ton.validatorConsole.Run("getconfig")
        text = parse(result, "---------", "--------")
        if text is None:
            raise Exception("Could not get config from validator-console")
        dir_name = self.ton.tempDir + f'/ton_backup_{int(time.time() * 1000)}'
        dir_name_db = dir_name + '/db'
        os.makedirs(dir_name_db)
        with open(dir_name_db + '/config.json', 'w') as f:
            f.write(text)
        self.create_keyring(dir_name_db)
        return dir_name

    @staticmethod
    def run_create_backup(args, user: Optional[str] = None):
        if user is None:
            user = get_current_user()
        with get_package_resource_path('mytonctrl', 'scripts/create_backup.sh') as backup_script_path:
            return subprocess.run(["bash", backup_script_path, "-u", user] + args, timeout=5)

    def create_backup(self, args):
        if not check_usage_args_min_max_len("create_backup", args, 0, 3):
            return
        tmp_dir = self.create_tmp_ton_dir()
        command_args = ["-m", self.ton.local.my_work_dir, "-t", tmp_dir]
        user = pop_user_from_args(args)
        if len(args) == 1:
            command_args += ["-d", args[0]]
        process = self.run_create_backup(command_args, user=user)

        if process.returncode == 0:
            color_print("create_backup - {green}OK{endc}")
        else:
            color_print("create_backup - {red}Error{endc}")
        shutil.rmtree(tmp_dir)
        return process.returncode

    @staticmethod
    def run_restore_backup(args, user: Optional[str] = None):
        if user is None:
            user = get_current_user()
        with get_package_resource_path('mytonctrl', 'scripts/restore_backup.sh') as restore_script_path:
            return run_as_root(["bash", restore_script_path, "-u", user] + args)

    def restore_backup(self, args):
        if not check_usage_args_min_max_len('restore_backup', args, 1, 5):
            return
        user = pop_user_from_args(args)
        if '-y' not in args:
            res = input(
                'This action will overwrite existing configuration with contents of backup archive, please make sure that donor node is not in operation prior to this action. Proceed [y/n]')
            if res.lower() != 'y':
                print('aborted.')
                return
        else:
            args.pop(args.index('-y'))
        if '--skip-create-backup' in args:
            args.pop(args.index('--skip-create-backup'))
        else:
            print('Before proceeding, mtc will create a backup of current configuration.')
            try:
                self.create_backup([])
            except Exception as e:
                color_print(f"{{red}}Could not create backup: {e}{{endc}}")

        ip = str(ip2int(get_own_ip()))
        command_args = ["-m", self.ton.local.my_work_dir, "-n", args[0], "-i", ip]

        if self.run_restore_backup(command_args, user=user) == 0:
            self.ton.local.load_db()
            if self.ton.using_validator():
                from modules.btc_teleport import BtcTeleportModule
                BtcTeleportModule(self.ton, self.local).init(reinstall=True)
            color_print("restore_backup - {green}OK{endc}")
            self.local.exit()
        else:
            color_print("restore_backup - {red}Error{endc}")

    def add_console_commands(self, console):
        add_command(self.local, console, "create_backup", self.create_backup)
        add_command(self.local, console, "restore_backup", self.restore_backup)
