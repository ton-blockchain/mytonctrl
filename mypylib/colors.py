from __future__ import annotations

from typing import Any


class bcolors:
    '''This class is designed to display text in color format'''
    red = "\033[31m"
    green = "\033[32m"
    yellow = "\033[33m"
    blue = "\033[34m"
    magenta = "\033[35m"
    cyan = "\033[36m"
    endc = "\033[0m"
    bold = "\033[1m"
    underline = "\033[4m"
    default = "\033[39m"
    dim = "\033[2m"

    DEBUG = magenta
    INFO = blue
    OKGREEN = green
    WARNING = yellow
    ERROR = red
    ENDC = endc
    BOLD = bold
    UNDERLINE = underline

    @staticmethod
    def get_args(*args: Any) -> str:
        text = ""
        for item in args:
            if item is None:
                continue
            text += str(item)
        return text

    @staticmethod
    def magenta_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.magenta + text + bcolors.endc
        return text

    @staticmethod
    def blue_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.blue + text + bcolors.endc
        return text

    @staticmethod
    def green_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.green + text + bcolors.endc
        return text

    @staticmethod
    def yellow_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.yellow + text + bcolors.endc
        return text

    @staticmethod
    def red_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.red + text + bcolors.endc
        return text

    @staticmethod
    def bold_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.bold + text + bcolors.endc
        return text

    @staticmethod
    def underline_text(*args: Any) -> str:
        text = bcolors.get_args(*args)
        text = bcolors.underline + text + bcolors.endc
        return text

    colors = {"red": red, "green": green, "yellow": yellow, "blue": blue, "magenta": magenta, "cyan": cyan,
              "endc": endc, "bold": bold, "underline": underline, "dim": dim}