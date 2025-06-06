import datetime
import os
import subprocess
import time
import questionary
import requests


def get_archive_ttl_message(answers: dict):
    archive_blocks = answers.get('archive-blocks')
    if not archive_blocks and answers['archive-blocks'] != 0:
        return 'Send the number of seconds to keep the blocks data in the node database. Press Enter to use default: 2592000 (30 days)'
    block_from = archive_blocks.split()[0]
    # or sent -1 to store downloaded blocks always
    if block_from.isdigit():
        seqno = int(block_from)
        url = f'https://toncenter.com/api/v2/getBlockHeader?workchain=-1&shard={-2**63}&seqno={seqno}'
        if answers['network'] == 'Testnet':
            url = url.replace('toncenter.com', 'testnet.toncenter.com')
        data = requests.get(url).json()
        if not data['ok']:
            raise Exception(f'Failed to get block: {data}')
        utime = int(data['result']['gen_utime'])
    else:
        utime = int(datetime.datetime.strptime(block_from, '%Y-%m-%d').timestamp())
    default_archive_ttl = int(time.time() - (utime - datetime.timedelta(days=30).total_seconds()))
    answers['archive-ttl-default'] = '-1'
    return f'Send the number of seconds to keep blocks in the node database. Press Enter to keep downloaded blocks always (recommended).\nFor your reference you can use TTL `{default_archive_ttl}` to keep blocks from provided block for 30 days (since {datetime.datetime.fromtimestamp(utime - datetime.timedelta(days=30).total_seconds())}).\nNote: in case you want to keep blocks garbage collection the node will sync 8-10 times slower.'


