from modules import btc_teleport as btc_teleport_module
from mytoncore.utils import get_package_resource_path
from mytoncore.mytoncore import MyTonCore
from mytoncore.models import Config


def test_remove_btc_teleport(cli, monkeypatch, ton):
    with get_package_resource_path('mytonctrl', 'scripts/remove_btc_teleport.sh') as script_path:
        assert script_path.is_file()

    # non-masterchain validator
    return_code = 0
    run_args = []
    def fake_run_as_root(args: list):
        nonlocal return_code, run_args
        run_args = args
        return return_code

    monkeypatch.setattr(btc_teleport_module, "run_as_root", fake_run_as_root)

    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda self: -1)
    monkeypatch.setattr(MyTonCore, "get_config_34", lambda self: Config(total_validators=0, main_validators=100, start_work_time=0, end_work_time=0, total_weight=None, validators=[]))

    output = cli.execute("remove_btc_teleport", no_color=True)
    assert "Removed btc_teleport" in output
    assert run_args == ['bash', str(script_path), '-s', '/usr/src/ton-teleport-btc-periphery', '-k', ton.local.my_work_dir + '/btc_oracle_keystore']

    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda self: 0)
    monkeypatch.setattr(MyTonCore, "get_config_34", lambda self: Config(total_validators=0, main_validators=10, start_work_time=0, end_work_time=0, total_weight=None, validators=[]))
    output = cli.execute("remove_btc_teleport", no_color=True)
    assert "Removed btc_teleport" in output
    assert run_args == ['bash', str(script_path), '-s', '/usr/src/ton-teleport-btc-periphery', '-k', ton.local.my_work_dir + '/btc_oracle_keystore']
