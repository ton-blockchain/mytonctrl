from __future__ import annotations

import pytest

from mypyconsole.mypyconsole import UsageError
from mytoncore.mytoncore import MyTonCore
from mytoninstaller.mytoninstaller import InstallerCtrl
from mypyconsole.command_parser import CommandParser
from tests.conftest import TestMyPyConsole


ADNL = "AB" * 32
ADNL_2 = "CD" * 32
ADNL_3 = "zs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs4="
ADDR = "EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N"
RAW_ADDR = "-1:" + "55" * 32
BUILTINS = {"help", "clear", "history", "exit"}
COMMANDS = {
    "about", "activate_pool", "activate_single_pool", "add_collator", "add_controller",
    "add_custom_overlay", "add_register_collator", "add_validator_to_collation_wl", "aw",
    "benchmark", "bl", "calculate_annual_controller_percentage", "check_ef", "cl",
    "controller_update_validator_set", "controllers_list", "create_backup", "create_controllers",
    "db", "delete_collator", "delete_custom_overlay", "delete_pool", "delete_register_collator",
    "delete_validator_from_collation_wl", "deposit_to_controller", "deposit_to_pool",
    "disable_alert", "disable_collation_wl", "disable_mode", "download_archive_blocks", "dw",
    "el", "enable_alert", "enable_mode", "ew", "get", "get_controller_data", "get_pool_data",
    "import_pool", "installer", "iw", "list_alerts", "list_custom_overlays", "mg", "mgtp", "nb",
    "new_pool", "new_single_pool", "nw", "od", "ol", "pools_list", "print_collation_config",
    "print_collation_whitelist", "print_collators", "print_local_collators",
    "reload_global_config", "remove_btc_teleport", "reset_collators", "restore_backup", "set",
    "set_collation_config", "set_quic_port", "set_self_collate", "setup_alert_bot",
    "setup_collator", "status", "status_modes", "status_settings",
    "stop_and_withdraw_controller", "stop_collator", "stop_controller", "swv", "test_alert",
    "test_calculate_loan_amount", "update", "update_collation_config", "update_collators_list",
    "update_controllers", "update_validator_set", "upgrade", "vah", "vas", "vc", "ve", "vl", "vo",
    "withdraw_from_controller", "withdraw_from_pool", "withdraw_from_single_pool", "wl",
}
INSTALLER_COMMANDS = {
    "status", "set_node_argument", "enable", "plsc", "clcf", "print_ls_proxy_config", "drvcf",
    "ton_storage_list",
}

