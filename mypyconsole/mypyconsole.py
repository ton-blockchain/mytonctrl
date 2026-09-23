# pyright: strict

from __future__ import annotations
import subprocess
import traceback
import sys
import readline
from typing import Any, Callable, NoReturn
from collections import deque
from dataclasses import dataclass

from mypylib import MyPyClass
from mypyconsole.command_parser import CommandParser, UsageError


@dataclass
class MyPyConsoleItem:
    cmd: str
    parser: CommandParser
    desc: str
    usage: str = ""


class MyPyConsole:
    RED = "\033[31m"
    GREEN = "\033[92m"
    ENDC = "\033[0m"

    def __init__(self, local: MyPyClass, name: str = "console", debug: bool = False):
        self.debug: bool = debug
        self.name: str = name
        self.color: str = self.GREEN
        self.unknown_cmd: str = "Unknown command"
        self.menu_items: list[MyPyConsoleItem] = []
        self.history: deque[str] = deque(maxlen=100)
        self.local: MyPyClass = local
        self.add_command("help", self.help, "Print help text")
        self.add_command("clear", self.clear, "Clear console")
        self.add_command("history", self.print_history, "Print last commands")
        self.add_command("exit", self.exit, "Exit from application")
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.readline_completer)

    def readline_completer(self, text: str, state: int):
        commands = [item.cmd for item in self.menu_items if item.cmd.startswith(text)]
        if state < len(commands):
            return commands[state]
        return None

    def add_command(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str | None = None,
        *,
        forward_unknown: bool = False,
    ) -> None:
        if description is None:
            description = self.local.translate(f"{name}_cmd")
        parser = CommandParser(
            name, handler, description, forward_unknown=forward_unknown
        )
        self.menu_items.append(
            MyPyConsoleItem(name, parser, description, parser.short_usage())
        )

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
            result = input(
                self._rl_escape(self.color)
                + self.name
                + "> "
                + self._rl_escape(self.ENDC)
            )
        except KeyboardInterrupt:
            self.exit()
        except EOFError:
            self.exit()
        return result

    def get_cmd_from_user(self):
        result = self.user_worker()
        self.add_history_item(result)
        self.run_cmd(result)

    def run_cmd(self, result: str) -> int:
        result_list = result.split(" ")
        result_list = list(filter(None, result_list))
        cmd = None
        if result_list:
            cmd = result_list[0]
        args = result_list[1:]
        for item in self.menu_items:
            if cmd == item.cmd:
                status = self._run_item(item.parser, args)
                print()
                return status
        print(self.unknown_cmd)
        return 1

    def _run_item(self, parser: CommandParser, args: list[str]) -> int:
        try:
            parser.run(args)
            return 0
        except UsageError as err:
            print(f"{self.RED}{err}{self.ENDC}", file=sys.stderr)
            return 2
        except Exception as err:
            if self.debug:
                raise
            traceback.print_exc()
            print(
                "{RED}Error: {err}{ENDC}".format(RED=self.RED, ENDC=self.ENDC, err=err)
            )
            return 1

    def help(self) -> None:
        index_list: list[int] = []
        for item in self.menu_items:
            index = len(item.cmd) + len(item.usage) + 1
            index_list.append(index)
        index = max(index_list) + 1
        for item in self.menu_items:
            cmd_text = (item.cmd + " " + item.usage).ljust(index)
            print(cmd_text, item.desc)

    def print_history(self) -> None:
        for i, cmd in enumerate(self.history):
            print(f"{i + 1}  {cmd}")

    def clear(self) -> None:
        subprocess.run(["clear"])

    def exit(self) -> NoReturn:
        print("Bye.")
        sys.exit()

    def Run(self):
        self.run()

    def run(self):
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
