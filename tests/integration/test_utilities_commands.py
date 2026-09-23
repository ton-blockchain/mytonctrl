"""Console commands of modules/utilities.py (account views, bookmarks, offers,
elections, validators, complaints, pool data).

These pin the behaviour of the handlers, including the bare keyword arguments
(``past``, ``fast``, ``offline``, ``adnl``, ``pubkey``, ``wallet``, ``hash``): each
command accepts only the keywords it reacts to, in any order, plus the ``--json`` flag.
"""
import json
import subprocess
import time
from dataclasses import asdict

from pytest_mock import MockerFixture

import modules.utilities as utilities_module
from mypylib import Dict
from mytoncore.models import Account, Block, Message, PoolDataV2, Transaction, ValidatorConfigExt
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import raw_addr_to_b64
from tests.helpers import create_pool_file


ACCOUNT_HEX = "11" * 32
ACCOUNT_ADDR = raw_addr_to_b64("0:" + ACCOUNT_HEX)
PEER_HEX = "22" * 32
PEER_ADDR = raw_addr_to_b64("0:" + PEER_HEX)
POOL_ADDR = raw_addr_to_b64("0:" + "33" * 32)
V3R2_CODE_HASH = "8a6d73bdd8704894f17d8c76ce6139034b8a51b1802907ca36283417798a219b"

ADNL = "AB" * 32
PUBKEY = "CD" * 32
WALLET = raw_addr_to_b64("-1:" + "ef" * 32)

UTILITIES_COMMANDS = ["vas", "vah", "nb", "bl", "db", "ol", "od", "el", "vl", "cl", "get_pool_data"]


def _reduct(value) -> str:
    value = str(value)
    return value[:6] + "..." + value[-6:]


def _rows(output: str) -> list:
    return [line.split() for line in output.splitlines() if line.strip()]


def _message(src_hex, dest_hex, value, ts) -> Message:
    block = Block(workchain=0, shardchain="8000000000000000", seqno=1, rootHash="00", fileHash="00")
    transaction = Transaction(block=block, type=None, time=ts, total_fees=None)
    return Message(
        transaction=transaction,
        src_workchain=0 if src_hex is not None else None,
        dest_workchain=0 if dest_hex is not None else None,
        src_addr=src_hex,
        dest_addr=dest_hex,
        value=value,
        body=None,
    )


def _mock_account_history(monkeypatch, mocker: MockerFixture):
    account = Account(0, ACCOUNT_HEX, status="active", balance=12.5, codeHash=V3R2_CODE_HASH)
    three_days_ago = int(time.time()) - (3 * 86400 + 7200)  # +2h: immune to DST shifts
    history = [
        _message(PEER_HEX, ACCOUNT_HEX, 1.5, three_days_ago),  # incoming
        _message(ACCOUNT_HEX, PEER_HEX, 0.5, None),  # outgoing, no time
        _message(None, ACCOUNT_HEX, None, None),  # external in: skipped
        _message(ACCOUNT_HEX, None, 0.0, None),  # external out: "None" destination
    ]
    get_account_mock = mocker.Mock(return_value=account)
    get_history_mock = mocker.Mock(return_value=history)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)
    monkeypatch.setattr(MyTonCore, "GetAccountHistory", get_history_mock)
    return account, get_account_mock, get_history_mock


HISTORY_ROWS = [
    ["Time", "Coins", "From/To"],
    ["3", "days", "ago", "<<<", "1.5", PEER_ADDR],
    ["n/a", ">>>", "0.5", PEER_ADDR],
    ["n/a", ">>>", "0.0", "None"],
]


def test_utilities_commands_registered(cli):
    output = cli.execute("help", no_color=True)
    registered = {line.split()[0] for line in output.splitlines() if line.strip()}
    assert set(UTILITIES_COMMANDS) <= registered


