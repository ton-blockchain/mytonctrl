from modules import btc_teleport as btc_teleport_module
from mytoncore.utils import get_package_resource_path
from mytoncore.mytoncore import MyTonCore


def test_remove_btc_teleport(cli, monkeypatch, ton):
    with get_package_resource_path('mytonctrl', 'scripts/remove_btc_teleport.sh') as script_path:
        assert script_path.is_file()

    # non-masterchain validator, no --force needed
    return_code = 0
    run_args = []
    def fake_run_as_root(args: list):
        nonlocal return_code, run_args
        run_args = args
        return return_code

    monkeypatch.setattr(btc_teleport_module, "run_as_root", fake_run_as_root)

    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda self: -1)
    monkeypatch.setattr(MyTonCore, "GetConfig34", lambda self: {"mainValidators": 100})

    output = cli.execute("remove_btc_teleport", no_color=True)
    assert "Removed btc_teleport" in output
    assert run_args == ['bash', script_path, '-s', '/usr/src/ton-teleport-btc-periphery', '-k', ton.local.my_work_dir + '/btc_oracle_keystore']

    # bad args
    run_args = []
    output = cli.execute("remove_btc_teleport arg1 arg2")
    assert "Bad args" in output
    assert not run_args

    # masterchain validator without --force
    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda self: 10)
    monkeypatch.setattr(MyTonCore, "GetConfig34", lambda self: {"mainValidators": 100})
    output = cli.execute("remove_btc_teleport", no_color=True)
    assert run_args == []
    assert 'You can not remove btc_teleport on working masterchain validator' in output

    # masterchain validator with --force
    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda self: 0)
    monkeypatch.setattr(MyTonCore, "GetConfig34", lambda self: {"mainValidators": 10})
    output = cli.execute("remove_btc_teleport --force", no_color=True)
    assert "Removed btc_teleport" in output
    assert run_args == ['bash', script_path, '-s', '/usr/src/ton-teleport-btc-periphery', '-k', ton.local.my_work_dir + '/btc_oracle_keystore']

    # non-masterchain validator
    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda self: 10)
    monkeypatch.setattr(MyTonCore, "GetConfig34", lambda self: {"mainValidators": 10})
    output = cli.execute("remove_btc_teleport", no_color=True)
    assert "Removed btc_teleport" in output
    assert run_args == ['bash', script_path, '-s', '/usr/src/ton-teleport-btc-periphery', '-k', ton.local.my_work_dir + '/btc_oracle_keystore']
