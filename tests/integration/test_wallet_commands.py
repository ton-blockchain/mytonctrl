import os
import base64

from mypylib import Dict
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import raw_addr_to_b64
from modules.wallet import WalletModule

from pytest_mock import MockerFixture


WALLET_ADDR = raw_addr_to_b64("-1:" + "3" * 64)
WALLET_ADDR_2 = raw_addr_to_b64("0:" + "44" * 32)
BAD_ADDR_ERROR = "argument wallet_addr: expected a TON address (in user-friendly or raw form), got 'not_an_address'"


def test_nw(cli, ton, monkeypatch):
    created_wallet = Dict()

    def fake_create_wallet(self, wallet_name, workchain, version, subwallet):
        nonlocal created_wallet
        wallet = Dict()
        wallet.name = wallet_name
        wallet.workchain = workchain
        wallet.version = version
        wallet.subwallet = subwallet
        wallet.addrB64 = "test"
        wallet.addrB64_init = "test_init"
        created_wallet = wallet
        return wallet

    monkeypatch.setattr(WalletModule, "create_wallet", fake_create_wallet)

    # happy path
    output = cli.execute("nw", no_color=True)

    assert created_wallet is not None
    assert created_wallet.name == "wallet_001"
    assert created_wallet.workchain == 0
    assert created_wallet.addrB64 == "test"
    assert created_wallet.subwallet == 698983191
    assert output.splitlines()[1].split() == ["wallet_001", "0", "test_init"]

    # provide workchain and wallet name
    created_wallet = Dict()
    output = cli.execute("nw -1 my_wallet", no_color=True)

    assert created_wallet.name == "my_wallet"
    assert created_wallet.workchain == -1
    assert created_wallet.version == "v1"
    assert created_wallet.subwallet == 698983190  # 698983191 + (-1)
    assert output.splitlines()[1].split() == ["my_wallet", "-1", "test_init"]

    # provide workchain, wallet name, version
    created_wallet = Dict()
    output = cli.execute("nw 0 test_wallet v3", no_color=True)

    assert created_wallet.name == "test_wallet"
    assert created_wallet.workchain == 0
    assert created_wallet.version == "v3"
    assert created_wallet.subwallet == 698983191
    assert output.splitlines()[1].split() == ["test_wallet", "0", "test_init"]

    # provide workchain, wallet name, version, subwallet
    created_wallet = Dict()
    output = cli.execute("nw 0 full_wallet v3r2 12345", no_color=True)

    assert created_wallet.name == "full_wallet"
    assert created_wallet.workchain == 0
    assert created_wallet.version == "v3r2"
    assert created_wallet.subwallet == 12345
    assert output.splitlines()[1].split() == ["full_wallet", "0", "test_init"]

    # Bad args
    created_wallet = Dict()
    output = cli.execute("nw 0", no_color=True)
    assert "nw: error: workchain_id and wallet_name must be given together" in output
    output = cli.execute("nw abc my_wallet", no_color=True)
    assert "usage: nw [-h] [workchain_id] [wallet_name] [version] [subwallet_id]" in output
    assert "nw: error: argument workchain_id: invalid int value: 'abc'" in output
    output = cli.execute("nw 0 my_wallet v3 1 extra", no_color=True)
    assert "nw: error: unrecognized arguments: extra" in output
    output = cli.execute("nw 0 my_wallet hv1", no_color=True)
    assert "nw: error: argument version: expected a wallet version v1, v2 or v3, optionally with a revision like v3r2, got 'hv1'" in output
    assert not created_wallet


