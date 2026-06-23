from __future__ import annotations

import io
import sys
import logging
from contextlib import redirect_stdout, redirect_stderr
import os
import pytest
from typing import Protocol

from mytoncore.utils import get_package_resource_path

from mypyconsole.mypyconsole import MyPyConsole
from mytoncore.mytoncore import MyTonCore
from mytonctrl.mytonctrl import MyTonCtrl
from mypylib.mypylib import MyPyClass
from mypylib.logger import setup_logging, ROOT_LOGGER_NAME
from tests.helpers import remove_colors


@pytest.fixture(autouse=True)
def _isolate_logging():
    '''Tear down the shared app-root logger after each test (logging is configured
    at the program entrypoint / per-fixture, not in MyPyClass).'''
    yield
    root = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


class TestLocal(MyPyClass):
    __test__ = False

    def __init__(self, file_path: str, work_dir: str, temp_dir: str):
        self._work_dir = work_dir
        self._temp_dir = temp_dir
        super().__init__(file_path)

    def get_my_work_dir(self):
        return self._work_dir

    def get_my_temp_dir(self):
        return self._temp_dir

    def self_test(self):
        pass

    # def write_db(self, data):
    #     self.buffer.old_db = Dict(self.db)
    #
    # def load_db(self, db_path=False):
    #     self.set_default_config()
    #     return True


@pytest.fixture()
def local(tmp_path):
    work_dir = str(tmp_path / "work") + '/'
    temp_dir = str(tmp_path / "tmp") + '/'
    file_path = str(tmp_path / "tests_runner.py")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    local = TestLocal(file_path=file_path, work_dir=work_dir, temp_dir=temp_dir)
    setup_logging(local.db.config.logLevel)  # console handler, mirrors the entrypoint

    local.db["liteClient"] = {
      "appPath": "/usr/bin/ton/lite-client/lite-client",
      "configPath": "/usr/bin/ton/global.config.json",
      "liteServer": {
        "pubkeyPath": "/var/ton-work/keys/liteserver.pub",
        "ip": "127.0.0.1",
        "port": 33333
      }
    }
    local.db["validatorConsole"] = {
      "appPath": "/usr/bin/ton/validator-engine-console/validator-engine-console",
      "privKeyPath": "/var/ton-work/keys/client",
      "pubKeyPath": "/var/ton-work/keys/server.pub",
      "addr": "127.0.0.1:44444"
    }
    local.db["fift"] = {
      "appPath": "/usr/bin/ton/crypto/fift",
      "libsPath": "/usr/src/ton/crypto/fift/lib",
      "smartcontsPath": "/usr/src/ton/crypto/smartcont"
    }
    return local


class ConsoleProtocol(Protocol):

    def execute(self, command: str, no_color: bool = False) -> str:
        ...


class TestMyPyConsole(MyPyConsole):
    __test__ = False

    mtc: MyTonCtrl
    _caplog = None  # injected by the `cli` fixture

    def _run_capturing(self, action) -> str:
        output = io.StringIO()
        self._caplog.clear()
        with self._caplog.at_level(logging.INFO):
            with redirect_stderr(output), redirect_stdout(output):
                action()
            logs = self._caplog.text
        return output.getvalue() + logs

    def run_pre_up(self, no_color: bool = False):
        output = self._run_capturing(self.mtc._pre_up)
        return remove_colors(output) if no_color else output

    def execute(self, command: str, no_color: bool = False) -> str:
        def action():
            self.user_worker = lambda: command
            self.get_cmd_from_user()
        output = self._run_capturing(action)
        return remove_colors(output) if no_color else output


@pytest.fixture()
def _cli_setup(local, monkeypatch, caplog) -> tuple[TestMyPyConsole, MyTonCore]:
    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, "save", lambda *args, **kwargs: None)
    monkeypatch.setattr(MyTonCore, "using_pool", lambda self: True)
    monkeypatch.setattr(MyTonCore, "using_nominator_pool", lambda self: True)
    monkeypatch.setattr(MyTonCore, "using_single_nominator", lambda self: True)
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py"])
    ton = MyTonCore(local)
    console = TestMyPyConsole(local)
    console._caplog = caplog
    mtc = MyTonCtrl(local, ton, console)
    console.mtc = mtc
    mtc._add_console_commands()
    with get_package_resource_path('mytonctrl', 'resources/translate.json') as translate_path:
        local.init_translator(str(translate_path))
    return console, ton


@pytest.fixture()
def cli(_cli_setup) -> TestMyPyConsole:
    return _cli_setup[0]


@pytest.fixture()
def ton(_cli_setup) -> MyTonCore:
    return _cli_setup[1]
