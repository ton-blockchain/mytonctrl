import base64
import os
import pathlib
import subprocess

import pytest
import requests
from pytest_mock import MockerFixture

from mytoncore.utils import get_package_resource_path
from mytonctrl import mytonctrl as mytonctrl_module
from mypylib.mypylib import MyPyClass
from mypylib.mypylib import Dict
from mytoncore.mytoncore import MyTonCore
import sys
from pathlib import Path

# def run_mytonctrl_cli(args: str, env=None, timeout=3):
#     cmd = [sys.executable, "-m", "mytonctrl"]
#     result = subprocess.run(
#         cmd,
#         input=args,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#         env=env,
#         timeout=timeout,
#     )
#     return result


def test_exit(cli, monkeypatch):
    monkeypatch.setattr(sys, "exit", lambda *_: None)
    result = cli.execute('exit')
    assert 'Bye.' in result


def test_help(cli):
    result = cli.execute('help')

    assert 'clear' in result
    assert 'history' in result
    assert 'exit' in result


def test_update(cli, monkeypatch, mocker):
    exit_mock = mocker.Mock()
    monkeypatch.setattr(MyPyClass, "exit", exit_mock)

    monkeypatch.setattr(mytonctrl_module, "check_git", lambda args, default_repo, text: ("author", "repo", "branch", None))

    calls = {}
    def fake_run_as_root(run_args):
        calls["run_args"] = run_args
        return 0
    monkeypatch.setattr(mytonctrl_module, "run_as_root", fake_run_as_root)

    output = cli.execute("update")
    with get_package_resource_path('mytonctrl', 'scripts/update.sh') as upd_path:
        assert upd_path.is_file()
    assert "Error" not in output
    assert calls["run_args"] == ['bash', upd_path, '-a', 'author', '-r', 'repo', '-b', 'branch']
    exit_mock.assert_called_once()


def test_upgrade(cli, monkeypatch):
    monkeypatch.setattr(mytonctrl_module, "check_git", lambda args, default_repo, text: ("author", "repo", "branch", None))

    calls = {}
    def fake_run_as_root(run_args):
        calls["run_args"] = run_args
        return 0

    monkeypatch.setattr(mytonctrl_module, "run_as_root", fake_run_as_root)
    monkeypatch.setattr(mytonctrl_module, "get_clang_major_version", lambda: 21)
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: False)
    with get_package_resource_path('mytonctrl', 'scripts/upgrade.sh') as upg_path:
        assert upg_path.is_file()

    def fake_GetSettings(self, name):
        if name == "liteClient":
            return {"configPath": "lite-client/ton-lite-client-test1.config.json", "liteServer": {"pubkeyPath": "/usr/bin/ton/old.pub"}}
        if name == "validatorConsole":
            return {"privKeyPath": "/usr/bin/ton/client", "pubKeyPath": "/usr/bin/ton/server.pub"}
        return {}

    captured_settings = {}
    def fake_SetSettings(self, name, value):
        captured_settings[name] = value

    monkeypatch.setattr(MyTonCore, "GetSettings", fake_GetSettings)
    monkeypatch.setattr(MyTonCore, "SetSettings", fake_SetSettings)

    output = cli.execute("upgrade")
    assert "Upgrade - \x1b[32mOK\x1b" in output
    assert "Error" not in output
    assert captured_settings["liteClient"]["configPath"] == "global.config.json"
    assert captured_settings["liteClient"]["liteServer"]["pubkeyPath"] == "/var/ton-work/keys/liteserver.pub"
    assert calls["run_args"] == ["bash", upg_path, "-a", "author", "-r", "repo", "-b", "branch"]

    # clang version is < 21, abort
    calls = {}
    monkeypatch.setattr(mytonctrl_module, "get_clang_major_version", lambda: 14)
    monkeypatch.setattr('builtins.input', lambda _: "n")
    output = cli.execute("upgrade")
    assert "aborted." in output
    assert not calls

    # clang version is < 21, proceed
    monkeypatch.setattr(mytonctrl_module, "get_clang_major_version", lambda: 14)
    monkeypatch.setattr('builtins.input', lambda _: "y")
    output = cli.execute("upgrade")
    assert "Upgrade - \x1b[32mOK\x1b" in output
    assert "Error" not in output
    assert calls["run_args"] == ["bash", upg_path, "-a", "author", "-r", "repo", "-b", "branch"]

    # call upgrade_btc_teleport if using validator
    monkeypatch.setattr(mytonctrl_module, "get_clang_major_version", lambda: 21)
    calls = {}
    monkeypatch.setattr(MyTonCore, "using_validator", lambda self: True)
    teleport_calls = {}
    def fake_upgrade_btc_teleport(local, ton, reinstall=False, branch="master", user=None):
        teleport_calls["called"] = True
        teleport_calls["reinstall"] = reinstall
        teleport_calls["branch"] = branch
        teleport_calls["user"] = user
    monkeypatch.setattr(mytonctrl_module, "upgrade_btc_teleport", fake_upgrade_btc_teleport)
    output = cli.execute("upgrade", no_color=True)
    assert teleport_calls.get("called") is True
    assert teleport_calls.get("reinstall") is False
    assert "Upgrade - OK" in output
    assert "Error" not in output
    assert calls["run_args"] == ["bash", upg_path, "-a", "author", "-r", "repo", "-b", "branch"]

    monkeypatch.setattr(mytonctrl_module, "run_as_root", lambda _: 1)
    output = cli.execute("upgrade", no_color=True)
    assert "Upgrade - Error" in output


