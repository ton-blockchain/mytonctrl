import base64
import json
import time

from modules.validator import ValidatorModule

from pytest_mock import MockerFixture

from mytoncore.mytoncore import MyTonCore
from mytoncore.models import Config, ValidatorConfigExt


def test_vote_offer(cli, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("vo", no_color=True)
    assert "Bad args" in output
    offers = [{"hash": "hash1", "data": "offer-data"}, {"hash": "hash2", "data": "offer-data"}, {"hash": "hash3", "data": "offer-data"}]
    monkeypatch.setattr(MyTonCore, "GetOffers", lambda _: offers)
    vote_offer_mock = mocker.Mock()
    add_save_offer_mock = mocker.Mock()

    monkeypatch.setattr(MyTonCore, "VoteOffer", vote_offer_mock)
    monkeypatch.setattr(MyTonCore, "add_save_offer", add_save_offer_mock)

    output = cli.execute("vo hash2", no_color=True)
    assert "VoteOffer - OK" in output
    add_save_offer_mock.assert_called_once_with(offers[1])
    vote_offer_mock.assert_called_once_with(offers[1])

    add_save_offer_mock.reset_mock()
    vote_offer_mock.reset_mock()
    output = cli.execute("vo hash2 hash3", no_color=True)
    assert "VoteOffer - OK" in output
    add_save_offer_mock.assert_has_calls(calls=[mocker.call(offers[1]), mocker.call(offers[2])], any_order=False)
    vote_offer_mock.assert_has_calls(calls=[mocker.call(offers[1]), mocker.call(offers[2])], any_order=False)


def test_ve(cli, monkeypatch, mocker: MockerFixture):
    elections_mocker = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'run_elections', elections_mocker)
    output = cli.execute("ve", no_color=True)
    assert "VoteElectionEntry - OK" in output
    elections_mocker.assert_called_once()


def test_vc(cli, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("vc", no_color=True)
    assert "Bad args" in output
    output = cli.execute("vc 123456", no_color=True)
    assert "Bad args" in output

    vote_complaint_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "VoteComplaint", vote_complaint_mock)
    output = cli.execute("vc 123456 abcdef", no_color=True)
    assert "VoteComplaint - OK" in output
    vote_complaint_mock.assert_called_once_with("123456", "abcdef")


def test_check_ef(cli, monkeypatch, mocker: MockerFixture):
    prev_validator = ValidatorConfigExt(
        adnl_addr="test_adnl", pubkey="pk", weight=1,
        mr=0.955, wr=0.955, efficiency=95.5, online=True,
        master_blocks_created=100, master_blocks_expected=105,
        blocks_created=100, blocks_expected=105,
        is_masterchain=True, wallet_addr=None, stake=None,
    )

    curr_validator = ValidatorConfigExt(
        adnl_addr="test_adnl", pubkey="pk", weight=1,
        mr=0.92, wr=0.92, efficiency=92.0, online=True,
        master_blocks_created=50, master_blocks_expected=54,
        blocks_created=50, blocks_expected=54,
        is_masterchain=True, wallet_addr=None, stake=None,
    )

    config32 = Config(
        total_validators=100, main_validators=100,
        start_work_time=1000000, end_work_time=2000000,
        total_weight=50000, validators=[],
    )

    config34 = Config(
        total_validators=100, main_validators=100,
        start_work_time=2000000, end_work_time=3000000,
        total_weight=50000, validators=[],
    )

    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [prev_validator] if past else [curr_validator])
    monkeypatch.setattr(MyTonCore, "GetAdnlAddr", lambda self: "test_adnl")
    monkeypatch.setattr(MyTonCore, "get_config_32", lambda self: config32)
    monkeypatch.setattr(MyTonCore, "get_config_34", lambda self: config34)

    output = cli.execute("check_ef", no_color=True)
    assert "Previous round efficiency: 95.5% (100 blocks created / 105 blocks expected)" in output
    assert "Current round efficiency: 92.0% (50 blocks created / 54 blocks expected)" in output

    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [] if past else [curr_validator])
    output = cli.execute("check_ef", no_color=True)
    assert "Couldn't find this validator in the previous round" in output
    assert "Current round efficiency" in output

    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [prev_validator] if past else [])
    output = cli.execute("check_ef", no_color=True)
    assert "Couldn't find this validator in the current round" in output
    assert "Previous round efficiency" in output

    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [prev_validator] if past else [curr_validator])
    config34.start_work_time = int(time.time() - 1000)
    config34.end_work_time = int(time.time() + 1000000)
    output = cli.execute("check_ef", no_color=True)
    assert "The validation round has started recently" in output
    assert "Previous round efficiency" in output

