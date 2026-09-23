"""Console commands of modules/controller.py (liquid-staking controllers).

These pin the behaviour of the console handlers: which MyTonCore calls each
command makes, with which arguments, and what it prints.
"""
import json
import os

import pytest
from pytest_mock import MockerFixture

import modules.controller as controller_module
from mytoncore.models import Account, Config15, Wallet
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import raw_addr_to_b64


CONTROLLER_0 = raw_addr_to_b64("-1:" + "a0" * 32)
CONTROLLER_1 = raw_addr_to_b64("-1:" + "a1" * 32)
CONTROLLER_2 = raw_addr_to_b64("-1:" + "a2" * 32)
CONTROLLER_3 = raw_addr_to_b64("-1:" + "a3" * 32)
LIQUID_POOL = raw_addr_to_b64("0:" + "cc" * 32)
BAD_ADDR_ERROR = "argument controller_addr: expected a TON address (in user-friendly or raw form), got 'not_an_address'"

CONTROLLER_COMMANDS = [
    "create_controllers",
    "update_controllers",
    "controllers_list",
    "get_controller_data",
    "deposit_to_controller",
    "withdraw_from_controller",
    "calculate_annual_controller_percentage",
    "controller_update_validator_set",
    "stop_controller",
    "stop_and_withdraw_controller",
    "add_controller",
    "test_calculate_loan_amount",
]


@pytest.fixture(autouse=True)
def _enable_liquid_staking(monkeypatch):
    # autouse: must be applied before the `cli` fixture registers the modules
    monkeypatch.setattr(MyTonCore, "using_liquid_staking", lambda self: True)


@pytest.fixture()
def validator_wallet(ton, monkeypatch, mocker: MockerFixture) -> Wallet:
    wallet = Wallet(-1, "ee" * 32, "wallet_001", ton.walletsDir + "wallet_001", "v3")
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", mocker.Mock(return_value=wallet))
    return wallet


@pytest.fixture()
def sign_boc_mock(monkeypatch, mocker: MockerFixture):
    mock = mocker.Mock(side_effect=lambda wallet, boc_path, dest, coins: boc_path + ".signed")
    monkeypatch.setattr(MyTonCore, "SignBocWithWallet", mock)
    return mock


@pytest.fixture()
def send_file_mock(monkeypatch, mocker: MockerFixture):
    mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "SendFile", mock)
    return mock


def _sections(output: str) -> dict:
    """Split `controllers_list` output into {"using controllers": [row, ...], ...}."""
    sections = {}
    current = None
    for line in output.splitlines():
        if line.endswith("controllers:"):
            current = line[:-1]
            sections[current] = []
        elif line.strip() and current is not None:
            sections[current].append(line.split())
    return sections


def test_controller_commands_registered(cli):
    output = cli.execute("help", no_color=True)
    registered = {line.split()[0] for line in output.splitlines() if line.strip()}
    assert set(CONTROLLER_COMMANDS) <= registered