FORMS = [
    ("update", {"target": None, "target_branch": None, "branch": None}),
    ("update dev", {"target": "dev", "target_branch": None, "branch": None}),
    ("update yungwine dev", {"target": "yungwine", "target_branch": "dev"}),
    ("update https://github.com/x/y dev", {"target": "https://github.com/x/y", "target_branch": "dev"}),
    ("update https://github.com/ton-blockchain/mytonctrl/tree/dev",
     {"target": "https://github.com/ton-blockchain/mytonctrl/tree/dev", "target_branch": None}),
    ("update --branch dev", {"target": None, "branch": "dev"}),
    ("upgrade", {"target": None, "target_branch": None, "branch": None, "url": None}),
    ("upgrade testnet", {"target": "testnet"}),
    ("upgrade https://github.com/x/ton testnet", {"target": "https://github.com/x/ton", "target_branch": "testnet"}),
    ("upgrade --url https://a/b#c --branch d", {"target": None, "url": "https://a/b#c", "branch": "d"}),
    ("upgrade --url https://github.com/someone/ton#feature",
     {"url": "https://github.com/someone/ton#feature", "branch": None}),
    ("reload_global_config", {"url": None}),
    ("reload_global_config https://example.com/global.config.json",
     {"url": "https://example.com/global.config.json"}),
    ("installer", {"forwarded": []}),
    ("installer status", {"forwarded": ["status"]}),
    ("installer enable THA", {"forwarded": ["enable", "THA"]}),
    ("installer set_node_argument --archive-ttl 86400 -d",
     {"forwarded": ["set_node_argument", "--archive-ttl", "86400", "-d"]}),
    ("status", {"mode": None}),
    ("status fast", {"mode": "fast"}),
    ("status_modes", {}),
    ("status_settings", {}),
    ("enable_mode validator", {"mode_name": "validator"}),
    ("enable_mode liquid-staking", {"mode_name": "liquid-staking"}),
    ("disable_mode liteserver", {"mode_name": "liteserver"}),
    ("about collator", {"mode_name": "collator"}),
    ("get stake", {"name": "stake"}),
    ("set stake 1000", {"name": "stake", "value": "1000", "force": False}),
    ("set stake 1000 --force", {"name": "stake", "value": "1000", "force": True}),
    ("create_backup", {"dest": None, "user": None, "from_host": False}),
    ("create_backup /d", {"dest": "/d", "user": None, "from_host": False}),
    ("create_backup /d -u user", {"dest": "/d", "user": "user", "from_host": False}),
    ("create_backup /d -u user --from-host", {"dest": "/d", "user": "user", "from_host": True}),
    ("create_backup -u user", {"dest": None, "user": "user"}),
    ("create_backup --from-host", {"dest": None, "from_host": True}),
    ("restore_backup f.tar.gz", {"filename": "f.tar.gz", "yes": False, "skip_create_backup": False, "user": None}),
    ("restore_backup f.tar.gz -y", {"filename": "f.tar.gz", "yes": True, "skip_create_backup": False}),
    ("restore_backup f.tar.gz -y --skip-create-backup -u user",
     {"filename": "f.tar.gz", "yes": True, "skip_create_backup": True, "user": "user"}),
    ("add_custom_overlay my_overlay /tmp/overlay.json", {"name": "my_overlay", "path_to_config": "/tmp/overlay.json"}),
    ("list_custom_overlays", {}),
    ("delete_custom_overlay my_overlay", {"name": "my_overlay"}),
    ("remove_btc_teleport", {}),
    ("vo h1", {"offer_hashes": ["h1"]}),
    ("vo h1 h2", {"offer_hashes": ["h1", "h2"]}),
    ("ve", {}),
    ("vc 1700000000 abcd", {"election_id": "1700000000", "complaint_hash": "abcd"}),
    ("check_ef", {}),
    (f"add_collator {ADNL}", {"adnl": ADNL, "self_collate": None}),
    (f"add_collator {ADNL} --self-collate true", {"adnl": ADNL, "self_collate": True}),
    (f"add_collator {ADNL} --self-collate false", {"adnl": ADNL, "self_collate": False}),
    (f"delete_collator {ADNL}", {"adnl": ADNL}),
    (f"add_register_collator {ADNL}", {"adnl": ADNL}),
    (f"delete_register_collator {ADNL}", {"adnl": ADNL}),
    ("set_self_collate true", {"value": True}),
    ("set_self_collate false", {"value": False}),
    ("print_collators", {"json_": False}),
    ("print_collators --json", {"json_": True}),
    ("reset_collators", {}),
    ("update_collators_list", {"force": False}),
    ("update_collators_list --force", {"force": True}),
    ("nw", {"workchain_id": None, "wallet_name": None, "version": "v1", "subwallet_id": None}),
    ("nw 0 w", {"workchain_id": 0, "wallet_name": "w", "version": "v1", "subwallet_id": None}),
    ("nw -1 w v3", {"workchain_id": -1, "wallet_name": "w", "version": "v3", "subwallet_id": None}),
    ("nw 0 w v3 1001", {"workchain_id": 0, "wallet_name": "w", "version": "v3", "subwallet_id": 1001}),
    ("aw w", {"wallet_name": "w", "all_": False}),
    ("aw --all", {"wallet_name": None, "all_": True}),
    ("wl", {}),
    (f"iw {ADDR} c2VjcmV0", {"wallet_addr": ADDR, "wallet_secret_key": "c2VjcmV0"}),
    (f"swv {ADDR} v3", {"wallet_addr": ADDR, "wallet_version": "v3"}),
    ("ew w", {"wallet_name": "w"}),
    ("dw w", {"wallet_name": "w"}),
    (f"mg w {ADDR} 10", {"wallet_name": "w", "destination": ADDR, "amount": 10.0}),
    (f"mg w {ADDR} 1.5", {"amount": 1.5}),
    (f"mg w {ADDR} all", {"amount": "all"}),
    ("mg w my_bookmark alld", {"destination": "my_bookmark", "amount": "alld"}),
    (f"mg w {RAW_ADDR} 1.5", {"destination": RAW_ADDR, "amount": 1.5}),
    (f"mg w {ADDR} 10 -n", {"no_bounce": True, "force_bounce": False}),
    (f"mg w {ADDR} 10 -b", {"no_bounce": False, "force_bounce": True}),
    (f"mg w {ADDR} 10 -C hello -t 60 -m 3",
     {"amount": 10.0, "comment": "hello", "timeout": 60, "mode": 3}),
    (f"mg w {ADDR} 10 -B body.boc -I init.boc", {"body": "body.boc", "with_init": "init.boc"}),
    (f"mgtp w {ADDR} 10", {"wallet_name": "w", "destination": ADDR, "amount": 10.0}),
    (f"vas {ADDR}", {"account_addr": ADDR}),
    (f"vas {RAW_ADDR}", {"account_addr": RAW_ADDR}),
    (f"vah {ADDR} 10", {"account_addr": ADDR, "limit": 10}),
    (f"nb my_bookmark {ADDR}", {"bookmark_name": "my_bookmark", "account_addr": ADDR}),
    ("bl", {}),
    ("db my_bookmark", {"bookmark_name": "my_bookmark"}),
    ("ol", {"words": [], "json_": False}),
    ("ol --json", {"words": [], "json_": True}),
    ("ol hash", {"words": ["hash"], "json_": False}),
    ("ol --json hash", {"words": ["hash"], "json_": True}),
    ("ol hash --json", {"words": ["hash"], "json_": True}),
    ("od abcd", {"offer_hash": "abcd"}),
    ("el", {"words": [], "json_": False}),
    ("el past", {"words": ["past"], "json_": False}),
    ("el --json", {"words": [], "json_": True}),
    ("el past adnl pubkey wallet", {"words": ["past", "adnl", "pubkey", "wallet"], "json_": False}),
    ("el past adnl pubkey wallet --json", {"words": ["past", "adnl", "pubkey", "wallet"], "json_": True}),
    ("el --json past adnl", {"words": ["past", "adnl"], "json_": True}),
    ("vl", {"words": [], "json_": False}),
    ("vl fast", {"words": ["fast"]}),
    ("vl offline", {"words": ["offline"]}),
    ("vl past fast offline adnl pubkey wallet",
     {"words": ["past", "fast", "offline", "adnl", "pubkey", "wallet"], "json_": False}),
    ("vl past fast offline adnl pubkey wallet --json",
     {"words": ["past", "fast", "offline", "adnl", "pubkey", "wallet"], "json_": True}),
    ("vl --json past", {"words": ["past"], "json_": True}),
    ("cl", {"words": [], "json_": False}),
    ("cl past adnl", {"words": ["past", "adnl"], "json_": False}),
    ("cl --json", {"words": [], "json_": True}),
    ("cl past adnl --json", {"words": ["past", "adnl"], "json_": True}),
    ("get_pool_data my_pool", {"pool_name": "my_pool"}),
    (f"get_pool_data {ADDR}", {"pool_name": ADDR}),
    ("pools_list", {}),
    ("delete_pool my_pool", {"pool_name": "my_pool"}),
    (f"import_pool my_pool {ADDR}", {"pool_name": "my_pool", "pool_addr": ADDR}),
    ("new_pool my_pool 5.5 10 10000 1000",
     {"pool_name": "my_pool", "validator_reward_share_percent": 5.5, "max_nominators_count": 10,
      "min_validator_stake": 10000, "min_nominator_stake": 1000}),
    ("activate_pool my_pool", {"pool_name": "my_pool"}),
    (f"update_validator_set {ADDR}", {"pool_addr": ADDR}),
    (f"withdraw_from_pool {ADDR} 10", {"pool_addr": ADDR, "amount": 10.0}),
    (f"deposit_to_pool {ADDR} 10.5", {"pool_addr": ADDR, "amount": 10.5}),
    (f"new_single_pool my_pool {ADDR}", {"pool_name": "my_pool", "owner_address": ADDR}),
    ("activate_single_pool my_pool", {"pool_name": "my_pool"}),
    (f"withdraw_from_single_pool {ADDR} 10", {"pool_addr": ADDR, "amount": 10.0}),
    ("create_controllers", {}),
    ("update_controllers", {}),
    ("controllers_list", {}),
    (f"get_controller_data {ADDR}", {"controller_addr": ADDR}),
    (f"deposit_to_controller {ADDR} 100", {"controller_addr": ADDR, "amount": 100.0}),
    (f"withdraw_from_controller {ADDR}", {"controller_addr": ADDR, "amount": None}),
    (f"withdraw_from_controller {ADDR} 50", {"controller_addr": ADDR, "amount": "50"}),
    ("calculate_annual_controller_percentage", {"percent_per_round": None}),
    ("calculate_annual_controller_percentage 0.5", {"percent_per_round": 0.5}),
    (f"controller_update_validator_set {ADDR}", {"controller_addr": ADDR}),
    (f"stop_controller {ADDR}", {"controller_addr": ADDR}),
    (f"stop_and_withdraw_controller {ADDR}", {"controller_addr": ADDR, "amount": None}),
    (f"stop_and_withdraw_controller {ADDR} 50", {"controller_addr": ADDR, "amount": "50"}),
    (f"add_controller {ADDR}", {"controller_addr": ADDR}),
    ("test_calculate_loan_amount", {}),
    ("set_collation_config /tmp/config.json", {"location": "/tmp/config.json"}),
    ("set_collation_config https://example.com/config.json", {"location": "https://example.com/config.json"}),
    ("update_collation_config", {}),
    ("print_collation_config", {}),
    ("setup_collator", {"adnl": None}),
    (f"setup_collator --adnl {ADNL}", {"adnl": ADNL}),
    ("print_local_collators", {}),
    (f"add_validator_to_collation_wl {ADNL}", {"adnls": [ADNL]}),
    (f"add_validator_to_collation_wl {ADNL} {ADNL_2} {ADNL_3}", {"adnls": [ADNL, ADNL_2, ADNL_3]}),
    (f"delete_validator_from_collation_wl {ADNL}", {"adnls": [ADNL]}),
    (f"delete_validator_from_collation_wl {ADNL} {ADNL_2} {ADNL_3}", {"adnls": [ADNL, ADNL_2, ADNL_3]}),
    ("disable_collation_wl", {}),
    ("print_collation_whitelist", {}),
    ("stop_collator", {"adnl_id": None}),
    (f"stop_collator {ADNL}", {"adnl_id": ADNL}),
    ("enable_alert low_efficiency", {"alert_name": "low_efficiency"}),
    ("disable_alert low_efficiency", {"alert_name": "low_efficiency"}),
    ("list_alerts", {}),
    ("test_alert", {}),
    ("setup_alert_bot 123:abc -1001234567890", {"bot_token": "123:abc", "chat_id": "-1001234567890"}),
    ("download_archive_blocks /data 100",
     {"from_block_seqno": 100, "to_block_seqno": None, "port": None, "only_master": False}),
    ("download_archive_blocks /data 100 200 --only-master",
     {"from_block_seqno": 100, "to_block_seqno": 200, "only_master": True}),
    ("download_archive_blocks --port 5555 /data 100", {"port": 5555, "from_block_seqno": 100}),
    ("benchmark", {"tmp_dir": None, "forwarded": []}),
    ("benchmark --nodes 4", {"tmp_dir": None, "forwarded": ["--nodes", "4"]}),
    ("benchmark --tmp-dir /x --nodes 4 --tps 1000", {"tmp_dir": "/x", "forwarded": ["--nodes", "4", "--tps", "1000"]}),
    ("set_quic_port 1234", {"port": 1234, "category": 2}),
    ("set_quic_port 1234 3", {"port": 1234, "category": 3}),
]