def test_add_collator(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock(return_value={})
    set_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_collators_mock)

    # Bad args
    output = cli.execute("add_collator", no_color=True)
    assert "Bad args" in output
    get_collators_mock.assert_not_called()
    set_collators_mock.assert_not_called()
    output = cli.execute("add_collator test_adnl extra_arg", no_color=True)
    assert "Bad args" in output
    get_collators_mock.assert_not_called()
    set_collators_mock.assert_not_called()

    # Bad args - invalid self collate value
    output = cli.execute("add_collator test_adnl --self-collate invalid", no_color=True)
    get_collators_mock.assert_not_called()
    set_collators_mock.assert_not_called()
    assert "Bad args" in output
    assert "Self collate must be one of" in output

    # add collator to empty list with default values
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    output = cli.execute("add_collator test_adnl", no_color=True)
    assert "add_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['disable_self_collate'] is False
    assert call_args['collators'] == [{'adnl_id': 'test_adnl'}]
    assert call_args['register_collators'] == []  # add_collator does not register the collator

    # add collator with custom parameters
    get_collators_mock.return_value = {}
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    output = cli.execute("add_collator test_adnl2 --self-collate false", no_color=True)
    assert "add_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['disable_self_collate'] is True
    assert call_args['collators'][0]['adnl_id'] == 'test_adnl2'

    # add collator to existing list
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': True,
    }

    output = cli.execute("add_collator new_adnl", no_color=True)
    assert "add_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['disable_self_collate'] is True  # not changed
    assert call_args['collators'] == [{'adnl_id': 'test_adnl'}, {'adnl_id': 'new_adnl'}]
    assert call_args['register_collators'] == [{'adnl_id': 'test_adnl'}]  # untouched

    # add duplicate collator
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': False,
    }

    output = cli.execute("add_collator test_adnl", no_color=True)
    assert "already exists" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_not_called()


def test_add_register_collator(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock(return_value={})
    set_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_collators_mock)

    # Bad args
    output = cli.execute("add_register_collator", no_color=True)
    assert "Bad args" in output
    set_collators_mock.assert_not_called()
    output = cli.execute("add_register_collator test_adnl extra_arg", no_color=True)
    assert "Bad args" in output
    set_collators_mock.assert_not_called()

    # register collator with no list set yet - delegation list is left alone
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    output = cli.execute("add_register_collator test_adnl", no_color=True)
    assert "add_register_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['collators'] == []
    assert call_args['register_collators'] == [{'adnl_id': 'test_adnl'}]
    assert call_args['disable_self_collate'] is False

    # register collator to existing list
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': True,
    }
    output = cli.execute("add_register_collator new_adnl", no_color=True)
    assert "add_register_collator - OK" in output
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['collators'] == [{'adnl_id': 'test_adnl'}]  # untouched
    assert call_args['register_collators'] == [{'adnl_id': 'test_adnl'}, {'adnl_id': 'new_adnl'}]
    assert call_args['disable_self_collate'] is True

    # register duplicate collator
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    get_collators_mock.return_value = {
        'collators': [],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': False,
    }
    output = cli.execute("add_register_collator test_adnl", no_color=True)
    assert "already exists" in output
    set_collators_mock.assert_not_called()


