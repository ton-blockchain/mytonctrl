from abc import ABC, abstractmethod
from mytoncore.mytoncore import MyTonCore


class MtcModule(ABC):

    def __init__(self, ton, local, *args, **kwargs):
        self.ton: MyTonCore = ton
        self.local = local

    @abstractmethod
    def add_console_commands(self, console):  ...
