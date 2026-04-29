# pyright: strict
from __future__ import annotations
import subprocess
import random
from dataclasses import dataclass
from typing import Callable, ClassVar

from mypylib import MyPyClass, Dict


_DEFAULT_TIMEOUT = 3

@dataclass
class CliTool:
    local: MyPyClass
    app_path: str
    tool_name: ClassVar[str]

    def _get_db_timeout(self) -> int | None:
        return self.local.db.get(f"{self.tool_name}_timeout")

    def _run(self, args: list[str], timeout: int | None) -> str:
        if not self.app_path:
            raise Exception(f"{self.tool_name} error: app_path is None")
        if timeout is None:
            timeout = self._get_db_timeout() or _DEFAULT_TIMEOUT
        args = [self.app_path] + args
        process = subprocess.run(
            args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout,
        )
        output = process.stdout.decode("utf-8", errors="backslashreplace")
        err = process.stderr.decode("utf-8", errors="backslashreplace")
        if err and (process.returncode != 0 or self.tool_name != "fift"):  # consider returncode only for fift for backward compatibility
            self.local.add_log(f"{self.tool_name} args: {args}", "error")
            raise Exception(f"{self.tool_name} error: {err}")
        return output

@dataclass
class Fift(CliTool):
    libs_path: str
    smartconts_path: str
    tool_name: ClassVar[str] = "fift"

    def Run(self, args: list[str], timeout: int | None = None, **_):
        args = list(map(str, args))
        include_path = self.libs_path + ':' + self.smartconts_path
        args = ["-I", include_path, "-s"] + args
        return self._run(args, timeout)

@dataclass
class LiteClient(CliTool):
    config_path: str
    pub_key_path: str | None
    addr: str | None
    get_validator_status: Callable[[], Dict]
    tool_name: ClassVar[str] = "liteclient"

    def Run(self, cmd: str, timeout: int | None = None, index: int | None = None, use_local: bool = True, **_):
        out_of_sync = None
        if index is None and use_local:
            try:
                validator_status = self.get_validator_status()
                out_of_sync = float(validator_status.get("out_of_sync", 'inf'))
            except Exception as e:
                self.local.add_log(f"LiteClient error: failed to call vc: {e}", "error")
        args = ["--global-config", self.config_path, "--verbosity", "0", "--cmd", cmd]
        if index is not None:
            args += ["-i", str(index)]
        elif use_local and self.pub_key_path and self.addr and out_of_sync is not None and out_of_sync < 20:
            args = ["--addr", self.addr, "--pub", self.pub_key_path, "--verbosity", "0", "--cmd", cmd]
        else:
            ls_list = self.local.db.get("liteServers")
            if ls_list:
                args += ["-i", str(random.choice(ls_list))]
        return self._run(args, timeout)


@dataclass
class ValidatorConsole(CliTool):
    priv_key_path: str
    pub_key_path: str
    addr: str
    tool_name: ClassVar[str] = "console"

    def Run(self, cmd: str, timeout: int | None = None, **_):
        args = ["-k", self.priv_key_path, "-p", self.pub_key_path, "-a", self.addr, "-v", "0", "--cmd", cmd]
        return self._run(args, timeout)
