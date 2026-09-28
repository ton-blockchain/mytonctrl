import json
import os
import shutil
import subprocess
import time
from typing import Optional

from modules.module import MtcModule
from mypyconsole.command_parser import Annotated, Arg
from mypylib.mypylib import color_print, ip2int, run_as_root, parse
from mytoncore.utils import get_package_resource_path
from mytonctrl.utils import get_current_user
from mytoninstaller.config import get_own_ip
from mytoninstaller.settings import update_client_path_settings


class BackupModule(MtcModule):

    def create_keyring(self, dir_name: str):
        keyring_dir = dir_name + '/keyring'
        self.ton.validatorConsole.run(f'exportallprivatekeys {keyring_dir}')

    def create_collators_list(self, dir_name: str):
        from modules.validator import ValidatorModule
        try:
            collators_list = ValidatorModule(self.ton, self.local).get_collators_list()
        except Exception as e:
            self.local.add_log(f'Failed to get collators list, skipping it in backup: {e}', 'warning')
            return
        with open(dir_name + '/collators-list.json', 'w') as f:
            json.dump(collators_list, f, indent=4)

    def create_tmp_ton_dir(self):
        result = self.ton.validatorConsole.run("getconfig")
        text = parse(result, "---------", "--------")
        if text is None:
            raise Exception("Could not get config from validator-console")
        dir_name = self.ton.tempDir + f'/ton_backup_{int(time.time() * 1000)}'
        dir_name_db = dir_name + '/db'
        os.makedirs(dir_name_db)
        with open(dir_name_db + '/config.json', 'w') as f:
            f.write(text)
        self.create_keyring(dir_name_db)
        self.create_collators_list(dir_name_db)
        return dir_name

    @staticmethod
    def run_create_backup(args, user: Optional[str] = None, as_root: bool = False) -> int:
        if user is None:
            user = get_current_user()
        with get_package_resource_path('mytonctrl', 'scripts/create_backup.sh') as backup_script_path:
            command = ["bash", str(backup_script_path), "-u", user] + args
            if as_root:
                return run_as_root(command)
            return subprocess.run(command, timeout=30).returncode

    def create_backup(
        self,
        dest: Annotated[Optional[str], Arg(help="archive path, default: mytonctrl_backup_<hostname>_<timestamp>.tar.gz in the current directory")] = None,
        *,
        user: Annotated[Optional[str], Arg("-u", help="owner of the archive (default: current user)")] = None,
        from_host: Annotated[bool, Arg(help="copy the node's db and keys from disk as root instead of exporting them through validator-console")] = False,
    ) -> int:
        paths = self.ton.get_paths()
        if from_host:
            tmp_dir = None
            source_args = ["-b", str(paths.ton_db)]
        else:
            tmp_dir = self.create_tmp_ton_dir()
            source_args = ["-t", tmp_dir]
        command_args = ["-m", self.ton.local.my_work_dir] + source_args + ["-k", str(paths.ton_keys)]
        if dest is not None:
            command_args += ["-d", dest]
        exit_code = self.run_create_backup(command_args, user=user, as_root=from_host)

        if exit_code == 0:
            color_print("create_backup - {green}OK{endc}")
        else:
            color_print("create_backup - {red}Error{endc}")
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir)
        return exit_code

    @staticmethod
    def run_restore_backup(args, user: Optional[str] = None):
        if user is None:
            user = get_current_user()
        with get_package_resource_path('mytonctrl', 'scripts/restore_backup.sh') as restore_script_path:
            return run_as_root(["bash", str(restore_script_path), "-u", user] + args)

    def restore_backup(
        self,
        filename: str,
        *,
        yes: Annotated[bool, Arg("-y", help="do not ask for confirmation")] = False,
        skip_create_backup: Annotated[bool, Arg("-s", help="skip creation of backup")] = False,
        user: Annotated[Optional[str], Arg("-u", help="owner of the restored files (default: current user)")] = None,
    ) -> None:
        if not yes:
            res = input(
                'This action will overwrite existing configuration with contents of backup archive, please make sure that donor node is not in operation prior to this action. Proceed [y/n]')
            if res.lower() != 'y':
                print('aborted.')
                return
        if not skip_create_backup:
            print('Before proceeding, mtc will create a backup of current configuration.')
            try:
                self.create_backup(dest=None, user=None, from_host=False)
            except Exception as e:
                color_print(f"{{red}}Could not create backup: {e}{{endc}}")

        ip = str(ip2int(get_own_ip()))
        command_args = ["-m", self.ton.local.my_work_dir, "-n", filename, "-i", ip, "-t", str(self.ton.get_paths().ton_work)]
        paths = self.ton.local.db.get("paths")

        if self.run_restore_backup(command_args, user=user) == 0:
            self.ton.local.load_db()
            # the restored db may carry the donor's paths — keep this installation's ones
            if paths is not None:
                self.ton.local.db["paths"] = paths
            else:
                self.ton.local.db.pop("paths", None)
            update_client_path_settings(self.ton.local.db, self.ton.get_paths())
            self.ton.local.save()
            # the restore script started mytoncore with the donor's settings
            run_as_root(["systemctl", "restart", "mytoncore"])
            color_print("restore_backup - {green}OK{endc}")
            self.local.exit()
        else:
            color_print("restore_backup - {red}Error{endc}")

    def add_console_commands(self, console):
        console.add_command("create_backup", self.create_backup)
        console.add_command("restore_backup", self.restore_backup)