def is_valid_date_format(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_archive_blocks(value):
    if not value:
        return True
    parts = value.split()
    if len(parts) > 2:
        return "Too many parameters provided"

    for part in parts:
        if part.isdigit() and int(part) < 0:
            return "Block number cannot be negative"
        elif not part.isdigit() and not is_valid_date_format(part):
            return "Incorrect date format, use YYYY-MM-DD"
    if len(parts) == 2 and parts[1].isdigit() and parts[0].isdigit():
        if int(parts[1]) < int(parts[0]):
            return "End block seqno cannot be less than start block seqno"
    return True


def validate_http_url(value):
    if not value.startswith("http"):
        return "URL must start with http"
    return True


def validate_digits_or_empty(value):
    if value == "":
        return True
    try:
        int(value)
        if int(value) <= 0:
            return "Input must be a positive number"
        return True
    except ValueError:
        return "Input must be a number"


def validate_state_ttl(value, archive_ttl):
    v = validate_digits_or_empty(value)
    if v is not True: return v
    if archive_ttl and value and int(value) > int(archive_ttl):
        return "State TTL cannot be greater than blocks TTL"
    return True



def validate_shard_format(value):
    if not value:
        return True
    for shard in value.split():
        if ":" not in shard:
            return "Each shard must be in format <workchain>:<shard>"
    return True


def run_cli():
    mode = questionary.select(
        "Select installation mode (More on https://docs.ton.org/participate/nodes/node-types)",
        choices=["validator", "liteserver"],
    ).unsafe_ask()

    network = questionary.select(
        "Select network",
        choices=["Mainnet", "Testnet", "Other"],
    ).unsafe_ask()

    config = None
    if network == "Other":
        config = questionary.text(
            "Provide network config uri",
            validate=validate_http_url
        ).unsafe_ask()

    validator_mode = None
    if mode == "validator":
        validator_mode = questionary.select(
            "Select mode for validator usage. You can set up this later",
            choices=["Validator wallet", "Nominator pool", "Single pool", "Liquid Staking", "Skip"],
        ).unsafe_ask()

    archive_blocks = None
    if mode != "validator":
        archive_blocks = questionary.text(
            "Do you want to download archive blocks via TON Storage? Press Enter to skip.\n"
            "If yes, provide block seqno or date to start from and (optionally) block seqno or date to end with (send `1` to download all blocks and setup full archive node).\n"
            "Examples: `30850000`, `10000000 10200000`, `2025-01-01`, `2025-01-01 2025-01-30`",
            validate=validate_archive_blocks
        ).unsafe_ask()

    archive_ttl = None
    state_ttl = None
    if mode == "liteserver":
        temp_answers = {
            'archive-blocks': archive_blocks,
            'network': network
        }
        archive_ttl = questionary.text(
            get_archive_ttl_message(temp_answers),
            validate=validate_digits_or_empty
        ).unsafe_ask()
        if not archive_ttl and 'archive-ttl-default' in temp_answers:
            archive_ttl = temp_answers['archive-ttl-default']
        if archive_ttl != '-1':
            state_ttl = questionary.text(
                'Send the number of seconds to keep blocks states in the node database. Press Enter to use default: 86400 (24 hours)',
                validate= lambda x: validate_state_ttl(x, archive_ttl)
            ).unsafe_ask()

    dump = None
    if not archive_blocks:
        dump = questionary.confirm(
            "Do you want to download blockchain's dump? "
            "This reduces synchronization time but requires to download a large file"
        ).unsafe_ask()

    add_shard = questionary.text(
        "Set shards node will sync. Press Enter to sync all shards.\n"
        "Format: <workchain>:<shard>. Divide multiple shards with space.\n"
        "Example: `0:2000000000000000 0:6000000000000000`",
        validate=validate_shard_format
    ).unsafe_ask()

    background = questionary.confirm(
        "Do you want to run MyTonCtrl installation in the background?"
    ).unsafe_ask()

    answers = {
        "mode": mode,
        "network": network,
        "config": config,
        "validator-mode": validator_mode,
        "archive-blocks": archive_blocks,
        "archive-ttl": archive_ttl,
        'state-ttl': state_ttl,
        "dump": dump,
        "add-shard": add_shard,
        "background": background
    }
    print(answers)
    return answers


def run_install(answers: dict):
    mode = answers["mode"]
    network = answers["network"].lower()
    config = answers["config"]
    archive_ttl = answers["archive-ttl"]
    state_ttl = answers["state-ttl"]
    add_shard = answers["add-shard"]
    validator_mode = answers["validator-mode"]
    archive_blocks = answers["archive-blocks"]
    dump = answers["dump"]
    background = answers["background"]

    command = ['bash', 'install.sh']
    args = f' -n {network}'

    user = os.environ.get("SUDO_USER") or os.environ.get("USER")
    args += f' -u {user}'

    if network not in ('mainnet', 'testnet'):
        args += f' -c {config}'

    if archive_ttl:
        os.environ['ARCHIVE_TTL'] = archive_ttl  # set env variable
    if state_ttl:
        os.environ['STATE_TTL'] = state_ttl
    if add_shard:
        os.environ['ADD_SHARD'] = add_shard
    if archive_blocks:
        os.environ['ARCHIVE_BLOCKS'] = archive_blocks

    if validator_mode and validator_mode not in ('Skip', 'Validator wallet'):
        if validator_mode == 'Nominator pool':
            validator_mode = 'nominator-pool'
        elif validator_mode == 'Single pool':
            validator_mode = 'single-nominator'
        elif validator_mode == 'Liquid Staking':
            validator_mode = 'liquid-staking'
        args += f' -m {validator_mode}'
    else:
        args += f' -m {mode}'

    if dump:
        args += ' -d'

    log = None
    stdin = None
    if background:
        os.environ['PYTHONUNBUFFERED'] = '1'
        log = open("mytonctrl_installation.log", "a")
        stdin=subprocess.DEVNULL
        command = ['nohup'] + command
    command += args.split()

    print(command)

    process = subprocess.Popen(
        command,
        stdout=log,
        stderr=log,
        stdin=stdin,
    )
    if not background:
        process.wait()
    if background:
        print("="*100 + f"\nRunning installation in the background. Check './mytonctrl_installation.log' for progress. PID: {process.pid}\n" + "="*100)


def main():
    try:
        answers = run_cli()
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user")
        return
    run_install(answers)


if __name__ == '__main__':
    main()