def test_upgrade_btc_teleport(cli, monkeypatch, mocker: MockerFixture):
    teleport_calls = {}
    def fake_upgrade_btc_teleport(local, ton, reinstall=False, branch="master", user=None):
        teleport_calls["called"] = True
        teleport_calls["reinstall"] = reinstall
        teleport_calls["branch"] = branch
        teleport_calls["user"] = user

    monkeypatch.setattr(mytonctrl_module, "upgrade_btc_teleport", fake_upgrade_btc_teleport)

    run_as_root_mocker = mocker.Mock()
    monkeypatch.setattr(mytonctrl_module, "run_as_root", run_as_root_mocker)
    check_git_mocker = mocker.Mock()
    monkeypatch.setattr(mytonctrl_module, "check_git", check_git_mocker)

    output = cli.execute("upgrade --btc-teleport dev -u alice")

    run_as_root_mocker.assert_not_called()

    assert teleport_calls["reinstall"] is True
    assert teleport_calls["branch"] == "dev"
    assert teleport_calls["user"] == "alice"
    check_git_mocker.assert_not_called()

    assert "Error" not in output


def test_installer(cli, monkeypatch):
    calls = {}
    def fake_run(args):
        calls["args"] = args
        return 0
    monkeypatch.setattr(subprocess, "run", fake_run)

    output = cli.execute("installer cmd arg1 arg2")
    assert calls["args"] == ["python3", "-m", "mytoninstaller", '-c',  "cmd arg1 arg2"]
    assert "Error" not in output


