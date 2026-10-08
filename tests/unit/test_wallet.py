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
    monkeypatch.setattr(module, 'get_new_wallet_fift_args', lambda version, workchain, wallet_path, subwallet: ['script.fif'])
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


# --- do_move_coins: the fift argv behind `mg` ---------------------------------

_SENDER_ADDR = 'SENDER_ADDR'
_DEST = 'DEST_ADDR'
_SAVED_BOC = '/tmp/saved_wallet-query.boc'


def _transfer_wallet(version: str = 'v1r3'):
    return types.SimpleNamespace(version=version, name='sender', path='/wallets/sender', addrB64=_SENDER_ADDR)


def _account(status: str = 'active', balance: float = 10.0) -> Account:
    return Account(0, 'EE' * 32, status=status, balance=balance)


def _result_file(module: WalletModule, wallet) -> str:
    return module.local.my_temp_dir + wallet.name + '_wallet-query'


def _patch_transfer(ton: MyTonCore, monkeypatch, sender_acc: Account, dest_status: str = 'active',
                    dest_bounceable: bool = True, fift_output: str = f'... Saved to file {_SAVED_BOC})'):
    '''Stub every node call of do_move_coins; returns the recorded fift argvs and SendFile calls.'''
    dest_acc = Account(0, 'FF' * 32, status=dest_status)
    monkeypatch.setattr(ton, 'GetAccount', lambda addr: sender_acc if addr == _SENDER_ADDR else dest_acc)
    monkeypatch.setattr(ton, 'IsBounceableAddrB64', lambda addr: dest_bounceable)
    monkeypatch.setattr(ton, 'get_seqno', lambda wallet: 5)
    calls = {'fift': [], 'send': []}

    def fake_fift_run(args):
        calls['fift'].append(list(args))
        return fift_output
    monkeypatch.setattr(ton.fift, 'run', fake_fift_run)
    monkeypatch.setattr(ton, 'SendFile', lambda path, wallet, timeout=30: calls['send'].append((path, wallet, timeout)))
    return calls


