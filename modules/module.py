from abc import ABC, abstractmethod

from mypylib.mypylib import MyPyClass


class MtcModule(ABC):

    description = ''  # module text description
    default_value = True  # is module enabled by default

    def __init__(self, ton, local, *args, **kwargs):
        from mytoncore.mytoncore import MyTonCore
        self.ton: MyTonCore = ton
        self.local: MyPyClass = local

    @abstractmethod
    def add_console_commands(self, console):  ...