def test_delete_collator(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("delete_collator")
    assert "Bad args" in output

    get_collators_mock = mocker.Mock()
    set_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_collators_mock)

    # no collators list
    get_collators_mock.return_value = {}
    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "No collators found" in output
    set_collators_mock.assert_not_called()

    # collators list is empty
    get_collators_mock.return_value = {'collators': [], 'register_collators': [], 'disable_self_collate': False}
    set_collators_mock.reset_mock()
    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "No collators found" in output
    set_collators_mock.assert_not_called()

    # delete collator - registry list is left alone
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}, {'adnl_id': 'other_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}, {'adnl_id': 'other_adnl'}],
        'disable_self_collate': True,
    }
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()

    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "delete_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()

    call_args = set_collators_mock.call_args[0][0]
    assert call_args['disable_self_collate'] is True
    assert call_args['collators'] == [{'adnl_id': 'other_adnl'}]
    assert call_args['register_collators'] == [{'adnl_id': 'test_adnl'}, {'adnl_id': 'other_adnl'}]

    # only registered collators, nothing to delegate
    get_collators_mock.return_value = {
        'collators': [],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': False,
    }
    set_collators_mock.reset_mock()
    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "No collators found" in output
    set_collators_mock.assert_not_called()

    # delete non-existent collator
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'other_adnl'}],
        'register_collators': [{'adnl_id': 'other_adnl'}],
        'disable_self_collate': False,
    }
    set_collators_mock.reset_mock()
    get_collators_mock.reset_mock()

    output = cli.execute("delete_collator abcd", no_color=True)
    assert "delete_collator - OK" in output
    set_collators_mock.assert_not_called()
    get_collators_mock.assert_called_once()


def test_delete_register_collator(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("delete_register_collator")
    assert "Bad args" in output

    get_collators_mock = mocker.Mock()
    set_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_collators_mock)

    # no collators list
    get_collators_mock.return_value = {}
    output = cli.execute("delete_register_collator test_adnl", no_color=True)
    assert "No collators found" in output
    set_collators_mock.assert_not_called()

    # delete registered collator - delegation list is left alone
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}, {'adnl_id': 'other_adnl'}],
        'disable_self_collate': False,
    }
    set_collators_mock.reset_mock()
    output = cli.execute("delete_register_collator test_adnl", no_color=True)
    assert "delete_register_collator - OK" in output
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['collators'] == [{'adnl_id': 'test_adnl'}]
    assert call_args['register_collators'] == [{'adnl_id': 'other_adnl'}]

    # delete non-existent collator
    get_collators_mock.return_value = {
        'collators': [],
        'register_collators': [{'adnl_id': 'other_adnl'}],
        'disable_self_collate': False,
    }
    set_collators_mock.reset_mock()
    output = cli.execute("delete_register_collator abcd", no_color=True)
    assert "delete_register_collator - OK" in output
    set_collators_mock.assert_not_called()


def test_set_self_collate(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock(return_value={})
    set_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_collators_mock)

    # Bad args
    output = cli.execute("set_self_collate", no_color=True)
    assert "Bad args" in output
    set_collators_mock.assert_not_called()

    output = cli.execute("set_self_collate maybe", no_color=True)
    assert "Bad args" in output
    assert "Self collate must be one of" in output
    set_collators_mock.assert_not_called()

    # disable self collate keeping the collators
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': False,
    }
    output = cli.execute("set_self_collate false", no_color=True)
    assert "set_self_collate - OK" in output
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['disable_self_collate'] is True
    assert call_args['collators'] == [{'adnl_id': 'test_adnl'}]
    assert call_args['register_collators'] == [{'adnl_id': 'test_adnl'}]

    # enable self collate when no list is set yet
    get_collators_mock.return_value = {}
    set_collators_mock.reset_mock()
    output = cli.execute("set_self_collate true", no_color=True)
    assert "set_self_collate - OK" in output
    call_args = set_collators_mock.call_args[0][0]
    assert call_args == {'collators': [], 'register_collators': [], 'disable_self_collate': False}