INSTALLER_FORMS = [
    ("status", {}),
    ("set_node_argument --archive-ttl 86400", {"forwarded": ["--archive-ttl", "86400"], "delete": False}),
    ("set_node_argument --archive-ttl -d", {"forwarded": ["--archive-ttl"], "delete": True}),
    ("set_node_argument --archive-ttl 86400 -d", {"forwarded": ["--archive-ttl", "86400"], "delete": True}),
    ("set_node_argument -M", {"forwarded": ["-M"], "delete": False}),
    ("set_node_argument --add-shard 0:2000000000000000 0:a000000000000000",
     {"forwarded": ["--add-shard", "0:2000000000000000", "0:a000000000000000"]}),
    ("enable DS", {"mode_name": "DS"}),
    ("enable THA", {"mode_name": "THA"}),
    ("enable LSP", {"mode_name": "LSP"}),
    ("enable TS", {"mode_name": "TS"}),
    ("plsc", {}),
    ("clcf", {"path": None}),
    ("clcf /tmp/local.config.json", {"path": "/tmp/local.config.json"}),
    ("print_ls_proxy_config", {}),
    ("drvcf", {}),
    ("ton_storage_list", {"api_port": None}),
    ("ton_storage_list 5555", {"api_port": 5555}),
]

CHANGED_FORMS = [
    ("download_archive_blocks 5555 /data 100", "argument from_block_seqno: invalid int value: '/data'"),
    ("update --url https://github.com/x/mytonctrl", "unrecognized arguments: --url"),
    ("update a b c", "unrecognized arguments: c"),
    ("nw 0 w v4", "argument version: expected a wallet version v1, v2 or v3"),
    (f"swv {ADDR} hv1", "argument wallet_version: expected a wallet version v1, v2 or v3"),
    (f"mg w {ADDR} 10 -x", "unrecognized arguments: -x"),
    ("vl past --json fast", "unrecognized arguments: fast"),
    ("el past --json adnl", "unrecognized arguments: adnl"),
    ("status slow", "argument mode: invalid choice: 'slow'"),
]


