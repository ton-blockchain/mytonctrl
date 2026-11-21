from __future__ import annotations

import os

import pytest
import requests
from pytest_mock import MockerFixture

from modules.validator import ValidatorModule
from mytoncore.mytoncore import MyTonCore


DEFAULT_URL = 'https://ton-blockchain.github.io/registry-voting-config.json'
TESTNET_URL = 'https://ton-blockchain.github.io/testnet-registry-voting-config.json'

PUBLISHED = b'{\n  "nodes" : [\n    {"adnl_id" : "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqo=", "roles_add" : 1, "roles_remove" : 0}\n  ]\n}\n'


class Resp:
    def __init__(self, status, content=b''):
        self.status_code = status
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'status {self.status_code}')


@pytest.fixture()
def module(ton) -> ValidatorModule:
    return ValidatorModule(ton, ton.local)


def test_apply_default_registry_voting(module, ton, monkeypatch, mocker: MockerFixture):
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda self: True)
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'mainnet')
    get_mock = mocker.Mock(return_value=Resp(200, PUBLISHED))
    monkeypatch.setattr('modules.validator.requests.get', get_mock)
    sent = []

    def fake_run(cmd):
        with open(cmd.split(' ', 1)[1], 'rb') as f:
            sent.append((cmd, f.read()))
        return 'success\n'
    monkeypatch.setattr(ton.validatorConsole, 'run', fake_run)

    fname = os.path.join(ton.tempDir, 'registry_voting_config.json')

    # off by default: nothing happens, including the fetch
    module.apply_default_registry_voting()
    get_mock.assert_not_called()
    assert sent == []

    ton.local.db['useDefaultRegistryVoting'] = True

    # the published file goes to the node as is
    module.apply_default_registry_voting()
    get_mock.assert_called_once_with(DEFAULT_URL, timeout=3)
    assert sent == [(f'set-registry-voting-config {fname}', PUBLISHED)]

    # ... on every cycle, whatever the node has
    module.apply_default_registry_voting()
    assert len(sent) == 2

    # testnet uses its own file
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'testnet')
    module.apply_default_registry_voting()
    assert get_mock.call_args[0][0] == TESTNET_URL
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'mainnet')

    # url override
    ton.local.db['defaultRegistryVotingUrl'] = 'TestUrl'
    module.apply_default_registry_voting()
    assert get_mock.call_args[0][0] == 'TestUrl'
    ton.local.db.pop('defaultRegistryVotingUrl')

    # fetch failures propagate, the node is not touched
    sent.clear()
    get_mock.side_effect = requests.ConnectionError('boom')
    with pytest.raises(requests.ConnectionError):
        module.apply_default_registry_voting()
    get_mock.side_effect = None
    get_mock.return_value = Resp(404, b'<html>not found</html>')
    with pytest.raises(requests.HTTPError):
        module.apply_default_registry_voting()
    assert sent == []
    get_mock.return_value = Resp(200, PUBLISHED)

    # a file the node rejects, or a node without the command
    for output in (
        'Failed set-registry-voting-config query: [Error : 0 : Expected array, got Object]\n',
        "unknown command 'set-registry-voting-config'\n",
    ):
        monkeypatch.setattr(ton.validatorConsole, 'run', lambda cmd, output=output: output)
        with pytest.raises(Exception, match='Failed to set registry voting config'):
            module.apply_default_registry_voting()
    monkeypatch.setattr(ton.validatorConsole, 'run', fake_run)

    # unknown network: no fetch
    get_mock.reset_mock()
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'unknown')
    module.apply_default_registry_voting()
    get_mock.assert_not_called()
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'mainnet')

    # validator mode off: no fetch
    monkeypatch.setattr(MyTonCore, 'using_validator', lambda self: False)
    module.apply_default_registry_voting()
    get_mock.assert_not_called()
    assert sent == []