def test_vas(cli, monkeypatch, mocker: MockerFixture):
    account, get_account_mock, get_history_mock = _mock_account_history(monkeypatch, mocker)

    # Bad args
    output = cli.execute("vas", no_color=True)
    assert "usage: vas [-h] account_addr" in output
    assert "vas: error: the following arguments are required: account_addr" in output
    output = cli.execute(f"vas {ACCOUNT_ADDR} extra", no_color=True)
    assert "vas: error: unrecognized arguments: extra" in output
    get_account_mock.assert_not_called()

    output = cli.execute(f"vas {ACCOUNT_ADDR}", no_color=True)
    assert _rows(output) == [
        ["Address", "Status", "Balance", "Version"],
        [ACCOUNT_ADDR, "active", "12.5", "v3r2"],
        ["Code", "hash"],
        [V3R2_CODE_HASH],
    ] + HISTORY_ROWS
    # once for the status table, once more for the history table
    assert get_account_mock.call_args_list == [mocker.call(ACCOUNT_ADDR), mocker.call(ACCOUNT_ADDR)]
    get_history_mock.assert_called_once_with(account, 10)

    # a raw address is converted to the bounceable user-friendly form first
    get_account_mock.reset_mock()
    output = cli.execute(f"vas 0:{ACCOUNT_HEX}", no_color=True)
    assert [ACCOUNT_ADDR, "active", "12.5", "v3r2"] in _rows(output)
    assert get_account_mock.call_args_list == [mocker.call(ACCOUNT_ADDR), mocker.call(ACCOUNT_ADDR)]


def test_vah(cli, monkeypatch, mocker: MockerFixture):
    account, get_account_mock, get_history_mock = _mock_account_history(monkeypatch, mocker)

    # Bad args
    output = cli.execute("vah", no_color=True)
    assert "usage: vah [-h] account_addr limit" in output
    assert "vah: error: the following arguments are required: account_addr, limit" in output
    output = cli.execute(f"vah {ACCOUNT_ADDR}", no_color=True)
    assert "vah: error: the following arguments are required: limit" in output
    output = cli.execute(f"vah {ACCOUNT_ADDR} 5 extra", no_color=True)
    assert "vah: error: unrecognized arguments: extra" in output
    get_history_mock.assert_not_called()

    output = cli.execute(f"vah {ACCOUNT_ADDR} 5", no_color=True)
    assert _rows(output) == HISTORY_ROWS
    get_account_mock.assert_called_once_with(ACCOUNT_ADDR)
    get_history_mock.assert_called_once_with(account, 5)

    # wrong limit
    get_history_mock.reset_mock()
    output = cli.execute(f"vah {ACCOUNT_ADDR} abc", no_color=True)
    assert "vah: error: argument limit: invalid int value: 'abc'" in output
    get_history_mock.assert_not_called()


def test_bookmarks(cli, ton, monkeypatch, mocker: MockerFixture):
    raw_peer = "0:" + PEER_HEX
    accounts = {
        ACCOUNT_ADDR: Account(0, ACCOUNT_HEX, status="active", balance=12.5),
        raw_peer: Account(0, PEER_HEX),  # empty
    }
    get_account_mock = mocker.Mock(side_effect=lambda addr: accounts[addr])
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)

    # Bad args
    output = cli.execute("nb", no_color=True)
    assert "usage: nb [-h] bookmark_name account_addr" in output
    assert "nb: error: the following arguments are required: bookmark_name, account_addr" in output
    output = cli.execute("nb my_bookmark", no_color=True)
    assert "nb: error: the following arguments are required: account_addr" in output
    output = cli.execute(f"nb my_bookmark {ACCOUNT_ADDR} extra", no_color=True)
    assert "nb: error: unrecognized arguments: extra" in output
    output = cli.execute("db", no_color=True)
    assert "usage: db [-h] bookmark_name" in output
    assert "db: error: the following arguments are required: bookmark_name" in output
    output = cli.execute("db my_bookmark extra", no_color=True)
    assert "db: error: unrecognized arguments: extra" in output
    assert "bookmarks" not in ton.local.db

    output = cli.execute("bl", no_color=True)
    assert "No data" in output

    # db before any bookmark was ever created crashes on the missing list
    output = cli.execute("db my_bookmark", no_color=True)
    assert "'NoneType' object is not iterable" in output

    # nb only accepts addresses
    output = cli.execute("nb my_bookmark not_an_address", no_color=True)
    assert "nb: error: argument account_addr: expected a TON address (in user-friendly or raw form), got 'not_an_address'" in output
    assert "bookmarks" not in ton.local.db

    output = cli.execute(f"nb my_bookmark {ACCOUNT_ADDR}", no_color=True)
    assert "CreatNewBookmark - OK" in output
    output = cli.execute(f"nb peer {raw_peer}", no_color=True)  # raw form is stored as typed
    assert "CreatNewBookmark - OK" in output
    assert ton.local.db["bookmarks"] == [
        {"name": "my_bookmark", "addr": ACCOUNT_ADDR},
        {"name": "peer", "addr": raw_peer},
    ]
    get_account_mock.assert_not_called()

    # bl looks up every bookmark and caches the balance ("empty" for empty accounts) in the db
    output = cli.execute("bl", no_color=True)
    assert _rows(output) == [
        ["Name", "Address", "Balance", "/", "Exp.", "date"],
        ["my_bookmark", ACCOUNT_ADDR, "12.5"],
        ["peer", raw_peer, "empty"],
    ]
    assert get_account_mock.call_args_list == [mocker.call(ACCOUNT_ADDR), mocker.call(raw_peer)]
    assert ton.local.db["bookmarks"][0]["data"] == 12.5
    assert ton.local.db["bookmarks"][1]["data"] == "empty"

    output = cli.execute("db my_bookmark", no_color=True)
    assert "DeleteBookmark - OK" in output
    assert [b["name"] for b in ton.local.db["bookmarks"]] == ["peer"]

    output = cli.execute("db my_bookmark", no_color=True)
    assert "DeleteBookmark error: Bookmark not found" in output
    assert [b["name"] for b in ton.local.db["bookmarks"]] == ["peer"]

    output = cli.execute("bl extra", no_color=True)
    assert "usage: bl [-h]" in output
    assert "bl: error: unrecognized arguments: extra" in output