def test_aw(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("aw", no_color=True)
    assert "aw: error: one of the arguments wallet_name --all is required" in output
    output = cli.execute("aw my_wallet --all", no_color=True)
    assert "aw: error: argument --all: not allowed with argument wallet_name" in output
    output = cli.execute("aw my_wallet other_wallet", no_color=True)
    assert "usage: aw [-h] [--all] [wallet_name]" in output
    assert "aw: error: unrecognized arguments: other_wallet" in output

    get_local_wallet_mock = mocker.Mock()
    activate_wallet_mock = mocker.Mock()
    wallets_check_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetLocalWallet", get_local_wallet_mock)
    monkeypatch.setattr(WalletModule, "do_activate_wallet", activate_wallet_mock)
    monkeypatch.setattr(WalletModule, '_wallets_check', wallets_check_mock)

    # happy path
    output = cli.execute("aw my_wallet", no_color=True)

    get_local_wallet_mock.assert_called_once_with("my_wallet")
    activate_wallet_mock.assert_called_once_with(get_local_wallet_mock.return_value)
    wallets_check_mock.assert_not_called()
    assert "ActivateWallet - OK" in output

    # happy path all wallets
    get_local_wallet_mock.reset_mock()
    activate_wallet_mock.reset_mock()
    wallets_check_mock.reset_mock()
    output = cli.execute("aw --all", no_color=True)

    get_local_wallet_mock.assert_not_called()
    activate_wallet_mock.assert_not_called()
    wallets_check_mock.assert_called_once()
    assert "ActivateWallet - OK" in output


def test_wl(cli, ton, monkeypatch, mocker: MockerFixture):
    get_wallets_mock = mocker.Mock()
    get_account_mock = mocker.Mock()
    monkeypatch.setattr(WalletModule, 'get_wallets', get_wallets_mock)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)

    output = cli.execute("wl extra", no_color=True)
    assert "usage: wl [-h]" in output
    assert "wl: error: unrecognized arguments: extra" in output
    get_wallets_mock.assert_not_called()

    # no wallets
    get_wallets_mock.return_value = []
    output = cli.execute("wl", no_color=True)
    assert "No data" in output
    get_account_mock.assert_not_called()

    # active wallet
    get_wallets_mock.reset_mock()
    get_account_mock.reset_mock()
    wallet1 = Dict()
    wallet1.name = "wallet1"
    wallet1.addrB64 = "wallet_1_addr"
    wallet1.addrB64_init = "wallet_1_addr_init"
    wallet1.version = "v3"
    wallet1.workchain = 0

    account1 = Dict()
    account1.status = "active"
    account1.balance = 100.5

    get_wallets_mock.return_value = [wallet1]
    get_account_mock.return_value = account1

    output = cli.execute("wl", no_color=True)
    assert output.splitlines()[1].split() == ["wallet1", "active", "100.5", "v3", "0", "wallet_1_addr"]
    get_account_mock.assert_called_once_with("wallet_1_addr")
    get_wallets_mock.assert_called_once()

    # inactive wallet
    get_wallets_mock.reset_mock()
    get_account_mock.reset_mock()
    wallet2 = Dict()
    wallet2.name = "wallet2"
    wallet2.addrB64 = "wallet_2_addr"
    wallet2.addrB64_init = "wallet_2_addr_init"
    wallet2.version = "v1"
    wallet2.workchain = -1

    account2 = Dict()
    account2.status = "uninit"
    account2.balance = 0

    get_wallets_mock.return_value = [wallet1, wallet2]
    get_account_mock.side_effect = [account1, account2]

    output = cli.execute("wl", no_color=True)

    get_account_mock.assert_has_calls(calls=[mocker.call("wallet_1_addr"), mocker.call("wallet_2_addr")], any_order=False)
    get_wallets_mock.assert_called_once()
    assert output.splitlines()[1].split() == ["wallet1", "active", "100.5", "v3", "0", "wallet_1_addr"]
    assert output.splitlines()[2].split() == ["wallet2", "uninit", "0", "v1", "-1", "wallet_2_addr_init"]



