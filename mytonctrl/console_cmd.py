import typing

from mypyconsole.mypyconsole import MyPyConsole
from mypylib import MyPyClass, color_print

USAGES = {
    "update": "[repo_url|repo_owner] [branch]",
    "upgrade": "[repo_url|repo_owner] [branch]",
    "installer": "[command]",
    "status": "[fast]",
    "enable_mode": "<mode_name>",
    "disable_mode": "<mode_name>",
    "about": "<mode_name>",
    "get": "<setting_name>",
    "set": "<setting_name> <value> [--force]",
    "create_backup": "[filename] [-u <user>]",
    "restore_backup": " <filename> [-y] [--skip-create-backup] [-u <user>]",
    "add_custom_overlay": "<name> <path_to_config>",
    "delete_custom_overlay": "<name>",
    "remove_btc_teleport": "[--force]",
    "vo": "<offer_hash>[ <offer_hash> ...]",
    "vc": "<election_id> <complaint_hash>",
    "add_collator": "<adnl> <shard> [--self-collate <true/false>] [--select-mode <random|ordered|round_robin>]",
    "delete_collator": "[shard] <adnl>",
    "print_collators": "[--json]",
    "nw": "[<workchain_id> <wallet_name> [<version>] [<subwallet_id>]]",
    "aw": "<wallet_name>|--all",
    "iw": "<wallet_addr> <wallet_secret_key>",
    "swv": "<wallet_addr> <wallet_version>",
    "ew": "<wallet_name>",
    "dw": "<wallet_name>",
    "wl": "",
    "mg": "<wallet_name> <account_addr|bookmark_name> <amount> [flags...]",
    "mgtp": "<wallet_name> <account_addr|bookmark_name> <amount>",
    "vas": "<account_addr>",
    "vah": "<account_addr> <limit>",
    "nb": "<bookmark_name> <account_addr>",
    "bl": "",
    "db": "<bookmark_name>",
    "ol": "[--json] [hash]",
    "od": "<offer_hash>",
    "el": "[past] [--json] [adnl] [pubkey] [wallet]",
    "vl": "[past] [fast] [offline] [--json] [adnl] [pubkey] [wallet]",
    "cl": "[past] [--json] [adnl]",
    "get_pool_data": "<pool_name|pool_addr>",
    "delete_pool": "<pool_name>",
    "import_pool": "<pool_name> <pool_addr>",
    "new_pool": "<pool_name> <validator_reward_share_percent> <max_nominators_count> <min_validator_stake> <min_nominator_stake>",
    "activate_pool": "<pool_name>",
    "update_validator_set": "<pool_addr>",
    "withdraw_from_pool": "<pool_addr> <amount>",
    "deposit_to_pool": "<pool_addr> <amount>",
    "new_single_pool": "<pool_name> <owner_address>",
    "activate_single_pool": "<pool_name>",
    "withdraw_from_single_pool": "<pool_addr> <amount>",
    "get_controller_data": "<controller_addr>",
    "deposit_to_controller": "<controller_addr> <amount>",
    "withdraw_from_controller": "<controller_addr> [amount]",
    "calculate_annual_controller_percentage": "[percent_per_round]",
    "controller_update_validator_set": "<controller_addr>",
    "stop_controller": "<controller_addr>",
    "stop_and_withdraw_controller": "<controller_addr> [amount]",
    "add_controller": "<controller_addr>",
    "set_collation_config": "<path/url>",
    "setup_collator": "[--force] [--adnl <ADNL address>] <shard1> [shard2] ...",
    "add_validator_to_collation_wl": "<adnl> [adnl2] [adnl3] ...",
    "delete_validator_from_collation_wl": "<adnl> [adnl2] [adnl3] ...",
    "stop_collator": "[<adnl_id> <shard>]",
    "enable_alert": "<alert_name>",
    "disable_alert": "<alert_name>",
    "setup_alert_bot": "<bot_token> <chat_id>",
    "download_archive_blocks": "[ton_storage_api_port] <download_path> <from_block_seqno> [to_block_seqno] [--only-master]",
    "benchmark": "[benchmark args ...]",
}


def check_usage_no_args(name: str, args: list) -> bool:
    return check_usage(name, args, lambda x: len(x) == 0)


def check_usage_one_arg(name: str, args: list) -> bool:
    return check_usage(name, args, lambda x: len(x) == 1)


def check_usage_two_args(name: str, args: list) -> bool:
    return check_usage(name, args, lambda x: len(x) == 2)


def check_usage_args_len(name: str, args: list, len_: int) -> bool:
    return check_usage(name, args, lambda x: len(x) == len_)


def check_usage_args_lens(name: str, args: list, lens: list) -> bool:
    return check_usage(name, args, lambda x: len(x) in lens)


def check_usage_args_min_len(name: str, args: list, min_len: int) -> bool:
    return check_usage(name, args, lambda x: len(x) >= min_len)


def check_usage_args_min_max_len(name: str, args: list, min_len: int, max_len: int) -> bool:
    return check_usage(name, args, lambda x: min_len <= len(x) <= max_len)


def check_usage(name: str, args: list, check_fun: typing.Callable) -> bool:
    usage = get_usage(name)
    if check_fun(args):
        return True
    else:
        color_print(f"{{red}}Bad args. Usage:{{endc}} {name} {usage}")
        return False


def get_usage(name: str) -> str:
    return USAGES.get(name, '')


def add_command(local: MyPyClass, console: MyPyConsole, name: str, function: typing.Callable):
    desc = local.translate(f"{name}_cmd")
    usage = get_usage(name)
    # if usage:
    #     desc += f"\nUsage: {usage}"
    console.add_item(name, function, desc, usage)