def test_ol(cli, monkeypatch, mocker: MockerFixture):
    hash1 = "12345678901234567890123456789012345"
    hash2 = "98765432109876543210987654321098765"
    offers = [
        Dict({"hash": hash1, "config": {"id": 12, "value": "x{AB}"}, "votedValidators": [0, 5],
              "wins": 1, "losses": 0, "approvedPercent": 33.3, "isPassed": False}),
        Dict({"hash": hash2, "config": {"id": 44, "value": "x{CD}"}, "votedValidators": [],
              "wins": 3, "losses": 1, "approvedPercent": 80.0, "isPassed": True}),
    ]
    get_offers_mock = mocker.Mock(return_value=offers)
    monkeypatch.setattr(MyTonCore, "GetOffers", get_offers_mock)
    header = ["Hash", "Config", "Votes", "W/L", "Approved", "Is", "passed"]

    output = cli.execute("ol", no_color=True)
    get_offers_mock.assert_called_once_with()
    assert _rows(output) == [
        header,
        [_reduct(hash1), "12", "2", "1/0", "33.3%", "false"],
        [_reduct(hash2), "44", "0", "3/1", "80.0%", "true"],
    ]

    output = cli.execute("ol --json", no_color=True)
    assert json.dumps(offers, indent=2) in output

    # the bare keyword `hash` shows full hashes
    output = cli.execute("ol hash", no_color=True)
    assert _rows(output)[1:] == [
        [hash1, "12", "2", "1/0", "33.3%", "false"],
        [hash2, "44", "0", "3/1", "80.0%", "true"],
    ]

    output = cli.execute(f"ol {hash1}", no_color=True)
    assert f"ol: error: argument words: invalid choice: '{hash1}'" in output

    get_offers_mock.return_value = []
    output = cli.execute("ol", no_color=True)
    assert "No data" in output