def test_create_controllers(cli, ton, monkeypatch, mocker: MockerFixture,
                            validator_wallet, sign_boc_mock, send_file_mock):
    ton.local.db["liquid_pool_addr"] = LIQUID_POOL
    get_controllers_mock = mocker.Mock(return_value=[CONTROLLER_0, CONTROLLER_1])
    download_contract_mock = mocker.Mock()
    time_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetControllers", get_controllers_mock)
    monkeypatch.setattr(MyTonCore, "DownloadContract", download_contract_mock)
    monkeypatch.setattr(controller_module, "time", time_mock)
    scripts = ton.contractsDir + "jetton_pool/fift-scripts/"

    # new controller set: download the contracts, deploy both controllers
    output = cli.execute("create_controllers", no_color=True)
    assert "CreateControllers - OK" in output
    get_controllers_mock.assert_called_once_with()
    download_contract_mock.assert_called_once_with("https://github.com/igroman787/jetton_pool")
    assert sign_boc_mock.call_args_list == [
        mocker.call(validator_wallet, scripts + "deploy_controller0.boc", LIQUID_POOL, 1),
        mocker.call(validator_wallet, scripts + "deploy_controller1.boc", LIQUID_POOL, 1),
    ]
    assert send_file_mock.call_args_list == [
        mocker.call(scripts + "deploy_controller0.boc.signed", validator_wallet),
        mocker.call(scripts + "deploy_controller1.boc.signed", validator_wallet),
    ]
    time_mock.sleep.assert_called_once_with(10)
    assert ton.local.db["old_controllers"] == []
    assert ton.local.db["using_controllers"] == [CONTROLLER_0, CONTROLLER_1]

    # update_controllers is the same handler; contracts already present -> no download
    os.makedirs(ton.contractsDir + "jetton_pool/")
    get_controllers_mock.return_value = [CONTROLLER_2, CONTROLLER_3]
    for mock in (download_contract_mock, sign_boc_mock, send_file_mock):
        mock.reset_mock()
    output = cli.execute("update_controllers", no_color=True)
    assert "CreateControllers - OK" in output
    download_contract_mock.assert_not_called()
    assert sign_boc_mock.call_count == 2
    assert send_file_mock.call_count == 2
    assert ton.local.db["old_controllers"] == [CONTROLLER_0, CONTROLLER_1]
    assert ton.local.db["using_controllers"] == [CONTROLLER_2, CONTROLLER_3]

    # unchanged controller set: nothing is sent, OK is still printed
    sign_boc_mock.reset_mock()
    send_file_mock.reset_mock()
    MyTonCore.GetValidatorWallet.reset_mock()
    output = cli.execute("update_controllers", no_color=True)
    assert "CreateControllers - OK" in output
    MyTonCore.GetValidatorWallet.assert_not_called()
    sign_boc_mock.assert_not_called()
    send_file_mock.assert_not_called()

    get_controllers_mock.reset_mock()
    output = cli.execute("create_controllers extra args", no_color=True)
    assert "usage: create_controllers [-h]" in output
    assert "create_controllers: error: unrecognized arguments: extra args" in output
    assert "CreateControllers - OK" not in output
    output = cli.execute("update_controllers extra", no_color=True)
    assert "update_controllers: error: unrecognized arguments: extra" in output
    assert "CreateControllers - OK" not in output
    get_controllers_mock.assert_not_called()
    sign_boc_mock.assert_not_called()


def test_create_controllers_without_liquid_pool(cli, monkeypatch, mocker: MockerFixture,
                                                validator_wallet, sign_boc_mock):
    monkeypatch.setattr(MyTonCore, "GetControllers", mocker.Mock(return_value=[CONTROLLER_0, CONTROLLER_1]))
    output = cli.execute("create_controllers", no_color=True)
    assert "GetLiquidPoolAddr error: liquid_pool_addr not set" in output
    assert "CreateControllers - OK" not in output
    sign_boc_mock.assert_not_called()


