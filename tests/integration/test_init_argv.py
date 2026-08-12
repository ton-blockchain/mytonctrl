import json
import os
import sys

import pytest

from mytoncore.mytoncore import MyTonCore
from mytonctrl import __main__ as main_module
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


def _stub_app(monkeypatch, mtc_local=None, mtcore_local=None, record=None):
    queue = iter([mtc_local, mtcore_local])
    monkeypatch.setattr(main_module, "MyPyClass", lambda *_: next(queue))

    class _StubMtc:
        def __init__(self, *a, **kw): pass
        def _add_console_commands(self, *a, **kw): pass
        def _pre_up(self, *a, **kw): pass
        def run(self, *a, **kw):
            if record is not None:
                record["run_args"] = a
                record["run_kwargs"] = kw
    monkeypatch.setattr(main_module, "MyTonCtrl", _StubMtc)

    monkeypatch.setattr(TestMyPyConsole, "run", lambda self: None, raising=False)
    monkeypatch.setattr(main_module, "MyPyConsole", TestMyPyConsole)

    monkeypatch.setattr(TestLocal, "run", lambda *a, **kw: None, raising=False)


def test_init_with_config_arg_loads_file_into_local(
    patched_local, mytonctrl_local, monkeypatch, tmp_path
):
    config_path = tmp_path / "custom.db"
    config_path.write_text(json.dumps(_custom_db_contents()))
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-c", str(config_path)])
    _stub_app(monkeypatch, mytonctrl_local, patched_local)

    main_module._main()

    assert patched_local.db_path == str(config_path)
    assert patched_local.db.get("test_marker") == "from_file"


def test_init_with_wallets_arg_sets_ton_walletsdir(
    patched_local, mytonctrl_local, monkeypatch, tmp_path
):
    wallets_dir = str(tmp_path / "custom_wallets")
    os.makedirs(wallets_dir)
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-w", wallets_dir])
    captured = _capture_ton(monkeypatch)
    _stub_app(monkeypatch, mytonctrl_local, patched_local)

    main_module._main()

    assert len(captured) == 1
    assert captured[0].walletsDir == wallets_dir


def test_init_with_unreadable_config_exits(
    patched_local, mytonctrl_local, monkeypatch, tmp_path, capsys
):
    bad = str(tmp_path / "missing.db")
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-c", bad])
    _stub_app(monkeypatch, mytonctrl_local, patched_local)

    with pytest.raises(SystemExit):
        main_module._main()

    err = capsys.readouterr().err
    assert f"Configuration file {bad} could not be opened" in err


def test_init_with_wallets_path_not_dir_exits(
    patched_local, mytonctrl_local, monkeypatch, tmp_path, capsys
):
    not_dir = tmp_path / "afile"
    not_dir.write_text("x")
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-w", str(not_dir)])
    _stub_app(monkeypatch, mytonctrl_local, patched_local)

    with pytest.raises(SystemExit):
        main_module._main()

    err = capsys.readouterr().err
    assert f"Wallets path {not_dir} is not a directory" in err


def test_mytonctrl_prints_version_on_startup(patched_local, mytonctrl_local, monkeypatch, capsys):
    from mytonctrl import __commit__, __version__
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py"])
    _stub_app(monkeypatch, mytonctrl_local, patched_local)
    main_module._main()
    out = capsys.readouterr().out
    assert "MyTonCtrl" in out
    assert __commit__ in out
    assert __version__ in out


def test_init_default_passes_skip_startup_checks_false(
    patched_local, mytonctrl_local, monkeypatch
):
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py"])
    record = {}
    _stub_app(monkeypatch, mytonctrl_local, patched_local, record=record)

    main_module._main()

    assert record["run_kwargs"].get("skip_startup_checks") is False


def test_init_with_no_startup_checks_short_flag(
    patched_local, mytonctrl_local, monkeypatch
):
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "-s"])
    record = {}
    _stub_app(monkeypatch, mytonctrl_local, patched_local, record=record)

    main_module._main()

    assert record["run_kwargs"].get("skip_startup_checks") is True


def test_init_with_no_startup_checks_long_flag(
    patched_local, mytonctrl_local, monkeypatch
):
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "--no-startup-checks"])
    record = {}
    _stub_app(monkeypatch, mytonctrl_local, patched_local, record=record)

    main_module._main()

    assert record["run_kwargs"].get("skip_startup_checks") is True


