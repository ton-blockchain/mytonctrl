import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import color_print, ip2int, run_as_root
from mytoninstaller.config import get_own_ip


class BackupModule(MtcModule):

    def create_backup(self, args):
        if len(args) > 2:
            color_print("{red}Bad args. Usage:{endc} create_backup [path_to_archive] [-y]")
            return
        if '-y' not in args:
            res = input(f'Mytoncore service will be stopped for few seconds while backup is created, Proceed [y/n]?')
            if res.lower() != 'y':
                print('aborted.')
                return
        else:
            args.pop(args.index('-y'))
        command_args = ["-m", self.ton.local.buffer.my_work_dir]
        if len(args) == 1:
            command_args += ["-d", args[0]]
        backup_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/create_backup.sh')
        if run_as_root(["bash", backup_script_path] + command_args) == 0:
            color_print("create_backup - {green}OK{endc}")
        else:
            color_print("create_backup - {red}Error{endc}")
    # end define

    def restore_backup(self, args):
        if len(args) == 0 or len(args) > 2:
            color_print("{red}Bad args. Usage:{endc} restore_backup <path_to_archive> [-y]")
            return
        if '-y' not in args:
            res = input(
                f'This action will overwrite existing configuration with contents of backup archive, please make sure that donor node is not in operation prior to this action. Proceed [y/n]')
            if res.lower() != 'y':
                print('aborted.')
                return
        else:
            args.pop(args.index('-y'))
        print('Before proceeding, mtc will create a backup of current configuration.')
        self.create_backup(['-y'])
        ip = str(ip2int(get_own_ip()))
        command_args = ["-m", self.ton.local.buffer.my_work_dir, "-n", args[0], "-i", ip]

        restore_script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/restore_backup.sh')
        if run_as_root(["bash", restore_script_path] + command_args) == 0:
            color_print("restore_backup - {green}OK{endc}")
            self.local.exit()
        else:
            color_print("restore_backup - {red}Error{endc}")
    # end define

    def add_console_commands(self, console):
        console.AddItem("create_backup", self.create_backup, self.local.translate("create_backup_cmd"))
        console.AddItem("restore_backup", self.restore_backup, self.local.translate("restore_backup_cmd"))