@pytest.fixture(autouse=True)
def _enable_every_mode(monkeypatch):
    for name in ("using_validator", "using_liquid_staking", "using_collator", "using_alert_bot"):
        monkeypatch.setattr(MyTonCore, name, lambda self: True)


@pytest.fixture()
def parsers(cli) -> dict[str, CommandParser]:
    return {item.cmd: item.parser for item in cli.menu_items if item.cmd not in BUILTINS}


@pytest.fixture()
def installer_parsers(local) -> dict[str, CommandParser]:
    console = TestMyPyConsole(local)
    installer = InstallerCtrl(local, mconfig_path="", paths=None, ls_data=None, get_init_block=None, console=console)
    installer._add_console_commands(console)
    return {item.cmd: item.parser for item in console.menu_items if item.cmd not in BUILTINS}


def _parse(parsers: dict[str, CommandParser], line: str) -> dict:
    name, *tokens = line.split()
    parser = parsers[name]
    if parser.forward_unknown:
        namespace, forwarded = parser.parse_known_args(tokens)
        values = {**vars(namespace), "forwarded": forwarded}
    else:
        values = vars(parser.parse_args(tokens))
    return {key: list(value) if isinstance(value, tuple) else value for key, value in values.items()}


def _assert_parses(parsers: dict[str, CommandParser], line: str, expected: dict) -> None:
    values = _parse(parsers, line)
    assert set(expected) <= set(values), sorted(values)
    assert {key: values[key] for key in expected} == expected


