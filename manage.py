import re

import click

from decimal import Decimal
from typing import Dict, Final, List, Optional

from pydantic.main import BaseModel
from mytoncore import MyTonCore, Wallet
from mypylib.mypylib import MyPyClass

from src.exceptions import BalanceIsTooLow, WalletAccountNotInitialized

main: Final[click.Group] = click.Group()

AMOUNT_MIN_VALUE: Final[int] = 0
VALID_ADDRESS_REGEXP: Final[re.Pattern] = re.compile(r'[0-9A-Za-z-_/]{48}$')

# Disable logging
MyPyClass.AddLog = lambda *args, **kwargs: None

WALLET_TABLE: Final[str] = '''--------------------
Account status: {}
Account balance: {}
Wallet address: {}
Wallet name: {}
Wallet version: {}
Wallet work-chain: {}
--------------------'''


class FlagArguments(BaseModel):
    flags: List[str]
    timeout: Optional[int]
    sub_wallet: Optional[str]


def get_ton_controller() -> MyTonCore:
    ton = MyTonCore()
    ton.Init()
    return ton


def validate_address(wallet_address: str) -> bool:
    return VALID_ADDRESS_REGEXP.match(wallet_address) is not None


def comma_separated(
    _: click.Context,
    __: click.Option,
    values: str,
) -> List[str]:
    if ',' not in values:
        return [values]
    return values.split(',')


def error(message: str, *additional_messages: str) -> SystemExit:
    formatted_messages = []
    for additional_message in additional_messages:
        formatted_messages.append(f'  ↳ {additional_message}')
    built_message = f'{message}\n' + '\n'.join(formatted_messages)
    click.secho(built_message, fg='red')
    return SystemExit(1)


def warning(message: str, *additional_messages: str) -> None:
    formatted_messages = []
    for additional_message in additional_messages:
        formatted_messages.append(f'  ↳ {additional_message}')
    built_message = f'{message}\n' + '\n'.join(formatted_messages)
    click.secho(built_message, fg='yellow')


def message(
    message: str,
    *additional_messages: str,
    exit_after: bool = False,
) -> Optional[SystemExit]:
    formatted_messages = []
    for additional_message in additional_messages:
        formatted_messages.append(f'  ↳ {additional_message}')
    built_message = None
    if formatted_messages:
        built_message = f'{message}' + '\n'.join(formatted_messages)
    click.secho(built_message or message)
    if exit_after is True:
        return SystemExit(0)


@main.command(
    'move-coins',
    help='Move coins to specified account/wallet.',
)
@click.argument('wallet-name', type=click.STRING)
@click.argument('target-address', type=click.STRING)
@click.argument('amount', type=Decimal)
@click.option(
    '-f', '--flags',
    default=None,
    callback=comma_separated,
    type=click.STRING,
    help='Additional flags.',
)
@click.option(
    '-t', '--timeout',
    default=30,
    type=click.INT,
    help='Transfer timeout.',
)
@click.option(
    '-sw', '--sub-wallet',
    default=None,
    type=click.STRING,
    help='Sub-wallet to be used.',
)
def move_coins(
    wallet_name: str,
    target_address: str,
    amount: Decimal,
    flags: Optional[List[str]] = None,
    timeout: Optional[int] = None,
    sub_wallet: Optional[str] = None,
) -> None:
    keywords = FlagArguments(
        flags=flags,
        timeout=timeout,
        sub_wallet=sub_wallet,
    )
    ton_controller: MyTonCore = get_ton_controller()
    if wallet_name == target_address:
        raise error('Given WALLET-ADDRESS & TARGET-ADDRESS are identical.')
    if amount < AMOUNT_MIN_VALUE:
        raise error(f'Amount to transfer cannot be lower than "{AMOUNT_MIN_VALUE}"')
    try:
        source_wallet: Wallet = ton_controller.GetLocalWallet(wallet_name)
    except Exception as err:
        raise error(
            f'Failed to get wallet with name/address "{wallet_name}"',
            *err.args,
        )
    try:
        target_wallet: Wallet = ton_controller.GetLocalWallet(target_address)
    except Exception as err:
        raise error(
            f'Failed to get wallet with name/address "{target_address}"',
            *err.args,
        )
    try:
        ton_controller.MoveCoins(
            source_wallet,
            target_wallet,
            amount,
            **keywords.dict(),
        )
    except (BalanceIsTooLow, WalletAccountNotInitialized) as err:
        raise error(
            f'Failed to make coins transfer.',
            *err.args,
        )


@main.command(
    'wallets-list',
    help='Wallets list of your account.',
)
def wallets_list():
    ton_controller: MyTonCore = get_ton_controller()
    wallets: List[Wallet] = ton_controller.GetWallets()
    if wallets is None or not wallets:
        raise message('Not found any wallets.', exit_after=True)
    wallets_map = []
    for wallet in wallets:
        account = ton_controller.GetAccount(wallet.addrB64)
        if account.status != 'active':
            wallet.addrB64 = wallet.addrB64_init
        wallets_map.append([
            account.status,
            account.balance,
            wallet.addrB64,
            wallet.name,
            wallet.version,
            wallet.workchain,
        ])
    for wallet_info in wallets_map:
        message(WALLET_TABLE.format(*wallet_info))


@main.command(
    'status',
    help='Get wallet status information.',
)
@click.argument(
    'status_type',
    default=None,
    type=click.STRING,
    help='Type of information getter speed.',
)
def get_status(status_type: Optional[str]) -> None:
    ton_controller: MyTonCore = get_ton_controller()
    adnl_address: Dict = ton_controller.GetAdnlAddr()
    root_workchain_enabled_time_int: int = ton_controller.GetRootWorkchainEnabledTime()
    config34: Dict = ton_controller.GetConfig34()
    config36: Dict = ton_controller.GetConfig36()
    total_validators = config34['totalValidators']
    online_validators = None
    validator_efficiency = None
    if status_type != 'fast':
        # TODO: Created ENUM for status type
        raise


if __name__ == '__main__':
    main()
