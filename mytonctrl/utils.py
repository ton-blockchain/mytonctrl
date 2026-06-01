import os
import pwd
import subprocess
import time
import typing

from mypylib.mypylib import bcolors


def timestamp2utcdatetime(timestamp, format="%d.%m.%Y %H:%M:%S"):
    if timestamp is None:
        return "n/a"
    datetime = time.gmtime(timestamp)
    result = time.strftime(format, datetime) + " UTC"
    return result


def GetItemFromList(data, index):
    try:
        return data[index]
    except IndexError:
        pass


def is_hex(s):
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def GetColorInt(data, border, logic, ending=None):
    result = "n/a"
    if data is None:
        return result
    elif logic == "more":
        if data >= border:
            result = bcolors.green_text(data, ending)
        else:
            result = bcolors.red_text(data, ending)
    elif logic == "less":
        if data <= border:
            result = bcolors.green_text(data, ending)
        else:
            result = bcolors.red_text(data, ending)
    return result


# end define


def get_current_user():
    return pwd.getpwuid(os.getuid()).pw_name


def pop_arg_from_args(args: typing.List[str], arg_name: str) -> typing.Optional[str]:
    if arg_name in args:
        arg_index = args.index(arg_name) + 1
        if arg_index >= len(args):
            raise Exception(f'Value not found after "{arg_name}" in args: {args}')
        value = args.pop(arg_index)
        args.pop(args.index(arg_name))
        return value
    return None


def pop_user_from_args(args: list) -> typing.Optional[str]:
    return pop_arg_from_args(args, "-u")


def get_clang_major_version():
    try:
        process = subprocess.run(
            ["clang", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if process.returncode != 0:
            return None

        output = process.stdout

        lines = output.strip().split("\n")
        if not lines:
            return None

        first_line = lines[0]
        if "clang version" not in first_line:
            return None

        version_part = first_line.split("clang version")[1].strip()
        major_version = version_part.split(".")[0]

        major_version = "".join(c for c in major_version if c.isdigit())

        if not major_version:
            return None

        return int(major_version)
    except Exception as e:
        print(f"Error checking clang version: {type(e)}: {e}")
        return None


def get_ton_http_api_version() -> typing.Optional[str]:
    pip_path = "/opt/virtualenv/ton_http_api/bin/pip3"
    if not os.path.exists(pip_path):
        return None
    try:
        process = subprocess.run(
            [pip_path, "show", "ton-http-api"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if process.returncode != 0:
            return None
        for line in process.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception as e:
        print(f"Error checking ton-http-api version: {type(e)}: {e}")
    return None


def get_os_version() -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    os_release_path = "/etc/os-release"

    if not os.path.exists(os_release_path):
        return None, None

    data: typing.Dict[str, str] = {}
    with open(os_release_path) as f:
        for line in f:
            if "=" not in line:
                continue
            key, val = line.strip().split("=", 1)
            data[key] = val.strip('"')

    distro = data.get("ID")
    version = data.get("VERSION_ID") or data.get("BUILD_ID") or data.get("VERSION")

    return distro, version