def test_status(cli, monkeypatch, mocker: MockerFixture):
    status_mocker = mocker.Mock()
    status_mocker.is_working = True
    status_mocker.out_of_sync = 30
    status_mocker.initial_sync = False
    status_mocker.masterchain_out_of_sync = 30
    status_mocker.shardchain_out_of_sync = 3
    status_mocker.out_of_ser = 10
    status_mocker.validator_groups_master = 1
    status_mocker.validator_groups_shard = 2

    monkeypatch.setattr(MyTonCore, "GetValidatorStatus", lambda *_: status_mocker)
    monkeypatch.setattr(MyTonCore, "get_adnl_addr", lambda *_: "1234ABCD", raising=False)
    monkeypatch.setattr(MyTonCore, "GetAdnlAddr", lambda *_: "1234ABCD", raising=False)
    monkeypatch.setattr(MyTonCore, "using_validator", lambda *_: True)
    validator_wallet = mocker.Mock()
    validator_wallet.addrB64 = "WALLET_ADDR"
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", lambda *_: validator_wallet)
    monkeypatch.setattr(MyTonCore, "GetDbSize", lambda *_: 123456)
    monkeypatch.setattr(MyTonCore, "GetDbUsage", lambda *_: 123456)

    def fake_GetSettings(self, name):
        if name == "statistics":
            return {"some": "stats"}
        return {}

    def fake_GetStatistics(self, name, stats):
        if name == 'disksLoadAvg':
            return {}
        return [-1, -1, -1]

    monkeypatch.setattr(MyTonCore, "GetSettings", fake_GetSettings)
    monkeypatch.setattr(MyTonCore, "GetStatistics", fake_GetStatistics)
    vconfig_mock = Dict()
    vconfig_mock.fullnode = base64.b64encode(b"\x01\x02\x03\x04").decode()
    vconfig_mock["addrs"] = [
            {"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [2]},
            {"@type": "engine.quicAddr", "ip": 2130706433, "port": 9999},
        ]
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda *_: vconfig_mock)
    monkeypatch.setattr(MyTonCore, "get_validator_engine_ip", lambda *_: '127.0.0.1')

    monkeypatch.setattr(mytonctrl_module, 'get_git_hash', lambda *_, **__: 'abcd')
    monkeypatch.setattr(mytonctrl_module, 'get_git_branch', lambda *_: 'master')
    monkeypatch.setattr(mytonctrl_module, 'get_bin_git_hash', lambda *_, **__: 'abcd')
    monkeypatch.setattr(mytonctrl_module, 'fix_git_config', lambda *_: None)
    monkeypatch.setattr(mytonctrl_module, 'get_service_status', lambda *_: True)
    monkeypatch.setattr(mytonctrl_module, 'get_service_uptime', lambda *_: 1000)

    output = cli.execute("status", no_color=True)
    assert 'Error' not in output
    assert 'Node ports: 30000, 9999 (QUIC)' in output
    assert 'Node status' in output
    assert 'Node mode: VALIDATOR' in output
    assert 'ADNL address of local validator: 1234ABCD' in output
    assert 'Public ADNL address of node: 01020304' in output
    assert 'Local validator wallet address: WALLET_ADDR' in output
    assert 'Mytoncore status: working, 16 minutes' in output
    assert 'Local validator status: working, 16 minutes' in output
    assert 'BTC Teleport status: working, 16 minutes' in output
    assert 'Local validator out of sync: 30' in output
    assert 'Masterchain out of sync: 30 sec' in output
    assert 'Shardchain out of sync: 3 blocks' in output
    assert 'Local validator last state serialization: 10 blocks ago' in output
    assert 'Active validator groups (masterchain,shardchain): 1,2' in output
    assert 'Local validator database size: 123456 Gb, 123456%' in output
    assert 'Version mytonctrl: abcd (master)' in output
    assert 'Version validator: abcd (master)' in output
    assert 'Version BTC Teleport: n/a (n/a)' in output

    # all status
    status_mocker.out_of_sync = 10

    monkeypatch.setattr(MyTonCore, "GetNetworkName", lambda *_: 'mainnet')
    monkeypatch.setattr(MyTonCore, "get_root_workchain_enabled_time", lambda *_: 1234, raising=False)
    monkeypatch.setattr(MyTonCore, "GetRootWorkchainEnabledTime", lambda *_: 1234, raising=False)
    monkeypatch.setattr(MyTonCore, "get_config_34", lambda _: {"totalValidators": 100, "startWorkTime": 0}, raising=False)
    monkeypatch.setattr(MyTonCore, "GetConfig34", lambda _: {"totalValidators": 100, "startWorkTime": 0}, raising=False)
    monkeypatch.setattr(MyTonCore, "get_config_36", lambda _: {"startWorkTime": None}, raising=False)
    monkeypatch.setattr(MyTonCore, "GetConfig36", lambda _: {"startWorkTime": None}, raising=False)
    monkeypatch.setattr(MyTonCore, "get_shards", lambda *_: [1, 2, 3], raising=False)
    monkeypatch.setattr(MyTonCore, "GetShards", lambda *_: [1, 2, 3], raising=False)
    monkeypatch.setattr(MyTonCore, "get_config", lambda *_: {'validators_elected_for': 65536, 'elections_start_before': 32768, 'elections_end_before': 8192, 'stake_held_for': 32768}, raising=False)
    monkeypatch.setattr(MyTonCore, "GetConfig", lambda *_: {'validators_elected_for': 65536, 'elections_start_before': 32768, 'elections_end_before': 8192, 'stake_held_for': 32768}, raising=False)
    monkeypatch.setattr(MyTonCore, "get_config_17", lambda *_: {'minStake': 10000.0, 'maxStake': 10000000.0, 'maxStakeFactor': 1966080, 'minTotalStake': 200000.0}, raising=False)
    monkeypatch.setattr(MyTonCore, "GetConfig17", lambda *_: {'minStake': 10000.0, 'maxStake': 10000000.0, 'maxStakeFactor': 1966080, 'minTotalStake': 200000.0}, raising=False)
    monkeypatch.setattr(MyTonCore, "get_full_config_addr", lambda *_: 'config_addr', raising=False)
    monkeypatch.setattr(MyTonCore, "GetFullConfigAddr", lambda *_: 'config_addr', raising=False)
    monkeypatch.setattr(MyTonCore, "get_full_elector_addr", lambda *_: 'elector_addr', raising=False)
    monkeypatch.setattr(MyTonCore, "GetFullElectorAddr", lambda *_: 'elector_addr', raising=False)
    monkeypatch.setattr(MyTonCore, "get_active_election_id", lambda *_: 0, raising=False)
    monkeypatch.setattr(MyTonCore, "GetActiveElectionId", lambda *_: 0, raising=False)
    monkeypatch.setattr(MyTonCore, "GetValidatorIndex", lambda *_: 10)
    monkeypatch.setattr(MyTonCore, "GetOffersNumber", lambda *_: None)
    monkeypatch.setattr(MyTonCore, "GetComplaintsNumber", lambda *_: None)
    monkeypatch.setattr(MyTonCore, "GetAccount", lambda *_: Dict({"balance": 1000}))

    monkeypatch.setattr(mytonctrl_module, "get_memory_info", lambda: {'total': 0, 'usage': 0, 'usagePercent': 0})
    monkeypatch.setattr(mytonctrl_module, "get_swap_info", lambda: {'total': 0, 'usage': 0, 'usagePercent': 0})

    output = cli.execute("status", no_color=True)
    assert "Traceback" not in output
    assert 'Error' not in output
    assert 'TON network status' in output
    assert 'Network name: mainnet' in output
    assert 'Number of validators: 100' in output
    assert 'Number of shardchains: 3' in output
    assert 'Number of offers: n/a(n/a)' in output
    assert 'Election status: closed' in output

    assert 'TON network configuration' in output
    assert 'Configurator address: config_addr' in output
    assert 'Elector address: elector_addr' in output
    assert 'Validation period: 65536, Duration of elections: 32768-8192, Hold period: 32768' in output
    assert 'Minimum stake: 10000.0, Maximum stake: 10000000.0' in output

    assert 'TON timestamps' in output

    # test fast
    output = cli.execute("status fast", no_color=True)
    assert 'Number of validators: ' not in output
    assert "Validation period" not in output
    assert "elections" not in output

    # test other mode
    monkeypatch.setattr(MyTonCore, "using_validator", lambda *_: False)
    monkeypatch.setattr(MyTonCore, "using_liteserver", lambda *_: True)
    output = cli.execute("status", no_color=True)

    assert 'Node mode: LITESERVER' in output
    assert 'TON timestamps' not in output
    assert 'TON network configuration' not in output


