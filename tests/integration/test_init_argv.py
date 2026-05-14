import json
import os
import sys

import pytest

from mytoncore.mytoncore import MyTonCore
from mytonctrl import mytonctrl as mytonctrl_module
from mytonctrl.mytonctrl import Init
from tests.conftest import TestLocal, TestMyPyConsole


@pytest.fixture()
def mytonctrl_local(tmp_path):
    work_dir = str(tmp_path / "mtc_work") + "/"
    temp_dir = str(tmp_path / "mtc_tmp") + "/"
    file_path = str(tmp_path / "mtc.py")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    return TestLocal(file_path=file_path, work_dir=work_dir, temp_dir=temp_dir)


@pytest.fixture()
def patched_local(local, monkeypatch):
    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, "save", lambda *a, **kw: None)
    return local


def _custom_db_contents():
    return {
        "config": {},
        "liteClient": {
            "appPath": "/usr/bin/ton/lite-client/lite-client",
            "configPath": "/usr/bin/ton/global.config.json",
            "liteServer": {
                "pubkeyPath": "/var/ton-work/keys/liteserver.pub",
                "ip": "127.0.0.1",
                "port": 33333,
            },
        },
        "validatorConsole": {
            "appPath": "/usr/bin/ton/validator-engine-console/validator-engine-console",
            "privKeyPath": "/var/ton-work/keys/client",
            "pubKeyPath": "/var/ton-work/keys/server.pub",
            "addr": "127.0.0.1:44444",
        },
        "fift": {
            "appPath": "/usr/bin/ton/crypto/fift",
            "libsPath": "/usr/src/ton/crypto/fift/lib",
            "smartcontsPath": "/usr/src/ton/crypto/smartcont",
        },
        "test_marker": "from_file",
    }


def _capture_ton(monkeypatch):
    captured = []
    original = MyTonCore.__init__

    def capturing(self, mtc_local):
        original(self, mtc_local)
        captured.append(self)

    monkeypatch.setattr(MyTonCore, "__init__", capturing)
    return captured


def test_init_with_config_arg_loads_file_into_local(
    patched_local, mytonctrl_local, monkeypatch, tmp_path
):
    config_path = tmp_path / "custom.db"
    config_path.write_text(json.dumps(_custom_db_contents()))
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-c", str(config_path)])

    console = TestMyPyConsole(mytonctrl_local)
    Init(mytonctrl_local, patched_local, console)

    assert patched_local.db_path == str(config_path)
    assert patched_local.db.get("test_marker") == "from_file"


def test_init_with_wallets_arg_sets_ton_walletsdir(
    patched_local, mytonctrl_local, monkeypatch, tmp_path
):
    wallets_dir = str(tmp_path / "custom_wallets")
    os.makedirs(wallets_dir)
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-w", wallets_dir])
    captured = _capture_ton(monkeypatch)

    console = TestMyPyConsole(mytonctrl_local)
    Init(mytonctrl_local, patched_local, console)

    assert len(captured) == 1
    assert captured[0].walletsDir == wallets_dir


def test_init_with_unreadable_config_exits(
    patched_local, mytonctrl_local, monkeypatch, tmp_path, capsys
):
    bad = str(tmp_path / "missing.db")
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-c", bad])

    console = TestMyPyConsole(mytonctrl_local)
    with pytest.raises(SystemExit):
        Init(mytonctrl_local, patched_local, console)

    err = capsys.readouterr().err
    assert f"Configuration file {bad} could not be opened" in err


def test_init_with_wallets_path_not_dir_exits(
    patched_local, mytonctrl_local, monkeypatch, tmp_path, capsys
):
    not_dir = tmp_path / "afile"
    not_dir.write_text("x")
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-w", str(not_dir)])

    console = TestMyPyConsole(mytonctrl_local)
    with pytest.raises(SystemExit):
        Init(mytonctrl_local, patched_local, console)

    err = capsys.readouterr().err
    assert f"Wallets path {not_dir} is not a directory" in err


def test_mytonctrl_prints_version_on_startup(monkeypatch, capsys):
    from mytonctrl import __commit__, __version__
    monkeypatch.setattr(mytonctrl_module, "MyPyClass", lambda *_: None)
    monkeypatch.setattr(mytonctrl_module, "Init", lambda *_: None)
    class _StubConsole:
        def __init__(self, local):
            pass
        def run(self):
            return
    monkeypatch.setattr(mytonctrl_module, "MyPyConsole", _StubConsole)
    mytonctrl_module.mytonctrl()
    out = capsys.readouterr().out
    assert "MyTonCtrl" in out
    assert __commit__ in out
    assert __version__ in out
