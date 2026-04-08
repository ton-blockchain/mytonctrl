from __future__ import annotations
import json
import time

from modules.btc_teleport import BtcTeleportModule
from mypylib.mypylib import Dict, color_print, get_timestamp
from modules.module import MtcModule
from mytoncore.utils import hex_shard_to_int, hex2b64
from mytonctrl.console_cmd import check_usage_two_args, add_command, check_usage_args_min_max_len

from mytonctrl.utils import timestamp2utcdatetime, GetColorInt, pop_arg_from_args, is_hex

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mytoncore import MyTonCore


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

    def find_myself(self, validators: list) -> Dict | None:
        adnl_addr = self.ton.GetAdnlAddr()
        for validator in validators:
            if validator.get("adnlAddr") == adnl_addr:
                return validator
        return None

    def check_efficiency(self, args):
        self.local.add_log("start GetValidatorEfficiency function", "debug")
        previous_validators = self.ton.GetValidatorsList(past=True)
        validators = self.ton.GetValidatorsList()
        validator = self.find_myself(previous_validators)
        config32 = self.ton.GetConfig32()
        config34 = self.ton.GetConfig34()
        color_print("{cyan}===[ Validator efficiency ]==={endc}")
        start_time = timestamp2utcdatetime(config32.startWorkTime)
        end_time = timestamp2utcdatetime(config32.endWorkTime)
        color_print(f"Previous round time: {{yellow}}from {start_time} to {end_time}{{endc}}")
        if validator:
            if validator.get('efficiency') is None:
                print('Failed to get efficiency for the previous round')
            elif validator.is_masterchain is False and validator.get('efficiency') != 0:
                print(f"Validator index is greater than {config32['mainValidators']} in the previous round - no efficiency data.")
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
        start_time = timestamp2utcdatetime(config34.startWorkTime)
        end_time = timestamp2utcdatetime(int(get_timestamp()))
        color_print(f"Current round time: {{green}}from {start_time} to {end_time}{{endc}}")
        if validator:
            if validator.is_masterchain is False and validator.efficiency != 0:
                print(f"Validator index is greater than {config34['mainValidators']} in the current round - no efficiency data.")
            elif (time.time() - config34.startWorkTime) / (config34.endWorkTime - config34.startWorkTime) < 0.8:
                print("The validation round has started recently, there is not enough data yet. "
                      "The efficiency evaluation will become more accurate towards the end of the round.")
            elif validator.get('efficiency') is None:
                print('Failed to get efficiency for the current round')
            else:
                efficiency = 100 if validator.efficiency > 100 else validator.efficiency
                color_efficiency = GetColorInt(efficiency, 90, logic="more", ending="%")
                created = validator.master_blocks_created
                expected = validator.master_blocks_expected
                color_print(f"Current round efficiency: {color_efficiency} {{yellow}}({created} blocks created / {round(expected, 1)} blocks expected){{endc}}")
        else:
            print("Couldn't find this validator in the current round")
    # end define

    def get_my_complaint(self):
        config32 = self.ton.GetConfig32()
        save_complaints = self.ton.GetSaveComplaints()
        complaints = save_complaints.get(str(config32['startWorkTime']))
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
        BtcTeleportModule(ton, ton.local).init()

    @staticmethod
    def _parse_collators_list(output: str) -> dict:
        result = {'shards': []}
        lines = output.strip().split('\n')
        current_shard = None
        for line in lines:
            line = line.strip()
            if line.startswith('Shard ('):
                shard_id = line.split('Shard (')[1].replace(',', ':').replace(')', '')
                current_shard = {
                    'shard_id': hex_shard_to_int(shard_id),
                    'self_collate': None,
                    'select_mode': None,
                    'collators': []
                }
                result['shards'].append(current_shard)
            elif line.startswith('Self collate = ') and current_shard:
                current_shard['self_collate'] = line.split('Self collate = ')[1] == 'true'
            elif line.startswith('Select mode = ') and current_shard:
                current_shard['select_mode'] = line.split('Select mode = ')[1]
            elif line.startswith('Collator ') and current_shard:
                collator_id = line.split('Collator ')[1]
                current_shard['collators'].append({'adnl_id': collator_id})
        return result

    def get_collators_list(self):
        result = self.ton.validatorConsole.Run('show-collators-list')
        if 'collators list is empty' in result:
            return {}
        return self._parse_collators_list(result)

    def set_collators_list(self, collators_list: dict):
        fname = self.ton.tempDir + '/collators_list.json'
        with open(fname, 'w') as f:
            f.write(json.dumps(collators_list))
        result = self.ton.validatorConsole.Run(f'set-collators-list {fname}')
        if 'success' not in result:
            raise Exception(f'Failed to set collators list: {result}')

    def add_collator(self, args: list):
        if not check_usage_args_min_max_len("add_collator", args, min_len=2, max_len=6):
            return
        adnl = args[0]
        shard = args[1]
        shard_id = hex_shard_to_int(shard)
        if is_hex(adnl):
            adnl = hex2b64(adnl)
        self_collate = pop_arg_from_args(args, '--self-collate') == 'true' if '--self-collate' in args else None
        select_mode = pop_arg_from_args(args, '--select-mode')
        if select_mode not in [None, 'random', 'ordered', 'round_robin']:
            color_print("{red}Bad args. Select mode must be one of: random, ordered, round_robin{endc}")
            return

        collators_list = self.get_collators_list()
        if 'shards' not in collators_list:
            collators_list['shards'] = []

        shard_exists = False
        for sh in collators_list['shards']:
            if sh['shard_id'] == shard_id:
                if any(c['adnl_id'] == adnl for c in sh['collators']):
                    raise Exception(f"Сollator {adnl} already exists in this shard {shard_id}.")
                sh['collators'].append({'adnl_id': adnl})
                shard_exists = True
                if self_collate is not None:
                    sh['self_collate'] = self_collate
                if select_mode is not None:
                    sh['select_mode'] = select_mode
        if not shard_exists:
            self_collate = self_collate if self_collate is not None else True
            select_mode = select_mode or 'random'
            self.local.add_log(f'Adding new shard {shard_id} to collators list. self_collate: {self_collate}, select_mode: {select_mode}', 'info')
            collators_list['shards'].append({
            'shard_id': shard_id,
            'self_collate': self_collate,
            'select_mode': select_mode,
            'collators': [{'adnl_id': adnl}]
        })
        self.set_collators_list(collators_list)
        color_print("add_collator - {green}OK{endc}")

    def delete_collator(self, args: list):
        if not check_usage_args_min_max_len("delete_collator", args, min_len=1, max_len=2):
            return

        shard_id = None
        if ':' in args[0]:
            shard_id = hex_shard_to_int(args[0])
            args.pop(0)
        adnl = args[0]
        if is_hex(adnl):
            adnl = hex2b64(adnl)

        collators_list = self.get_collators_list()
        if 'shards' not in collators_list or not collators_list['shards']:
            color_print("{red}No collators found.{endc}")
            return

        deleted = False
        for sh in collators_list['shards'].copy():
            if shard_id is None or sh['shard_id'] == shard_id:
                for c in sh['collators'].copy():
                    if c['adnl_id'] == adnl:
                        sh['collators'].remove(c)
                        self.local.add_log(f'Removing collator {adnl} from shard {sh["shard_id"]}', 'info')
                        if not sh['collators']:
                            collators_list['shards'].remove(sh)
                            self.local.add_log(f'Removing shard {sh["shard_id"]} from collators list because it has no collators left', 'info')
                        deleted = True
        if deleted:
            self.set_collators_list(collators_list)
        color_print("delete_collator - {green}OK{endc}")

    def get_collators_stats(self):
        output = self.ton.validatorConsole.Run('collation-manager-stats')
        if 'No stats' in output:
            return {}
        result = {}
        lines = output.split('\n')
        prev_line = lines[0].strip()
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('alive'):
                result[prev_line] = bool(int(line.split()[0].split('=')[1]))
            prev_line = line
        return result

    def print_collators(self, args: list):
        if '--json' in args:
            print(json.dumps(self.get_collators_list(), indent=2))
        else:
            result = self.ton.validatorConsole.Run('show-collators-list')
            result = result.split('conn ready')[1].strip()
            if 'collators list is empty' in result:
                print("No collators found")
                return
            collators_stats = self.get_collators_stats()
            for adnl, alive in collators_stats.items():
                if adnl in result:
                    status = '{green}online{endc}' if alive else '{red}offline{endc}'
                    result = result.replace(adnl, f"{adnl} ({status})")
            color_print(result)

    def reset_collators(self, args: list):
        if not self.get_collators_list():
            color_print("{red}No collators to reset.{endc}")
            return
        result = self.ton.validatorConsole.Run('clear-collators-list')
        if 'success' not in result:
            raise Exception(f'Failed to reset collators list: {result}')
        color_print("reset_collators - {green}OK{endc}")

    def add_console_commands(self, console):
        add_command(self.local, console, "vo", self.vote_offer)
        add_command(self.local, console, "ve", self.vote_election_entry)
        add_command(self.local, console, "vc", self.vote_complaint)
        add_command(self.local, console, "check_ef", self.check_efficiency)
        add_command(self.local, console, "add_collator", self.add_collator)
        add_command(self.local, console, "delete_collator", self.delete_collator)
        add_command(self.local, console, "print_collators", self.print_collators)
        add_command(self.local, console, "reset_collators", self.reset_collators)