def parse_modes_output(output: str) -> dict:
    result = {}
    for line in output.splitlines()[1:-1]:
        key, value, _ = line.split(maxsplit=2)
        result[key.strip()] = value.strip()
    return result

def test_modes(cli, monkeypatch):  # status_modes, enable_mode, disable_mode
    monkeypatch.setattr(sys, "exit", lambda *_: None)

    output = cli.execute("status_modes", no_color=True)
    modes = parse_modes_output(output)
    from modules import MODES
    assert len(modes) == len(MODES)
    assert modes["validator"] == "enabled"  # default enabled
    assert modes["liteserver"] == "disabled"

    output = cli.execute("disable_mode validator", no_color=True)
    assert 'disable_mode - OK' in output
    output = cli.execute("status_modes", no_color=True)
    modes = parse_modes_output(output)
    assert modes["validator"] == "disabled"
    assert modes["liteserver"] == "disabled"

    output = cli.execute("enable_mode liteserver", no_color=True)
    assert 'enable_mode - OK' in output
    output = cli.execute("status_modes", no_color=True)
    modes = parse_modes_output(output)
    assert modes["validator"] == "disabled"
    assert modes["liteserver"] == "enabled"

    output = cli.execute("enable_mode", no_color=True)
    assert 'Bad args' in output
    output = cli.execute("disable_mode", no_color=True)
    assert 'Bad args' in output

def parse_settings_output(output: str) -> dict:
    result = {}
    for line in output.splitlines()[1:-1]:
        split = line.split()
        name, mode, default, value = split[0], split[-3], split[-2], split[-1]
        result[name] = {
            "mode": mode,
            "default": default,
            "value": value
        }
    return result

