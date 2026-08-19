from __future__ import annotations

import pytest
import requests
from pytest_mock import MockerFixture

from modules.validator import ValidatorModule
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import hex2b64


HEX_ADNL_1 = 'AA' * 32
HEX_ADNL_2 = 'BB' * 32
B64_ADNL_1 = hex2b64(HEX_ADNL_1)
B64_ADNL_2 = hex2b64(HEX_ADNL_2)

DEFAULT_URL = 'https://ton-blockchain.github.io/collators-list.json'
TESTNET_URL = 'https://ton-blockchain.github.io/testnet-collators-list.json'


class Resp:
    def __init__(self, status, data=None, bad_json=False):
        self.status_code = status
        self._data = data
        self._bad_json = bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'status {self.status_code}')

    def json(self):
        if self._bad_json:
            raise ValueError('bad json')
        return self._data


@pytest.fixture()
def module(ton) -> ValidatorModule:
    return ValidatorModule(ton, ton.local)


def test_get_default_collators_list(module, ton, monkeypatch):
    captured = {}

    def set_response(resp):
        def fake_get(url, timeout):
            captured['url'] = url
            captured['timeout'] = timeout
            return resp
        monkeypatch.setattr('modules.validator.requests.get', fake_get)

    # unknown network: no fetch
    def fail_get(url, timeout):
        raise AssertionError('should not fetch for unknown network')
    monkeypatch.setattr('modules.validator.requests.get', fail_get)
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'unknown')
    assert module.get_default_collators_list() is None
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'mainnet')

    # fetch failures propagate
    def raising_get(url, timeout):
        raise requests.ConnectionError('boom')
    monkeypatch.setattr('modules.validator.requests.get', raising_get)
    with pytest.raises(requests.ConnectionError):
        module.get_default_collators_list()

    set_response(Resp(500))
    with pytest.raises(requests.HTTPError):
        module.get_default_collators_list()

    set_response(Resp(200, bad_json=True))
    with pytest.raises(ValueError, match='bad json'):
        module.get_default_collators_list()

    # malformed shapes
    for data in (
        ['not', 'a', 'dict'],
        {'collator': []},  # typo in the key
        {'collators': 'not-a-list'},
    ):
        set_response(Resp(200, data=data))
        with pytest.raises(ValueError, match='Malformed remote config'):
            module.get_default_collators_list()

    # bad entries: not a dict, missing/non-string/non-b64/wrong-length adnl_id
    for entry in (
        'not-a-dict',
        {},
        {'adnl_id': None},
        {'adnl_id': 42},
        {'adnl_id': 'not base64!!'},
        {'adnl_id': HEX_ADNL_1},  # hex decodes as b64 to 48 bytes, not 32
        {'adnl_id': hex2b64('AA' * 31)},  # 31 bytes
    ):
        set_response(Resp(200, data={'collators': [entry]}))
        with pytest.raises(ValueError, match='Could not parse adnl_id'):
            module.get_default_collators_list()

    # empty list is valid
    set_response(Resp(200, data={'collators': []}))
    assert module.get_default_collators_list() == []

    # happy path: b64 adnl ids as in the published file, duplicates dropped
    set_response(Resp(200, data={
        'collators': [
            {'adnl_id': B64_ADNL_1},
            {'adnl_id': B64_ADNL_1},  # duplicate
            {'adnl_id': B64_ADNL_2},
        ],
    }))
    assert module.get_default_collators_list() == [B64_ADNL_1, B64_ADNL_2]
    assert captured['url'] == DEFAULT_URL
    assert captured['timeout'] == 3

    # testnet uses its own file
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'testnet')
    module.get_default_collators_list()
    assert captured['url'] == TESTNET_URL
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'mainnet')

    # url override
    ton.local.db['defaultCollatorsUrl'] = 'TestUrl'
    module.get_default_collators_list()
    assert captured['url'] == 'TestUrl'
    ton.local.db.pop('defaultCollatorsUrl')


def test_apply_default_collators(module, ton, monkeypatch, mocker: MockerFixture):
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda self: True)
    monkeypatch.setattr(ValidatorModule, 'get_default_collators_list', lambda self: [B64_ADNL_1, B64_ADNL_2])
    get_mock = mocker.Mock(return_value={})
    set_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_collators_list', get_mock)
    monkeypatch.setattr(ValidatorModule, 'set_collators_list', set_mock)

    # empty node list: all defaults added, other fields initialized like add_collator does
    module.apply_default_collators()
    set_mock.assert_called_once()
    assert set_mock.call_args[0][0] == {
        'collators': [{'adnl_id': B64_ADNL_1}, {'adnl_id': B64_ADNL_2}],
        'register_collators': [],
        'disable_self_collate': False,
    }

    # partial overlap: only the missing adnl is appended, nothing else is touched
    get_mock.return_value = {
        'collators': [{'adnl_id': B64_ADNL_1}],
        'register_collators': [{'adnl_id': 'reg_adnl'}],
        'disable_self_collate': True,
    }
    set_mock.reset_mock()
    module.apply_default_collators()
    assert set_mock.call_args[0][0] == {
        'collators': [{'adnl_id': B64_ADNL_1}, {'adnl_id': B64_ADNL_2}],
        'register_collators': [{'adnl_id': 'reg_adnl'}],
        'disable_self_collate': True,
    }

    # full overlap: no write to the node
    get_mock.return_value = {
        'collators': [{'adnl_id': B64_ADNL_1}, {'adnl_id': B64_ADNL_2}],
        'register_collators': [],
        'disable_self_collate': False,
    }
    set_mock.reset_mock()
    module.apply_default_collators()
    set_mock.assert_not_called()

    # console errors propagate to the cycle wrapper
    get_mock.side_effect = Exception('console dead')
    with pytest.raises(Exception, match='console dead'):
        module.apply_default_collators()
    set_mock.assert_not_called()
    get_mock.side_effect = None

    get_mock.return_value = {}
    set_mock.side_effect = Exception('set failed')
    with pytest.raises(Exception, match='set failed'):
        module.apply_default_collators()

    # empty default list: nothing happens
    set_mock.reset_mock(side_effect=True)
    get_mock.reset_mock()
    monkeypatch.setattr(ValidatorModule, 'get_default_collators_list', lambda self: [])
    module.apply_default_collators()
    get_mock.assert_not_called()
    set_mock.assert_not_called()

    # validator mode off: nothing happens
    monkeypatch.setattr(ValidatorModule, 'get_default_collators_list', lambda self: [B64_ADNL_1])
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda self: False)
    module.apply_default_collators()
    get_mock.assert_not_called()
    set_mock.assert_not_called()

    # opt-out setting disables the whole reconcile, including the fetch
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda self: True)
    fetch_mock = mocker.Mock()
    monkeypatch.setattr(ValidatorModule, 'get_default_collators_list', fetch_mock)
    ton.local.db['useDefaultCollators'] = False
    module.apply_default_collators()
    fetch_mock.assert_not_called()
    get_mock.assert_not_called()
    set_mock.assert_not_called()
    ton.local.db.pop('useDefaultCollators')


def test_get_collators_list_node_support(module, ton, monkeypatch):
    monkeypatch.setattr(ton.validatorConsole, 'run', lambda cmd: "unknown command 'show-collators-list'")
    with pytest.raises(Exception, match='old node'):
        module.get_collators_list()

    monkeypatch.setattr(ton.validatorConsole, 'run', lambda cmd: 'collators list is empty')
    assert module.get_collators_list() == {}