@pytest.mark.parametrize("line, expected", FORMS, ids=[line for line, _ in FORMS])
def test_documented_form_parses(parsers, line, expected):
    _assert_parses(parsers, line, expected)


@pytest.mark.parametrize("line, expected", INSTALLER_FORMS, ids=[line for line, _ in INSTALLER_FORMS])
def test_documented_installer_form_parses(installer_parsers, line, expected):
    _assert_parses(installer_parsers, line, expected)


@pytest.mark.parametrize("line, error", CHANGED_FORMS, ids=[line for line, _ in CHANGED_FORMS])
def test_deliberately_changed_form_is_a_usage_error(parsers, line, error):
    with pytest.raises(UsageError) as info:
        _parse(parsers, line)
    assert error in str(info.value)


def test_every_command_is_registered_and_listed_by_help(cli, parsers):
    assert set(parsers) == COMMANDS
    output = cli.execute("help", no_color=True)
    listed = {line.split()[0] for line in output.splitlines() if line.strip()}
    assert listed == COMMANDS | BUILTINS


def test_every_command_has_a_documented_form(installer_parsers):
    assert {line.split()[0] for line, _ in FORMS} == COMMANDS
    assert {line.split()[0] for line, _ in INSTALLER_FORMS} == set(installer_parsers) == INSTALLER_COMMANDS
