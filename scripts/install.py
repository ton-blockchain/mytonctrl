import datetime
import os
import subprocess
import time
import inquirer
import requests


def get_archive_ttl_message(answers: dict):
    global default_archive_ttl
    archive_blocks = answers.get('archive-blocks')
    if not archive_blocks and answers['archive-blocks'] != 0:
        return 'Send the number of seconds to keep the block data in the node database. Default is 2592000 (30 days)'
    block_from = archive_blocks.split()[0]
    # or sent -1 to store downloaded blocks always
    if block_from.isdigit():
        seqno = int(block_from)
        url = f'https://toncenter.com/api/v2/getBlockHeader?workchain=-1&shard={-2**63}&seqno={seqno}'
        if answers['network'] == 'Testnet':
            url = url.replace('toncenter.com', 'testnet.toncenter.com')
        data = requests.get(url).json()
        utime = int(data['result']['gen_utime'])
    else:
        utime = int(datetime.datetime.strptime(block_from, '%Y-%m-%d').timestamp())
    default_archive_ttl = int(time.time() - (utime - datetime.timedelta(days=30).total_seconds()))
    answers['archive-ttl-default'] = default_archive_ttl
    return f'Send the number of seconds to keep the block data in the node database. Default is {default_archive_ttl} to keep archive blocks from {datetime.datetime.fromtimestamp(utime - datetime.timedelta(days=30).total_seconds())}\nOr send -1 to keep downloaded blocks always (recommended).'


def is_valid_date_format(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_archive_blocks(_, value):
    if not value:
        return True
    parts = value.split()
    if len(parts) > 2:
        return False

    for part in parts:
        if part.isdigit() and int(part) < 0:
            return False
        elif not is_valid_date_format(part):
            return False
    return True


def run_cli():
    questions = [
        inquirer.List(
            "mode",
            message="Select installation mode (More on https://docs.ton.org/participate/nodes/node-types)",
            choices=["validator", "liteserver"],
        ),
        inquirer.List(
            "network",
            message="Select network",
            choices=["Mainnet", "Testnet", "Other"],
        ),
        inquirer.Text(
            "config",
            message="Provide network config uri",
            ignore=lambda x: x["network"] != "Other",  # do not ask this question if network is not 'Other'
            validate=lambda _, x: x.startswith("http"),
        ),
        inquirer.List(
            "validator-mode",
            message="Select mode for validator usage. You can skip and set up this later",
            ignore=lambda x: x["mode"] != "validator",  # do not ask this question if mode is not validator
            choices=["Validator wallet", "Nominator pool", "Single pool", "Liquid Staking", "Skip"],
        ),
        inquirer.Text(
            "archive-blocks",
            message="Do you want to download archive blocks via TON Storage? Press Enter to skip.\n"
                    "If yes, provide block seqno or date to start from and (optionally) block seqno or date to end with (send 0 to download all blocks and setup full archive node).\n"
                    "Examples: `30850000`, `10000000 10200000`, `2025-01-01`, `2025-01-01 2025-01-30`",
            ignore=lambda x: x["mode"] == "validator",
            validate=validate_archive_blocks,
        ),
        inquirer.Text(
            "archive-ttl",
            message=get_archive_ttl_message,
            ignore=lambda x: x["mode"] != "liteserver",  # do not ask this question if mode is not liteserver
            validate=lambda _, x: not x or x.isdigit(),  # must be empty string or a number
            # default=get_default_archive_ttl
        ),
        inquirer.Confirm(
            "dump",
            message="Do you want to download blockchain's dump? "
                    "This reduces synchronization time but requires to download a large file",
            ignore=lambda x: x["archive-blocks"],
        ),
        inquirer.Text(
            "add-shard",
            message="Set shards node will sync. Skip to sync all shards. "
                    "Format: <workchain>:<shard>. Divide multiple shards with space. "
                    "Example: `0:2000000000000000 0:6000000000000000`",
            validate=lambda _, x: not x or all([":" in i for i in x.split()])
        )
    ]

    answers = inquirer.prompt(questions)

    return answers


def parse_args(answers: dict):
    mode = answers["mode"]
    network = answers["network"].lower()
    config = answers["config"]
    archive_ttl = answers["archive-ttl"] or answers.get("archive-ttl-default")
    add_shard = answers["add-shard"]
    validator_mode = answers["validator-mode"]
    archive_blocks = answers["archive-blocks"]
    dump = answers["dump"]

    res = f' -n {network}'

    if network not in ('mainnet', 'testnet'):
        res += f' -c {config}'

    if archive_ttl:
        os.putenv('ARCHIVE_TTL', archive_ttl)  # set env variable
    if add_shard:
        os.putenv('ADD_SHARD', add_shard)
    if archive_blocks:
        os.putenv('ARCHIVE_BLOCKS', archive_blocks)

    if validator_mode and validator_mode not in ('Skip', 'Validator wallet'):
        if validator_mode == 'Nominator pool':
            validator_mode = 'nominator-pool'
        elif validator_mode == 'Single pool':
            validator_mode = 'single-nominator'
        elif validator_mode == 'Liquid Staking':
            validator_mode = 'liquid-staking'
        res += f' -m {validator_mode}'
    else:
        res += f' -m {mode}'

    if dump:
        res += ' -d'

    return res


def main():
    answers = run_cli()
    command = parse_args(answers)
    # subprocess.run('bash scripts/install.sh ' + command, shell=True)
    print('bash install.sh ' + command)
    subprocess.run(['bash', 'install.sh'] + command.split())


if __name__ == '__main__':
    main()
