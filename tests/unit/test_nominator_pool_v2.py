"""Unit tests for the nominator-pool v2 election-cycle get-method readers.

These feed crafted `lite-client runmethodfull` output through the real
`run_get_method` -> `parse_result_stack` path and assert the v2 readers parse the
flattened TVM stacks correctly (field order, uint256-hash address decoding, null
handling; slice items are carried raw, never parsed).
"""
from __future__ import annotations

import time

import pytest

from mytoncore.mytoncore import MyTonCore
from mytoncore.models import Account
from mytoncore.utils import parse_mc_addr_from_vm_int, raw_addr_to_b64


def lc_slice(workchain: int, hash_hex: str) -> str:
    """Build an address slice EXACTLY as lite-client `runmethodfull` prints it:
    ``CS{Cell{<d1><d2><data>} bits: 0..267; refs: 0..0}`` where the cell hex carries
    the two descriptor bytes (d1=00 -> 0 refs, d2=0x43 -> 267 data bits) before the
    addr_std data (addr_std$10 anycast:0 wc:int8 hash:bits256, completion-padded)."""
    bits = '100' + format(workchain & 0xFF, '08b') + format(int(hash_hex, 16), '0256b')
    data_bits = bits + '1'
    while len(data_bits) % 8 != 0:
        data_bits += '0'
    data_hex = format(int(data_bits, 2), '0{}x'.format(len(data_bits) // 4))
    cell_hex = '0043' + data_hex
    return f'CS{{Cell{{{cell_hex}}} bits: 0..267; refs: 0..0}}'


MC_HASH = '11' * 32
MC_SLICE = lc_slice(-1, MC_HASH)
MC_ADDR = raw_addr_to_b64('-1:' + MC_HASH)
PROXY_E_HASH = '33' * 32
PROXY_O_HASH = '44' * 32
POOL_V2_CODE_HASH = '653ada77b5f36e40d42e59841c9f035a39fb2eedda1fa7bfa60511b6755294d3'


def test_parse_mc_addr_from_vm_int():
    # v2 proxies come back as bare uint256 hash ints; the workchain is always -1.
    assert parse_mc_addr_from_vm_int(str(int(MC_HASH, 16))) == MC_ADDR
    # lite-client prints a null stack entry as '()'; '(null)' is the StackEntry::dump
    # spelling that shows up in other lite-client output.
    assert parse_mc_addr_from_vm_int("()") is None
    assert parse_mc_addr_from_vm_int("(null)") is None
    assert parse_mc_addr_from_vm_int(None) is None
    # short hashes zero-pad to the full 64 hex chars
    assert parse_mc_addr_from_vm_int("5") == raw_addr_to_b64('-1:' + '5'.zfill(64))


def test_pool_v2_code_hash_is_registered(ton: MyTonCore):
    assert ton.GetVersionFromCodeHash(POOL_V2_CODE_HASH) == "npool_v2"


def _stub(ton, monkeypatch, table: dict, seen: list | None = None):
    """Route liteClient.run by the get-method name embedded in the command."""
    def get_output(cmd):
        if seen is not None:
            seen.append(cmd)
        for method, out in table.items():
            if method in cmd:
                return out
        raise AssertionError(f"unexpected liteclient cmd: {cmd}")

    monkeypatch.setattr(
        ton.liteClient,
        "run",
        lambda cmd, **kw: f"... \nresult: [ {get_output(cmd)} ]\n",
    )
    monkeypatch.setattr(
        ton.liteClient,
        "run_local",
        lambda cmd, **kw: f"... \nremote result: [ {get_output(cmd)} ]\n",
    )


def test_get_pool_data_v2(ton: MyTonCore, monkeypatch):
    stack = (f"{MC_SLICE} 42 0 1677721 5000000000000 0 7 "
             f"C{{a1b2}} C{{c3d4}} 100 4000000000000 250000000000 0")
    _stub(ton, monkeypatch, {"get_pool_data": stack})
    data = ton.get_pool_data_v2("EQpool")
    assert data.pool_id == 42
    assert data.halted is False
    assert data.owner_share == 1677721
    assert data.pool_supply == 5000000000000
    assert data.round_closed is False
    assert data.round_index == 7          # odd round
    assert data.max_nominators == 100
    assert data.nominators_amount == 4000000000000
    assert data.pending_deposits == 250000000000
    assert data.pending_withdrawals == 0


def test_get_pool_data_v2_bool_is_minus_one(ton: MyTonCore, monkeypatch):
    # TVM booleans are -1 (true) / 0 (false).
    stack = (f"{MC_SLICE} 1 -1 0 0 -1 6 C{{a}} C{{b}} 0 0 0 0")
    _stub(ton, monkeypatch, {"get_pool_data": stack})
    data = ton.get_pool_data_v2("EQpool")
    assert data.halted is True
    assert data.round_closed is True
    assert data.round_index == 6          # even round


def test_get_limits_per_validator_v2(ton: MyTonCore, monkeypatch):
    _stub(ton, monkeypatch, {"get_limits_per_validator": "100000000000 1000000000000000 3000000000"})
    limits = ton.get_limits_per_validator_v2("EQpool")
    assert limits.min_ton_per_validator == 100000000000
    assert limits.max_ton_per_validator == 1000000000000000
    assert limits.refund_bonus == 3000000000


def test_get_validator_info_v2(ton: MyTonCore, monkeypatch):
    validator = f"0 2 {int(PROXY_E_HASH, 16)} {int(PROXY_O_HASH, 16)} () 0 3"
    # cur/prev round usage records (slots 7..22): proxy, heldFor, tonUsed, validator,
    # rotation.{vsetHash, rotationTime, rotationCount}, trailing present_flag.
    cur = f"{int(PROXY_O_HASH, 16)} 86400 150000000000000 {MC_SLICE} 123456789 1700000000 2 -1"
    prev = "() () () () () () () 0"
    seen = []
    _stub(ton, monkeypatch, {"get_validator_info_mtc":
          f"{validator} {cur} {prev} 250000000000000 7 -1"},
          seen=seen)
    info = ton.get_validator_info_v2("EQpool", MC_ADDR)
    # the _mtc getter takes the validator as (workchain, hash) int args, not a slice literal
    assert f"get_validator_info_mtc -1 0x{MC_HASH}" in seen[-1]
    assert info.is_banned is False
    assert info.usage_state == 2
    assert info.round_parity == 3
    # proxy hash ints resolve to masterchain addresses
    assert info.even_proxy == raw_addr_to_b64('-1:' + PROXY_E_HASH)
    assert info.odd_proxy == raw_addr_to_b64('-1:' + PROXY_O_HASH)
    assert info.prev_round_usage is None          # present_flag == 0 -> not staked in prev
    cur_usage = info.cur_round_usage
    assert cur_usage is not None
    assert cur_usage.proxy_addr == raw_addr_to_b64('-1:' + PROXY_O_HASH)
    assert cur_usage.held_for == 86400
    assert cur_usage.ton_used == 150000000000000
    assert cur_usage.rotation_time == 1700000000
    assert cur_usage.rotation_count == 2
    assert info.stakeable == 250000000000000
    assert info.round_index == 7
    assert info.rotated is True


def test_get_validator_info_v2_null_odd_proxy(ton: MyTonCore, monkeypatch):
    # A validator allowed only in even rounds (roundParity=2) has no odd proxy: the
    # contract's deployProxy only sets the allowed parity, so lite-client prints '()'.
    validator = f"0 0 {int(PROXY_E_HASH, 16)} () () 0 2"
    no_usage = "() () () () () () () 0"
    _stub(ton, monkeypatch, {"get_validator_info_mtc": f"{validator} {no_usage} {no_usage} 0 8 0"})
    info = ton.get_validator_info_v2("EQpool", MC_ADDR)
    assert info.even_proxy == raw_addr_to_b64('-1:' + PROXY_E_HASH)
    assert info.odd_proxy is None
    assert info.stakeable == 0
    assert info.round_index == 8
    assert info.rotated is False


def test_get_validator_proxy_v2_uses_projected_round(ton: MyTonCore, monkeypatch):
    info = _Obj(
        even_proxy="Ef-even",
        odd_proxy="Ef-odd",
        round_index=9,
        rotated=True,
    )
    monkeypatch.setattr(ton, "get_validator_info_v2", lambda p, v: info)
    monkeypatch.setattr(
        ton,
        "get_pool_data_v2",
        lambda p: pytest.fail("projected round must not be replaced with stored pool round"),
    )

    assert ton.get_validator_proxy_v2("EQpool", MC_ADDR) == "Ef-odd"


def test_get_validator_info_v2_old_25_item_stack_raises(ton: MyTonCore, monkeypatch):
    # A pre-projected-round contract response (8-slot validator with refundAmount,
    # no roundIndex/rotated tail) is too short and must be rejected.
    validator = f"0 2 {int(PROXY_E_HASH, 16)} {int(PROXY_O_HASH, 16)} () 0 0 3"
    no_usage = "() () () () () () () 0"
    _stub(ton, monkeypatch, {"get_validator_info_mtc": f"{validator} {no_usage} {no_usage} 0"})
    with pytest.raises(Exception, match="expected 26 stack items"):
        ton.get_validator_info_v2("EQpool", MC_ADDR)


def test_get_pool_data_v2_short_stack_raises(ton: MyTonCore, monkeypatch):
    _stub(ton, monkeypatch, {"get_pool_data": f"{MC_SLICE} 1 0"})
    with pytest.raises(Exception, match="expected 13 stack items"):
        ton.get_pool_data_v2("EQpool")


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _stake_stubs(ton, monkeypatch, stakeable, min_ton=10000, validating=False):
    """Stub everything the v2 path of GetStake reads: the mode flags, config17, the
    contract-computed stakeable amount (TON), the pool minimum, the validator wallet and
    whether the node is already in the current vset."""
    monkeypatch.setattr(ton, "using_nominator_pool_v2", lambda: True)
    monkeypatch.setattr(ton, "using_nominator_pool", lambda: False)
    monkeypatch.setattr(ton, "using_single_nominator", lambda: False)
    monkeypatch.setattr(ton, "using_liquid_staking", lambda: False)
    monkeypatch.setattr(ton, "account_is_pool_v2", lambda a: True)
    monkeypatch.setattr(ton, "get_config_17", lambda: _Obj(min_stake=min_ton, max_stake=10**6))
    monkeypatch.setattr(ton, "get_validator_info_v2", lambda p, v: _Obj(stakeable=stakeable * 10**9))
    monkeypatch.setattr(ton, "get_limits_per_validator_v2",
                        lambda a: _Obj(min_ton_per_validator=min_ton * 10**9,
                                       max_ton_per_validator=1000000 * 10**9,
                                       refund_bonus=3 * 10**9))
    monkeypatch.setattr(ton, "GetValidatorWallet", lambda: _Obj(addrB64=MC_ADDR))
    monkeypatch.setattr(ton, "GetValidatorConfig",
                        lambda: _Obj(validators=["adnl"] if validating else []))


def _clear_stake_settings(ton):
    for key in ("stake", "stakePercent", "stakeNoSplit"):
        ton.local.db.pop(key, None)


def _pool_account() -> Account:
    # The v2 pool account GetStake receives in v2 mode: .addrB64 (pool address for the
    # getters) derives from workchain+addr; .balance feeds the final guard; codeHash None
    # -> not a single-nominator.
    account = Account(0, 'cc' * 32)
    account.balance = 10**9
    return account


def test_get_stake_v2_no_split_first_entry(ton: MyTonCore, monkeypatch):
    # v2 pools never split the stake in half, even before the first vset entry: the
    # contract computes stakeable per round and the pool balance funds both proxy
    # rounds, so the v1 half-now-half-next-round bootstrap does not apply.
    _stake_stubs(ton, monkeypatch, stakeable=100000)
    _clear_stake_settings(ton)
    assert ton.GetStake(_pool_account()) == 99995


def test_get_stake_v2_full_when_validating(ton: MyTonCore, monkeypatch):
    # Already in the vset -> the other half is locked in a round; use all that is left
    # (stakeable already excludes the stake in use).
    _stake_stubs(ton, monkeypatch, stakeable=100000, validating=True)
    _clear_stake_settings(ton)
    assert ton.GetStake(_pool_account()) == 99995


def test_get_stake_v2_below_pool_min_raises(ton: MyTonCore, monkeypatch):
    # The pool minimum can be above the network minimum from config17; a
    # stakePercent-reduced stake below it must raise instead of being sent
    # (the contract would refund such a NewStake anyway).
    _stake_stubs(ton, monkeypatch, stakeable=15000, min_ton=10000)
    monkeypatch.setattr(ton, "get_config_17", lambda: _Obj(min_stake=1000, max_stake=10**6))
    _clear_stake_settings(ton)
    ton.local.db["stakePercent"] = 50
    with pytest.raises(Exception, match="min stake: 10000"):
        ton.GetStake(_pool_account())
    ton.local.db.pop("stakePercent", None)


def test_get_stake_v2_stake_no_split(ton: MyTonCore, monkeypatch):
    _stake_stubs(ton, monkeypatch, stakeable=100000)
    _clear_stake_settings(ton)
    ton.local.db["stakeNoSplit"] = True
    assert ton.GetStake(_pool_account()) == 99995
    ton.local.db.pop("stakeNoSplit", None)


def test_get_stake_v2_honors_stake_percent(ton: MyTonCore, monkeypatch):
    _stake_stubs(ton, monkeypatch, stakeable=100000, validating=True)
    _clear_stake_settings(ton)
    ton.local.db["stakePercent"] = 50
    # (100000 - 5) * 0.5 = 49997.5 -> int 49997
    assert ton.GetStake(_pool_account()) == 49997
    ton.local.db.pop("stakePercent", None)


def test_get_stake_v2_explicit_setting(ton: MyTonCore, monkeypatch):
    _stake_stubs(ton, monkeypatch, stakeable=100000)
    _clear_stake_settings(ton)
    ton.local.db["stake"] = 50000
    assert ton.GetStake(_pool_account()) == 50000
    ton.local.db.pop("stake", None)


def test_get_stake_v2_explicit_setting_not_capped(ton: MyTonCore, monkeypatch):
    # Decided behavior, same as v1: an explicit `stake` setting is the operator's
    # responsibility and is NOT capped at stakeable - a NewStake above it is refunded
    # by the contract, only config17 and the pool balance are checked locally.
    _stake_stubs(ton, monkeypatch, stakeable=100000)
    _clear_stake_settings(ton)
    ton.local.db["stake"] = 200000
    assert ton.GetStake(_pool_account()) == 200000
    ton.local.db.pop("stake", None)


def test_get_stake_non_v2_account_with_v2_mode_on(ton: MyTonCore, monkeypatch):
    # Account-based dispatch: with the v2 mode enabled, an account that is NOT a v2 pool
    # (e.g. a v1 pool being readiness-checked) must not be sent v2 get methods - it takes
    # the v1 pool branch (balance - 20).
    _stake_stubs(ton, monkeypatch, stakeable=100000)
    monkeypatch.setattr(ton, "account_is_pool_v2", lambda a: False)
    monkeypatch.setattr(ton, "get_validator_info_v2",
                        lambda p, v: pytest.fail("v2 getter called for a non-v2 account"))
    _clear_stake_settings(ton)
    account = Account(0, 'dd' * 32)
    account.balance = 50000
    assert ton.GetStake(account) == 49980   # balance - 20, the v1 pool branch


def test_get_stake_v2_zero_stakeable_raises(ton: MyTonCore, monkeypatch):
    # stakeable == 0 means the pool refuses right now (blocked validator or underfunded pool).
    _stake_stubs(ton, monkeypatch, stakeable=0)
    _clear_stake_settings(ton)
    with pytest.raises(Exception, match="Stakeable is zero for pool"):
        ton.GetStake(_pool_account())


def test_new_stake_builder_arg_order(ton: MyTonCore, monkeypatch):
    captured = {}

    def fake_fift_run(args, **kw):
        captured["args"] = args
        return "validator public key ABCDEF\nSaved to file /tmp/out.boc\n"

    monkeypatch.setattr(ton.fift, "run", fake_fift_run)
    pubkey, path = ton.sign_election_request_with_pool_v2_with_validator(
        "Ef-proxy", 1700000000, 3, "cd" * 32, "sig_b64", "pub36_b64", 150000)
    args = captured["args"]
    # [script, proxy, startWorkTime, maxFactor, adnl, pubkey, sig, savefile, stake];
    # everything is stringified before fift.run
    assert args[1] == "Ef-proxy"            # PROXY address is the signed/bound address
    assert args[2] == "1700000000"
    assert args[8] == "150000"              # stake amount is last
    assert pubkey == "ABCDEF"
    assert path == "/tmp/out.boc"


def test_pools_update_validator_set_dispatches_by_family_and_mode(ton: MyTonCore, monkeypatch):
    # One walker serves both pool families: each pool is classified once (single
    # GetAccount) and dispatched to its family's updater, gated by that family's mode -
    # a pool of a disabled family must not be touched (e.g. a v2 pool after rolling
    # back to v1), and a v2 pool must never reach the v1 get_pool_data parse.
    monkeypatch.setattr(ton, "GetValidatorWallet", lambda: _Obj(addrB64="Ef-validator"))
    monkeypatch.setattr(ton, "GetPools", lambda: [_Obj(addrB64="EQv1"), _Obj(addrB64="EQv2")])
    accounts = {
        "EQv1": _Obj(codeHash="v1hash", status="active"),
        "EQv2": _Obj(codeHash="v2hash", status="active"),
    }
    monkeypatch.setattr(ton, "GetAccount", lambda addr: accounts[addr])
    monkeypatch.setattr(ton, "account_is_pool_v2", lambda acc: acc.codeHash == "v2hash")
    monkeypatch.setattr(ton, "using_nominator_pool", lambda: True)
    monkeypatch.setattr(ton, "using_single_nominator", lambda: False)
    monkeypatch.setattr(ton, "using_nominator_pool_v2", lambda: True)
    updated = []
    monkeypatch.setattr(ton, "PoolUpdateValidatorSet", lambda addr, w: updated.append(("v1", addr)))
    monkeypatch.setattr(
        ton,
        "pool_update_validator_set_v2",
        lambda pool, w: updated.append(("v2", pool.addrB64)),
    )

    ton.PoolsUpdateValidatorSet()          # migration: both families served in one pass
    assert updated == [("v1", "EQv1"), ("v2", "EQv2")]

    updated.clear()                        # v1-only: the v2 pool is not touched
    monkeypatch.setattr(ton, "using_nominator_pool_v2", lambda: False)
    ton.PoolsUpdateValidatorSet()
    assert updated == [("v1", "EQv1")]

    updated.clear()                        # v2-only: the v1 pool is not touched
    monkeypatch.setattr(ton, "using_nominator_pool_v2", lambda: True)
    monkeypatch.setattr(ton, "using_nominator_pool", lambda: False)
    ton.PoolsUpdateValidatorSet()
    assert updated == [("v2", "EQv2")]

    updated.clear()                        # undeployed v2 pool: nothing to update yet
    accounts["EQv2"] = _Obj(codeHash="v2hash", status="uninit")
    ton.PoolsUpdateValidatorSet()
    assert updated == []


def test_get_pool_v1_skips_v2_pools(ton: MyTonCore, monkeypatch):
    # The v1 election path (get_pool -> is_pool_ready_to_stake) must not probe a v2 pool
    # sitting in the same poolsDir (e.g. v1 fallback during migration) with v1 getters -
    # its GetPoolData call would IndexError on the v2 storage shape and crash ElectionEntry.
    monkeypatch.setattr(ton, "GetPools", lambda: [_Obj(addrB64="EQv2"), _Obj(addrB64="EQv1")])
    monkeypatch.setattr(ton, "GetAccount",
                        lambda addr: _Obj(codeHash="v2hash" if addr == "EQv2" else "v1hash"))
    monkeypatch.setattr(ton, "account_is_pool_v2", lambda acc: acc.codeHash == "v2hash")
    monkeypatch.setattr(ton, "is_account_single_nominator", lambda acc: False)
    monkeypatch.setattr(ton, "using_single_nominator", lambda: False)
    monkeypatch.setattr(ton, "GetStake", lambda acc: 10000)
    monkeypatch.setattr(ton, "get_config_15",
                        lambda: _Obj(validators_elected_for=65536, stake_held_for=32768))
    probed = []
    def fake_last_sent_stake_time(addr):
        probed.append(addr)
        return 0
    monkeypatch.setattr(ton, "get_pool_last_sent_stake_time", fake_last_sent_stake_time)

    pool = ton.get_pool()
    assert pool.addrB64 == "EQv1"
    assert probed == ["EQv1"]    # the v2 pool was never touched with v1 getters


def test_get_pool_data_console_cmd_dispatches_v2(ton: MyTonCore, monkeypatch, capsys):
    # The always-registered inspection command must not run the v1 16-slot parse against
    # a v2 pool (raw IndexError in the console) - it dispatches on the account code hash
    # and prints the PoolDataV2 fields as json.
    import json
    from modules.utilities import UtilitiesModule
    module = UtilitiesModule(ton, ton.local)
    stack = (f"{MC_SLICE} 42 0 1677721 5000000000000 0 7 "
             f"C{{a1b2}} C{{c3d4}} 100 4000000000000 250000000000 0")
    _stub(ton, monkeypatch, {"get_pool_data": stack})
    monkeypatch.setattr(ton, "IsAddr", lambda s: True)
    monkeypatch.setattr(ton, "GetAccount", lambda addr: _Obj(codeHash="v2hash"))
    monkeypatch.setattr(ton, "account_is_pool_v2", lambda acc: True)
    monkeypatch.setattr(ton, "GetPoolData",
                        lambda addr: pytest.fail("v1 parser called for a v2 pool"))
    module.get_pool_data("EQpool")
    printed = json.loads(capsys.readouterr().out)
    assert printed["pool_id"] == 42
    assert printed["round_index"] == 7
    assert printed["pending_deposits"] == 250000000000


def test_run_elections_runs_pool_cron_for_any_pool_family(ton: MyTonCore, monkeypatch):
    # The merged maintenance cron serves every pool family; run_elections must trigger
    # it when only v2 mode is on (using_pool covers v2) just like for v1/migration.
    from modules.validator import ValidatorModule
    calls = []
    monkeypatch.setattr(ton, "using_nominator_pool_v2", lambda: True)
    monkeypatch.setattr(ton, "using_nominator_pool", lambda: False)
    monkeypatch.setattr(ton, "using_single_nominator", lambda: False)
    monkeypatch.setattr(ton, "using_liquid_staking", lambda: False)
    monkeypatch.setattr(ton, "using_validator", lambda: False)
    monkeypatch.setattr(ton, "PoolsUpdateValidatorSet", lambda: calls.append("pools"))
    monkeypatch.setattr(ton, "RecoverStake", lambda: None)
    ValidatorModule(ton, ton.local).run_elections()
    assert calls == ["pools"]


def test_import_pool_downloads_v1_scripts_only_for_v1_modes(ton: MyTonCore, monkeypatch, tmp_path):
    # v2 pools run on vendored package resources; importing one must not force a git clone
    # of the v1 nominator-pool repo (it can hang/crash on firewalled hosts). The clone is
    # only for the v1-family modes that actually consume those fift scripts.
    from modules.pool import PoolModule
    module = PoolModule(ton, ton.local)
    monkeypatch.setattr(ton, "poolsDir", str(tmp_path) + "/")
    monkeypatch.setattr(ton, "using_nominator_pool", lambda: False)
    monkeypatch.setattr(ton, "using_single_nominator", lambda: False)
    downloads = []
    monkeypatch.setattr(module, "check_download_pool_contract_scripts",
                        lambda: downloads.append(1))

    module.do_import_pool("imported_v2", MC_ADDR)
    assert downloads == []                                     # no clone for a v2-only setup
    assert (tmp_path / "imported_v2.addr").is_file()           # .addr still written

    monkeypatch.setattr(ton, "using_nominator_pool", lambda: True)
    module.do_import_pool("imported_v1", MC_ADDR)
    assert downloads == [1]                                    # v1 mode still gets the scripts


def _usage(proxy, rotation_time, rotation_count, held_for=9000):
    return _Obj(proxy_addr=proxy, held_for=held_for, ton_used=10**14,
                rotation_time=rotation_time, rotation_count=rotation_count)


def test_pool_v2_update_vset_gate_and_recovery(ton: MyTonCore, monkeypatch):
    vset_calls, recover_calls, elector_queries = [], [], []
    monkeypatch.setattr(ton, "pool_send_update_vset_v2", lambda p, w: vset_calls.append(p))
    monkeypatch.setattr(
        ton,
        "pool_send_recover_stake_v2",
        lambda p, w: recover_calls.append((p, w)),
    )
    monkeypatch.setattr(ton, "GetFullElectorAddr", lambda: "Ef-elector")
    returned = {"Ef-even": 1234.5, "Ef-odd": 1234.5}
    def get_returned_stake(elector, addr):
        elector_queries.append(addr)
        return returned[addr]
    monkeypatch.setattr(ton, "get_returned_stake", get_returned_stake)
    info = _Obj(even_proxy="Ef-even", odd_proxy="Ef-odd",
                cur_round_usage=None, prev_round_usage=None)
    monkeypatch.setattr(ton, "get_validator_info_v2", lambda p, v: info)
    pool, wallet = _Obj(addrB64="EQpool"), _Obj(addrB64="Ef-validator")
    now = int(time.time())

    # no stake records of ours -> fully quiet, the elector is not even queried
    ton.pool_update_validator_set_v2(pool, wallet)
    assert vset_calls == [] and recover_calls == [] and elector_queries == []

    # wind-down with a rotation pending: the getter PROJECTS the rotation, stamping
    # rotationTime with the query moment (i.e. "now"). A refused recovery would not
    # persist the rotation, so the cron pushes UpdateVset instead and defers recovery.
    info.prev_round_usage = _usage("Ef-odd", now - 5, 2)
    ton.pool_update_validator_set_v2(pool, wallet)
    assert vset_calls == ["EQpool"] and recover_calls == []

    # stamp is stale (materialized long ago) but the record has seen only one
    # materialized vset change -> the pool would refuse with RoundTooEarly, don't send
    info.prev_round_usage = _usage("Ef-odd", now - 10_000, 1)
    ton.pool_update_validator_set_v2(pool, wallet)
    assert vset_calls == ["EQpool"] and recover_calls == []

    # rotationCount == 2 and heldFor + 60 not yet elapsed since the second rotation ->
    # RecoveryTimeTooEarly, don't send (the v1 analog: validatorSetChangeTime gate)
    info.prev_round_usage = _usage("Ef-odd", now - 5_000, 2, held_for=9_000)
    ton.pool_update_validator_set_v2(pool, wallet)
    assert recover_calls == []

    # rotationCount == 2 and the hold period has passed -> recovery proceeds
    info.prev_round_usage = _usage("Ef-odd", now - 10_000, 2, held_for=9_000)
    ton.pool_update_validator_set_v2(pool, wallet)
    assert recover_calls == [("EQpool", wallet)]

    # rotationCount > 2 -> no timestamp requirement, recovery proceeds
    info.prev_round_usage = _usage("Ef-odd", now - 100, 3)
    ton.pool_update_validator_set_v2(pool, wallet)
    assert recover_calls == [("EQpool", wallet)] * 2

    # both rounds hold records with returned stake: the pool acts on the prev-round
    # record first, so query/recover only that one -> one recovery message per tick
    elector_queries.clear()
    info.cur_round_usage = _usage("Ef-even", now - 100, 3)
    ton.pool_update_validator_set_v2(pool, wallet)
    assert recover_calls == [("EQpool", wallet)] * 3
    assert elector_queries == ["Ef-odd"]