def test_iw(cli, ton, monkeypatch, tmp_path):
    wallets_dir = ton.walletsDir

    assert len(os.listdir(wallets_dir)) == 0

    # Bad args
    output = cli.execute("iw", no_color=True)
    assert "usage: iw [-h] wallet_addr wallet_secret_key" in output
    assert "iw: error: the following arguments are required: wallet_addr, wallet_secret_key" in output
    assert len(os.listdir(wallets_dir)) == 0

    # Bad args
    output = cli.execute(f"iw {WALLET_ADDR}", no_color=True)
    assert "iw: error: the following arguments are required: wallet_secret_key" in output
    assert len(os.listdir(wallets_dir)) == 0
    output = cli.execute("iw not_an_address c2VjcmV0", no_color=True)
    assert f"iw: error: {BAD_ADDR_ERROR}" in output
    assert len(os.listdir(wallets_dir)) == 0

    # happy path
    test_addr = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"
    test_key = base64.b64encode(b"\x01\x02"*16).decode()

    output = cli.execute(f"iw {test_addr} {test_key}", no_color=True)

    wallet_name = 'wallet_001'
    assert f"Wallet name: {wallet_name}" in output
    addr_file = wallets_dir + wallet_name + ".addr"
    pk_file = wallets_dir + wallet_name + ".pk"
    assert os.path.exists(addr_file)
    assert os.path.exists(pk_file)
    with open(pk_file, 'rb') as f:
        stored_pk = f.read()
        assert stored_pk == b"\x01\x02"*16
    with open(addr_file, 'rb') as f:
        stored_addr = f.read()
        assert stored_addr == b"\x00" * 32 + b"\x00" * 4  # addr + wc

    # one more wallet
    test_addr2 = "Ef8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAU"

    output = cli.execute(f"iw {test_addr2} {test_key}", no_color=True)

    wallet_name2 = 'wallet_002'
    assert f"Wallet name: {wallet_name2}" in output
    addr_file2 = wallets_dir + wallet_name2 + ".addr"
    pk_file2 = wallets_dir + wallet_name2 + ".pk"
    assert os.path.exists(addr_file2)
    assert os.path.exists(pk_file2)
    with open(pk_file2, 'rb') as f:
        stored_pk2 = f.read()
        assert stored_pk2 == b"\x01\x02"*16
    with open(addr_file2, 'rb') as f:
        stored_addr = f.read()
        assert stored_addr == b"\x00" * 32 + b'\xff\xff\xff\xff'  # addr + wc
    wallet_files = os.listdir(wallets_dir)
    assert f"{wallet_name}.addr" in wallet_files
    assert f"{wallet_name}.pk" in wallet_files
    assert f"{wallet_name2}.addr" in wallet_files
    assert f"{wallet_name2}.pk" in wallet_files


def test_swv(cli, ton, monkeypatch):
    # Bad args
    output = cli.execute("swv", no_color=True)
    assert "usage: swv [-h] wallet_addr wallet_version" in output
    assert "swv: error: the following arguments are required: wallet_addr, wallet_version" in output
    output = cli.execute(f"swv {WALLET_ADDR}", no_color=True)
    assert "swv: error: the following arguments are required: wallet_version" in output
    output = cli.execute("swv not_an_address v3", no_color=True)
    assert f"swv: error: {BAD_ADDR_ERROR}" in output
    assert "not_an_address" not in ton.GetWalletsVersionList()
    output = cli.execute(f"swv {WALLET_ADDR} v4", no_color=True)
    assert "swv: error: argument wallet_version: expected a wallet version v1, v2 or v3, optionally with a revision like v3r2, got 'v4'" in output
    assert WALLET_ADDR not in ton.GetWalletsVersionList()

    # happy path
    test_addr = WALLET_ADDR
    test_version = "v1r3"
    wallets_version_list = ton.GetWalletsVersionList()
    assert test_addr not in wallets_version_list

    output = cli.execute(f"swv {test_addr} {test_version}", no_color=True)

    assert "SetWalletVersion - OK" in output
    wallets_version_list = ton.GetWalletsVersionList()
    assert test_addr in wallets_version_list
    assert wallets_version_list[test_addr] == "v1r3"

    # update wallet version
    test_version2 = "v3"

    output = cli.execute(f"swv {test_addr} {test_version2}", no_color=True)

    assert "SetWalletVersion - OK" in output
    wallets_version_list = ton.GetWalletsVersionList()
    assert test_addr in wallets_version_list
    assert wallets_version_list[test_addr] == "v3"

    # another wallet
    test_addr2 = WALLET_ADDR_2
    test_version3 = "v2r2"

    output = cli.execute(f"swv {test_addr2} {test_version3}", no_color=True)

    assert "SetWalletVersion - OK" in output
    wallets_version_list = ton.GetWalletsVersionList()
    assert test_addr in wallets_version_list
    assert wallets_version_list[test_addr] == "v3"
    assert test_addr2 in wallets_version_list
    assert wallets_version_list[test_addr2] == "v2r2"