def test_settings(cli, ton, monkeypatch):  # status_settings, get, set
    from modules import SETTINGS
    output = cli.execute('status_settings', no_color=True)
    settings = parse_settings_output(output)
    assert len(settings) == len(SETTINGS)

    output = cli.execute('get stake', no_color=True)
    assert 'null' in output
    output = cli.execute('status_settings', no_color=True)
    settings = parse_settings_output(output)
    assert settings['stake']['value'] == 'None'

    # test set
    output = cli.execute('set stake abc', no_color=True)
    assert 'SetSettings - OK' in output
    output = cli.execute('status_settings', no_color=True)
    settings = parse_settings_output(output)
    assert settings['stake']['value'] == 'abc'
    output = cli.execute('get stake', no_color=True)
    assert 'abc' in output

    # set value converts to int
    output = cli.execute('set stake 1000', no_color=True)
    assert 'SetSettings - OK' in output
    output = cli.execute('status_settings', no_color=True)
    settings = parse_settings_output(output)
    assert settings['stake']['value'] == '1000'
    output = cli.execute('get stake', no_color=True)
    assert '1000' in output
    assert ton.GetSettings('stake') == 1000

    # bad args
    output = cli.execute("get", no_color=True)
    assert 'Bad args' in output
    output = cli.execute("set", no_color=True)
    assert 'Bad args' in output
    output = cli.execute("set a", no_color=True)
    assert 'Bad args' in output

    # set for disabled mode
    ton.disable_mode('validator')
    output = cli.execute('set stake 1000', no_color=True)
    assert 'Error: mode validator is disabled' in output

    # set --force for disabled mode
    output = cli.execute('set stake 1000 --force', no_color=True)
    assert 'SetSettings - OK' in output
    assert ton.GetSettings('stake') == 1000

    # set unexisting setting
    output = cli.execute('set abc abc', no_color=True)
    assert 'Error: setting abc not found' in output

    # set --force for unexisting setting
    output = cli.execute('set abc abc --force', no_color=True)
    assert 'SetSettings - OK' in output
    assert ton.GetSettings('abc') == 'abc'

def test_about(cli, monkeypatch):
    from modules import MODES

    output = cli.execute('about', no_color=True)
    assert 'Bad args' in output

    output = cli.execute('about validator', no_color=True)
    assert MODES['validator'].description in output
    assert 'Enabled: yes' in output

    output = cli.execute('about liteserver', no_color=True)
    assert MODES['liteserver'].description in output
    assert 'Enabled: no' in output

    output = cli.execute('about abc', no_color=True)
    assert 'Mode abc not found' in output

def test_download_archive_blocks(cli, monkeypatch):
    output = cli.execute('download_archive_blocks')
    assert 'Bad args' in output

    calls = []
    def download_blocks(*args):
        nonlocal calls
        calls = args
        return

    monkeypatch.setattr('mytonctrl.mytonctrl.download_blocks', download_blocks)

    output = cli.execute('download_archive_blocks test/ 1')
    assert 'Failed to get Ton Storage API port and port was not provided' in output
    monkeypatch.setattr('mytonctrl.mytonctrl.get_ton_storage_port', lambda *_: 3334)

    # unable to connect
    output = cli.execute('download_archive_blocks test/ 1')
    assert 'Error: cannot connect to ton-storage at 127.0.0.1:3334' in output

    monkeypatch.setattr(requests, 'get', lambda *_, **__: None)

    output = cli.execute('download_archive_blocks test/ 1')

    assert 'Error' not in output
    assert calls[1:] == (str(pathlib.Path(os.getcwd()) / 'test/'), 1, None, False)
    assert calls[0].buffer.ton_storage.api_port == 3334

    output = cli.execute('download_archive_blocks test/ 1 2')

    assert 'Error' not in output
    assert calls[1:] == (str(pathlib.Path(os.getcwd()) / 'test/'), 1, 2, False)
    assert calls[0].buffer.ton_storage.api_port == 3334

    output = cli.execute('download_archive_blocks test/ 1 2 --only-master')

    assert 'Error' not in output
    assert calls[1:] == (str(pathlib.Path(os.getcwd()) / 'test/'), 1, 2, True)
    assert calls[0].buffer.ton_storage.api_port == 3334

    output = cli.execute('download_archive_blocks 123 test/ 1 2 --only-master')

    assert 'Error' not in output
    assert calls[1:] == (str(pathlib.Path(os.getcwd()) / 'test/'), 1, 2, True)
    assert calls[0].buffer.ton_storage.api_port == 123

    output = cli.execute('download_archive_blocks 123 /test/ 1')

    assert 'Error' not in output
    assert calls[1:] == ('/test', 1, None, False)
    assert calls[0].buffer.ton_storage.api_port == 123


