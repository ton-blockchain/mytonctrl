import json
import time

from modules.validator import ValidatorModule

import pytest
from pytest_mock import MockerFixture

from mypylib import Dict
from mytoncore.mytoncore import MyTonCore


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
    prev_validator = Dict()
    prev_validator.adnlAddr = "test_adnl"
    prev_validator.efficiency = 95.5
    prev_validator.is_masterchain = True
    prev_validator.master_blocks_created = 100
    prev_validator.master_blocks_expected = 105
    prev_validator.blocks_created = 100
    prev_validator.blocks_expected = 105

    curr_validator = Dict()
    curr_validator.adnlAddr = "test_adnl"
    curr_validator.efficiency = 92.0
    curr_validator.is_masterchain = True
    curr_validator.master_blocks_created = 50
    curr_validator.master_blocks_expected = 54

    config32 = Dict()
    config32.startWorkTime = 1000000
    config32.endWorkTime = 2000000
    config32.mainValidators = 100

    config34 = Dict()
    config34.startWorkTime = 2000000
    config34.endWorkTime = 3000000
    config34.mainValidators = 100

    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [prev_validator] if past else [curr_validator])
    monkeypatch.setattr(MyTonCore, "GetAdnlAddr", lambda self: "test_adnl")
    monkeypatch.setattr(MyTonCore, "GetConfig32", lambda self: config32)
    monkeypatch.setattr(MyTonCore, "GetConfig34", lambda self: config34)

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

    prev_validator.efficiency = None
    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [prev_validator] if past else [curr_validator])
    output = cli.execute("check_ef", no_color=True)
    assert "Failed to get efficiency for the previous round" in output
    assert "Current round efficiency" in output

    prev_validator.efficiency = 95.5
    monkeypatch.setattr(MyTonCore, "GetValidatorsList", lambda self, past=False: [prev_validator] if past else [curr_validator])
    config34.startWorkTime = int(time.time() - 1000)
    config34.endWorkTime = int(time.time() + 1000000)
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
    output = cli.execute("add_collator test_adnl", no_color=True)
    assert "Bad args" in output
    get_collators_mock.assert_not_called()
    set_collators_mock.assert_not_called()

    # Bad args - invalid select mode
    output = cli.execute("add_collator test_adnl 0:8000000000000000 --select-mode invalid", no_color=True)
    get_collators_mock.assert_not_called()
    set_collators_mock.assert_not_called()
    assert "Bad args" in output
    assert "Select mode must be one of" in output

    # add collator to new shard with default values
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    output = cli.execute("add_collator test_adnl 0:8000000000000000", no_color=True)
    assert "add_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert len(call_args['shards']) == 1
    assert call_args['shards'][0]['shard_id'] == {'workchain': 0, 'shard': -9223372036854775808}
    assert call_args['shards'][0]['self_collate'] is True
    assert call_args['shards'][0]['select_mode'] == 'random'
    assert len(call_args['shards'][0]['collators']) == 1
    assert call_args['shards'][0]['collators'][0]['adnl_id'] == 'test_adnl'

    # add collator with custom parameters
    get_collators_mock.return_value = {}
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    output = cli.execute("add_collator test_adnl2 0:8000000000000000 --self-collate false --select-mode ordered", no_color=True)
    assert "add_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert call_args['shards'][0]['self_collate'] is False
    assert call_args['shards'][0]['select_mode'] == 'ordered'
    assert call_args['shards'][0]['collators'][0]['adnl_id'] == 'test_adnl2'

    # add collator to existing shard
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    existing_collators = {
        'shards': [{
            'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
            'self_collate': True,
            'select_mode': 'random',
            'collators': [{'adnl_id': 'test_adnl'}]
        }]
    }
    get_collators_mock.return_value = existing_collators

    output = cli.execute("add_collator new_adnl 0:8000000000000000", no_color=True)
    assert "add_collator - OK" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()
    call_args = set_collators_mock.call_args[0][0]
    assert len(call_args['shards']) == 1
    assert len(call_args['shards'][0]['collators']) == 2
    assert call_args['shards'][0]['collators'][0]['adnl_id'] == 'test_adnl'
    assert call_args['shards'][0]['collators'][1]['adnl_id'] == 'new_adnl'

    # add duplicate collator
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()
    get_collators_mock.return_value = {
        'shards': [{
            'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
            'self_collate': True,
            'select_mode': 'random',
            'collators': [{'adnl_id': 'test_adnl'}]
        }]
    }

    output = cli.execute("add_collator test_adnl 0:8000000000000000", no_color=True)
    assert "already exists" in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_not_called()


