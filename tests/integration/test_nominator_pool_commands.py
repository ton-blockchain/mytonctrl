import os
import pathlib

import pytest
from pytest_mock import MockerFixture

from mypylib import Dict

from mytoncore.mytoncore import MyTonCore

from tests.helpers import create_pool_file


def test_new_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("new_pool", no_color=True)
    assert "Bad args" in output
    output = cli.execute(f"new_pool pool 5.5", no_color=True)
    assert "Bad args" in output

    # happy path
    download_contract_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "DownloadContract", download_contract_mock)

    get_validator_wallet_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_validator_wallet_mock)

    def fake_fift_run(args: list):
        file_path = args[-1]
        with open(file_path + ".addr", 'wb') as f:
            f.write(b'\x00'*36)
        return "Saved pool"

    monkeypatch.setattr(ton.fift, "run", fake_fift_run)

    pool_name = "test_new_pool"
    pool_path = ton.poolsDir + pool_name
    addr_file = pool_path + ".addr"
    assert not os.path.exists(addr_file)

    output = cli.execute(f"new_pool {pool_name} 5.5 10 10000 1000", no_color=True)

    assert "NewPool - OK" in output
    download_contract_mock.assert_called_once()
    get_validator_wallet_mock.assert_called_once()
    assert os.path.isfile(addr_file)

    # pool already exists
    output = cli.execute(f"new_pool {pool_name} 5.5 10 10000 1000", no_color=True)
    assert 'CreatePool warning: Pool already exists' in output

    output = cli.execute(f"new_pool pool2 5.5 10 10000 1000", no_color=True)
    assert os.path.isfile(addr_file)
    assert 'Pool with the same parameters already exists' in output


def test_activate_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("activate_pool", no_color=True)
    assert "Bad args" in output

    # happy path
    pool_name = "test_activate_pool"
    pool_path = ton.poolsDir + pool_name
    create_pool_file(pool_path, b'\x00' * 36)

    account = Dict()
    account.status = "uninit"
    get_account_mock = mocker.Mock(return_value=account)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)

    validator_wallet = Dict()
    validator_wallet.addrB64 = "test_addr"
    get_validator_wallet_mock = mocker.Mock(return_value=validator_wallet)
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_validator_wallet_mock)

    check_account_active_mock = mocker.Mock()
    send_file_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "check_account_active", check_account_active_mock)
    monkeypatch.setattr(MyTonCore, "SendFile", send_file_mock)

    output = cli.execute(f"activate_pool {pool_name}", no_color=True)

    assert "ActivatePool - OK" in output
    get_account_mock.assert_called_once()
    get_validator_wallet_mock.assert_called_once()
    check_account_active_mock.assert_called_once_with(validator_wallet.addrB64)
    send_file_mock.assert_called_once()

    # empty account
    account.status = "empty"
    output = cli.execute(f"activate_pool {pool_name}")
    assert "account status is empty" in output

    # already active account
    account.status = "active"
    get_account_mock.reset_mock()
    get_validator_wallet_mock.reset_mock()
    check_account_active_mock.reset_mock()
    send_file_mock.reset_mock()

    output = cli.execute(f"activate_pool {pool_name}", no_color=True)
    assert "ActivatePool - OK" in output
    get_account_mock.assert_called_once()
    get_validator_wallet_mock.assert_not_called()
    check_account_active_mock.assert_not_called()
    send_file_mock.assert_not_called()


def test_update_validator_set(cli, ton, monkeypatch, mocker: MockerFixture):
    output = cli.execute("update_validator_set", no_color=True)
    assert "Bad args" in output

    get_validator_wallet_mock = mocker.Mock()
    pool_update_validator_set_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_validator_wallet_mock)
    monkeypatch.setattr(MyTonCore, "PoolUpdateValidatorSet", pool_update_validator_set_mock)

    output = cli.execute(f"update_validator_set test", no_color=True)

    # Verify the command succeeded
    assert "UpdateValidatorSet - OK" in output
    get_validator_wallet_mock.assert_called_once()
    pool_update_validator_set_mock.assert_called_once_with('test', get_validator_wallet_mock.return_value)


def test_withdraw_from_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    output = cli.execute("withdraw_from_pool", no_color=True)
    assert "Bad args" in output
    output = cli.execute("withdraw_from_pool test", no_color=True)
    assert "Bad args" in output

    pool_data = Dict()
    pool_data.state = 0
    get_pool_data_mock = mocker.Mock(return_value=pool_data)
    monkeypatch.setattr(MyTonCore, "GetPoolData", get_pool_data_mock)

    withdraw_from_pool_process_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "WithdrawFromPoolProcess", withdraw_from_pool_process_mock)

    # happy path
    pool_addr = "test"
    amount = 100.5
    output = cli.execute(f"withdraw_from_pool {pool_addr} {amount}", no_color=True)

    assert "WithdrawFromPool - OK" in output
    get_pool_data_mock.assert_called_once_with(pool_addr)
    withdraw_from_pool_process_mock.assert_called_once_with(pool_addr, amount)

    pool_data.state = 1
    get_pool_data_mock.reset_mock()
    withdraw_from_pool_process_mock.reset_mock()

    output = cli.execute(f"withdraw_from_pool {pool_addr} {amount}", no_color=True)

    assert "WithdrawFromPool - OK" in output
    get_pool_data_mock.assert_called_once_with(pool_addr)
    withdraw_from_pool_process_mock.assert_not_called()
    assert ton.GetPendingWithdraws()[pool_addr] == 100.5


def test_deposit_to_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("deposit_to_pool", no_color=True)
    assert "Bad args" in output
    output = cli.execute("deposit_to_pool test", no_color=True)
    assert "Bad args" in output

    # happy path
    get_validator_wallet_mock = mocker.Mock()
    get_validator_wallet_mock.return_value.name = 'wallet_name'
    fift_run_mock = mocker.Mock(return_value="Success")
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_validator_wallet_mock)
    monkeypatch.setattr(ton.fift, "run", fift_run_mock)

    result_file_path = "/tmp/signed.boc"
    sign_boc_mock = mocker.Mock(return_value=result_file_path)
    monkeypatch.setattr(MyTonCore, "SignBocWithWallet", sign_boc_mock)
    send_file_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "SendFile", send_file_mock)

    pool_addr = "test_addr"
    amount = 500.0
    output = cli.execute(f"deposit_to_pool {pool_addr} {amount}", no_color=True)

    assert "DepositToPool - OK" in output
    get_validator_wallet_mock.assert_called_once()
    fift_run_mock.assert_called_once()
    fift_args = fift_run_mock.call_args[0][0]
    assert "/contracts/nominator-pool/func/validator-deposit.fif" in fift_args[0]
    assert pathlib.Path(fift_args[1]).name == 'wallet_namevalidator-deposit-query.boc'

    sign_boc_mock.assert_called_once()
    sign_call_args = sign_boc_mock.call_args[0]
    assert sign_call_args[0] == get_validator_wallet_mock.return_value
    assert "wallet_namevalidator-deposit-query.boc" in sign_call_args[1]
    assert sign_call_args[2] == pool_addr
    assert sign_call_args[3] == amount

    send_file_mock.assert_called_once_with(result_file_path, get_validator_wallet_mock.return_value)
