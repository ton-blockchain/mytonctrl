from __future__ import annotations

import sys

from mypylib.mypylib import run_as_root

from mytoncore.utils import get_package_resource_path

from mypylib import color_print


def get_validator_service():
    path = '/etc/systemd/system/validator.service'
    with open(path, 'r') as file:
        return file.read()
#end define


def get_node_start_command():
    service = get_validator_service()
    for line in service.split('\n'):
        if line.startswith('ExecStart'):
            return line.split('=')[1].strip()
#end define

def get_node_args(start_command: str | None = None):
    if start_command is None:
        start_command = get_node_start_command()
    if start_command is None:
        raise Exception("Can't get node start command")

    result = dict() # {key: [value1, value2]}
    node_args = start_command.split(' ')[1:]
    key = None
    for item in node_args:
        if item.startswith('-'):
            key = item
            if key not in result:
                result[key] = []
        else:
            result[key].append(item)
    return result
#end define

def set_node_argument(args: list[str]) -> None:
    if len(args) < 1:
        raise Exception(f"Bad args: {args}")

    arg_name = args[0]
    script_args = [arg_name, " ".join(args[1:])]

    with get_package_resource_path("mytoninstaller.scripts", "set_node_argument.py") as script_path:
        run_as_root([sys.executable, str(script_path)] + script_args)

    color_print("set_node_argument - {green}OK{endc}")