def test_delete_collator(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("delete_collator")
    assert "Bad args" in output

    get_collators_mock = mocker.Mock()
    set_collators_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_collators_mock)

    # no collators
    get_collators_mock.return_value = {}
    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "No collators found" in output
    set_collators_mock.assert_not_called()

    # collators list has no shards
    get_collators_mock.return_value = {'shards': []}
    set_collators_mock.reset_mock()
    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "No collators found" in output
    set_collators_mock.assert_not_called()

    # delete collator without specifying shard
    get_collators_mock.return_value = {
        'shards': [{
            'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
            'self_collate': True,
            'select_mode': 'random',
            'collators': [
                {'adnl_id': 'test_adnl'},
                {'adnl_id': 'other_adnl'}
            ]
        },
            {
                'shard_id': {'workchain': -1, 'shard': -9223372036854775808},
                'self_collate': True,
                'select_mode': 'random',
                'collators': [
                    {'adnl_id': 'test_adnl'},
                ]
            }
        ]
    }
    get_collators_mock.reset_mock()
    set_collators_mock.reset_mock()

    output = cli.execute("delete_collator test_adnl", no_color=True)
    assert "delete_collator - OK" in output
    assert 'Removing shard' in output
    get_collators_mock.assert_called_once()
    set_collators_mock.assert_called_once()

    call_args = set_collators_mock.call_args[0][0]
    assert len(call_args['shards']) == 1
    assert len(call_args['shards'][0]['collators']) == 1
    assert call_args['shards'][0]['collators'][0]['adnl_id'] == 'other_adnl'

    # delete collator from specific shard
    get_collators_mock.return_value = {
        'shards': [
            {
                'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
                'self_collate': True,
                'select_mode': 'random',
                'collators': [{'adnl_id': 'test_adnl'}, {'adnl_id': 'other_adnl'}]
            },
            {
                'shard_id': {'workchain': -1, 'shard': -9223372036854775808},
                'self_collate': True,
                'select_mode': 'random',
                'collators': [{'adnl_id': 'test_adnl'}]
            }
        ]
    }
    set_collators_mock.reset_mock()
    get_collators_mock.reset_mock()

    output = cli.execute("delete_collator 0:8000000000000000 test_adnl", no_color=True)
    assert "delete_collator - OK" in output
    set_collators_mock.assert_called_once()
    get_collators_mock.assert_called_once()

    call_args = set_collators_mock.call_args[0][0]
    assert len(call_args['shards']) == 2
    assert len(call_args['shards'][0]['collators']) == 1
    assert call_args['shards'][0]['collators'][0]['adnl_id'] == 'other_adnl'
    assert len(call_args['shards'][1]['collators']) == 1
    assert call_args['shards'][1]['collators'][0]['adnl_id'] == 'test_adnl'

    # delete non-existent collator
    get_collators_mock.return_value = {
        'shards': [{
            'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
            'self_collate': True,
            'select_mode': 'random',
            'collators': [{'adnl_id': 'other_adnl'}]
        }]
    }
    set_collators_mock.reset_mock()
    get_collators_mock.reset_mock()

    output = cli.execute("delete_collator abcd", no_color=True)
    assert "delete_collator - OK" in output
    set_collators_mock.assert_not_called()
    get_collators_mock.assert_called_once()


def test_print_collators(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock()
    get_collators_stats_mock = mocker.Mock()
    validator_console_mock = mocker.Mock()

    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    monkeypatch.setattr(ValidatorModule, 'get_collators_stats', get_collators_stats_mock)
    ton.validatorConsole = validator_console_mock

    # --json flag
    collators_data = {"some_data": "some_value", 1: 2}
    get_collators_mock.return_value = collators_data

    output = cli.execute("print_collators --json", no_color=True)
    assert json.dumps(collators_data, indent=2) in output
    get_collators_stats_mock.assert_not_called()
    validator_console_mock.Run.assert_not_called()

    # happy path
    console_output = """some header
conn ready
show-collators-list
Collators list:
Shard (0,8000000000000000)
  Self collate = true
  Select mode = random
  Collator test_adnl1
  Collator test_adnl2
  """

    validator_console_mock.Run.return_value = console_output
    get_collators_stats_mock.return_value = {
        'adnl1': True,
        'adnl2': False
    }

    output = cli.execute("print_collators", no_color=True)

    validator_console_mock.Run.assert_called_once_with('show-collators-list')
    get_collators_stats_mock.assert_called_once()

    assert """
Collators list:
Shard (0,8000000000000000)
  Self collate = true
  Select mode = random
  Collator test_adnl1 (online)
  Collator test_adnl2 (offline)
""" in output

    # collators list empty
    validator_console_mock.Run.reset_mock()
    get_collators_stats_mock.reset_mock()
    validator_console_mock.Run.return_value = "some header\nconn ready\ncollators list is empty"
    output = cli.execute("print_collators", no_color=True)
    validator_console_mock.Run.assert_called_once_with('show-collators-list')
    assert "No collators found" in output
    get_collators_stats_mock.assert_not_called()


def test_reset_collators(cli, ton, monkeypatch, mocker: MockerFixture):
    get_collators_mock = mocker.Mock()
    validator_console_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_collators_mock)
    ton.validatorConsole = validator_console_mock

    # no collators
    get_collators_mock.return_value = {}
    output = cli.execute("reset_collators", no_color=True)
    assert "No collators to reset" in output
    validator_console_mock.Run.assert_not_called()

    # happy path
    get_collators_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    get_collators_mock.return_value = {
        'shards': [{
            'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
            'self_collate': True,
            'select_mode': 'random',
            'collators': [{'adnl_id': 'test_adnl'}]
        }]
    }
    validator_console_mock.Run.return_value = "success"
    output = cli.execute("reset_collators", no_color=True)
    assert "reset_collators - OK" in output
    validator_console_mock.Run.assert_called_once_with('clear-collators-list')
    get_collators_mock.assert_called_once()

    # fails
    get_collators_mock.reset_mock()
    validator_console_mock.Run.reset_mock()
    get_collators_mock.return_value = {
        'shards': [{
            'shard_id': {'workchain': 0, 'shard': -9223372036854775808},
            'self_collate': True,
            'select_mode': 'random',
            'collators': [{'adnl_id': 'test_adnl'}]
        }]
    }
    validator_console_mock.Run.return_value = "error: failed to clear"

    output = cli.execute("reset_collators", no_color=True)
    assert "Failed to reset collators list" in output
    validator_console_mock.Run.assert_called_once_with('clear-collators-list')
    get_collators_mock.assert_called_once()
