import types

import pytest

from mytoncore.mytoncore import MyTonCore


def test_getseqno(ton: MyTonCore, monkeypatch):
    wallet = types.SimpleNamespace(addrB64='addr')
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: 'some output without keyword')
    with pytest.raises(Exception) as e:
        ton.get_seqno(wallet)
    assert 'not found' in str(e.value)
    output = 'something\narguments:  [ 85143 ]\n result:  [ 297 ]'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: output)
    assert ton.get_seqno(wallet) == 297