def test_controllers_list(cli, ton, monkeypatch, mocker: MockerFixture):
    accounts = {
        CONTROLLER_0: Account(-1, "a0" * 32, status="active", balance=100.5),
        CONTROLLER_1: Account(-1, "a1" * 32, status="active", balance=50.0),
        CONTROLLER_2: Account(-1, "a2" * 32),  # empty
        CONTROLLER_3: Account(-1, "a3" * 32, status="uninit", balance=1.0),
    }
    controller_data = {
        CONTROLLER_0: {"approved": -1, "state": 0},
        CONTROLLER_1: {"approved": 0, "state": 3},
        CONTROLLER_3: {"approved": -1, "state": 2},
    }

    def fake_get_controller_data(addr):
        if addr not in controller_data:
            raise Exception("runmethodfull failed")  # swallowed by the handler
        return controller_data[addr]

    get_controllers_mock = mocker.Mock(return_value=[CONTROLLER_0, CONTROLLER_1])
    get_account_mock = mocker.Mock(side_effect=lambda addr: accounts[addr])
    get_controller_data_mock = mocker.Mock(side_effect=fake_get_controller_data)
    monkeypatch.setattr(MyTonCore, "GetControllers", get_controllers_mock)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)
    monkeypatch.setattr(MyTonCore, "GetControllerData", get_controller_data_mock)
    header = ["Address", "Status", "Balance", "Approved", "State"]

    # fresh db: nothing in use yet, the controllers from the liquid pool are "new"
    output = cli.execute("controllers_list", no_color=True)
    assert _sections(output) == {
        "using controllers": [],
        "new controllers": [
            header,
            [CONTROLLER_0, "active", "100.5", "True", "0"],
            [CONTROLLER_1, "active", "50.0", "False", "3"],
        ],
    }
    get_controllers_mock.assert_called_once_with()

    # every section, controller data failure shown as not approved / state None
    ton.local.db["using_controllers"] = [CONTROLLER_0, CONTROLLER_1]
    ton.local.db["old_controllers"] = [CONTROLLER_2]
    ton.local.db["user_controllers_list"] = [CONTROLLER_3]
    get_account_mock.reset_mock()
    output = cli.execute("controllers_list", no_color=True)
    assert _sections(output) == {
        "using controllers": [
            header,
            [CONTROLLER_0, "active", "100.5", "True", "0"],
            [CONTROLLER_1, "active", "50.0", "False", "3"],
        ],
        "old controllers": [header, [CONTROLLER_2, "empty", "0", "False", "None"]],
        "user controllers": [header, [CONTROLLER_3, "uninit", "1.0", "True", "2"]],
    }
    assert get_account_mock.call_args_list == [
        mocker.call(CONTROLLER_0), mocker.call(CONTROLLER_1), mocker.call(CONTROLLER_2), mocker.call(CONTROLLER_3),
    ]

    # the "user controllers" section reads `user_controllers_list`, while add_controller
    # writes `user_controllers`: controllers added with add_controller are not listed
    del ton.local.db["user_controllers_list"]
    ton.local.db["old_controllers"] = []
    output = cli.execute(f"add_controller {CONTROLLER_3}", no_color=True)
    assert "AddController - OK" in output
    output = cli.execute("controllers_list", no_color=True)
    assert list(_sections(output)) == ["using controllers"]
    assert CONTROLLER_3 not in output

    get_controllers_mock.reset_mock()
    output = cli.execute("controllers_list extra", no_color=True)
    assert "usage: controllers_list [-h]" in output
    assert "controllers_list: error: unrecognized arguments: extra" in output
    assert "using controllers:" not in output
    get_controllers_mock.assert_not_called()


def test_get_controller_data(cli, ton, monkeypatch, mocker: MockerFixture):
    lite_client_run_mock = mocker.Mock(
        return_value="conn ready\nresult:  [ 0 0 -1 1000000000000 1700000000 12345 2 1700000100 32768 5 1699990000 ] \n"
    )
    monkeypatch.setattr(ton.liteClient, "run", lite_client_run_mock)

    # Bad args
    output = cli.execute("get_controller_data", no_color=True)
    assert "usage: get_controller_data [-h] controller_addr" in output
    assert "get_controller_data: error: the following arguments are required: controller_addr" in output
    output = cli.execute(f"get_controller_data {CONTROLLER_0} {CONTROLLER_1}", no_color=True)
    assert f"get_controller_data: error: unrecognized arguments: {CONTROLLER_1}" in output
    output = cli.execute("get_controller_data not_an_address", no_color=True)
    assert f"get_controller_data: error: {BAD_ADDR_ERROR}" in output
    lite_client_run_mock.assert_not_called()

    output = cli.execute(f"get_controller_data {CONTROLLER_0}", no_color=True)
    lite_client_run_mock.assert_called_once_with(f"runmethodfull {CONTROLLER_0} get_validator_controller_data")
    expected = {
        "state": 0,
        "halted": 0,
        "approved": -1,
        "stake_amount_sent": 1000000000000,
        "stake_at": 1700000000,
        "saved_validator_set_hash": 12345,
        "validator_set_changes_count": 2,
        "validator_set_change_time": 1700000100,
        "stake_held_for": 32768,
        "borrowed_amount": 5,
        "borrowing_time": 1699990000,
    }
    assert json.dumps(expected, indent=4) in output


