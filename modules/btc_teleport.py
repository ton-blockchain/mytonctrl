import json
import os
import subprocess

import pkg_resources

from modules.module import MtcModule
from mypylib.mypylib import run_as_root, color_print, bcolors, print_table


class BtcTeleportModule(MtcModule):

    COORDINATOR_ADDRESS = 'EQD43RtdAQ_Y8nl86SqzxjlL_-rAvdZiBDk_s7OTF-oRxmwo'
    CONFIGURATOR_ADDRESS = 'EQAFmcPeyXxpBsX7Y-fuGyDz3tvIMeMr5EXi9WuvFzgGPZSz'

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.keystore_path = self.ton.local.buffer.my_work_dir + '/btc_oracle_keystore'
        self.repo_name = 'ton-teleport-btc-periphery'
        self.src_dir = '/usr/src/' + f'/{self.repo_name}'
        self.bin_dir = self.src_dir + '/out'

    def create_local_file(self):
        from mytoninstaller.mytoninstaller import CreateLocalConfigFile
        CreateLocalConfigFile(self.local, [])

    def create_env_file(self, reinit=False):
        env_path = self.bin_dir + '/.env'
        if os.path.exists(env_path) and not reinit:
            return
        self.create_local_file()
        config_path = "/usr/bin/ton/local.config.json"
        if not os.path.exists(config_path):
            config_path = 'https://ton.org/global-config.json'
            warning_text = f"""
WARNING: Could not create local config file. Using global config file ({config_path}).
Please try to create local config file (`mytonctrl <<< "installer clcf"`) and update its path in {env_path} and restart 
btc teleport service (`systemctl restart btc_teleport`) or contact validators support. 
"""
            self.local.add_log(warning_text, 'warning')
        text = f"""
COMMON_TON_CONFIG={config_path}
COMMON_TON_CONTRACT_COORDINATOR={self.COORDINATOR_ADDRESS}
ORACLE_STANDALONE_MODE=false
ORACLE_KEYSTORE_PATH={self.keystore_path}
ORACLE_VALIDATOR_ENGINE_CONSOLE_PATH={self.ton.validatorConsole.appPath}
ORACLE_SERVER_PUBLIC_KEY_PATH={self.ton.validatorConsole.pubKeyPath}
ORACLE_CLIENT_PRIVATE_KEY_PATH={self.ton.validatorConsole.privKeyPath}
ORACLE_VALIDATOR_SERVER_ADDR={self.ton.validatorConsole.addr}
API_CALL_TIMEOUT=30
LOG_FILE=/var/log/btc_teleport/btc_teleport.log
"""
        with open(env_path, 'w') as f:
            f.write(text)

    def add_daemon(self):
        start = f'{self.bin_dir}/oracle'
        script_path = pkg_resources.resource_filename('mytoninstaller', 'scripts/add2systemd.sh')
        user = os.environ.get("USER", "root")
        run_as_root(['bash', script_path, '-n', 'btc_teleport', '-u', user, '-g', user, '-s', start, '-w', self.bin_dir])

    def install(self, branch):
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport1.sh')
        exit_code = run_as_root(["bash", script_path, "-s", '/usr/src', "-r", self.repo_name, "-b", branch])
        if exit_code != 0:
            raise Exception('Failed to install btc_teleport')
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/btc_teleport2.sh')
        subprocess.run(["bash", script_path, "-s", self.src_dir])

    def init(self, reinstall=False, branch: str = 'master'):
        if os.path.exists(self.src_dir) and not reinstall:
            return
        self.local.add_log('Installing btc_teleport', 'info')
        os.makedirs(self.keystore_path, mode=0o700, exist_ok=True)
        self.install(branch)
        self.create_env_file()
        self.add_daemon()
        self.local.add_log('Installed btc_teleport', 'info')

    @staticmethod
    def run_remove_btc_teleport(args):
        script_path = pkg_resources.resource_filename('mytonctrl', 'scripts/remove_btc_teleport.sh')
        return run_as_root(["bash", script_path] + args)

    def get_save_offers(self):
        bname = "saveOffersBtcTeleport"
        save_offers = self.ton.local.db.get(bname)
        if save_offers is None:
            save_offers = dict()
            self.ton.local.db[bname] = save_offers
        return save_offers

    def auto_vote_offers(self):
        save_offers = self.get_save_offers()
        if not save_offers:
            return
        current_offers = self.get_offers()
        for save_offer in list(save_offers.values()):
            offer_hash = save_offer['hash']
            if offer_hash not in current_offers:
                continue
            offer = current_offers[save_offer['hash']]
            if offer['isPassed']:
                save_offers.pop(offer_hash)
                continue
            self.vote_offer_btc_teleport([offer['hash']])

    def get_offers(self):
        self.local.add_log("start get_offers_btc_teleport function", "debug")
        cmd = f"runmethodfull {self.CONFIGURATOR_ADDRESS} list_proposals"
        result = self.ton.liteClient.Run(cmd)
        raw_offers = self.ton.Result2List(result)
        raw_offers = raw_offers[0]
        validators = self.ton.GetValidatorsList(fast=True)
        total_weight = 0
        for v in validators:
            if v['is_masterchain'] is False:
                continue
            total_weight += v['weight']

        offers = {}
        for offer in raw_offers:
            if len(offer) == 0:
                continue
            item = {}
            o_hash = str(offer[0])
            item["hash"] = o_hash
            item["remaining_losses"] = offer[1]
            item["price"] = offer[2]
            item["proposal"] = offer[3]
            item["votedValidators"] = offer[4]
            weight_remaining = offer[5]
            item["weightRemaining"] = weight_remaining
            item["vset_id"] = offer[6]
            item["creator"] = offer[7]
            item["created_at"] = offer[-1]  # todo: bug in parsing slice in get method output
            required_weight = total_weight * 3 / 4
            if len(item["votedValidators"]) == 0:
                weight_remaining = required_weight
            available_weight = required_weight - weight_remaining
            item["approvedPercent"] = round(available_weight / total_weight * 100, 3)
            item["isPassed"] = (weight_remaining < 0)
            offers[o_hash] = item
        return offers

    def vote_offer_btc_teleport(self, args):
        if len(args) == 0:
            color_print("{red}Bad args. Usage:{endc} vote_offer_btc_teleport <offer-hash> [offer-hash-2 offer-hash-3 ...]")
            return
        wallet = self.ton.GetValidatorWallet(mode="vote")
        validator_key = self.ton.GetValidatorKey()
        validator_pubkey_b64 = self.ton.GetPubKeyBase64(validator_key)
        validator_index = self.ton.GetValidatorIndex()
        for offer_hash in args:
            current_offers = self.get_offers()
            if offer_hash not in current_offers:
                self.local.add_log("Offer not found, skip", "warning")
                return
            offer = current_offers[offer_hash]
            if validator_index in offer.get("votedValidators"):
                self.local.add_log("Proposal already has been voted", "debug")
                return
            self.get_save_offers()[offer_hash] = offer
            self.ton.local.save()
            request_hash = self.ton.CreateConfigProposalRequest(offer_hash, validator_index)
            validator_signature = self.ton.GetValidatorSignature(validator_key, request_hash)
            path = self.ton.SignProposalVoteRequestWithValidator(offer_hash, validator_index, validator_pubkey_b64,
                                                                 validator_signature)
            path = self.ton.SignBocWithWallet(wallet, path, self.CONFIGURATOR_ADDRESS, 1.5)
            self.ton.SendFile(path, wallet)

    def print_offers_btc_teleport_list(self, args):
        data = self.get_offers()
        if not data:
            print("No data")
            return
        if "--json" in args:
            text = json.dumps(data, indent=2)
            print(text)
            return
        table = [["Hash", "Votes", "Approved", "Is passed"]]
        for item in data.values():
            o_hash = item.get("hash")
            voted_validators = len(item.get("votedValidators"))
            approved_percent_text = f"{item.get('approvedPercent')}%"
            is_passed = item.get("isPassed")
            if "hash" not in args:
                from modules.utilities import UtilitiesModule
                o_hash = UtilitiesModule.reduct(o_hash)
            if is_passed is True:
                is_passed = bcolors.green_text("true")
            if is_passed is False:
                is_passed = bcolors.red_text("false")
            table += [[o_hash, voted_validators, approved_percent_text, is_passed]]
        print_table(table)

    def remove_btc_teleport(self, args: list):
        if len(args) > 1:
            color_print("{red}Bad args. Usage:{endc} remove_btc_teleport [--force]")
            return
        if '--force' not in args:
            if -1 < self.ton.GetValidatorIndex() < self.ton.GetConfig34()['mainValidators']:
                self.local.add_log('You can not remove btc_teleport on working masterchain validator', 'error')
                return
        exit_code = self.run_remove_btc_teleport(["-s", self.src_dir, "-k", self.keystore_path])
        if exit_code != 0:
            raise Exception('Failed to remove btc_teleport')
        self.local.add_log('Removed btc_teleport', 'info')

    def add_console_commands(self, console):
        console.AddItem("remove_btc_teleport", self.remove_btc_teleport, self.local.translate("remove_btc_teleport_cmd"))
        console.AddItem("vote_offer_btc_teleport", self.vote_offer_btc_teleport, self.local.translate("vote_offer_btc_teleport_cmd"))
        console.AddItem("print_offers_btc_teleport_list", self.print_offers_btc_teleport_list, self.local.translate("print_offers_btc_teleport_list_cmd"))
