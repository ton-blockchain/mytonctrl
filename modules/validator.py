from __future__ import annotations
import base64
import json
import time

import requests

from mypylib.mypylib import color_print, get_timestamp, print_table
from modules.module import MtcModule
from mytoncore.utils import b642hex, hex2b64
from mytoncore.models import ValidatorConfig
from mytonctrl.console_cmd import (add_command, check_usage, check_usage_args_len,
                                   check_usage_args_min_max_len, check_usage_one_arg, check_usage_two_args)

from mytonctrl.utils import timestamp2utcdatetime, GetColorInt, pop_arg_from_args, is_hex

from typing import TYPE_CHECKING, Sequence, TypeVar

if TYPE_CHECKING:
    from mytoncore import MyTonCore


X = TypeVar("X", bound=ValidatorConfig)


class ValidatorModule(MtcModule):

    description = ('Validator functions. Activates participating in elections and staking. '
                   'If pools and l/s modes are disabled stakes from validator wallet.')

    default_value = True

    def vote_offer(self, args):
        if not check_usage_args_min_max_len("vo", args, min_len=1, max_len=1000):
            return
        offers = self.ton.GetOffers()
        for offer_hash in args:
            offer = self.ton.GetOffer(offer_hash, offers)
            self.ton.add_save_offer(offer)
        for offer_hash in args:
            offer = self.ton.GetOffer(offer_hash, offers)
            self.ton.VoteOffer(offer)
        color_print("VoteOffer - {green}OK{endc}")

    def run_elections(self):
        use_pool = self.ton.using_pool()
        use_liquid_staking = self.ton.using_liquid_staking()
        if use_pool:
            self.ton.PoolsUpdateValidatorSet()
        if use_liquid_staking:
            self.ton.ControllersUpdateValidatorSet()
        self.ton.RecoverStake()
        if self.ton.using_validator():
            self.ton.ElectionEntry()

    def vote_election_entry(self, args):
        self.run_elections()
        color_print("VoteElectionEntry - {green}OK{endc}")

    def vote_complaint(self, args):
        if not check_usage_two_args("vc", args):
            return
        election_id = args[0]
        complaint_hash = args[1]
        self.ton.VoteComplaint(election_id, complaint_hash)
        color_print("VoteComplaint - {green}OK{endc}")

    def find_myself(self, validators: Sequence[X]) -> X | None:
        adnl_addr = self.ton.GetAdnlAddr()
        for validator in validators:
            if validator.adnl_addr == adnl_addr:
                return validator
        return None

    def check_efficiency(self, args):
        self.local.add_log("start GetValidatorEfficiency function", "debug")
        previous_validators = []
        try:
            previous_validators = self.ton.GetValidatorsList(past=True)
        except Exception as e:
            self.local.add_log(f"Failed to get validators list: {e}", "error")
        validators = []
        try:
            validators = self.ton.GetValidatorsList()
        except Exception as e:
            self.local.add_log(f"Failed to get validators list: {e}", "error")
        validator = self.find_myself(previous_validators)
        config32 = self.ton.get_config_32()
        config34 = self.ton.get_config_34()
        color_print("{cyan}===[ Validator efficiency ]==={endc}")
        start_time = timestamp2utcdatetime(config32.start_work_time)
        end_time = timestamp2utcdatetime(config32.end_work_time)
        color_print(f"Previous round time: {{yellow}}from {start_time} to {end_time}{{endc}}")
        if validator:
            if not validator.is_masterchain:
                print(f"Validator index is greater than {config32.main_validators} in the previous round - no efficiency data.")
            else:
                efficiency = 100 if validator.efficiency > 100 else validator.efficiency
                color_efficiency = GetColorInt(efficiency, 90, logic="more", ending="%")
                created = validator.master_blocks_created
                expected = validator.master_blocks_expected
                if created is None:  # there is no updated prev round info in cache
                    created = validator.blocks_created
                    expected = validator.blocks_expected
                color_print(f"Previous round efficiency: {color_efficiency} {{yellow}}({created} blocks created / {round(expected, 1)} blocks expected){{endc}}")
        else:
            print("Couldn't find this validator in the previous round")
        validator = self.find_myself(validators)
        start_time = timestamp2utcdatetime(config34.start_work_time)
        end_time = timestamp2utcdatetime(int(get_timestamp()))
        color_print(f"Current round time: {{green}}from {start_time} to {end_time}{{endc}}")
        if validator:
            if not validator.is_masterchain:
                print(f"Validator index is greater than {config34.main_validators} in the current round - no efficiency data.")
            elif (time.time() - config34.start_work_time) / (config34.end_work_time - config34.start_work_time) < 0.8:
                print("The validation round has started recently, there is not enough data yet. "
                      "The efficiency evaluation will become more accurate towards the end of the round.")
            else:
                efficiency = 100 if validator.efficiency > 100 else validator.efficiency
                color_efficiency = GetColorInt(efficiency, 90, logic="more", ending="%")
                created = validator.master_blocks_created
                expected = validator.master_blocks_expected
                color_print(f"Current round efficiency: {color_efficiency} {{yellow}}({created} blocks created / {round(expected, 1)} blocks expected){{endc}}")
        else:
            print("Couldn't find this validator in the current round")

    def get_my_complaint(self):
        config32 = self.ton.get_config_32()
        save_complaints = self.ton.GetSaveComplaints()
        complaints = save_complaints.get(str(config32.start_work_time))
        if not complaints:
            return
        for c in complaints.values():
            if c["adnl"] == self.ton.GetAdnlAddr() and c["isPassed"]:
                return c

    @classmethod
    def check_enable(cls, ton: "MyTonCore"):
        if ton.using_liteserver():
            raise Exception('Cannot enable validator mode while liteserver mode is enabled. '
                            'Use `disable_mode liteserver` first.')
        if ton.using_collator():
            raise Exception('Cannot enable validator mode while collator mode is enabled. '
                            'Use `disable_mode collator` first.')

    @staticmethod
    def _parse_collators_list(output: str) -> dict:
        result = {'collators': [], 'register_collators': [], 'disable_self_collate': False}
        for line in output.strip().split('\n'):
            line = line.strip()
            if line.startswith('Register collator '):
                result['register_collators'].append({'adnl_id': line.split('Register collator ')[1]})
            elif line.startswith('Collator '):
                result['collators'].append({'adnl_id': line.split('Collator ')[1]})
            elif line.startswith('Disable self collate = '):
                result['disable_self_collate'] = line.split('Disable self collate = ')[1] == 'true'
        return result

    def get_collators_list(self) -> dict:
        result = self.ton.validatorConsole.run('show-collators-list')
        if 'unknown command' in result:
            raise Exception('node does not support collators list commands (old node version)')
        if 'collators list is empty' in result:
            return {}
        return self._parse_collators_list(result)

    def set_collators_list(self, collators_list: dict):
        fname = self.ton.tempDir + '/collators_list.json'
        with open(fname, 'w') as f:
            f.write(json.dumps(collators_list))
        result = self.ton.validatorConsole.run(f'set-collators-list {fname}')
        if 'success' not in result:
            raise Exception(f'Failed to set collators list: {result}')

    def add_collator(self, args: list):
        if not check_usage_args_min_max_len("add_collator", args, min_len=1, max_len=3):
            return
        self_collate = pop_arg_from_args(args, '--self-collate')
        if self_collate not in (None, 'true', 'false'):
            color_print("{red}Bad args. Self collate must be one of: true, false{endc}")
            return
        if not check_usage_args_len("add_collator", args, 1):
            return
        adnl = args[0]
        if is_hex(adnl):
            adnl = hex2b64(adnl)

        collators_list = self.get_collators_list()
        collators = collators_list.setdefault('collators', [])
        collators_list.setdefault('register_collators', [])
        collators_list.setdefault('disable_self_collate', False)
        if any(c['adnl_id'] == adnl for c in collators):
            raise Exception(f"Сollator {adnl} already exists in the collators list.")
        collators.append({'adnl_id': adnl})
        if self_collate is not None:
            collators_list['disable_self_collate'] = self_collate == 'false'
        self.local.add_log(f'Adding collator {adnl} to collators list. '
                           f'self_collate: {not collators_list["disable_self_collate"]}', 'info')
        self.set_collators_list(collators_list)
        color_print("add_collator - {green}OK{endc}")

    def add_register_collator(self, args: list):
        if not check_usage_one_arg("add_register_collator", args):
            return
        adnl = args[0]
        if is_hex(adnl):
            adnl = hex2b64(adnl)

        collators_list = self.get_collators_list()
        collators_list.setdefault('collators', [])
        register_collators = collators_list.setdefault('register_collators', [])
        collators_list.setdefault('disable_self_collate', False)
        if any(c['adnl_id'] == adnl for c in register_collators):
            raise Exception(f"Сollator {adnl} already exists in the register collators list.")
        register_collators.append({'adnl_id': adnl})
        self.local.add_log(f'Adding collator {adnl} to register collators list', 'info')
        self.set_collators_list(collators_list)
        color_print("add_register_collator - {green}OK{endc}")

    def _delete_collator(self, args: list, name: str, key: str):
        if not check_usage_one_arg(name, args):
            return

        adnl = args[0]
        if is_hex(adnl):
            adnl = hex2b64(adnl)

        collators_list = self.get_collators_list()
        if not collators_list.get(key):
            color_print("{red}No collators found.{endc}")
            return

        deleted = False
        for c in collators_list[key].copy():
            if c['adnl_id'] == adnl:
                collators_list[key].remove(c)
                self.local.add_log(f'Removing collator {adnl} from {key}', 'info')
                deleted = True
        if deleted:
            self.set_collators_list(collators_list)
        color_print(f"{name} - {{green}}OK{{endc}}")

    def delete_collator(self, args: list):
        self._delete_collator(args, "delete_collator", "collators")

    def delete_register_collator(self, args: list):
        self._delete_collator(args, "delete_register_collator", "register_collators")

    def set_self_collate(self, args: list):
        if not check_usage_one_arg("set_self_collate", args):
            return
        if args[0] not in ('true', 'false'):
            color_print("{red}Bad args. Self collate must be one of: true, false{endc}")
            return
        collators_list = self.get_collators_list()
        collators_list.setdefault('collators', [])
        collators_list.setdefault('register_collators', [])
        collators_list['disable_self_collate'] = args[0] == 'false'
        self.set_collators_list(collators_list)
        color_print("set_self_collate - {green}OK{endc}")

    @staticmethod
    def _print_collators_table(collators: list):
        table = [['ADNL Address']]
        for c in collators:
            table.append([b642hex(c['adnl_id']).upper()])
        print_table(table)

    def print_collators(self, args: list):
        collators_list = self.get_collators_list()
        if '--json' in args:
            print(json.dumps(collators_list, indent=2))
            return
        collators = collators_list.get('collators')
        register_collators = collators_list.get('register_collators')
        if not collators and not register_collators:
            print("No collators found")
        if collators:
            print("Collators list:")
            self._print_collators_table(collators)
        if register_collators:
            print("Register collators list:")
            self._print_collators_table(register_collators)
        print(f"Self collate: {not collators_list.get('disable_self_collate', False)}")

    def reset_collators(self, args: list):
        if not self.get_collators_list():
            color_print("{red}No collators to reset.{endc}")
            return
        result = self.ton.validatorConsole.run('clear-collators-list')
        if 'success' not in result:
            raise Exception(f'Failed to reset collators list: {result}')
        color_print("reset_collators - {green}OK{endc}")

    def get_default_collators_list(self) -> list[str] | None:
        network = self.ton.GetNetworkName()
        if network == 'unknown':
            return None
        prefix = 'testnet-' if network == 'testnet' else ''
        default_url = f'https://ton-blockchain.github.io/{prefix}collators-list.json'
        url = self.ton.local.db.get('defaultCollatorsUrl', default_url)
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        config = resp.json()
        if not isinstance(config, dict) or not isinstance(config.get('collators'), list):
            raise ValueError(f"Malformed remote config from {url}: {config}")
        result: list[str] = []
        for item in config['collators']:
            try:
                adnl_id = item['adnl_id']
                if len(base64.b64decode(adnl_id, validate=True)) != 32:
                    raise ValueError('adnl_id must be 32 bytes')
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"Could not parse adnl_id in the remote config: {item}: {config}") from e
            if adnl_id not in result:
                result.append(adnl_id)
        return result

    def apply_default_collators(self) -> None:
        if not self.ton.using_validator():
            return
        if not self.ton.local.db.get('useDefaultCollators', True):
            return
        default_collators = self.get_default_collators_list()
        if not default_collators:
            return
        collators_list = self.get_collators_list()
        existing = {c['adnl_id'] for c in collators_list.get('collators', [])}
        to_add = [adnl for adnl in default_collators if adnl not in existing]
        if not to_add:
            return
        collators = collators_list.setdefault('collators', [])
        collators_list.setdefault('register_collators', [])
        collators_list.setdefault('disable_self_collate', False)
        for adnl in to_add:
            collators.append({'adnl_id': adnl})
        self.set_collators_list(collators_list)
        self.local.add_log(f'apply_default_collators: added {len(to_add)} default collators: {to_add}', 'info')

    def update_collators_list(self, args: list):
        if not check_usage("update_collators_list", args, lambda x: x in ([], ['--force'])):
            return
        force = bool(args)

        default_collators = self.get_default_collators_list()
        if default_collators is None:
            raise Exception('Could not get default collators list')

        collators_list = self.get_collators_list()
        existing = [c['adnl_id'] for c in collators_list.get('collators', [])]

        if not force:
            to_add = [adnl for adnl in default_collators if adnl not in existing]
            to_remove = [adnl for adnl in existing if adnl not in default_collators]
            color_print("{red}WARNING: This action will overwrite the collators list of this validator "
                        "with the default collators list.{endc}\n")
            if to_remove:
                print(f"Collators to be removed ({len(to_remove)}):")
                self._print_collators_table([{'adnl_id': adnl} for adnl in to_remove])
            if to_add:
                print(f"Collators to be added ({len(to_add)}):")
                self._print_collators_table([{'adnl_id': adnl} for adnl in to_add])
            if input("Continue anyway? [Y/n]\n").strip().lower() not in ('y', ''):
                print('aborted.')
                return

        collators_list['collators'] = [{'adnl_id': adnl} for adnl in default_collators]
        collators_list.setdefault('register_collators', [])
        collators_list.setdefault('disable_self_collate', False)
        self.set_collators_list(collators_list)
        self.local.add_log(f'update_collators_list: set {len(default_collators)} default collators: '
                           f'{default_collators}', 'info')
        color_print("update_collators_list - {green}OK{endc}")

    def add_console_commands(self, console):
        add_command(self.local, console, "vo", self.vote_offer)
        add_command(self.local, console, "ve", self.vote_election_entry)
        add_command(self.local, console, "vc", self.vote_complaint)
        add_command(self.local, console, "check_ef", self.check_efficiency)
        add_command(self.local, console, "add_collator", self.add_collator)
        add_command(self.local, console, "delete_collator", self.delete_collator)
        add_command(self.local, console, "add_register_collator", self.add_register_collator)
        add_command(self.local, console, "delete_register_collator", self.delete_register_collator)
        add_command(self.local, console, "set_self_collate", self.set_self_collate)
        add_command(self.local, console, "print_collators", self.print_collators)
        add_command(self.local, console, "reset_collators", self.reset_collators)
        add_command(self.local, console, "update_collators_list", self.update_collators_list)