def test_deposit_to_controller(cli, ton, validator_wallet, sign_boc_mock, send_file_mock):
    top_up_boc = ton.contractsDir + "jetton_pool/fift-scripts/top-up.boc"

    # Bad args
    output = cli.execute("deposit_to_controller", no_color=True)
    assert "usage: deposit_to_controller [-h] controller_addr amount" in output
    assert "deposit_to_controller: error: the following arguments are required: controller_addr, amount" in output
    output = cli.execute(f"deposit_to_controller {CONTROLLER_0}", no_color=True)
    assert "deposit_to_controller: error: the following arguments are required: amount" in output
    output = cli.execute(f"deposit_to_controller {CONTROLLER_0} 100 extra", no_color=True)
    assert "deposit_to_controller: error: unrecognized arguments: extra" in output
    output = cli.execute("deposit_to_controller not_an_address 100", no_color=True)
    assert f"deposit_to_controller: error: {BAD_ADDR_ERROR}" in output
    sign_boc_mock.assert_not_called()

    # integer amount is sent as float coins attached to the top-up message
    output = cli.execute(f"deposit_to_controller {CONTROLLER_0} 100", no_color=True)
    sign_boc_mock.assert_called_once_with(validator_wallet, top_up_boc, CONTROLLER_0, 100.0)
    assert type(sign_boc_mock.call_args[0][3]) is float
    send_file_mock.assert_called_once_with(top_up_boc + ".signed", validator_wallet)
    assert output.strip() == ""  # no confirmation line is printed

    # fractional amount
    sign_boc_mock.reset_mock()
    send_file_mock.reset_mock()
    cli.execute(f"deposit_to_controller {CONTROLLER_1} 12.5", no_color=True)
    sign_boc_mock.assert_called_once_with(validator_wallet, top_up_boc, CONTROLLER_1, 12.5)
    send_file_mock.assert_called_once_with(top_up_boc + ".signed", validator_wallet)

    sign_boc_mock.reset_mock()
    send_file_mock.reset_mock()
    output = cli.execute(f"deposit_to_controller {CONTROLLER_0} abc", no_color=True)
    assert "deposit_to_controller: error: argument amount: invalid float value: 'abc'" in output
    sign_boc_mock.assert_not_called()
    send_file_mock.assert_not_called()


def test_withdraw_from_controller(cli, monkeypatch, mocker: MockerFixture):
    withdraw_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "WithdrawFromController", withdraw_mock)

    # Bad args
    output = cli.execute("withdraw_from_controller", no_color=True)
    assert "usage: withdraw_from_controller [-h] controller_addr [amount]" in output
    assert "withdraw_from_controller: error: the following arguments are required: controller_addr" in output
    output = cli.execute(f"withdraw_from_controller {CONTROLLER_0} 50 extra", no_color=True)
    assert "withdraw_from_controller: error: unrecognized arguments: extra" in output
    output = cli.execute("withdraw_from_controller not_an_address 50", no_color=True)
    assert f"withdraw_from_controller: error: {BAD_ADDR_ERROR}" in output
    withdraw_mock.assert_not_called()

    # with amount: passed on as the raw string
    output = cli.execute(f"withdraw_from_controller {CONTROLLER_0} 50", no_color=True)
    withdraw_mock.assert_called_once_with(CONTROLLER_0, "50")
    assert output.strip() == ""  # no confirmation line is printed

    # without amount: None (MyTonCore then withdraws the whole balance)
    withdraw_mock.reset_mock()
    cli.execute(f"withdraw_from_controller {CONTROLLER_0}", no_color=True)
    withdraw_mock.assert_called_once_with(CONTROLLER_0, None)

    # wrong amount: not validated by the handler
    withdraw_mock.reset_mock()
    cli.execute(f"withdraw_from_controller {CONTROLLER_0} abc", no_color=True)
    withdraw_mock.assert_called_once_with(CONTROLLER_0, "abc")


