import psutil

from modules.module import MtcModule


class LiteserverModule(MtcModule):

    description = 'For liteserver usage only - can\'t be used with validator.'
    default_value = False

    def add_console_commands(self, console):
        ...
