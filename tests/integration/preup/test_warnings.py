import pytest
from pytest_mock import MockerFixture

import modules
from mytoncore import MyTonCore
from mytonctrl import mytonctrl


@pytest.fixture(autouse=True)
def before_test(monkeypatch):
    monkeypatch.setattr(mytonctrl, 'check_mytonctrl_update', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'check_installer_user', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'check_vport', lambda *_: None)

def test_check_disk_usage(cli, monkeypatch):
    monkeypatch.setattr(MyTonCore, 'GetDbUsage', lambda *_: 95)
    output = cli.run_pre_up()
    assert 'Disk is almost full, clean the TON database immediately' in output

    monkeypatch.setattr(MyTonCore, 'GetDbUsage', lambda *_: 70)
    output = cli.run_pre_up()
    assert 'Disk is almost full' not in output


def test_check_sync(cli, monkeypatch, ton, mocker: MockerFixture):
    mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, 'GetValidatorStatus', mock)
    output = cli.run_pre_up()
    assert 'Node sync is not completed' in output

    mock.return_value.initial_sync = None
    mock.return_value.is_working = False
    output = cli.run_pre_up()
    assert 'Node is out of sync' in output

    mock.return_value.is_working = True
    output = cli.run_pre_up()
    assert 'Node is out of sync' not in output
    assert 'Node sync is not completed' not in output


def test_check_adnl(cli, monkeypatch, mocker: MockerFixture):
    config_mock = mocker.Mock()

    config_mock.fullnodeslaves = None
    from modules.utilities import UtilitiesModule
    monkeypatch.setattr(UtilitiesModule, 'check_adnl_connection', lambda *_: (False, 'ADNL connection failed'))
    output = cli.run_pre_up()
    assert 'ADNL connection failed' in output

    config_mock.fullnodeslaves = True
    monkeypatch.setattr(MyTonCore, 'GetValidatorConfig', lambda *_: config_mock)
    output = cli.run_pre_up()
    assert 'ADNL' not in output

    config_mock.fullnodeslaves = None
    monkeypatch.setattr(UtilitiesModule, 'check_adnl_connection', lambda *_: (True, None))
    output = cli.run_pre_up()
    assert 'ADNL connection failed' not in output


def test_check_validator_balance(cli, monkeypatch, mocker: MockerFixture):
    validator_status_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, 'GetValidatorStatus', lambda *_: validator_status_mock)

    account_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, 'GetAccount', lambda *_: account_mock)

    validator_wallet_mock = mocker.Mock()
    validator_wallet_mock.addrB64 = 'test_address'
    monkeypatch.setattr(MyTonCore, 'GetValidatorWallet', lambda *_: validator_wallet_mock)

    validator_status_mock.is_working = False
    validator_status_mock.out_of_sync = 0
    output = cli.run_pre_up()
    assert 'balance' not in output

    validator_status_mock.is_working = True
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: False)
    output = cli.run_pre_up()
    assert 'balance' not in output

    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: True)
    monkeypatch.setattr(MyTonCore, 'GetAccount', lambda *_: None)
    output = cli.run_pre_up()
    assert 'Failed to check validator wallet balance' in output

    monkeypatch.setattr(MyTonCore, 'GetAccount', lambda *_: account_mock)
    account_mock.balance = 50
    output = cli.run_pre_up()
    assert 'Validator wallet balance is low' in output

    account_mock.balance = 150
    output = cli.run_pre_up()
    assert 'Validator wallet balance is low' not in output


def test_check_vps(cli, monkeypatch):
    monkeypatch.setattr('mytonctrl.mytonctrl.is_host_virtual', lambda : {'virtual': True, 'product_name': 'VirtualBox'})
    output = cli.run_pre_up()
    assert 'Virtualization detected' in output

    monkeypatch.setattr('mytonctrl.mytonctrl.is_host_virtual', lambda : {'virtual': False})
    output = cli.run_pre_up()
    assert 'Virtualization detected' not in output


def test_check_tg_channel(cli, monkeypatch, ton):
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: True)
    output = cli.run_pre_up()
    assert 'Make sure you are subscribed to the TON validators channel' in output

    ton.local.db['subscribe_tg_channel'] = True
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: True)
    output = cli.run_pre_up()
    assert 'Make sure you are subscribed to the TON validators channel' not in output

    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: False)
    output = cli.run_pre_up()
    assert 'Make sure you are subscribed to the TON validators channel' not in output


