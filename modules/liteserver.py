import psutil

from modules.module import MtcModule


class LiteserverModule(MtcModule):

    description = 'For liteserver usage only - can\'t be used with validator.'
    default_value = False

    def enable(self):
        from mytoninstaller.mytoninstaller import set_node_argument
        set_node_argument(self.local, ["--celldb-no-preload-all"])
        data = psutil.virtual_memory()
        ram = data.total / 2**30
        if ram < 100:
            set_node_argument(self.local, ["--celldb-cache-size", "1073741824"])

    def disable(self):
        from mytoninstaller.mytoninstaller import set_node_argument
        from mytoninstaller.node_args import get_node_args
        set_node_argument(self.local, ["--celldb-no-preload-all", "-d"])
        if get_node_args()['--celldb-cache-size']:
            set_node_argument(self.local, ["--celldb-cache-size", "-d"])

    def add_console_commands(self, console):
        ...
