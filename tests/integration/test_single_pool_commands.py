import os
import struct

import pytest
from pytest_mock import MockerFixture
from mypylib import Dict
from mytoncore.mytoncore import MyTonCore
from modules.single_pool import SingleNominatorModule
from tests.helpers import create_pool_file


def test_new_single_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("new_single_pool", no_color=True)
    assert "Bad args" in output
    output = cli.execute("new_single_pool test_pool", no_color=True)
    assert "Bad args" in output

    # happy path
    download_contract_mock = mocker.Mock()
    get_validator_wallet_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "DownloadContract", download_contract_mock)
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_validator_wallet_mock)

    def fake_fift_run(args):
        file_path = args[-1]
        with open(file_path + ".addr", 'wb') as f:
            f.write(b'\x00'*36)
        return "Saved single nominator pool"

    monkeypatch.setattr(ton.fift, "run", fake_fift_run)

    pool_name = "test_single_pool"
    pool_path = ton.poolsDir + pool_name
    addr_file = pool_path + ".addr"
    owner_address = "owner_address"

    assert not os.path.exists(addr_file)

    output = cli.execute(f"new_single_pool {pool_name} {owner_address}", no_color=True)

    assert "new_single_pool - OK" in output
    download_contract_mock.assert_called_once()
    get_validator_wallet_mock.assert_called_once()
    assert os.path.isfile(addr_file)

    # pool already exists
    output = cli.execute(f"new_single_pool {pool_name} {owner_address}", no_color=True)
    assert "create_single_pool warning: Pool already exists" in output
    assert os.path.isfile(addr_file)

    output = cli.execute(f"new_single_pool pool2 {owner_address}")
    assert os.path.isfile(addr_file)
    assert 'Pool with the same parameters already exists' in output


def test_activate_single_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("activate_single_pool", no_color=True)
    assert "Bad args" in output

    pool_name = "test_activate_single_pool"
    pool_path = ton.poolsDir + pool_name
    create_pool_file(pool_path, b'\x00' * 36)

    boc_file = pool_path + "-query.boc"
    with open(boc_file, 'wb') as f:
        f.write(b'\x00' * 100)

    get_validator_wallet_mock = mocker.Mock()
    validator_wallet = get_validator_wallet_mock.return_value
    check_account_active_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_validator_wallet_mock)
    monkeypatch.setattr(MyTonCore, "check_account_active", check_account_active_mock)

    result_file_path = "/tmp/signed.boc"
    sign_boc_mock = mocker.Mock(return_value=result_file_path)
    monkeypatch.setattr(MyTonCore, "SignBocWithWallet", sign_boc_mock)

    send_file_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "SendFile", send_file_mock)

    output = cli.execute(f"activate_single_pool {pool_name}", no_color=True)

    assert "activate_single_pool - OK" in output
    get_validator_wallet_mock.assert_called_once()
    check_account_active_mock.assert_called_once_with(validator_wallet.addrB64)
    sign_boc_mock.assert_called_once()

    sign_call_args = sign_boc_mock.call_args[0]
    assert sign_call_args[0] == validator_wallet
    assert sign_call_args[1] == boc_file
    assert sign_call_args[2] == 'UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJKZ'
    assert sign_call_args[3] == 1
    assert sign_boc_mock.call_args[1]['boc_mode'] == "--with-init"

    send_file_mock.assert_called_once_with(result_file_path, validator_wallet)

    # pool already activated
    os.remove(boc_file)
    get_validator_wallet_mock.reset_mock()
    check_account_active_mock.reset_mock()
    sign_boc_mock.reset_mock()
    send_file_mock.reset_mock()

    output = cli.execute(f"activate_single_pool {pool_name}", no_color=True)

    assert "Pool test_activate_single_pool already activated" in output
    get_validator_wallet_mock.assert_not_called()
    check_account_active_mock.assert_not_called()
    sign_boc_mock.assert_not_called()
    send_file_mock.assert_not_called()


def test_withdraw_from_single_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("withdraw_from_single_pool", no_color=True)
    assert "Bad args" in output
    output = cli.execute("withdraw_from_single_pool test", no_color=True)
    assert "Bad args" in output

    # happy path
    withdraw_from_pool_process_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "WithdrawFromPoolProcess", withdraw_from_pool_process_mock)
    pool_addr = "test_addr"
    amount = 250.75
    output = cli.execute(f"withdraw_from_single_pool {pool_addr} {amount}", no_color=True)

    assert "withdraw_from_single_pool - OK" in output
    withdraw_from_pool_process_mock.assert_called_once_with(pool_addr, amount)
