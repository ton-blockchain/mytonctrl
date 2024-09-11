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
        inquirer.Confirm(
            "dump",
            message="Do you want to download blockchain's dump? "
                    "This reduces synchronization time but requires to download a large file",
        )
    ]

    answers = inquirer.prompt(questions)

    return answers


def parse_args(answers: dict):
    mode = answers["mode"]
    network = answers["network"].lower()
    config = answers["config"]
    archive_ttl = answers["archive-ttl"]
    validator_mode = answers["validator-mode"]
    dump = answers["dump"]

    res = f' -n {network}'

    if network not in ('mainnet', 'testnet'):
        res += f' -c {config}'

    if archive_ttl:
        os.putenv('ARCHIVE_TTL', archive_ttl)  # set env variable

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
