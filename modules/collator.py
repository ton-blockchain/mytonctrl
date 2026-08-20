from __future__ import annotations

from modules.module import MtcModule
from mypylib import color_print, print_table
from mytoncore.utils import b642hex
from mytonctrl.console_cmd import (add_command, check_usage_args_lens, check_usage_args_min_len,
                                   check_usage_no_args, get_usage)
from mytonctrl.utils import pop_arg_from_args

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mytoncore import MyTonCore


class CollatorModule(MtcModule):

    description = 'Blocks collator-only module.'
    default_value = False


    def add_collator_to_vc(self, adnl_addr: str):
        self.local.add_log("start add_collator_to_vc function", "debug")
        result = self.ton.validatorConsole.run(f"add-collator {adnl_addr}")
        return result

    def setup_collator(self, args: list[str]):
        if not check_usage_args_lens("setup_collator", args, [0, 2]):
            return
        adnl_addr = pop_arg_from_args(args, '--adnl')
        if args:
            color_print("{red}Bad args. Usage:{endc} setup_collator " + get_usage("setup_collator"))
            return
        if adnl_addr is None:
            adnl_addr = self.ton.CreateNewKey()
        self.ton.add_adnl_addr(adnl_addr)
        res = self.add_collator_to_vc(adnl_addr)
        if 'successfully' not in res:
            raise Exception(f'Failed to enable collator: add-collator query failed: {res}')
        self.local.add_log(f'Collator enabled with ADNL address {adnl_addr}\n'
                           f'To add this collator to validator use command:\n'
                           f'`add_collator {adnl_addr}`')
        color_print("setup_collator - {green}OK{endc}")

    def stop_collator(self, args: list):
        if not check_usage_args_lens("stop_collator", args, [0, 1]):
            return
        if not args:
            text = "{red}WARNING: This action will stop and delete all local collation broadcasts from this node.{endc}\n"
            color_print(text)
            if input("Continue anyway? [Y/n]\n").strip().lower() not in ('y', ''):
                print('aborted.')
                return
            collators = self.get_collators()
            if not collators:
                print("No collators found")
                return
            errors = []
            for adnl_b64 in collators:
                res = self.ton.validatorConsole.run(f"del-collator {b642hex(adnl_b64).upper()}")
                if 'success' not in res.lower():
                    errors.append(res.strip())
            if errors:
                raise Exception(f"Failed to delete some collators: {'; '.join(errors)}")
            color_print("stop_collator - {green}OK{endc}")
            return

        res = self.ton.validatorConsole.run(f"del-collator {args[0]}")
        if 'successfully removed collator' not in res.lower():
            raise Exception(f'Failed to disable collator: del-collator query failed: {res}')
        color_print("stop_collator - {green}OK{endc}")

    def get_collators(self) -> list[str]:
        return self.ton.GetValidatorConfig()['collators']

    def print_collators(self, args: list[str]):
        collators = self.get_collators()
        if not collators:
            print("No collators found")
            return
        print("Collators list:")
        table = [['ADNL Address']]
        for adnl_b64 in collators:
            table.append([b642hex(adnl_b64).upper()])
        print_table(table)

    def add_validator_to_collation_wl(self, args: list):
        if not check_usage_args_min_len("add_validator_to_collation_wl", args, 1):
            return
        self.ton.validatorConsole.run("collator-whitelist-enable 1")
        self.local.add_log("Collation whitelist enabled")
        for adnl_addr in args:
            result = self.ton.validatorConsole.run(f"collator-whitelist-add {adnl_addr}")
            if 'success' not in result:
                raise Exception(f'Failed to add validator to collation whitelist: {result}')
        color_print("add_validator_to_collation_wl - {green}OK{endc}")

    def delete_validator_from_collation_wl(self, args: list):
        if not check_usage_args_min_len("delete_validator_from_collation_wl", args, 1):
            return
        for adnl_addr in args:
            result = self.ton.validatorConsole.run(f"collator-whitelist-del {adnl_addr}")
            if 'success' not in result:
                raise Exception(f'Failed to delete validator from collation whitelist: {result}')
        color_print("delete_validator_from_collation_wl - {green}OK{endc}")

    def disable_collation_validator_wl(self, args: list):
        if not check_usage_no_args("disable_collation_wl", args):
            return
        result = self.ton.validatorConsole.run("collator-whitelist-enable 0")
        if 'success' not in result:
            raise Exception(f'Failed to disable collation validator whitelist: {result}')
        color_print("disable_collation_validator_wl - {green}OK{endc}")

    def print_collation_validators_whitelist(self, args: list[str]):
        result = self.ton.validatorConsole.run('collator-whitelist-show')
        result = result.split('conn ready')[1].strip()
        print(result)

    @classmethod
    def check_enable(cls, ton: "MyTonCore"):
        if ton.using_validator():
            raise Exception('Cannot enable collator mode while validator mode is enabled. '
                            'Use `disable_mode validator` first.')

    def check_disable(self):
        have_collators_text = 'This node has active collator working. ' if self.get_collators() else ''
        text = (f"{{red}}WARNING: {have_collators_text}Collators registered on this node stay in the node config "
                f"and keep collating for validators that delegate to them until you remove them "
                f"with `stop_collator`. Make sure you know what you're doing.{{endc}}\n")
        color_print(text)
        if input("Continue anyway? [Y/n]\n").strip().lower() not in ('y', ''):
            raise Exception('aborted.')


    def add_console_commands(self, console):
        add_command(self.local, console, "setup_collator", self.setup_collator)
        add_command(self.local, console, "print_local_collators", self.print_collators)
        add_command(self.local, console, "add_validator_to_collation_wl", self.add_validator_to_collation_wl)
        add_command(self.local, console, "delete_validator_from_collation_wl", self.delete_validator_from_collation_wl)
        add_command(self.local, console, "disable_collation_wl", self.disable_collation_validator_wl)
        add_command(self.local, console, "print_collation_whitelist", self.print_collation_validators_whitelist)
        add_command(self.local, console, "stop_collator", self.stop_collator)
