# pyright: strict

from __future__ import annotations
import os
import sys
import readline
from typing import Callable
from collections import deque
from dataclasses import dataclass

from mypylib import MyPyClass


CallableFunc = Callable[["list[str]"], None]


@dataclass
class MyPyConsoleItem:
    cmd: str
    func: CallableFunc
    desc: str
    usage: str = ""


class MyPyConsole:
    RED = "\033[31m"
    GREEN = "\033[92m"
    ENDC = "\033[0m"

    def __init__(self, local: MyPyClass):
        self.debug: bool = False
        self.name: str = "console"
        self.color: str = self.GREEN
        self.unknown_cmd: str = "Unknown command"
        self.hello_text: str = (
            "Welcome to the console. Enter 'help' to display the help menu."
        )
        self.start_function: Callable[[], None] | None = None
        self.menu_items: list[MyPyConsoleItem] = []
        self.history: deque[str] = deque(maxlen=100)
        self.local: MyPyClass = local
        self.add_item("help", self.help, "Print help text")
        self.add_item("clear", self.clear, "Clear console")
        self.add_item("history", self.print_history, "Print last commands")
        self.add_item("exit", self.exit, "Exit from application")
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.readline_completer)

    def readline_completer(self, text: str, state: int):
        commands = [item.cmd for item in self.menu_items if item.cmd.startswith(text)]
        if state < len(commands):
            return commands[state]
        return None

    def add_item(self, cmd: str, func: CallableFunc, desc: str, usage: str = ""):
        item = MyPyConsoleItem(cmd, func, desc, usage)
        self.menu_items.append(item)

    def add_history_item(self, item: str):
        try:
            self.history.append(item)
            self.local.db["console_history"] = list(self.history)
            self.local.save()
        except Exception:
            pass

    @staticmethod
    def _rl_escape(code: str):
        """Wrap ANSI code so readline ignores its width."""
        return f"\x01{code}\x02"

    def user_worker(self):
        try:
            result = input(self._rl_escape(self.color) + self.name + "> " + self._rl_escape(self.ENDC))
        except KeyboardInterrupt:
            self.exit([])
        except EOFError:
            self.exit([])
        return result

    def get_cmd_from_user(self):
        result = self.user_worker()
        self.add_history_item(result)
        result_list = result.split(" ")
        result_list = list(filter(None, result_list))
        cmd = None
        if result_list:
            cmd = result_list[0]
        args = result_list[1:]
        for item in self.menu_items:
            if cmd == item.cmd:
                if self.debug:
                    item.func(args)
                else:
                    self._try(item.func, args)
                print()
                return
        print(self.unknown_cmd)

    def _try(self, func: CallableFunc, args: list[str]):
        try:
            func(args)
        except Exception as err:
            print(
                "{RED}Error: {err}{ENDC}".format(RED=self.RED, ENDC=self.ENDC, err=err)
            )

    def help(self, _: list[str]):
        index_list: list[int] = []
        for item in self.menu_items:
            index = len(item.cmd) + len(item.usage) + 1
            index_list.append(index)
        index = max(index_list) + 1
        for item in self.menu_items:
            cmd_text = (item.cmd + " " + item.usage).ljust(index)
            print(cmd_text, item.desc)

    def print_history(self, _: list[str]):
        for i, cmd in enumerate(self.history):
            print(f"{i + 1}  {cmd}")

    def clear(self, _: list[str]):
        os.system("clear")

    def exit(self, _: list[str]):
        print("Bye.")
        sys.exit()

    def Run(self):
        self.run()

    def run(self):
        print(self.hello_text)
        if self.start_function:
            self.start_function()
        try:
            self.history.extend(
                self.local.db.get("console_history", [])
            )  # now self.history = deque(db["console_history"])
            for item in self.history:
                readline.add_history(item)
        except Exception:
            pass
        while True:
            self.get_cmd_from_user()