def test_check_slashed(cli, monkeypatch, mocker: MockerFixture):
    validator_status_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, 'GetValidatorStatus', lambda *_: validator_status_mock)

    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: True)
    validator_status_mock.out_of_sync = 10

    monkeypatch.setattr(modules.ValidatorModule, 'get_my_complaint', lambda *_: {'suggestedFine': 99})
    validator_status_mock.is_working = True
    output = cli.run_pre_up()
    assert 'You were fined by 99 TON' in output

    monkeypatch.setattr(modules.ValidatorModule, 'get_my_complaint', lambda *_: None)
    validator_status_mock.is_working = True
    output = cli.run_pre_up()
    assert 'You were fined' not in output

    validator_status_mock.is_working = False
    output = cli.run_pre_up()
    assert 'You were fined' not in output


def test_check_node_port(cli, monkeypatch):
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: True)

    # Port > 64535, no quic addr -> warning
    vconfig = {"addrs": [{"@type": "engine.addr", "port": 64536}]}
    monkeypatch.setattr(MyTonCore, 'GetValidatorConfig', lambda *_: vconfig)
    output = cli.run_pre_up()
    assert 'Node port 64536 is greater than 64535' in output

    # Port <= 64535 -> no warning
    vconfig["addrs"] = [{"@type": "engine.addr", "port": 64535}]
    output = cli.run_pre_up()
    assert 'greater than 64535' not in output

    vconfig["addrs"] = [{"@type": "engine.addr", "port": 30000}]
    output = cli.run_pre_up()
    assert 'greater than 64535' not in output

    # Port > 64535 but quic addr exists -> no warning
    vconfig["addrs"] = [{"@type": "engine.addr", "port": 64536}, {"@type": "engine.quicAddr", "port": 64536}]
    output = cli.run_pre_up()
    assert 'greater than 64535' not in output

    # Not a validator -> no warning
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda *_: False)
    vconfig["addrs"] = [{"@type": "engine.addr", "port": 64536}]
    output = cli.run_pre_up()
    assert 'greater than 64535' not in output


def test_check_ubuntu_version(cli, monkeypatch, mocker: MockerFixture):
    monkeypatch.setattr(mytonctrl.os.path, 'exists', lambda _: True)
    res = '''
PRETTY_NAME="Ubuntu 22.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.4 LTS (Jammy Jellyfish)"
VERSION_CODENAME=jammy
ID=ubuntu
'''
    mock = mocker.mock_open(read_data=res)
    monkeypatch.setattr('builtins.open', mock)
    output = cli.run_pre_up()
    assert 'Ubuntu' not in output

    monkeypatch.setattr(mytonctrl.os.path, 'exists', lambda _: True)
    res = '''
    PRETTY_NAME="Ubuntu 24.04.4 LTS"
    NAME="Ubuntu"
    VERSION_ID="24.04"
    VERSION="24.04.3 LTS (Noble Numbat)"
    VERSION_CODENAME=noble
    ID=ubuntu
    '''
    mock = mocker.mock_open(read_data=res)
    monkeypatch.setattr('builtins.open', mock)
    output = cli.run_pre_up()
    assert 'Ubuntu' not in output

    res = '''
PRETTY_NAME="Ubuntu 20.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="20.04"
VERSION="20.04.4 LTS (Focal Fossa)"
VERSION_CODENAME=focal
ID=ubuntu
'''
    mock = mocker.mock_open(read_data=res)
    monkeypatch.setattr('builtins.open', mock)
    output = cli.run_pre_up()
    assert 'Ubuntu version must be 22.04 or 24.04. Found 20.04.' in output

    res = '''
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
NAME="Debian GNU/Linux"
VERSION_ID="12"
VERSION="12 (bookworm)"
VERSION_CODENAME=bookworm
ID=debian
'''
    mock = mocker.mock_open(read_data=res)
    monkeypatch.setattr('builtins.open', mock)
    output = cli.run_pre_up()
    assert 'Ubuntu' not in output