def test_od(cli, ton, monkeypatch, mocker: MockerFixture):
    offer_hash = "777"
    offer = {"hash": offer_hash, "config": {"id": 1, "value": "x{ABCDEF}"}}
    get_offer_mock = mocker.Mock(return_value=offer)
    full_config_addr = "-1:" + "55" * 32
    old_config = {"_": "config_param1", "x": 0}
    get_config_mock = mocker.Mock(return_value=old_config)
    monkeypatch.setattr(MyTonCore, "GetOffer", get_offer_mock)
    monkeypatch.setattr(MyTonCore, "GetFullConfigAddr", mocker.Mock(return_value=full_config_addr))
    monkeypatch.setattr(MyTonCore, "get_config", get_config_mock)

    fake_subprocess = mocker.Mock()
    fake_subprocess.PIPE = subprocess.PIPE
    process = fake_subprocess.Popen.return_value
    process.stdout.read.return_value = "\n".join([
        "conn ready",
        "dumping cells as values of TLB type (ConfigParam 1)",
        "x{ABCDEF}",
        "(config_param1 x:1)",
        ">",
    ]).encode()
    monkeypatch.setattr(utilities_module, "subprocess", fake_subprocess)
    monkeypatch.setattr(utilities_module, "time", mocker.Mock())

    # Bad args
    output = cli.execute("od", no_color=True)
    assert "usage: od [-h] offer_hash" in output
    assert "od: error: the following arguments are required: offer_hash" in output
    output = cli.execute(f"od {offer_hash} extra", no_color=True)
    assert "od: error: unrecognized arguments: extra" in output
    get_offer_mock.assert_not_called()

    output = cli.execute(f"od {offer_hash}", no_color=True)
    get_offer_mock.assert_called_once_with(offer_hash)
    # an interactive lite-client is fed the proposal list and the proposed cell
    fake_subprocess.Popen.assert_called_once_with(
        [ton.liteClient.app_path, "--global-config", ton.liteClient.config_path, "--verbosity", "0"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdin.write.call_args_list == [
        mocker.call(f"runmethodfull {full_config_addr} list_proposals\n".encode()),
        mocker.call(b"dumpcellas ConfigParam1 ABCDEF\n"),
    ]
    process.terminate.assert_called_once_with()
    get_config_mock.assert_called_once_with(1)
    with open(ton.tempDir + "data1diff") as f:
        assert json.load(f) == {"_": "config_param1", "x": 1}
    with open(ton.tempDir + "data2diff") as f:
        assert json.load(f) == old_config
    assert json.dumps(old_config, indent=2) in output
    fake_subprocess.run.assert_called_once_with(
        ["diff", "--color", ton.tempDir + "data2diff", ton.tempDir + "data1diff"]
    )

    # negative config ids cannot be diffed
    fake_subprocess.reset_mock()
    get_offer_mock.return_value = {"hash": offer_hash, "config": {"id": -999, "value": "x{}"}}
    output = cli.execute(f"od {offer_hash}", no_color=True)
    assert "Offer config id is negative. Cannot get diff." in output
    fake_subprocess.Popen.assert_not_called()


def test_el(cli, monkeypatch, mocker: MockerFixture):
    entries = {PUBKEY: {"adnlAddr": ADNL, "pubkey": PUBKEY, "walletAddr": WALLET,
                        "stake": 100000.5, "maxFactor": 3.0}}
    get_entries_mock = mocker.Mock(return_value=entries)
    monkeypatch.setattr(MyTonCore, "GetElectionEntries", get_entries_mock)
    header = ["ADNL", "Pubkey", "Wallet", "Stake", "Max-factor"]

    output = cli.execute("el", no_color=True)
    get_entries_mock.assert_called_once_with(past=False)
    assert _rows(output) == [header, [_reduct(ADNL), _reduct(PUBKEY), _reduct(WALLET), "100000.5", "3.0"]]

    get_entries_mock.reset_mock()
    output = cli.execute("el past --json", no_color=True)
    get_entries_mock.assert_called_once_with(past=True)
    assert json.dumps(entries, indent=2) in output

    # bare keywords widen the columns
    output = cli.execute("el adnl pubkey wallet", no_color=True)
    assert _rows(output) == [header, [ADNL, PUBKEY, WALLET, "100000.5", "3.0"]]
    output = cli.execute("el wallet", no_color=True)
    assert _rows(output)[1] == [_reduct(ADNL), _reduct(PUBKEY), WALLET, "100000.5", "3.0"]

    get_entries_mock.reset_mock()
    output = cli.execute("el fast", no_color=True)
    assert "el: error: argument words: invalid choice: 'fast'" in output
    get_entries_mock.assert_not_called()

    get_entries_mock.return_value = {}
    output = cli.execute("el", no_color=True)
    assert "No data" in output
    get_entries_mock.return_value = None
    output = cli.execute("el past", no_color=True)
    assert "No data" in output


def _validator(adnl, pubkey, wallet, efficiency, online, stake) -> ValidatorConfigExt:
    return ValidatorConfigExt(
        adnl_addr=adnl, pubkey=pubkey, weight=10, mr=1.0, wr=1.0, efficiency=efficiency, online=online,
        master_blocks_created=10, master_blocks_expected=10, blocks_created=10, blocks_expected=10,
        is_masterchain=True, wallet_addr=wallet, stake=stake,
    )


def test_vl(cli, monkeypatch, mocker: MockerFixture):
    adnl2, pubkey2, wallet2 = "12" * 32, "34" * 32, raw_addr_to_b64("-1:" + "56" * 32)
    validators = [
        _validator(ADNL, PUBKEY, WALLET, 99.5, True, 500000.0),
        _validator(adnl2, pubkey2, wallet2, 0.0, False, 300000.0),
    ]
    get_validators_mock = mocker.Mock(return_value=validators)
    monkeypatch.setattr(MyTonCore, "GetValidatorsList", get_validators_mock)
    header = ["id", "ADNL", "Pubkey", "Wallet", "Stake", "Efficiency", "Online"]
    short_rows = [
        ["0", _reduct(ADNL), _reduct(PUBKEY), _reduct(WALLET), "500000.0", "99.5", "true"],
        ["1", _reduct(adnl2), _reduct(pubkey2), _reduct(wallet2), "300000.0", "0.0", "false"],
    ]

    output = cli.execute("vl", no_color=True)
    get_validators_mock.assert_called_once_with(past=False, fast=False)
    assert _rows(output) == [header] + short_rows

    get_validators_mock.reset_mock()
    output = cli.execute("vl past", no_color=True)
    get_validators_mock.assert_called_once_with(past=True, fast=False)
    assert _rows(output) == [header] + short_rows

    get_validators_mock.reset_mock()
    cli.execute("vl past fast", no_color=True)
    get_validators_mock.assert_called_once_with(past=True, fast=True)

    get_validators_mock.reset_mock()
    output = cli.execute("vl --json", no_color=True)
    get_validators_mock.assert_called_once_with(past=False, fast=False)
    assert json.dumps([asdict(v) for v in validators], indent=2) in output

    # bare keywords widen the columns
    get_validators_mock.reset_mock()
    output = cli.execute("vl past adnl pubkey wallet", no_color=True)
    get_validators_mock.assert_called_once_with(past=True, fast=False)
    assert _rows(output) == [
        header,
        ["0", ADNL, PUBKEY, WALLET, "500000.0", "99.5", "true"],
        ["1", adnl2, pubkey2, wallet2, "300000.0", "0.0", "false"],
    ]

    # offline hides online validators, the ids keep their list position
    output = cli.execute("vl offline", no_color=True)
    assert _rows(output) == [header, short_rows[1]]

    get_validators_mock.reset_mock()
    output = cli.execute("vl past fast --json", no_color=True)
    get_validators_mock.assert_called_once_with(past=True, fast=True)
    assert json.dumps([asdict(v) for v in validators], indent=2) in output
    get_validators_mock.reset_mock()
    output = cli.execute("vl hash", no_color=True)
    assert "vl: error: argument words: invalid choice: 'hash'" in output
    get_validators_mock.assert_not_called()

    get_validators_mock.return_value = []
    output = cli.execute("vl", no_color=True)
    assert "No data" in output


def test_cl(cli, monkeypatch, mocker: MockerFixture):
    complaints = {
        "chash1": {"electionId": 1700000000, "adnl": ADNL, "suggestedFine": 101.0, "suggestedFinePart": 0,
                   "votedValidators": [1, 2, 3], "approvedPercent": 12.5, "isPassed": False},
        "chash2": {"electionId": 1700000000, "adnl": "EF" * 32, "suggestedFine": 1001.0, "suggestedFinePart": 0,
                   "votedValidators": [], "approvedPercent": 90.0, "isPassed": True},
    }
    get_complaints_mock = mocker.Mock(return_value=complaints)
    monkeypatch.setattr(MyTonCore, "GetComplaints", get_complaints_mock)
    header = ["Election", "id", "ADNL", "Fine", "(part)", "Votes", "Approved", "Is", "passed"]

    output = cli.execute("cl", no_color=True)
    get_complaints_mock.assert_called_once_with(past=False)
    assert _rows(output) == [
        header,
        ["1700000000", _reduct(ADNL), "101.0", "(0)", "3", "12.5%", "false"],
        ["1700000000", _reduct("EF" * 32), "1001.0", "(0)", "0", "90.0%", "true"],
    ]

    get_complaints_mock.reset_mock()
    output = cli.execute("cl past", no_color=True)
    get_complaints_mock.assert_called_once_with(past=True)
    assert len(_rows(output)) == 3

    output = cli.execute("cl --json", no_color=True)
    assert json.dumps(complaints, indent=2) in output

    # the bare keyword `adnl` shows full ADNL addresses
    output = cli.execute("cl past adnl", no_color=True)
    assert [row[1] for row in _rows(output)[1:]] == [ADNL, "EF" * 32]

    get_complaints_mock.reset_mock()
    output = cli.execute("cl pubkey", no_color=True)
    assert "cl: error: argument words: invalid choice: 'pubkey'" in output
    get_complaints_mock.assert_not_called()

    get_complaints_mock.return_value = {}
    output = cli.execute("cl", no_color=True)
    assert "No data" in output


def test_get_pool_data(cli, ton, monkeypatch, mocker: MockerFixture):
    account = Account(0, "33" * 32, status="active", balance=10.0)
    pool_data = {"state": 0, "nominatorsCount": 2, "stakeAt": 0}
    pool_data_v2 = PoolDataV2(
        pool_id=1, halted=False, owner_share=100, pool_supply=0, round_closed=False, round_index=0,
        validators_cell=None, nominators_cell=None, max_nominators=40, nominators_amount=0,
        pending_deposits=0, pending_withdrawals=0,
    )
    get_account_mock = mocker.Mock(return_value=account)
    is_pool_v2_mock = mocker.Mock(return_value=False)
    get_pool_data_mock = mocker.Mock(return_value=pool_data)
    get_pool_data_v2_mock = mocker.Mock(return_value=pool_data_v2)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)
    monkeypatch.setattr(MyTonCore, "account_is_pool_v2", is_pool_v2_mock)
    monkeypatch.setattr(MyTonCore, "GetPoolData", get_pool_data_mock)
    monkeypatch.setattr(MyTonCore, "get_pool_data_v2", get_pool_data_v2_mock)

    # Bad args
    output = cli.execute("get_pool_data", no_color=True)
    assert "usage: get_pool_data [-h] pool_name" in output
    assert "get_pool_data: error: the following arguments are required: pool_name" in output
    output = cli.execute(f"get_pool_data {POOL_ADDR} extra", no_color=True)
    assert "get_pool_data: error: unrecognized arguments: extra" in output
    get_account_mock.assert_not_called()

    # by address, v1 pool
    output = cli.execute(f"get_pool_data {POOL_ADDR}", no_color=True)
    get_account_mock.assert_called_once_with(POOL_ADDR)
    is_pool_v2_mock.assert_called_once_with(account)
    get_pool_data_mock.assert_called_once_with(POOL_ADDR)
    get_pool_data_v2_mock.assert_not_called()
    assert json.dumps(pool_data, indent=4) in output

    # by local pool name, v2 pool
    create_pool_file(ton.poolsDir + "my_pool", bytes.fromhex("33" * 32) + (0).to_bytes(4, "little"))
    is_pool_v2_mock.return_value = True
    get_account_mock.reset_mock()
    get_pool_data_mock.reset_mock()
    output = cli.execute("get_pool_data my_pool", no_color=True)
    get_account_mock.assert_called_once_with(POOL_ADDR)
    get_pool_data_v2_mock.assert_called_once_with(POOL_ADDR)
    get_pool_data_mock.assert_not_called()
    assert json.dumps(asdict(pool_data_v2), indent=4) in output

    # unknown pool name: Pool.from_file fails before GetLocalPool's own "Address file not found" check
    get_account_mock.reset_mock()
    output = cli.execute("get_pool_data no_such_pool", no_color=True)
    assert "No such file or directory" in output
    assert "no_such_pool.addr" in output
    get_account_mock.assert_not_called()