def test_withdraw_from_controller_idle(cli, ton, monkeypatch, mocker: MockerFixture,
                                       validator_wallet, sign_boc_mock, send_file_mock):
    # controller state 0 (not staking): the withdraw request is sent right away
    get_controller_data_mock = mocker.Mock(return_value={"state": 0})
    get_account_mock = mocker.Mock(return_value=Account(-1, "a0" * 32, status="active", balance=110.1))
    fift_run_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetControllerData", get_controller_data_mock)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)
    monkeypatch.setattr(ton.fift, "run", fift_run_mock)
    script = ton.contractsDir + "jetton_pool/fift-scripts/withdraw-controller.fif"
    request_boc = ton.tempDir + "wallet_001_withdraw_request.boc"

    # with amount: the raw string goes to fift
    cli.execute(f"withdraw_from_controller {CONTROLLER_0} 50", no_color=True)
    get_controller_data_mock.assert_called_once_with(CONTROLLER_0)
    get_account_mock.assert_not_called()
    fift_run_mock.assert_called_once_with([script, "50", request_boc])
    sign_boc_mock.assert_called_once_with(validator_wallet, request_boc, CONTROLLER_0, 1.06)
    send_file_mock.assert_called_once_with(request_boc + ".signed", validator_wallet)

    # without amount: the whole balance minus 10.1 TON
    fift_run_mock.reset_mock()
    sign_boc_mock.reset_mock()
    send_file_mock.reset_mock()
    cli.execute(f"withdraw_from_controller {CONTROLLER_0}", no_color=True)
    get_account_mock.assert_called_once_with(CONTROLLER_0)
    fift_run_mock.assert_called_once_with([script, 110.1 - 10.1, request_boc])
    sign_boc_mock.assert_called_once_with(validator_wallet, request_boc, CONTROLLER_0, 1.06)
    send_file_mock.assert_called_once()

    # amounts below 3 TON are silently dropped
    fift_run_mock.reset_mock()
    sign_boc_mock.reset_mock()
    send_file_mock.reset_mock()
    output = cli.execute(f"withdraw_from_controller {CONTROLLER_0} 2", no_color=True)
    assert output.strip() == ""
    fift_run_mock.assert_not_called()
    send_file_mock.assert_not_called()

    # wrong amount: int() of the raw string fails, so fractional amounts fail too
    output = cli.execute(f"withdraw_from_controller {CONTROLLER_0} 5.5", no_color=True)
    assert "invalid literal for int() with base 10: '5.5'" in output
    output = cli.execute(f"withdraw_from_controller {CONTROLLER_0} abc", no_color=True)
    assert "invalid literal for int() with base 10: 'abc'" in output
    fift_run_mock.assert_not_called()
    send_file_mock.assert_not_called()


def test_withdraw_from_controller_staking(cli, ton, monkeypatch, mocker: MockerFixture, send_file_mock):
    # controller is staking (state != 0): the withdraw is stored as pending
    monkeypatch.setattr(MyTonCore, "GetControllerData", mocker.Mock(return_value={"state": 3}))
    fift_run_mock = mocker.Mock()
    monkeypatch.setattr(ton.fift, "run", fift_run_mock)

    cli.execute(f"withdraw_from_controller {CONTROLLER_0} 50", no_color=True)
    cli.execute(f"withdraw_from_controller {CONTROLLER_1}", no_color=True)
    cli.execute(f"withdraw_from_controller {CONTROLLER_2} abc", no_color=True)
    assert ton.local.db["controllerPendingWithdraws"] == {
        CONTROLLER_0: "50",
        CONTROLLER_1: None,
        CONTROLLER_2: "abc",
    }
    fift_run_mock.assert_not_called()
    send_file_mock.assert_not_called()


def test_calculate_annual_controller_percentage(cli, ton, monkeypatch, mocker: MockerFixture):
    config15 = Config15(validators_elected_for=65536, elections_start_before=32768,
                        elections_end_before=8192, stake_held_for=32768)
    get_config_15_mock = mocker.Mock(return_value=config15)
    monkeypatch.setattr(MyTonCore, "get_config_15", get_config_15_mock)

    # Bad args
    output = cli.execute("calculate_annual_controller_percentage 1 2", no_color=True)
    assert "usage: calculate_annual_controller_percentage [-h] [percent_per_round]" in output
    assert "calculate_annual_controller_percentage: error: unrecognized arguments: 2" in output
    get_config_15_mock.assert_not_called()

    # explicit percent per round
    output = cli.execute("calculate_annual_controller_percentage 1.5", no_color=True)
    assert [line for line in output.splitlines() if line] == [
        "roundPeriod 65536",
        "rounds 481.201171875",
        "percentPerRound 1.5",
        "yearInterest 488.41918945312494",
        "yearInterestPercent: 4.88%",
    ]
    get_config_15_mock.assert_called_once_with()

    # without argument: the `max_interest_percent` db setting
    ton.local.db["max_interest_percent"] = 2
    output = cli.execute("calculate_annual_controller_percentage", no_color=True)
    assert "percentPerRound 2\n" in output
    assert "yearInterest 490.8251953125" in output
    assert "yearInterestPercent: 4.91%" in output

    # without argument and without the db setting: the default 1.5, the same the loan request uses
    del ton.local.db["max_interest_percent"]
    output = cli.execute("calculate_annual_controller_percentage", no_color=True)
    assert "percentPerRound 1.5\n" in output
    assert "yearInterestPercent: 4.88%" in output

    # wrong percent
    output = cli.execute("calculate_annual_controller_percentage abc", no_color=True)
    assert "calculate_annual_controller_percentage: error: argument percent_per_round: invalid float value: 'abc'" in output


