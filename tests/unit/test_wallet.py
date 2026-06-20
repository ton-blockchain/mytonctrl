import os
import struct
import types
import pytest

from mytoncore.models import Account
from mytoncore.mytoncore import MyTonCore
from modules.wallet import WalletModule


@pytest.fixture
def module(ton: MyTonCore):
    return WalletModule(ton, ton.local)


def _write_addr_file(path: str, addr_hex: str, workchain: int):
    with open(path, 'wb') as f:
        f.write(bytes.fromhex(addr_hex))
        f.write(struct.pack('i', workchain))


def test_do_activate_wallet(ton: MyTonCore, module: WalletModule, monkeypatch):
    w = types.SimpleNamespace(addrB64='addr', bocFilePath='/tmp/wallet-query.boc')

    # empty -> raises
    monkeypatch.setattr(ton, 'GetAccount', lambda a: types.SimpleNamespace(status='empty'))
    called = {}
    monkeypatch.setattr(ton, 'SendFile', lambda *args, **kwargs: called.setdefault('sent', True))
    with pytest.raises(Exception):
        module.do_activate_wallet(w)
    assert 'sent' not in called

    # active -> noop
    monkeypatch.setattr(ton, 'GetAccount', lambda a: types.SimpleNamespace(status='active'))
    module.do_activate_wallet(w)  # should not raise
    assert 'sent' not in called

    # uninitialized -> send file
    monkeypatch.setattr(ton, 'GetAccount', lambda a: types.SimpleNamespace(status='uninitialized'))
    args_captured = {}
    def fake_send(fpath, wallet, remove=False):
        args_captured['fpath'] = fpath
        args_captured['wallet'] = wallet
        args_captured['remove'] = remove
    monkeypatch.setattr(ton, 'SendFile', fake_send)
    module.do_activate_wallet(w)
    assert args_captured['fpath'] == w.bocFilePath
    assert args_captured['wallet'] is w
    assert args_captured['remove'] is False


def test_create_wallet(ton: MyTonCore, module: WalletModule, monkeypatch, tmp_path):
    # existing wallet
    name = 'wexist'
    pk_path = os.path.join(ton.walletsDir, f'{name}.pk')
    addr_path = os.path.join(ton.walletsDir, f'{name}.addr')
    open(pk_path, 'wb').close()
    _write_addr_file(addr_path, 'AA'*32, 0)

    wallet_obj = types.SimpleNamespace(addrB64='ADDR', name=name)
    monkeypatch.setattr(ton, 'GetLocalWallet', lambda n, version='v1': wallet_obj)
    monkeypatch.setattr(ton, 'SetWalletVersion', lambda a, v: None)
    module.create_wallet(name, version='v1')  # should not raise

    name = 'wnew'
    wallet_path = os.path.join(ton.walletsDir, name)
    # ensure no pk file
    if os.path.isfile(wallet_path + '.pk'):
        os.remove(wallet_path + '.pk')
    if os.path.isfile(wallet_path + '.addr'):
        os.remove(wallet_path + '.addr')
    wallet_obj = types.SimpleNamespace(addrB64='ADDR', name=name)
    monkeypatch.setattr(ton.fift, 'run', lambda args: '... Creating new wallet ...')
    monkeypatch.setattr(ton, 'GetLocalWallet', lambda n, version='v1': wallet_obj)
    called = {}
    monkeypatch.setattr(ton, 'SetWalletVersion', lambda a, v: called.setdefault('set', (a, v)))
    module.create_wallet(name, version='v1')
    assert called['set'][1] == 'v1'


def test_generate_wallet_name_and_list(ton: MyTonCore, module: WalletModule, tmp_path):
    wallets_dir = ton.walletsDir
    assert module.generate_wallet_name() == 'wallet_001'

    open(os.path.join(wallets_dir, 'wallet_001.addr'), 'wb').close()
    open(os.path.join(wallets_dir, 'wallet_001.pk'), 'wb').close()
    open(os.path.join(wallets_dir, 'stray.addr'), 'wb').close()

    assert ton.GetWalletsNameList() == ['wallet_001']
    assert module.generate_wallet_name() == 'wallet_002'


