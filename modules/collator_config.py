import json
import requests

from mypylib.mypylib import color_print
from modules.module import MtcModule


class CollatorConfigModule(MtcModule):

    @staticmethod
    def check_config_url(url):
        try:
            r = requests.get(url, timeout=3)
            if r.status_code != 200:
                print(f'Failed to get config from {url}: {r.status_code} code; {r.text}')
                return
            return r.json()
        except Exception as e:
            print(f'Failed to get config from {url}: {e}')
            return

    @staticmethod
    def check_config_file(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f'Failed to read config from {path}: {e}')
            return

    @staticmethod
    def get_config(path):
        if 'http' in path:
            config = CollatorConfigModule.check_config_url(path)
        else:
            config = CollatorConfigModule.check_config_file(path)
        if config is None:
            raise Exception(f'Failed to get config')
        return config

    def add_collator_config_to_vc(self, config: dict):
        self.local.add_log(f"Adding collator options config to validator console", "debug")
        path = self.ton.tempDir + f'/collator_config.json'
        with open(path, 'w') as f:
            json.dump(config, f)
        result = self.ton.validatorConsole.Run(f"setcollatoroptionsjson {path}")
        return 'success' in result, result

    def set_collator_config(self, args):
        if len(args) != 1:
            color_print("{red}Bad args. Usage:{endc} set_collator_config <path/url>")
            return
        location = args[0]
        config = self.get_config(location)
        self.ton.set_collator_config(location)
        added, msg = self.add_collator_config_to_vc(config)
        if not added:
            print(f'Failed to add collator config to validator console: {msg}')
            color_print("set_collator_config - {red}ERROR{endc}")
            return
        color_print("set_collator_config - {green}OK{endc}")

    def get_collator_config(self, args):
        location = self.ton.get_collator_config_location()
        print(f'Collator config location: {location}')
        path = self.ton.tempDir + f'/current_collator_config.json'
        output = self.ton.validatorConsole.Run(f'getcollatoroptionsjson {path}')
        if 'saved config to' not in output:
            print(f'Failed to get collator config: {output}')
            color_print("get_collator_config - {red}ERROR{endc}")
            return
        with open(path, 'r') as f:
            config = json.load(f)
        print(f'Collator config:')
        print(json.dumps(config, indent=4))
        color_print("get_collator_config - {green}OK{endc}")

    def update_collator_config(self, args):
        location = self.ton.get_collator_config_location()
        config = self.get_config(location)
        added, msg = self.add_collator_config_to_vc(config)
        if not added:
            print(f'Failed to add collator config to validator console: {msg}')
            color_print("update_collator_config - {red}ERROR{endc}")
            return
        color_print("update_collator_config - {green}OK{endc}")

    def add_console_commands(self, console):
        console.AddItem("set_collator_config", self.set_collator_config, self.local.translate("set_collator_config_cmd"))
        console.AddItem("update_collator_config", self.update_collator_config, self.local.translate("update_collator_config_cmd"))
        console.AddItem("get_collator_config", self.get_collator_config, self.local.translate("get_collator_config_cmd"))