def test_controller_update_validator_set(cli, monkeypatch, mocker: MockerFixture):
    update_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "ControllerUpdateValidatorSet", update_mock)

    # Bad args
    output = cli.execute("controller_update_validator_set", no_color=True)
    assert "usage: controller_update_validator_set [-h] controller_addr" in output
    assert "controller_update_validator_set: error: the following arguments are required: controller_addr" in output
    output = cli.execute(f"controller_update_validator_set {CONTROLLER_0} {CONTROLLER_1}", no_color=True)
    assert f"controller_update_validator_set: error: unrecognized arguments: {CONTROLLER_1}" in output
    output = cli.execute("controller_update_validator_set not_an_address", no_color=True)
    assert f"controller_update_validator_set: error: {BAD_ADDR_ERROR}" in output
    update_mock.assert_not_called()

    output = cli.execute(f"controller_update_validator_set {CONTROLLER_0}", no_color=True)
    assert "ControllerUpdateValidatorSet - OK" in output
    update_mock.assert_called_once_with(CONTROLLER_0)


def test_stop_controller(cli, ton):
    # Bad args
    output = cli.execute("stop_controller", no_color=True)
    assert "usage: stop_controller [-h] controller_addr" in output
    assert "stop_controller: error: the following arguments are required: controller_addr" in output
    output = cli.execute(f"stop_controller {CONTROLLER_0} {CONTROLLER_1}", no_color=True)
    assert f"stop_controller: error: unrecognized arguments: {CONTROLLER_1}" in output
    output = cli.execute("stop_controller not_an_address", no_color=True)
    assert f"stop_controller: error: {BAD_ADDR_ERROR}" in output
    assert "stop_controllers_list" not in ton.local.db

    ton.local.db["user_controllers"] = [CONTROLLER_0, CONTROLLER_1]
    output = cli.execute(f"stop_controller {CONTROLLER_0}", no_color=True)
    assert "StopController - OK" in output
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_0]
    assert ton.local.db["user_controllers"] == [CONTROLLER_1]

    # stopping twice does not duplicate the entry
    output = cli.execute(f"stop_controller {CONTROLLER_0}", no_color=True)
    assert "StopController - OK" in output
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_0]

    # a controller that was never added is still recorded as stopped
    cli.execute(f"stop_controller {CONTROLLER_2}", no_color=True)
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_0, CONTROLLER_2]
    assert ton.local.db["user_controllers"] == [CONTROLLER_1]


