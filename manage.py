import click
import mytoncore

from decimal import Decimal
from typing import Dict, Final, List, Optional
from enum import Enum

from pydantic.main import BaseModel
from mypylib.mypylib import MyPyClass

from src.ton.factory import get_ton_controller
from src.utils.click import comma_separated
from src.utils.click_messages import error, message
from src.utils.exceptions import BalanceIsTooLow, WalletAccountNotInitialized

main: Final[click.Group] = click.Group()

AMOUNT_MIN_VALUE: Final[int] = 0

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


class WalletStatusInfoGetEnum(str, Enum):
    fast = 'fast'
    slow = 'slow'


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
    ton_controller: mytoncore.MyTonCore = get_ton_controller()
    if wallet_name == target_address:
        raise error('Given WALLET-ADDRESS & TARGET-ADDRESS are identical.')
    if amount < AMOUNT_MIN_VALUE:
        raise error(f'Amount to transfer cannot be lower than "{AMOUNT_MIN_VALUE}"')
    try:
        source_wallet: mytoncore.Wallet = ton_controller.GetLocalWallet(wallet_name)
    except Exception as err:
        raise error(
            f'Failed to get wallet with name/address "{wallet_name}"',
            *err.args,
        )
    try:
        target_wallet: mytoncore.Wallet = ton_controller.GetLocalWallet(target_address)
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
    ton_controller: mytoncore.MyTonCore = get_ton_controller()
    wallets: List[mytoncore.Wallet] = ton_controller.GetWallets()
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
    help='Get wallet status information. ',
)
@click.argument(
    'status_type',
    default=WalletStatusInfoGetEnum.fast,
    type=WalletStatusInfoGetEnum,
)
def get_status(status_type: Optional[str]) -> None:
    ton_controller: mytoncore.MyTonCore = get_ton_controller()
    adnl_address: Dict = ton_controller.GetAdnlAddr()
    root_workchain_enabled_time_int: int = ton_controller.GetRootWorkchainEnabledTime()
    config34: Dict = ton_controller.GetConfig34()
    config36: Dict = ton_controller.GetConfig36()
    total_validators = config34['totalValidators']
    online_validators = None
    validator_efficiency = None
    if status_type != WalletStatusInfoGetEnum.fast:
        online_validators = ton_controller.GetOnlineValidators()
        validator_efficiency = ton_controller.GetValidatorEfficiency()
    
    if online_validators is not None:
        online_validators = len(online_validators)
    
    old_start_work_time = config36.get('startWorkTime')
    if old_start_work_time is None:
        old_start_work_time = config34.get('startWorkTime')
    
    shards_number = ton_controller.GetShardsNumber()
    validator_status = ton_controller.GetValidatorStatus()
    config15 = ton_controller.GetConfig15()
    config17 = ton_controller.GetConfig17()
    full_config_address = ton_controller.GetFullConfigAddr()
    full_elector_address = ton_controller.GetFullElectorAddr()
    start_work_time = ton_controller.GetActiveElectionId(full_elector_address)
    validator_index = ton_controller.GetValidatorIndex()
    validator_wallet = ton_controller.GetValidatorWallet()
    database_size = ton_controller.GetDbSize()
    database_usage = ton_controller.GetDbUsage()
    memory_info = mytoncore.GetMemoryInfo()
    swap_info = mytoncore.GetSwapInfo()
    offset_number = ton_controller.GetOffersNumber()
    complaints_number = ton_controller.GetComplaintsNumber()
    statistics = ton_controller.GetSettings('statistics')
    tps_average = ton_controller.GetStatistics('tpsAvg', statistics)
    network_load_average = ton_controller.GetStatistics('netLoadAvg', statistics)
    disks_load_average = ton_controller.GetStatistics('disksLoadAvg', statistics)
    disks_load_percent_average = ton_controller.GetStatistics('disksLoadPercentAvg', statistics)
    if validator_wallet is not None:
        validator_account = ton_controller.GetAccount(validator_wallet.addrB64)
    else:
        validator_account = None


if __name__ == '__main__':
    main()