def test_print_collators(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)

    # --json flag
    collators_data = {"some_data": "some_value", "1": 2}
    get_collators_mock.return_value = collators_data

    output = cli.execute("print_collators --json", no_color=True)
    assert json.dumps(collators_data, indent=2) in output

    # happy path
    adnl1 = base64.b64encode(b"\xaa" * 32).decode()
    adnl2 = base64.b64encode(b"\xbb" * 32).decode()
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': adnl1}, {'adnl_id': adnl2}],
        'register_collators': [{'adnl_id': adnl1}, {'adnl_id': adnl2}],
        'disable_self_collate': True,
    }

    output = cli.execute("print_collators", no_color=True)
    assert "Collators list:" in output
    assert "Register collators list:" in output
    assert "AA" * 32 in output
    assert "BB" * 32 in output
    assert "Self collate: False" in output

    # only registered collators - the delegation table is not printed
    get_collators_mock.return_value = {
        'collators': [],
        'register_collators': [{'adnl_id': adnl2}],
        'disable_self_collate': False,
    }
    output = cli.execute("print_collators", no_color=True)
    assert "Collators list:" not in output
    assert "Register collators list:" in output
    assert "BB" * 32 in output
    assert "Self collate: True" in output

    # empty lists - self collate is still reported, it applies without collators
    get_collators_mock.return_value = {
        'collators': [],
        'register_collators': [],
        'disable_self_collate': True,
    }
    output = cli.execute("print_collators", no_color=True)
    assert "No collators found" in output
    assert "Self collate: False" in output

    # collators list empty
    get_collators_mock.return_value = {}
    output = cli.execute("print_collators", no_color=True)
    assert "No collators found" in output
    assert "Self collate: True" in output  # node default when no list is set


def test_reset_collators(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock()
    validator_console_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    ton._validator_console = validator_console_mock

    # no collators
    get_collators_mock.return_value = {}
    output = cli.execute("reset_collators", no_color=True)
    assert "No collators to reset" in output
    validator_console_mock.run.assert_not_called()

    # happy path
    get_collators_mock.reset_mock()
    validator_console_mock.run.reset_mock()
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': False,
    }
    validator_console_mock.run.return_value = "success"
    output = cli.execute("reset_collators", no_color=True)
    assert "reset_collators - OK" in output
    validator_console_mock.run.assert_called_once_with('clear-collators-list')
    get_collators_mock.assert_called_once()

    # fails
    get_collators_mock.reset_mock()
    validator_console_mock.run.reset_mock()
    get_collators_mock.return_value = {
        'collators': [{'adnl_id': 'test_adnl'}],
        'register_collators': [{'adnl_id': 'test_adnl'}],
        'disable_self_collate': False,
    }
    validator_console_mock.run.return_value = "error: failed to clear"

    output = cli.execute("reset_collators", no_color=True)
    assert "Failed to reset collators list" in output
    validator_console_mock.run.assert_called_once_with('clear-collators-list')
    get_collators_mock.assert_called_once()


def test_parse_collators_list():
    output = """some header
conn ready
Collators list:
Collator qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqo=
Register collator u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7s=
Disable self collate = true
"""
    assert ValidatorModule._parse_collators_list(output) == {
        'collators': [{'adnl_id': 'qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqo='}],
        'register_collators': [{'adnl_id': 'u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7s='}],
        'disable_self_collate': True,
    }

    # both lists empty - the node still reports self collate, it applies on its own
    empty_output = """some header
conn ready
Collators list:
List is empty
Disable self collate = true
"""
    assert ValidatorModule._parse_collators_list(empty_output) == {
        'collators': [],
        'register_collators': [],
        'disable_self_collate': True,
    }
