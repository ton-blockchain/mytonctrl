import json
import requests

from mypylib.mypylib import color_print
from modules.module import MtcModule
from mypyconsole.command_parser import Annotated, Arg


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
            raise Exception('Failed to get config')
        return config

    def add_collator_config_to_vc(self, config: dict):
        self.local.add_log("Adding collator options config to validator console", "debug")
        path = self.ton.tempDir + '/collator_config.json'
        with open(path, 'w') as f:
            json.dump(config, f)
        result = self.ton.validatorConsole.run(f"setcollatoroptionsjson {path}")
        return 'success' in result, result

    def set_collator_config(
        self, location: Annotated[str, Arg(help="path or URL of the collator options JSON")]
    ) -> None:
        config = self.get_config(location)
        self.ton.set_collator_config(location)
        added, msg = self.add_collator_config_to_vc(config)
        if not added:
            print(f'Failed to add collation config to validator console: {msg}')
            color_print("set_collator_config - {red}ERROR{endc}")
            return
        color_print("set_collator_config - {green}OK{endc}")

    def get_collator_config(self) -> None:
        location = self.ton.get_collator_config_location()
        print(f'Collator config location: {location}')
        path = self.ton.tempDir + '/current_collator_config.json'
        output = self.ton.validatorConsole.run(f'getcollatoroptionsjson {path}')
        if 'saved config to' not in output:
            print(f'Failed to get collator config: {output}')
            color_print("get_collator_config - {red}ERROR{endc}")
            return
        with open(path, 'r') as f:
            config = json.load(f)
        print('Collator config:')
        print(json.dumps(config, indent=4))
        color_print("get_collator_config - {green}OK{endc}")

    def update_collator_config(self) -> None:
        location = self.ton.get_collator_config_location()
        config = self.get_config(location)
        added, msg = self.add_collator_config_to_vc(config)
        if not added:
            print(f'Failed to add collator config to validator console: {msg}')
            color_print("update_collator_config - {red}ERROR{endc}")
            return
        color_print("update_collator_config - {green}OK{endc}")

    def add_console_commands(self, console):
        console.add_command("set_collation_config", self.set_collator_config)
        console.add_command("update_collation_config", self.update_collator_config)
        console.add_command("print_collation_config", self.get_collator_config)
