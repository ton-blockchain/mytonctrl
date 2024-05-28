import json
import requests

from mypylib.mypylib import color_print
from modules.module import MtcModule
from mytoncore.utils import hex2base64


class CustomOverlayModule(MtcModule):

    @staticmethod
    def parse_config(name: str, config: dict, vset: list = None):
        """
        Converts config to validator-console friendly format
        :param name: custom overlay name
        :param config: config
        :param vset: list of validators adnl addresses, can be None if `@validators` not in config
        :return:
        """
        result = {
            "name": name,
            "nodes": []
        }
        for k, v in config.items():
            if k == '@validators' and v:
                if vset is None:
                    raise Exception("Validators set is not defined but @validators is in config")
                for v_adnl in vset:
                    result["nodes"].append({
                        "adnl_id": hex2base64(v_adnl),
                        "msg_sender": False,
                    })
            else:
                if "block_sender" in v:
                    result["nodes"].append({
                        "adnl_id": hex2base64(k),
                        "block_sender": v["block_sender"],
                    })
                elif "msg_sender" in v:
                    result["nodes"].append({
                        "adnl_id": hex2base64(k),
                        "msg_sender": v["msg_sender"],
                    })
                    if v["msg_sender"]:
                        result["nodes"][-1]["msg_sender_priority"] = v["msg_sender_priority"]
                else:
                    raise Exception("Unknown node type")
        return result

    def add_custom_overlay(self, args):
        if len(args) != 2:
            color_print("{red}Bad args. Usage:{endc} add_custom_overlay <name> <path_to_config>")
            return
        path = args[1]
        with open(path, 'r') as f:
            config = json.load(f)
        self.ton.set_custom_overlay(args[0], config)
        if '@validators' in config:
            print('Dynamic overlay will be added within 1 minute')
        else:
            result = self.add_custom_overlay_to_vc(self.parse_config(args[0], config))
            if not result:
                print('Failed to add overlay to validator console')
                color_print("add_custom_overlay - {red}ERROR{endc}")
                return
        color_print("add_custom_overlay - {green}OK{endc}")

    def list_custom_overlays(self, args):
        if not self.ton.get_custom_overlays():
            color_print("{red}No custom overlays{endc}")
            return
        for k, v in self.ton.get_custom_overlays().items():
            color_print(f"Custom overlay {{bold}}{k}{{endc}}:")
            print(json.dumps(v, indent=4))

    def delete_custom_overlay(self, args):
        if len(args) != 1:
            color_print("{red}Bad args. Usage:{endc} delete_custom_overlay <name>")
            return
        if '@validators' in self.ton.get_custom_overlays().get(args[0], {}):
            self.ton.delete_custom_overlay(args[0])
            print('Dynamic overlay will be deleted within 1 minute')
        else:
            self.ton.delete_custom_overlay(args[0])
            result = self.delete_custom_overlay_from_vc(args[0])
            if not result:
                print('Failed to delete overlay from validator console')
                color_print("delete_custom_overlay - {red}ERROR{endc}")
                return
        color_print("delete_custom_overlay - {green}OK{endc}")

    def check_node_eligible_for_custom_overlay(self, config: dict):
        vconfig = self.ton.GetValidatorConfig()
        my_adnls = vconfig.adnl
        node_adnls = [i["adnl_id"] for i in config["nodes"]]
        for adnl in my_adnls:
            if adnl.id in node_adnls:
                return True
        return False

    def delete_custom_overlay_from_vc(self, name: str):
        result = self.ton.validatorConsole.Run(f"delcustomoverlay {name}")
        return 'success' in result

    def add_custom_overlay_to_vc(self, config: dict):
        if not self.check_node_eligible_for_custom_overlay(config):
            self.ton.local.add_log(f"Node has no adnl address required for custom overlay {config.get('name')}", "debug")
            return False
        self.ton.local.add_log(f"Adding custom overlay {config.get('name')}", "debug")
        path = self.ton.tempDir + f'/custom_overlay_{config["name"]}.json'
        with open(path, 'w') as f:
            json.dump(config, f)
        result = self.ton.validatorConsole.Run(f"addcustomoverlay {path}")
        return 'success' in result

    def custom_overlays(self):
        config = self.get_default_custom_overlay()
        if config is not None:
            self.ton.set_custom_overlay('default', config)
        self.deploy_custom_overlays()

    def deploy_custom_overlays(self):
        result = self.ton.validatorConsole.Run("showcustomoverlays")
        if 'unknown command' in result:
            return  # node old version
        names = []
        for line in result.split('\n'):
            if line.startswith('Overlay'):
                names.append(line.split(' ')[1].replace('"', '').replace(':', ''))

        config34 = self.ton.GetConfig34()
        current_el_id = config34['startWorkTime']
        current_vset = [i["adnlAddr"] for i in config34['validators']]

        config36 = self.ton.GetConfig36()
        next_el_id = config36['startWorkTime'] if config36['validators'] else 0
        next_vset = [i["adnlAddr"] for i in config36['validators']]

        for name in names:
            # check that overlay still exists in mtc db
            pure_name = name
            suffix = name.split('_')[-1]
            if suffix.startswith('elid') and suffix.split('elid')[-1].isdigit():  # probably election id
                pure_name = '_'.join(name.split('_')[:-1])
                el_id = int(suffix.split('elid')[-1])
                if el_id not in (current_el_id, next_el_id):
                    self.ton.local.add_log(f"Overlay {name} is not in current or next election, deleting", "debug")
                    self.delete_custom_overlay_from_vc(name)  # delete overlay if election id is not in current or next election
                    continue

            if pure_name not in self.ton.get_custom_overlays():
                self.ton.local.add_log(f"Overlay {name} ({pure_name}) is not in mtc db, deleting", "debug")
                self.delete_custom_overlay_from_vc(name)  # delete overlay if it's not in mtc db

        for name, config in self.ton.get_custom_overlays().items():
            if name in names:
                continue
            if '@validators' in config:
                new_name = name + '_elid' + str(current_el_id)
                if new_name not in names:
                    node_config = self.parse_config(new_name, config, current_vset)
                    self.add_custom_overlay_to_vc(node_config)

                if next_el_id != 0:
                    new_name = name + '_elid' + str(next_el_id)
                    if new_name not in names:
                        node_config = self.parse_config(new_name, config, next_vset)
                        self.add_custom_overlay_to_vc(node_config)
            else:
                node_config = self.parse_config(name, config)
                self.add_custom_overlay_to_vc(node_config)

    def get_default_custom_overlay(self):
        if not self.ton.local.db.get('useDefaultCustomOverlays', True):
            return None
        network = self.ton.GetNetworkName()
        default_url = 'https://ton-blockchain.github.io/fallback_custom_overlays.json'
        url = self.ton.local.db.get('defaultCustomOverlaysUrl', default_url)
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            self.ton.local.add_log(f"Failed to get default custom overlays from {url}", "error")
            return None
        config = resp.json()
        return config.get(network)

    def add_console_commands(self, console):
        console.AddItem("add_custom_overlay", self.add_custom_overlay, self.local.translate("add_custom_overlay_cmd"))
        console.AddItem("list_custom_overlays", self.list_custom_overlays, self.local.translate("list_custom_overlays_cmd"))
        console.AddItem("delete_custom_overlay", self.delete_custom_overlay, self.local.translate("delete_custom_overlay_cmd"))