def test_mytonctrl_run_skips_pre_up_when_flag_set(local, monkeypatch):
    from mytonctrl.mytonctrl import MyTonCtrl

    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, "save", lambda *a, **kw: None)
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_collator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_alert_bot", lambda self: False)
    monkeypatch.setattr(TestLocal, "run", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(TestMyPyConsole, "run", lambda self: None, raising=False)

    ton = MyTonCore(local)
    console = TestMyPyConsole(local)
    mtc = MyTonCtrl(local, ton, console)

    pre_up_calls = []
    monkeypatch.setattr(mtc, "_pre_up", lambda: pre_up_calls.append(1))

    mtc.run(skip_startup_checks=True)
    assert pre_up_calls == []

    mtc.run(skip_startup_checks=False)
    assert pre_up_calls == [1]


def test_init_with_cmd_flag_passes_through_and_skips_startup_checks(
    patched_local, mytonctrl_local, monkeypatch
):
    monkeypatch.setattr(sys, "argv", ["mytonctrl.py", "--cmd", "status"])
    record = {}
    _stub_app(monkeypatch, mytonctrl_local, patched_local, record=record)

    main_module._main()

    assert record["run_kwargs"].get("cmd") == "status"
    assert record["run_kwargs"].get("skip_startup_checks") is True


def test_mytonctrl_run_executes_single_cmd_and_exits(local, monkeypatch):
    from mytonctrl.mytonctrl import MyTonCtrl

    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, "save", lambda *a, **kw: None)
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_collator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_alert_bot", lambda self: False)
    monkeypatch.setattr(TestLocal, "run", lambda *a, **kw: None, raising=False)

    ton = MyTonCore(local)
    console = TestMyPyConsole(local)
    mtc = MyTonCtrl(local, ton, console)

    run_loop_calls = []
    monkeypatch.setattr(console, "run", lambda: run_loop_calls.append(1))

    invoked = []
    console.add_item("foo", lambda args: invoked.append(args), "test cmd")

    mtc.run(skip_startup_checks=True, cmd="foo bar baz")

    assert invoked == [["bar", "baz"]]
    assert run_loop_calls == []


def test_mytonctrl_run_exits_nonzero_when_cmd_unknown(local, monkeypatch):
    from mytonctrl.mytonctrl import MyTonCtrl

    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, "save", lambda *a, **kw: None)
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_collator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_alert_bot", lambda self: False)
    monkeypatch.setattr(TestLocal, "run", lambda *a, **kw: None, raising=False)

    ton = MyTonCore(local)
    console = TestMyPyConsole(local)
    mtc = MyTonCtrl(local, ton, console)

    run_loop_calls = []
    monkeypatch.setattr(console, "run", lambda: run_loop_calls.append(1))

    with pytest.raises(SystemExit) as ei:
        mtc.run(skip_startup_checks=True, cmd="not_a_real_cmd")
    assert ei.value.code == 1
    assert run_loop_calls == []


def test_mytonctrl_run_exits_nonzero_when_cmd_raises(local, monkeypatch):
    from mytonctrl.mytonctrl import MyTonCtrl

    monkeypatch.setattr(MyTonCore, "create_self_db_backup", lambda self: None)
    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda self: "mainnet")
    monkeypatch.setattr(TestLocal, "save", lambda *a, **kw: None)
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_collator", lambda self: False)
    monkeypatch.setattr(MyTonCore, "using_alert_bot", lambda self: False)
    monkeypatch.setattr(TestLocal, "run", lambda *a, **kw: None, raising=False)

    ton = MyTonCore(local)
    console = TestMyPyConsole(local)
    mtc = MyTonCtrl(local, ton, console)

    run_loop_calls = []
    monkeypatch.setattr(console, "run", lambda: run_loop_calls.append(1))

    def boom(_args):
        raise RuntimeError("kaboom")

    console.add_item("boom", boom, "raises")

    with pytest.raises(SystemExit) as ei:
        mtc.run(skip_startup_checks=True, cmd="boom")
    assert ei.value.code == 1
    assert run_loop_calls == []
