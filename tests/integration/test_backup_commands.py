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

    def create_tmp_ton_dir(_):
        os.makedirs(tmp_dir)
        return str(tmp_dir)

    monkeypatch.setattr(BackupModule, "create_tmp_ton_dir", create_tmp_ton_dir)

    fun_args, fun_user = [], None
    return_code = 0

    def run_create_backup(_, args: list, user: str):
        nonlocal fun_args, fun_user, return_code
        fun_args = args
        fun_user = user
        mock = mocker.Mock()
        mock.returncode = return_code
        return mock

    monkeypatch.setattr(BackupModule, "run_create_backup", run_create_backup)

    output = cli.execute("create_backup", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user is None
    assert fun_args == ["-m", ton.local.my_work_dir, "-t", str(tmp_dir)]

    output = cli.execute("create_backup /to_dir/", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user is None
    assert fun_args == ["-m", ton.local.my_work_dir, "-t", str(tmp_dir), "-d", "/to_dir/"]
    assert not Path(tmp_dir).exists()

    output = cli.execute("create_backup /to_dir/ -u yungwine", no_color=True)
    assert "create_backup - OK" in output
    assert fun_user == 'yungwine'
    assert fun_args == ["-m", ton.local.my_work_dir, "-t", str(tmp_dir), "-d", "/to_dir/"]
    assert not Path(tmp_dir).exists()

    return_code = 1
    output = cli.execute("create_backup /to_dir/ -u yungwine", no_color=True)
    assert "create_backup - Error" in output



def test_restore_backup(cli, ton, monkeypatch, tmp_path, mocker: MockerFixture):
    exit_mock = mocker.Mock()
    monkeypatch.setattr(MyPyClass, "exit", exit_mock)

    create_backup_mock = mocker.Mock()
    monkeypatch.setattr(BackupModule, "create_backup", create_backup_mock)
    monkeypatch.setattr("modules.backups.get_own_ip", lambda: "127.0.0.1")

    return_code = 0
    run_args = []
    def fake_run_as_root(args: list):
        nonlocal return_code, run_args
        run_args = args
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
        assert run_args == ['bash', backup_path, '-u', user, '-m', ton.local.my_work_dir, '-n',
                            'backup.tar.gz', '-i', '2130706433']
        assert ton.local.db.get('abc') == 123  # db updated after restore_backup

    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)

    # bad args
    output = cli.execute("restore_backup", no_color=True)
    assert "Bad args" in output

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

    # check btc teleport installment
    exit_mock.reset_mock()
    create_backup_mock.reset_mock()
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: True)

    from modules import btc_teleport
    btc_teleport_mock = mocker.Mock()
    monkeypatch.setattr(btc_teleport, "BtcTeleportModule", btc_teleport_mock)

    output = cli.execute("restore_backup backup.tar.gz --skip-create-backup -u abc -y", no_color=True)

    assert_happy_run_args(output, 'abc')
    create_backup_mock.assert_not_called()
    btc_teleport_mock.assert_called_once()
    btc_teleport_mock.return_value.init.assert_called_once_with(reinstall=True)

    # Failed to restore backup
    return_code = 1
    output = cli.execute("restore_backup backup.tar.gz --skip-create-backup -y", no_color=True)
    assert "restore_backup - Error" in output