def test_do_move_coins(ton: MyTonCore, module: WalletModule, monkeypatch, tmp_path):
    # wallet v1
    wallet = types.SimpleNamespace(version='v1r1', name='w_v1', path='/tmp/w_v1', addrB64='WALLET_V1')
    # accounts
    wallet_acc = Account(0, 'EE'*32)
    wallet_acc.status = 'active'
    wallet_acc.balance = 10.0

    dest = 'DEST_ADDR'
    dest_acc = Account(0, 'FF'*32)
    dest_acc.status = 'active'

    import mytoncore.utils
    monkeypatch.setattr(mytoncore.utils, 'raw_addr_to_b64', lambda a: wallet.addrB64 if a == 'EE'*32 else dest)

    monkeypatch.setattr(ton, 'GetAccount', lambda arg: wallet_acc if arg == wallet.addrB64 else dest_acc)
    # non-bounceable + active dest -> should add -b
    monkeypatch.setattr(ton, 'IsBounceableAddrB64', lambda *_: False)
    monkeypatch.setattr(ton, 'get_seqno', lambda *_: 5)

    captured = {}
    def fake_fift_run(args):
        captured['args'] = args
        return '... Saved to file /tmp/file_v1.boc)'
    monkeypatch.setattr(ton.fift, 'run', fake_fift_run)

    sent = {}
    monkeypatch.setattr(ton, 'SendFile', lambda p, w, timeout=30: sent.setdefault('x', (p, w.addrB64, timeout)))

    module.do_move_coins(wallet, dest, 1.0, flags=['--custom'], timeout=7)

    assert captured['args'][0] == 'wallet.fif'
    # args layout: [script, wallet.path, dest, seqno, coins, '-m', mode, resultFile]
    assert captured['args'][1] == wallet.path
    assert captured['args'][2] == dest
    assert captured['args'][3] == '5'
    assert captured['args'][4] == '1.0'
    assert '-m' in captured['args'] and '3' in captured['args']
    # must include '-b' and our custom flag
    assert '-b' in captured['args'] and '--custom' in captured['args']
    # sent file
    assert sent['x'][0] == '/tmp/file_v1.boc' and sent['x'][1] == wallet.addrB64 and sent['x'][2] == 7

    wallet_acc.status = 'active'
    wallet_acc.balance = 10.0

    dest = 'DEST2'
    dest_acc = Account(0, '22'*32)
    dest_acc.status = 'uninitialized'

    monkeypatch.setattr(mytoncore.utils, 'raw_addr_to_b64', lambda a: 'WALLET_V1B' if a == 'EE'*32 else dest)

    monkeypatch.setattr(ton, 'GetAccount', lambda arg: wallet_acc if arg == wallet.addrB64 else dest_acc)
    # bounceable + inactive dest + no -n flag -> should raise
    monkeypatch.setattr(ton, 'IsBounceableAddrB64', lambda *_: True)
    monkeypatch.setattr(ton, 'get_seqno', lambda *_: 6)
    monkeypatch.setattr(ton.fift, 'run', lambda *_: '...')
    with pytest.raises(Exception):
        module.do_move_coins(wallet, dest, 1.0)


    # v3
    wallet = types.SimpleNamespace(version='v3r2', name='w_v3', path='/tmp/w_v3', addrB64='WALLET_V3', workchain=0)
    wallet_acc = Account(0, '33'*32)
    wallet_acc.status = 'active'
    wallet_acc.balance = 10.0

    monkeypatch.setattr(mytoncore.utils, 'raw_addr_to_b64', lambda _: wallet.addrB64)

    dest_acc.status = 'active'

    monkeypatch.setattr(ton, 'GetAccount', lambda arg: wallet_acc if arg == wallet.addrB64 else dest_acc)
    monkeypatch.setattr(ton, 'IsBounceableAddrB64', lambda *_: True)  # avoid -b assert dependency
    monkeypatch.setattr(ton, 'get_seqno', lambda *_: 8)
    monkeypatch.setattr(module, '_get_wallet_id', lambda w: 777)

    captured = {}
    monkeypatch.setattr(ton.fift, 'run', lambda args: captured.setdefault('args', args) and '... Saved to file /tmp/file_v3.boc)')
    sent = {}
    monkeypatch.setattr(ton, 'SendFile', lambda p, w, timeout=30: sent.setdefault('x', (p, w.addrB64, timeout)))

    module.do_move_coins(wallet, dest, 'all', timeout=11)

    # args layout: [script, wallet.path, dest, subwallet, seqno, coins, '-m', mode, resultFile]
    args = captured['args']
    assert args[0] == 'wallet-v3.fif'
    assert args[3] == '777' and args[4] == '8'  # subwallet and seqno
    assert args[5] == '0'  # coins for 'all'
    assert '-m' in args and '130' in args # mode 130 for 'all'
    assert sent['x'][0] == '/tmp/file_v3.boc' and sent['x'][2] == 11


def test_get_wallet_id(ton: MyTonCore, module: WalletModule, monkeypatch):
    w = types.SimpleNamespace(workchain=0, addrB64='EQD...')

    # success parse
    output = '\nresult:  [ 777 ]\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: output)
    assert module._get_wallet_id(w) == 777

    # error or missing -> default
    w2 = types.SimpleNamespace(workchain=-1, addrB64='EQC...')
    output2 = '\nerror: cannot run method\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: output2)
    assert module._get_wallet_id(w2) == 698983190  # 698983191 + (-1)
