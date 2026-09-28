import json
import os

from pytest_mock import MockerFixture

from modules.backups import BackupModule
from modules import backups as backups_module
from mypylib.mypylib import MyPyClass
from mytoncore.utils import get_package_resource_path
from mytoncore.mytoncore import MyTonCore
from pathlib import Path

from mytonctrl.utils import get_current_user


def test_create_backup(cli, ton, monkeypatch, tmp_path, mocker: MockerFixture):
    tmp_dir = tmp_path / "test"
    tmp_dir_created = 0

    def create_tmp_ton_dir(_):
        nonlocal tmp_dir_created
        tmp_dir_created += 1
        os.makedirs(tmp_dir)
        return str(tmp_dir)

    monkeypatch.setattr(BackupModule, "create_tmp_ton_dir", create_tmp_ton_dir)

    fun_args, fun_user, fun_as_root = [], None, None
    return_code = 0

    def run_create_backup(_, args: list, user: str, as_root: bool = False) -> int:
        nonlocal fun_args, fun_user, fun_as_root, return_code
        fun_args = args
        fun_user = user
        fun_as_root = as_root
        return return_code

    monkeypatch.setattr(BackupModule, "run_create_backup", run_create_backup)

    output = cli.execute("create_backup", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user is None
    assert fun_as_root is False
    assert fun_args == ["-m", ton.local.my_work_dir, "-t", str(tmp_dir), "-k", "/var/ton-work/keys"]
    assert tmp_dir_created == 1

    output = cli.execute("create_backup /to_dir/", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user is None
    assert fun_as_root is False
    assert fun_args == ["-m", ton.local.my_work_dir, "-t", str(tmp_dir), "-k", "/var/ton-work/keys", "-d", "/to_dir/"]
    assert not Path(tmp_dir).exists()

    output = cli.execute("create_backup /to_dir/ -u yungwine", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user == 'yungwine'
    assert fun_args == ["-m", ton.local.my_work_dir, "-t", str(tmp_dir), "-k", "/var/ton-work/keys", "-d", "/to_dir/"]
    assert not Path(tmp_dir).exists()
    assert tmp_dir_created == 3

    # --from-host: no validator-console round-trip, the node's own db dir is handed to the script,
    # which then has to run as root to read the validator-owned keyring and config.json
    output = cli.execute("create_backup --from-host", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user is None
    assert fun_as_root is True
    assert fun_args == ["-m", ton.local.my_work_dir, "-b", "/var/ton-work/db", "-k", "/var/ton-work/keys"]
    assert tmp_dir_created == 3

    output = cli.execute("create_backup /to_dir/ --from-host -u yungwine", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user == 'yungwine'
    assert fun_as_root is True
    assert fun_args == ["-m", ton.local.my_work_dir, "-b", "/var/ton-work/db", "-k", "/var/ton-work/keys", "-d", "/to_dir/"]
    assert tmp_dir_created == 3
    assert not Path(tmp_dir).exists()

    # the db dir comes from the configured paths, not from <ton_work>/db
    ton.local.db["paths"] = {"ton_db": "/mnt/ton-db/", "ton_keys": "/mnt/keys/"}
    output = cli.execute("create_backup --from-host", no_color=True)
    assert "create_backup - OK" in output
    assert fun_args == ["-m", ton.local.my_work_dir, "-b", "/mnt/ton-db", "-k", "/mnt/keys"]
    ton.local.db.pop("paths")

    return_code = 1
    output = cli.execute("create_backup /to_dir/ -u yungwine", no_color=True)
    assert "create_backup - Error" in output

    output = cli.execute("create_backup /to_dir/ --from-host", no_color=True)
    assert "create_backup - Error" in output

    # too many args
    output = cli.execute("create_backup /to_dir/ --from-host -u yungwine extra", no_color=True)
    assert "usage: create_backup [-h] [-u USER] [--from-host] [dest]" in output
    assert "create_backup: error: unrecognized arguments: extra" in output
    output = cli.execute("create_backup -u", no_color=True)
    assert "create_backup: error: argument -u/--user: expected one argument" in output


def test_make_backup_passes_dest_and_current_user(ton, monkeypatch, tmp_path):
    def create_tmp_ton_dir(_):
        os.makedirs(tmp_path / "ton_backup")
        return str(tmp_path / "ton_backup")

    calls = []

    def run_create_backup(_, args: list, user: str, as_root: bool = False) -> int:
        calls.append((args, user, as_root))
        return 0

    monkeypatch.setattr(BackupModule, "create_tmp_ton_dir", create_tmp_ton_dir)
    monkeypatch.setattr(BackupModule, "run_create_backup", run_create_backup)
    ton.local.db["auto_backup"] = True
    ton.local.db["auto_backup_path"] = str(tmp_path / "auto_backups")

    ton.make_backup(123)

    dest = str(tmp_path / "auto_backups") + "/mytonctrl_backup_elid123.zip"
    assert calls == [(["-m", ton.local.my_work_dir, "-t", str(tmp_path / "ton_backup"), "-k", "/var/ton-work/keys", "-d", dest], None, False)]


def test_run_create_backup_as_root(monkeypatch, mocker: MockerFixture):
    runs, root_runs = [], []

    def fake_run(cmd, **kwargs):
        runs.append((cmd, kwargs))
        return mocker.Mock(returncode=7)

    def fake_run_as_root(cmd):
        root_runs.append(cmd)
        return 5

    monkeypatch.setattr(backups_module.subprocess, "run", fake_run)
    monkeypatch.setattr(backups_module, "run_as_root", fake_run_as_root)
    with get_package_resource_path('mytonctrl', 'scripts/create_backup.sh') as backup_path:
        script = str(backup_path)

    # default: plain bash with a timeout, exit code passed through
    assert BackupModule.run_create_backup(["-m", "/mtc"], user="abc") == 7
    assert runs == [(["bash", script, "-u", "abc", "-m", "/mtc"], {"timeout": 30})]
    assert root_runs == []

    # as_root: goes through run_as_root, which handles sudo/su and runs without a timeout
    assert BackupModule.run_create_backup(["-m", "/mtc"], user="abc", as_root=True) == 5
    assert root_runs == [["bash", script, "-u", "abc", "-m", "/mtc"]]
    assert len(runs) == 1

    # user defaults to the caller, resolved before any sudo so the archive is handed back to them
    monkeypatch.setattr(backups_module, "get_current_user", lambda: "caller")
    BackupModule.run_create_backup([], as_root=True)
    assert root_runs[-1] == ["bash", script, "-u", "caller"]


def test_restore_backup(cli, ton, monkeypatch, tmp_path, mocker: MockerFixture):
    exit_mock = mocker.Mock()
    monkeypatch.setattr(MyPyClass, "exit", exit_mock)

    create_backup_mock = mocker.Mock()
    monkeypatch.setattr(BackupModule, "create_backup", create_backup_mock)
    monkeypatch.setattr("modules.backups.get_own_ip", lambda: "127.0.0.1")

    return_code = 0
    all_run_args = []
    def fake_run_as_root(args: list):
        nonlocal return_code
        all_run_args.append(args)
        return return_code

    monkeypatch.setattr(backups_module, "run_as_root", fake_run_as_root)

    run_restore_backup = BackupModule.run_restore_backup

    def fake_run_restore_backup(*args, **kwargs):
        # really do update db after restore
        with open(ton.local.db_path, 'w') as f:
            new_db = ton.local.db.copy()
            new_db.update({"abc": 123})
            f.write(json.dumps(new_db))
        return run_restore_backup(*args, **kwargs)

    monkeypatch.setattr(BackupModule, "run_restore_backup", staticmethod(fake_run_restore_backup))

    current_user = get_current_user()
    with get_package_resource_path('mytonctrl', 'scripts/restore_backup.sh') as backup_path:
        assert backup_path.is_file()

    def assert_happy_run_args(outp: str, user: str):
        assert 'restore_backup - OK' in outp
        exit_mock.assert_called_once()  # exited after restore_backup
        assert all_run_args[-2] == ['bash', str(backup_path), '-u', user, '-m', ton.local.my_work_dir, '-n',
                                    'backup.tar.gz', '-i', '2130706433', '-t', '/var/ton-work']
        # mytoncore is restarted after the restored db paths are fixed up
        assert all_run_args[-1] == ['systemctl', 'restart', 'mytoncore']
        assert ton.local.db.get('abc') == 123  # db updated after restore_backup

    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)

    # bad args
    output = cli.execute("restore_backup", no_color=True)
    assert "usage: restore_backup [-h] [-y] [-s] [-u USER] filename" in output
    assert "restore_backup: error: the following arguments are required: filename" in output
    output = cli.execute("restore_backup backup.tar.gz other.tar.gz", no_color=True)
    assert "restore_backup: error: unrecognized arguments: other.tar.gz" in output
    exit_mock.assert_not_called()

    # prompt: abort
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    output = cli.execute("restore_backup backup.tar.gz", no_color=True)
    assert "aborted." in output
    create_backup_mock.assert_not_called()
    exit_mock.assert_not_called()

    # happy path
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    output = cli.execute("restore_backup backup.tar.gz", no_color=True)
    assert_happy_run_args(output, current_user)
    create_backup_mock.assert_called_once()

    # happy path custom user
    exit_mock.reset_mock()
    create_backup_mock.reset_mock()
    output = cli.execute("restore_backup backup.tar.gz -u customuser", no_color=True)
    create_backup_mock.assert_called_once()
    assert_happy_run_args(output, 'customuser')
    create_backup_mock.assert_called_once()

    # skip prompt
    exit_mock.reset_mock()
    create_backup_mock.reset_mock()
    output = cli.execute("restore_backup backup.tar.gz -y", no_color=True)
    assert_happy_run_args(output, current_user)
    create_backup_mock.assert_called_once()

    # skip create_backup
    exit_mock.reset_mock()
    create_backup_mock.reset_mock()
    output = cli.execute("restore_backup backup.tar.gz --skip-create-backup -y -u abc", no_color=True)
    assert_happy_run_args(output, 'abc')
    create_backup_mock.assert_not_called()

    # Failed to restore backup
    return_code = 1
    output = cli.execute("restore_backup backup.tar.gz --skip-create-backup -y", no_color=True)
    assert "restore_backup - Error" in output


def test_restore_backup_pre_restore_backup_as_current_user(cli, ton, monkeypatch, tmp_path):
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    monkeypatch.setattr("modules.backups.get_own_ip", lambda: "127.0.0.1")
    monkeypatch.setattr(BackupModule, "create_tmp_ton_dir", lambda _: str(tmp_path / "ton_backup"))
    os.makedirs(tmp_path / "ton_backup")
    backup_calls = []

    def run_create_backup(_, args: list, user: str, as_root: bool = False) -> int:
        backup_calls.append((user, as_root))
        return 0

    monkeypatch.setattr(BackupModule, "run_create_backup", run_create_backup)
    monkeypatch.setattr(BackupModule, "run_restore_backup", staticmethod(lambda args, user=None: 1))

    output = cli.execute("restore_backup backup.tar.gz -u abc", no_color=True)
    assert backup_calls == [(None, False)]
    assert "Could not create backup" not in output
    assert "create_backup - OK" in output
    assert "restore_backup - Error" in output


def test_create_tmp_ton_dir_collators_list(ton, monkeypatch, tmp_path):
    from modules.validator import ValidatorModule

    def fake_run(cmd):
        assert cmd == "getconfig"
        return "---------\n{}\n--------"

    monkeypatch.setattr(ton.validatorConsole, "run", fake_run)
    monkeypatch.setattr(ton, "tempDir", str(tmp_path))
    monkeypatch.setattr(BackupModule, "create_keyring", lambda self, dir_name: None)

    collators_list = {
        "collators": [{"adnl_id": "abc"}],
        "register_collators": [],
        "disable_self_collate": True,
    }
    monkeypatch.setattr(ValidatorModule, "get_collators_list", lambda self: collators_list)

    module = BackupModule(ton, ton.local)
    dumped = Path(module.create_tmp_ton_dir()) / "db" / "collators-list.json"
    assert json.loads(dumped.read_text()) == collators_list


def test_create_collators_list_empty(ton, monkeypatch, tmp_path):
    from modules.validator import ValidatorModule

    module = BackupModule(ton, ton.local)

    # list was never set on this node -> empty json, which the node reads back as an empty
    # list, so restoring the backup clears the recipient's one
    monkeypatch.setattr(ValidatorModule, "get_collators_list", lambda self: {})
    module.create_collators_list(str(tmp_path))
    assert json.loads((tmp_path / "collators-list.json").read_text()) == {}


def test_create_collators_list_unreadable(ton, monkeypatch, tmp_path):
    from modules.validator import ValidatorModule

    module = BackupModule(ton, ton.local)

    # node too old / console error -> backup still succeeds, just without the file here;
    # create_backup.sh then stores an empty list, same as for a node with no list set
    def raise_(self):
        raise Exception("node does not support collators list commands (old node version)")

    monkeypatch.setattr(ValidatorModule, "get_collators_list", raise_)
    module.create_collators_list(str(tmp_path))
    assert not (tmp_path / "collators-list.json").exists()