def test_set_quic_port(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args - no args
    output = cli.execute("set_quic_port", no_color=True)
    assert "Bad args" in output

    # Bad args - too many args
    output = cli.execute("set_quic_port 1234 2 extra", no_color=True)
    assert "Bad args" in output

    # Bad args - port not integer
    output = cli.execute("set_quic_port abc", no_color=True)
    assert "Port must be an integer" in output

    # Bad args - port out of range
    output = cli.execute("set_quic_port -1", no_color=True)
    assert "Port must be between 0 and 65535" in output
    output = cli.execute("set_quic_port 65536", no_color=True)
    assert "Port must be between 0 and 65535" in output

    # Bad args - category not integer
    output = cli.execute("set_quic_port 1234 abc", no_color=True)
    assert "Category must be an integer" in output

    # Happy path - set quic port with default category, no existing quic addrs, no collators
    validator_console_mock = mocker.Mock()
    validator_console_mock.Run.return_value = "success"
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda self: {
        "addrs": [{"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [2]}],  # 127.0.0.1
        "collators": [],
    })
    monkeypatch.setattr(MyTonCore, "GetAdnlAddr", lambda self: "TEST_ADNL_ADDR")
    update_adnl_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "update_adnl_category", update_adnl_mock)
    ton.validatorConsole = validator_console_mock

    output = cli.execute("set_quic_port 1234", no_color=True)
    update_adnl_mock.assert_called_once_with(adnl_addr="TEST_ADNL_ADDR", category=2)
    validator_console_mock.Run.assert_called_once_with("add-quic-addr 127.0.0.1:1234 [ 2 ] [ ]")

    # Happy path - with custom category
    update_adnl_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda self: {
        "addrs": [{"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [3]}],
        "collators": [],
    })
    output = cli.execute("set_quic_port 5555 3", no_color=True)
    update_adnl_mock.assert_called_once_with(adnl_addr="TEST_ADNL_ADDR", category=3)
    validator_console_mock.Run.assert_called_once_with("add-quic-addr 127.0.0.1:5555 [ 3 ] [ ]")

    # Happy path - delete existing quic addr before adding new one
    update_adnl_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda self: {
        "addrs": [
            {"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [2]},
            {"@type": "engine.quicAddr", "ip": 2130706433, "port": 9999, "categories": [1], "priority_categories": []},
        ],
        "collators": [],
    })
    output = cli.execute("set_quic_port 1234", no_color=True)
    assert "Deleted quic addr 127.0.0.1:9999" in output
    assert validator_console_mock.Run.call_count == 2
    validator_console_mock.Run.assert_any_call("del-quic-addr 127.0.0.1:9999 [ 1 ] [  ]")
    validator_console_mock.Run.assert_any_call("add-quic-addr 127.0.0.1:1234 [ 2 ] [ ]")

    # Happy path - with collators, updates their adnl categories too
    update_adnl_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda self: {
        "addrs": [{"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [2]}],
        "collators": [{"adnl_id": base64.b64encode(b"\xaa" * 32).decode()}],
    })
    output = cli.execute("set_quic_port 1234", no_color=True)
    assert update_adnl_mock.call_count == 2
    update_adnl_mock.assert_any_call(adnl_addr="TEST_ADNL_ADDR", category=2)

    # Port 0 - should not call add-quic-addr
    update_adnl_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda self: {
        "addrs": [{"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [2]}, {"@type": "engine.quicAddr", "ip": 2130706433, "port": 9999, "categories": [1], "priority_categories": []}],
        "collators": [],
    })
    output = cli.execute("set_quic_port 0", no_color=True)
    update_adnl_mock.assert_not_called()
    validator_console_mock.Run.assert_called_once_with("del-quic-addr 127.0.0.1:9999 [ 1 ] [  ]")

    # Category not set for address - should raise
    update_adnl_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", lambda self: {
        "addrs": [{"@type": "engine.addr", "ip": 2130706433, "port": 30000, "categories": [1, 3]}],
        "collators": [],
    })
    output = cli.execute("set_quic_port 1234", no_color=True)
    assert "Category 2 is not set for address" in output
    validator_console_mock.Run.assert_not_called()
    update_adnl_mock.assert_not_called()
