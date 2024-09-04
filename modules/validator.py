from mypylib.mypylib import color_print, get_timestamp
from modules.module import MtcModule
from mytonctrl.utils import timestamp2utcdatetime, GetColorInt


class ValidatorModule(MtcModule):

    description = ('Validator functions. Activates participating in elections and staking. '
                   'If pools and l/s modes are disabled stakes from validator wallet.')

    default_value = True

    def vote_offer(self, args):
        if len(args) == 0:
            color_print("{red}Bad args. Usage:{endc} vo <offer-hash>")
            return
        for offerHash in args:
            self.ton.VoteOffer(offerHash)
        color_print("VoteOffer - {green}OK{endc}")

    def vote_election_entry(self, args):
        from mytoncore.functions import Elections
        Elections(self.ton.local, self.ton)
        color_print("VoteElectionEntry - {green}OK{endc}")

    def vote_complaint(self, args):
        try:
            election_id = args[0]
            complaint_hash = args[1]
        except:
            color_print("{red}Bad args. Usage:{endc} vc <election-id> <complaint-hash>")
            return
        self.ton.VoteComplaint(election_id, complaint_hash)
        color_print("VoteComplaint - {green}OK{endc}")

    def find_myself(self, validators: list) -> dict:
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
        if validator:
            if validator.get('efficiency') is None:
                print('Failed to get efficiency for the past round')
            else:
                efficiency = 100 if validator.efficiency > 100 else validator.efficiency
                color_efficiency = GetColorInt(efficiency, 90, logic="more", ending="%")
                created = validator.blocks_created
                expected = validator.blocks_expected
                start_time = timestamp2utcdatetime(config32.startWorkTime)
                end_time = timestamp2utcdatetime(config32.endWorkTime)
                color_print(f"Previous round efficiency: {color_efficiency} {{yellow}}({created} blocks created / {expected} blocks expected){{endc}}")
                color_print(f"Previous round time: {{yellow}}from {start_time} to {end_time}{{endc}}")
        else:
            print("Couldn't find this validator in the past round")
        validator = self.find_myself(validators)
        if validator:
            if validator.get('efficiency') is None:
                print('Failed to get efficiency for the current round')
            else:
                efficiency = 100 if validator.efficiency > 100 else validator.efficiency
                color_efficiency = GetColorInt(efficiency, 90, logic="more", ending="%")
                created = validator.blocks_created
                expected = validator.blocks_expected
                start_time = timestamp2utcdatetime(config34.startWorkTime)
                end_time = timestamp2utcdatetime(int(get_timestamp()))
                if not validator.is_masterchain and efficiency < 90:
                    print("Your validator index is greater than 100.")
                    print("Efficiency until the validation round is complete may be inaccurate and not displayed.")
                else:
                    color_print(f"Current round efficiency: {color_efficiency} {{yellow}}({created} blocks created / {expected} blocks expected){{endc}}")
                    color_print(f"Current round time: {{green}}from {start_time} to {end_time}{{endc}}")
        else:
            print("Couldn't find this validator in the current round")
    # end define

    def add_console_commands(self, console):
        console.AddItem("vo", self.vote_offer, self.local.translate("vo_cmd"))
        console.AddItem("ve", self.vote_election_entry, self.local.translate("ve_cmd"))
        console.AddItem("vc", self.vote_complaint, self.local.translate("vc_cmd"))
        console.AddItem("check_ef", self.check_efficiency, self.local.translate("check_ef_cmd"))
