import os
import shutil
import subprocess
import time

import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import color_print, ip2int, run_as_root, parse, MyPyClass
from mytoninstaller.config import get_own_ip


class BackupModule(MtcModule):

    def create_keyring(self, dir_name):
        keyring_dir = dir_name + '/keyring'
        self.ton.validatorConsole.Run(f'exportallprivatekeys {keyring_dir}')

    def create_tmp_ton_dir(self):
        result = self.ton.validatorConsole.Run("getconfig")
        text = parse(result, "---------", "--------")
        dir_name = self.ton.tempDir + f'/ton_backup_{int(time.time() * 1000)}'
        dir_name_db = dir_name + '/db'
        os.makedirs(dir_name_db)
        with open(dir_name_db + '/config.json', 'w') as f:
            f.write(text)
        self.create_keyring(dir_name_db)
        return dir_name

    @staticmethod
    def run_create_backup(args):
        backup_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/create_backup.sh')
        return subprocess.run(["bash", backup_script_path] + args, timeout=5)

    def create_backup(self, args):
        if len(args) > 1:
            color_print("{red}Bad args. Usage:{endc} create_backup [filename]")
            return
        tmp_dir = self.create_tmp_ton_dir()
        command_args = ["-m", self.ton.local.buffer.my_work_dir, "-t", tmp_dir]
        if len(args) == 1:
            command_args += ["-d", args[0]]
        process = self.run_create_backup(command_args)

        if process.returncode == 0:
            color_print("create_backup - {green}OK{endc}")
        else:
            color_print("create_backup - {red}Error{endc}")
        shutil.rmtree(tmp_dir)
        return process.returncode
    # end define

    @staticmethod
    def run_restore_backup(args):
        restore_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/restore_backup.sh')
        return run_as_root(["bash", restore_script_path] + args)

    def restore_backup(self, args):
        if len(args) == 0 or len(args) > 3:
            color_print("{red}Bad args. Usage:{endc} restore_backup <filename> [-y] [--skip-create-backup]")
            return
        if '-y' not in args:
            res = input(
                f'This action will overwrite existing configuration with contents of backup archive, please make sure that donor node is not in operation prior to this action. Proceed [y/n]')
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
            except:
                color_print("{red}Could not create backup{endc}")

        ip = str(ip2int(get_own_ip()))
        command_args = ["-m", self.ton.local.buffer.my_work_dir, "-n", args[0], "-i", ip]

        if self.run_restore_backup(command_args) == 0:
            self.ton.local.load_db()
            if self.ton.using_validator():
                from modules.btc_teleport import BtcTeleportModule
                BtcTeleportModule(self.ton, self.local).init(reinstall=True)
            color_print("restore_backup - {green}OK{endc}")
            self.local.exit()
        else:
            color_print("restore_backup - {red}Error{endc}")
    # end define

    def add_console_commands(self, console):
        console.AddItem("create_backup", self.create_backup, self.local.translate("create_backup_cmd"))
        console.AddItem("restore_backup", self.restore_backup, self.local.translate("restore_backup_cmd"))