def test_do_move_coins_alld_sends_zero_coins_with_mode_160(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet('v1r3')
    calls = _patch_transfer(ton, monkeypatch, _account())

    module.do_move_coins(wallet, _DEST, 'alld')

    assert calls['fift'] == [
        ['wallet.fif', wallet.path, _DEST, '5', '0', '-m', '160', _result_file(module, wallet)],
    ]
    assert calls['send'] == [(_SAVED_BOC, wallet, 30)]


def test_do_move_coins_v2_wallet_uses_wallet_v2_fif_without_subwallet(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet('v2r2')
    calls = _patch_transfer(ton, monkeypatch, _account())
    monkeypatch.setattr(module, '_get_wallet_id', lambda w: pytest.fail('subwallet is only for v3 wallets'))

    module.do_move_coins(wallet, _DEST, 1.5)

    assert calls['fift'] == [
        ['wallet-v2.fif', wallet.path, _DEST, '5', '1.5', '-m', '3', _result_file(module, wallet)],
    ]
    assert calls['send'] == [(_SAVED_BOC, wallet, 30)]


def test_do_move_coins_unsupported_wallet_version_raises(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet('v5r1')
    calls = _patch_transfer(ton, monkeypatch, _account())

    with pytest.raises(Exception, match="Wallet version 'v5r1' is not supported"):
        module.do_move_coins(wallet, _DEST, 1.0)

    assert calls['fift'] == []
    assert calls['send'] == []


def test_do_move_coins_highload_wallet_is_not_supported(ton: MyTonCore, module: WalletModule, monkeypatch):
    # "hv1" contains "v1": a substring match used to pick wallet.fif for a highload wallet
    wallet = _transfer_wallet('hv1')
    calls = _patch_transfer(ton, monkeypatch, _account())

    with pytest.raises(Exception, match="Wallet version 'hv1' is not supported"):
        module.do_move_coins(wallet, _DEST, 1.0)

    assert calls['fift'] == []
    assert calls['send'] == []


def test_do_move_coins_unknown_wallet_version_is_not_supported(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet(None)
    calls = _patch_transfer(ton, monkeypatch, _account())

    with pytest.raises(Exception, match="Wallet version None is not supported"):
        module.do_move_coins(wallet, _DEST, 1.0)

    assert calls['fift'] == []


@pytest.mark.parametrize("version, script", [("v1", "new-wallet.fif"), ("v1r3", "new-wallet.fif"), ("v2r2", "new-wallet-v2.fif"), ("v3", "new-wallet-v3.fif"), ("v3r2", "new-wallet-v3.fif")])
def test_get_new_wallet_fift_args_picks_the_script_by_version_prefix(version, script):
    assert WalletModule.get_new_wallet_fift_args(version, 0, "/w/x", 7)[0] == script


@pytest.mark.parametrize("version", ["hv1", "v4", "unknown"])
def test_get_new_wallet_fift_args_rejects_other_versions(version):
    with pytest.raises(Exception, match=f"fift script for `{version}` not found"):
        WalletModule.get_new_wallet_fift_args(version, 0, "/w/x", 7)


def test_do_move_coins_insufficient_balance_raises_before_fift(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet()
    sender_acc = _account(balance=1.0)
    calls = _patch_transfer(ton, monkeypatch, sender_acc)

    # 5 coins + 0.1 reserved for fees > 1.0 on the balance
    with pytest.raises(Exception) as e:
        module.do_move_coins(wallet, _DEST, 5)

    assert str(e.value) == (
        f'Account {sender_acc.addrB64} balance is less than requested coins. '
        f'Balance: 1.0, requested amount: 5.1 (need 4.1 more)'
    )
    assert calls['fift'] == []
    assert calls['send'] == []


def test_do_move_coins_inactive_sender_raises_before_fift(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet()
    sender_acc = _account(status='uninitialized')
    calls = _patch_transfer(ton, monkeypatch, sender_acc)

    with pytest.raises(Exception) as e:
        module.do_move_coins(wallet, _DEST, 1.0)

    assert str(e.value) == f'Account {sender_acc.addrB64} account is uninitialized'
    assert calls['fift'] == []
    assert calls['send'] == []


def test_do_move_coins_fift_did_not_save_boc_raises_without_sending(ton: MyTonCore, module: WalletModule, monkeypatch):
    wallet = _transfer_wallet()
    calls = _patch_transfer(ton, monkeypatch, _account(), fift_output='[ 1][t 0] error: cannot open file')

    with pytest.raises(Exception, match='Fift script did not save boc'):
        module.do_move_coins(wallet, _DEST, 1.0)

    assert len(calls['fift']) == 1
    assert calls['send'] == []


def test_do_move_coins_no_bounce_flag_allows_bounceable_addr_to_inactive_dest(ton: MyTonCore, module: WalletModule, monkeypatch):
    # without -n this exact situation raises (see test_do_move_coins)
    wallet = _transfer_wallet()
    calls = _patch_transfer(ton, monkeypatch, _account(), dest_status='uninitialized', dest_bounceable=True)

    module.do_move_coins(wallet, _DEST, 1.0, flags=['-n'])

    assert calls['fift'] == [
        ['wallet.fif', wallet.path, _DEST, '5', '1.0', '-m', '3', _result_file(module, wallet), '-n'],
    ]
    assert calls['send'] == [(_SAVED_BOC, wallet, 30)]


def test_do_move_coins_caller_mode_is_appended_after_derived_mode(ton: MyTonCore, module: WalletModule, monkeypatch):
    # `mg -m` "overrides the one derived from amount": fift takes the last -m it sees
    wallet = _transfer_wallet()
    calls = _patch_transfer(ton, monkeypatch, _account())

    module.do_move_coins(wallet, _DEST, 'all', flags=['-m', '1'])

    assert calls['fift'] == [
        ['wallet.fif', wallet.path, _DEST, '5', '0', '-m', '130', _result_file(module, wallet), '-m', '1'],
    ]
    argv = calls['fift'][0]
    first_m = argv.index('-m')
    last_m = len(argv) - 1 - argv[::-1].index('-m')
    assert argv[first_m + 1] == '130'
    assert last_m > first_m
    assert last_m == len(argv) - 2
    assert argv[last_m + 1] == '1'


# --- do_move_coins_through_proxy: the `mgtp` hop sequence ---------------------

def test_do_move_coins_through_proxy_call_sequence(ton: MyTonCore, module: WalletModule, monkeypatch):
    log = []

    class FakeProxyWallet:
        def __init__(self, name: str):
            self.name = name
            self.addrB64_init = name.upper() + '_INIT'

        def delete(self):
            log.append(('delete', self))

    proxies = {'proxy_wallet1': FakeProxyWallet('proxy_wallet1'), 'proxy_wallet2': FakeProxyWallet('proxy_wallet2')}
    w1, w2 = proxies['proxy_wallet1'], proxies['proxy_wallet2']

    def fake_create_wallet(*args, **kwargs):
        log.append(('create_wallet', args, kwargs))
        return proxies[args[0]]

    monkeypatch.setattr(module, 'create_wallet', fake_create_wallet)
    monkeypatch.setattr(module, 'do_move_coins', lambda *args, **kwargs: log.append(('do_move_coins', args, kwargs)))
    monkeypatch.setattr(module, 'do_activate_wallet', lambda w: log.append(('do_activate_wallet', w)))
    wallet = _transfer_wallet()

    module.do_move_coins_through_proxy(wallet, _DEST, 7.5)

    assert log == [
        ('create_wallet', ('proxy_wallet1', 0), {}),
        ('create_wallet', ('proxy_wallet2', 0), {}),
        ('do_move_coins', (wallet, w1.addrB64_init, 7.5), {}),
        ('do_activate_wallet', w1),
        ('do_move_coins', (w1, w2.addrB64_init, 'alld'), {}),
        ('do_activate_wallet', w2),
        ('do_move_coins', (w2, _DEST, 'alld'), {'flags': ['-n']}),
        ('delete', w1),
        ('delete', w2),
    ]
