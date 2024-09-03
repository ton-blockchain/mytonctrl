from mypylib.mypylib import color_print, get_timestamp
from modules.module import MtcModule
from mytonctrl.mytonctrl import GetColorInt
from mytonctrl.utils import timestamp2utcdatetime


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
        validators = self.ton.GetValidatorsList(past=True)
        validator = self.find_myself(validators)
        config32 = self.ton.GetConfig32()
        if validator:
            efficiency = GetColorInt(validator["efficiency"], 90, logic="more", ending=" %")
            expected = validator['blocks_expected']
            created = validator['blocks_created']
            print('#' * 30)
            print(
                f"Previous round efficiency: {efficiency} ({created} blocks created / {expected} blocks expected) from {timestamp2utcdatetime(config32['startWorkTime'])} to {timestamp2utcdatetime(config32['endWorkTime'])}")
            print('#' * 30)
        else:
            print("Couldn't find this validator in the past round")
        validators = self.ton.GetValidatorsList()
        validator = self.find_myself(validators)
        config34 = self.ton.GetConfig34()
        if validator:
            efficiency = GetColorInt(validator["efficiency"], 90, logic="more", ending=" %")
            expected = validator['blocks_expected']
            created = validator['blocks_created']
            print('#' * 30)
            print(
                f"Current round efficiency: {efficiency} ({created} blocks created / {expected} blocks expected) from {timestamp2utcdatetime(config34['startWorkTime'])} to {timestamp2utcdatetime(int(get_timestamp()))}")
            print('#' * 30)
        else:
            print("Couldn't find this validator in the current round")

    # end define

    def add_console_commands(self, console):
        console.AddItem("vo", self.vote_offer, self.local.translate("vo_cmd"))
        console.AddItem("ve", self.vote_election_entry, self.local.translate("ve_cmd"))
        console.AddItem("vc", self.vote_complaint, self.local.translate("vc_cmd"))
        console.AddItem("check_ef", self.check_efficiency, self.local.translate("check_ef_cmd"))