def create_wallet_files(base_path: str, pk: bytes, addr: bytes):
    with open(base_path + ".pk", 'wb') as f:
        f.write(pk)
    with open(base_path + ".addr", 'wb') as f:
        f.write(addr)


def test_ew(cli, ton, monkeypatch, tmp_path):
    wallets_dir = ton.walletsDir

    # Bad args
    output = cli.execute("ew", no_color=True)
    assert "usage: ew [-h] wallet_name" in output
    assert "ew: error: the following arguments are required: wallet_name" in output

    # happy path
    wallet_name = "test_wallet_001"
    wallet_addr = "Ef8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAU"
    wallet_key_bytes = b"\x01"*32
    wallet_key_b64 = base64.b64encode(wallet_key_bytes).decode()

    ton.GetWalletsVersionList()[wallet_addr] = "v3"  # avoid going to ton.GetAccount

    wallet_path = wallets_dir + wallet_name
    create_wallet_files(wallet_path, wallet_key_bytes, b"\x00" * 32 + b'\xff\xff\xff\xff')

    output = cli.execute(f"ew {wallet_name}", no_color=True)
    assert f"Wallet name: {wallet_name}" in output
    assert f"Address: {wallet_addr}" in output
    assert f"Secret key: {wallet_key_b64}" in output


