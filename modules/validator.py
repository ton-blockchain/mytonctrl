import time

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
        offers = self.ton.GetOffers()
        for offer_hash in args:
            offer = self.ton.GetOffer(offer_hash, offers)
            self.ton.add_save_offer(offer)
        for offer_hash in args:
            offer = self.ton.GetOffer(offer_hash, offers)
            self.ton.VoteOffer(offer)
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
    # end define

    def add_console_commands(self, console):
        console.AddItem("vo", self.vote_offer, self.local.translate("vo_cmd"))
        console.AddItem("ve", self.vote_election_entry, self.local.translate("ve_cmd"))
        console.AddItem("vc", self.vote_complaint, self.local.translate("vc_cmd"))
        console.AddItem("check_ef", self.check_efficiency, self.local.translate("check_ef_cmd"))
