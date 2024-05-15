import psutil

from modules.module import MtcModule
from mytoninstaller.mytoninstaller import set_node_argument
from mytoninstaller.node_args import get_node_args


class LiteserverModule(MtcModule):

    description = 'For liteserver usage only - can\'t be used with validator.'
    default_value = False

    def enable(self):
        set_node_argument(self.local, ["--celldb-no-preload-all"])
        data = psutil.virtual_memory()
        ram = round(data.total / 2**30, 2)
        if ram < 100:
            set_node_argument(self.local, ["--celldb-cache-size", "1073741824"])

    def disable(self):
        set_node_argument(self.local, ["--celldb-no-preload-all", "-d"])
        if get_node_args()['--celldb-cache-size']:
            set_node_argument(self.local, ["--celldb-cache-size", "-d"])

    def add_console_commands(self, console):
        ...