def test_dw(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("dw", no_color=True)
    assert "usage: dw [-h] wallet_name" in output
    assert "dw: error: the following arguments are required: wallet_name" in output

    # cancel deletion
    monkeypatch.setattr('builtins.input', lambda _: 'no')
    output = cli.execute("dw test_wallet", no_color=True)
    assert "Cancel wallet deletion" in output

    # happy path
    wallet_name = 'test_wallet'
    wallet_path = ton.walletsDir + wallet_name
    create_wallet_files(wallet_path, b'\x01' * 32, b"\x00" * 32 + b'\xff\xff\xff\xff')
    wallet_addr = "Ef8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAU"
    ton.GetWalletsVersionList()[wallet_addr] = "v3"  # avoid going to ton.GetAccount
    assert os.path.exists(wallet_path + '.addr')
    assert os.path.exists(wallet_path + '.pk')
    monkeypatch.setattr('builtins.input', lambda _: 'yes')
    output = cli.execute("dw test_wallet", no_color=True)
    assert "DeleteWallet - OK" in output
    assert not os.path.exists(wallet_path + '.addr')
    assert not os.path.exists(wallet_path + '.pk')


def test_mg(cli, ton, monkeypatch, mocker: MockerFixture):
    get_local_wallet_mock = mocker.Mock()
    get_destination_addr_mock = mocker.Mock(return_value="dest_addr_parsed")
    move_coins_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetLocalWallet", get_local_wallet_mock)
    monkeypatch.setattr(MyTonCore, "get_destination_addr", get_destination_addr_mock)
    monkeypatch.setattr(WalletModule, "do_move_coins", move_coins_mock)

    # Bad args
    output = cli.execute("mg", no_color=True)
    assert "usage: mg [-h] [-n] [-b] [-C COMMENT] [-t TIMEOUT] [-m MODE] [-B BODY]" in output
    assert "mg: error: the following arguments are required: wallet_name, destination, amount" in output
    output = cli.execute("mg wallet1", no_color=True)
    assert "mg: error: the following arguments are required: destination, amount" in output
    output = cli.execute("mg wallet1 dest_addr", no_color=True)
    assert "mg: error: the following arguments are required: amount" in output
    output = cli.execute("mg wallet1 dest_addr abc", no_color=True)
    assert "mg: error: argument amount: expected an amount in TON or all / alld, got 'abc'" in output
    output = cli.execute("mg wallet1 dest_addr -5", no_color=True)
    assert "mg: error: argument amount: amount must be a non-negative number, got -5" in output
    output = cli.execute("mg wallet1 dest_addr 10 -Some flags", no_color=True)
    assert "mg: error: unrecognized arguments: -Some flags" in output
    output = cli.execute("mg wallet1 dest_addr 10 -x 1", no_color=True)
    assert "mg: error: unrecognized arguments: -x 1" in output
    output = cli.execute("mg wallet1 dest_addr 10 extra", no_color=True)
    assert "mg: error: unrecognized arguments: extra" in output
    get_local_wallet_mock.assert_not_called()
    get_destination_addr_mock.assert_not_called()
    move_coins_mock.assert_not_called()

    # happy path
    output = cli.execute("mg wallet1 dest_addr 10", no_color=True)
    assert "MoveCoins - OK" in output
    get_local_wallet_mock.assert_called_once_with("wallet1")
    get_destination_addr_mock.assert_called_once_with("dest_addr")
    move_coins_mock.assert_called_once_with(
        get_local_wallet_mock.return_value,
        "dest_addr_parsed",
        10.0,
        flags=[]
    )

    # with flags
    for reset in (get_local_wallet_mock, get_destination_addr_mock, move_coins_mock):
        reset.reset_mock()
    output = cli.execute("mg wallet2 dest_addr_2 all -n --comment hello -m 1 -t 120", no_color=True)
    assert "MoveCoins - OK" in output
    get_local_wallet_mock.assert_called_once_with("wallet2")
    get_destination_addr_mock.assert_called_once_with("dest_addr_2")
    move_coins_mock.assert_called_once_with(
        get_local_wallet_mock.return_value,
        "dest_addr_parsed",
        "all",
        flags=["-n", "-C", "hello", "-t", "120", "-m", "1"]
    )

    move_coins_mock.reset_mock()
    output = cli.execute("mg -b -B body.boc -I init.boc wallet2 dest_addr_2 1.5", no_color=True)
    assert "MoveCoins - OK" in output
    move_coins_mock.assert_called_once_with(
        get_local_wallet_mock.return_value,
        "dest_addr_parsed",
        1.5,
        flags=["-b", "-B", "body.boc", "-I", "init.boc"]
    )


def test_mgtp(cli, ton, monkeypatch, mocker: MockerFixture):
    get_local_wallet_mock = mocker.Mock()
    get_destination_addr_mock = mocker.Mock(return_value="dest_addr_parsed")
    do_move_coins_through_proxy_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetLocalWallet", get_local_wallet_mock)
    monkeypatch.setattr(MyTonCore, "get_destination_addr", get_destination_addr_mock)
    monkeypatch.setattr(WalletModule, "do_move_coins_through_proxy", do_move_coins_through_proxy_mock)

    # Bad args
    output = cli.execute("mgtp", no_color=True)
    assert "usage: mgtp [-h] wallet_name destination amount" in output
    assert "mgtp: error: the following arguments are required: wallet_name, destination, amount" in output
    output = cli.execute("mgtp wallet1", no_color=True)
    assert "mgtp: error: the following arguments are required: destination, amount" in output
    output = cli.execute("mgtp wallet1 dest_addr", no_color=True)
    assert "mgtp: error: the following arguments are required: amount" in output
    output = cli.execute("mgtp wallet1 dest_addr 10 extra", no_color=True)
    assert "mgtp: error: unrecognized arguments: extra" in output
    get_local_wallet_mock.assert_not_called()
    do_move_coins_through_proxy_mock.assert_not_called()
    get_destination_addr_mock.assert_not_called()

    # happy path
    output = cli.execute("mgtp wallet1 dest_addr 10", no_color=True)
    assert "MoveCoinsThroughProxy - OK" in output
    get_local_wallet_mock.assert_called_once_with("wallet1")
    get_destination_addr_mock.assert_called_once_with("dest_addr")
    do_move_coins_through_proxy_mock.assert_called_once_with(
        get_local_wallet_mock.return_value,
        "dest_addr_parsed",
        10.0
    )
