import os
import subprocess
import inquirer


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
        inquirer.Text(
            "archive-ttl",
            message="Send the number of seconds to keep the block data in the node database. Default is 2592000 (30 days)",
            ignore=lambda x: x["mode"] != "liteserver",  # do not ask this question if mode is not liteserver
            validate=lambda _, x: not x or x.isdigit(),  # must be empty string or a number
            # default=2592000
        ),
        inquirer.List(
            "validator-mode",
            message="Select mode for validator usage. You can skip and set up this later",
            ignore=lambda x: x["mode"] != "validator",  # do not ask this question if mode is not validator
            choices=["Validator wallet", "Nominator pool", "Single pool", "Liquid Staking", "Skip"],
        ),
        inquirer.Text(
            "archive-blocks",
            message="Do you want to download archive blocks via TON Storage? If yes, provide block seqno to start from or press Enter to skip.",
            ignore=lambda x: x["mode"] == "validator",
            validate=lambda _, x: not x or (x.isdigit() and int(x) >= 0),
        ),
        inquirer.Confirm(
            "dump",
            message="Do you want to download latest blockchain's state via TON Storage?",
            ignore= lambda x: x["archive-blocks"],
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
    archive_ttl = answers["archive-ttl"]
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