def test_stop_and_withdraw_controller(cli, ton, monkeypatch, mocker: MockerFixture):
    withdraw_mock = mocker.Mock()
    get_account_mock = mocker.Mock(return_value=Account(-1, "a1" * 32, status="active", balance=1000))
    monkeypatch.setattr(MyTonCore, "WithdrawFromController", withdraw_mock)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)

    # Bad args
    output = cli.execute("stop_and_withdraw_controller", no_color=True)
    assert "usage: stop_and_withdraw_controller [-h] controller_addr [amount]" in output
    assert "stop_and_withdraw_controller: error: the following arguments are required: controller_addr" in output
    output = cli.execute(f"stop_and_withdraw_controller {CONTROLLER_0} 50 extra", no_color=True)
    assert "stop_and_withdraw_controller: error: unrecognized arguments: extra" in output
    output = cli.execute("stop_and_withdraw_controller not_an_address 50", no_color=True)
    assert f"stop_and_withdraw_controller: error: {BAD_ADDR_ERROR}" in output
    withdraw_mock.assert_not_called()
    assert "stop_controllers_list" not in ton.local.db

    # with amount: controller is stopped, the raw amount string is withdrawn
    ton.local.db["user_controllers"] = [CONTROLLER_0]
    output = cli.execute(f"stop_and_withdraw_controller {CONTROLLER_0} 50", no_color=True)
    assert "StopAndWithdrawController - OK" in output
    withdraw_mock.assert_called_once_with(CONTROLLER_0, "50")
    get_account_mock.assert_not_called()
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_0]
    assert ton.local.db["user_controllers"] == []

    # without amount: the whole balance minus 10.1 TON, computed by the handler
    withdraw_mock.reset_mock()
    output = cli.execute(f"stop_and_withdraw_controller {CONTROLLER_1}", no_color=True)
    assert "StopAndWithdrawController - OK" in output
    get_account_mock.assert_called_once_with(CONTROLLER_1)
    withdraw_mock.assert_called_once_with(CONTROLLER_1, 1000 - 10.1)
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_0, CONTROLLER_1]

    # wrong amount: not validated, the controller is stopped and the string passed on
    withdraw_mock.reset_mock()
    output = cli.execute(f"stop_and_withdraw_controller {CONTROLLER_2} abc", no_color=True)
    assert "StopAndWithdrawController - OK" in output
    withdraw_mock.assert_called_once_with(CONTROLLER_2, "abc")
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_0, CONTROLLER_1, CONTROLLER_2]


def test_add_controller(cli, ton):
    # Bad args
    output = cli.execute("add_controller", no_color=True)
    assert "usage: add_controller [-h] controller_addr" in output
    assert "add_controller: error: the following arguments are required: controller_addr" in output
    output = cli.execute(f"add_controller {CONTROLLER_0} {CONTROLLER_1}", no_color=True)
    assert f"add_controller: error: unrecognized arguments: {CONTROLLER_1}" in output
    output = cli.execute("add_controller not_an_address", no_color=True)
    assert f"add_controller: error: {BAD_ADDR_ERROR}" in output
    assert "user_controllers" not in ton.local.db

    ton.local.db["stop_controllers_list"] = [CONTROLLER_0, CONTROLLER_1]
    output = cli.execute(f"add_controller {CONTROLLER_0}", no_color=True)
    assert "AddController - OK" in output
    assert ton.local.db["user_controllers"] == [CONTROLLER_0]
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_1]

    # adding twice does not duplicate the entry
    cli.execute(f"add_controller {CONTROLLER_0}", no_color=True)
    assert ton.local.db["user_controllers"] == [CONTROLLER_0]

    cli.execute(f"add_controller {CONTROLLER_2}", no_color=True)
    assert ton.local.db["user_controllers"] == [CONTROLLER_0, CONTROLLER_2]
    assert ton.local.db["stop_controllers_list"] == [CONTROLLER_1]


def test_test_calculate_loan_amount(cli, ton, monkeypatch, mocker: MockerFixture):
    calculate_mock = mocker.Mock(return_value=42000000000000)
    monkeypatch.setattr(MyTonCore, "calculate_loan_amount", calculate_mock)

    # defaults: min_loan 41000, max_loan 43000, max_interest_percent 1.5
    output = cli.execute("test_calculate_loan_amount", no_color=True)
    assert "42000000000000" in output.splitlines()
    calculate_mock.assert_called_once_with(41000, 43000, 251658)  # int(1.5 / 100 * 2**24)

    # values from the db
    ton.local.db["min_loan"] = 1000
    ton.local.db["max_loan"] = 2000
    ton.local.db["max_interest_percent"] = 10
    calculate_mock.reset_mock()
    calculate_mock.return_value = -1
    output = cli.execute("test_calculate_loan_amount", no_color=True)
    assert "-1" in output.splitlines()
    calculate_mock.assert_called_once_with(1000, 2000, 1677721)

    calculate_mock.reset_mock()
    output = cli.execute("test_calculate_loan_amount extra", no_color=True)
    assert "usage: test_calculate_loan_amount [-h]" in output
    assert "test_calculate_loan_amount: error: unrecognized arguments: extra" in output
    calculate_mock.assert_not_called()
