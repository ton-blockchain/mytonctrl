import io
from contextlib import redirect_stdout, redirect_stderr
import os
import pytest
from typing import Protocol

from mypyconsole.mypyconsole import MyPyConsole
from mytoncore.mytoncore import MyTonCore
from mytonctrl.mytonctrl import Init
from mypylib.mypylib import MyPyClass
from tests.helpers import remove_colors


class TestLocal(MyPyClass):
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

    def write_log(self):
        pass


@pytest.fixture()
def local(tmp_path):
    work_dir = str(tmp_path / "work") + '/'
    temp_dir = str(tmp_path / "tmp") + '/'
    file_path = str(tmp_path / "tests_runner.py")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    local = TestLocal(file_path=file_path, work_dir=work_dir, temp_dir=temp_dir)

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


@pytest.fixture()
def ton(local, monkeypatch):
    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, 'save', lambda *args, **kwargs: None)
    return MyTonCore(local)


class ConsoleProtocol(Protocol):

    def execute(self, command: str, no_color: bool = False) -> str:
        ...


class TestMyPyConsole(MyPyConsole):

    def run_pre_up(self, no_color: bool = False):
        output = io.StringIO()
        with redirect_stderr(output), redirect_stdout(output):
            self.startFunction()
            output = output.getvalue()
            if no_color:
                output = remove_colors(output)
            return output

    def execute(self, command: str, no_color: bool = False) -> str:
        output = io.StringIO()
        with redirect_stderr(output), redirect_stdout(output):
            self.user_worker = lambda: command
            self.get_cmd_from_user()
            output = output.getvalue()
            if no_color:
                output = remove_colors(output)
            return output


@pytest.fixture()
def cli(local, ton) -> TestMyPyConsole:
    console = TestMyPyConsole(local)
    mp = pytest.MonkeyPatch()
    mp.setattr(MyTonCore, "using_pool", lambda self: True)
    mp.setattr(MyTonCore, "using_nominator_pool", lambda self: True)
    mp.setattr(MyTonCore, "using_single_nominator", lambda self: True)
    Init(local, ton, console, argv=[])
    mp.undo()
    # console.debug = True
    return console
