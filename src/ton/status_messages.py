import multiprocessing

import mypylib.mypylib as mypylib
import mytoncore
import mytonctrl

from datetime import datetime
from typing import Dict, Tuple, Final, Optional

from src.utils.time import format_timestamp_as_delta, format_timestamp_as_date


BORDER_WIDTH: Final[int] = 20
MTC_SOURCE_PATH: Final[str] = '/usr/src/mytonctrl'
VALIDATOR_SOURCE_PATH: Final[str] = '/usr/src/ton'


def build_status_message(
    start_work_time: int,
    online_validators: int,
    total_validators: int,
    shards_count: int,
    offers_count: Dict[str, int],
    complaints_count: Dict[str, int],
    transactions_per_second: Tuple[int],
) -> str:
    heading = 'TON network status'
    transactions_per_second: str = ' '.join(str(i) for i in transactions_per_second)
    messages = [
        heading.center(len(heading) + BORDER_WIDTH, '-'),
        'Transactions per second: {tps}'.format(tps=transactions_per_second),
        'Count of validators: {online} ({total})'.format(
            online=online_validators,
            total=total_validators,
        ),
        'Count of shard-chains: {count}'.format(count=shards_count),
        'Count of offers: {new} ({all})'.format(
            new=offers_count.get('new'),
            all=offers_count.get('all'),
        ),
        'Count of complaints: {new} ({all})'.format(
            new=complaints_count.get('new'),
            all=complaints_count.get('all'),
        ),
        'Election status: {status}'.format(
            status='closed' if start_work_time == 0 else 'open'
        ),
    ]
    return '\n'.join(messages)


def build_local_validator_status_message(
    adnl_address: str,
    validator_index: int,
    validator_efficiency: Optional[int],
    validator_wallet: mytonctrl.Wallet,
    validator_account: mytonctrl.Account,
    validator_status: Dict[str, int],
    database_size: int,
    database_usage: int,
    memory_info: Dict[str, int],
    swap_info: Dict[str, int],
    network_load_average: Tuple[float],
    disk_load_average: Dict[str, Tuple],
    disk_load_percent_average: Dict[str, Tuple],
) -> str:
    heading = 'Local validator status'
    messages = [
        heading.center(len(heading) + BORDER_WIDTH, '-'),
        'Validator index: {index}'.format(index=validator_index),
        'Validator efficiency: {eff}'.format(eff=validator_efficiency or 'N/A'),
        'ADNL address of local validator: {address}'.format(address=adnl_address),
        'Local validator wallet address: {address}'.format(address=validator_wallet.addrB64),
        'Local validator wallet balance: {balance}'.format(balance=validator_account.balance),
        'Load average ({cores_count} cores): {load}'.format(
            cores_count=multiprocessing.cpu_count(),
            load=' '.join(str(load) for load in mypylib.GetLoadAvg()),
        ),
        'Network load average (Mbit/s): {load}'.format(
            load=' '.join(str(load) for load in network_load_average),
        ),
        'Memory load:\n'
        '\tRAM: [{ram_amount}, {ram_usage}%]\n'
        '\tSWAP: [{swap_amount}, {swap_usage}%]'.format(
            ram_amount=memory_info.get('usage'),
            ram_usage=memory_info.get('usagePercent'),
            swap_amount=swap_info.get('usage'),
            swap_usage=swap_info.get('usagePercent'),
        ),
        # TODO: Copied from "mytonctrl.py / line 354",
        #  must rework this shit to real dict operating
        'Disks load average (MB/s):\n'
        ''.join(
            '\t{storage_type}:[{storage_amount}, {storage_usage}%]\n'.format(
                storage_type=storage_type,
                storage_amount=storage_stats[0],
                storage_usage=disk_load_percent_average[storage_type][2],
            )
            for storage_type, storage_stats in disk_load_average.items()
        ),
        '"mytoncore" status: {status}, {uptime}'.format(
            status=(
                'UP'
                if mytoncore.GetServiceStatus('mytoncore') is True
                else 'DOWN'
            ),
            uptime=format_timestamp_as_delta(mytoncore.GetServiceUptime('mytoncore')),
        ),
        'Local validator status: {status}, {uptime}'.format(
            status=(
                'UP'
                if mytoncore.GetServiceStatus('validator') is True
                else 'DOWN'
            ),
            uptime=format_timestamp_as_delta(mytoncore.GetServiceUptime('validator')),
        ),
        'Local validator out of sync: {time}'.format(
            time='N/A' if validator_status.get('outOfSync') is None
            else f'{validator_status.get("outOfSync")} s',
        ),
        'Local validator database size: {amount}, {usage}'.format(
            amount=database_size,
            usage=database_usage,
        ),
        'Version of "mytonctrl": {commit} {branch}'.format(
            commit=mytoncore.GetGitHash(MTC_SOURCE_PATH, short=True),
            branch=mytoncore.GetGitBranch(MTC_SOURCE_PATH),
        ),
        'Version of validator: {commit} {branch}'.format(
            commit=mytoncore.GetGitHash(VALIDATOR_SOURCE_PATH, short=True),
            branch=mytoncore.GetGitBranch(VALIDATOR_SOURCE_PATH),
        ),
    ]
    return '\n'.join(messages)


def build_network_configuration_message(
    full_config_address: str,
    full_elector_address: str,
    config15: Dict,
    config17: Dict,
) -> str:
    heading = 'TON network configuration'
    messages = [
        heading.center(len(heading) + BORDER_WIDTH, '-'),
        'Configurator address: {address}'.format(address=full_config_address),
        'Elector address: {address}'.format(address=full_elector_address),
        'Validation period: {period}'.format(period=config15['validatorsElectedFor']),
        'Duration of elections: {start}-{end}'.format(
            start=config15['electionsStartBefore'],
            end=config15['electionsEndBefore'],
        ),
        'Hold period: {period}'.format(period=config15['stakeHeldFor']),
        'Minimum stake: {amount}'.format(amount=config17['minStake']),
        'Maximum stake: {amount}'.format(amount=config17['maxStake']),
    ]
    return '\n'.join(messages)


def build_ton_timestamps_message(
    root_work_chain_enabled_time: int,
    start_work_time: int,
    old_start_work_time: int,
    config15: Dict,
) -> str:
    heading = 'TON timestamps'
    if start_work_time == 0:
        start_work_time = old_start_work_time
    messages = [
        heading.center(len(heading) + BORDER_WIDTH, '-'),
        'TON network was launched: {date}'.format(
            date=format_timestamp_as_date(root_work_chain_enabled_time),
        ),
        'Start of the validation cycle: {date}'.format(
            date=format_timestamp_as_date(start_work_time),
        ),
        'End of validation cycle: {date}'.format(
            date=format_timestamp_as_date(start_work_time + config15['validatorsElectedFor']),
        ),
        'Start of elections: {date}'.format(
            date=format_timestamp_as_date(start_work_time - config15["electionsStartBefore"]),
        ),
        'End of elections: {date}'.format(
            date=format_timestamp_as_date(start_work_time - config15['electionsEndBefore']),
        ),
        'Beginning of the next election: {date}'.format(
            date=format_timestamp_as_date(
                (start_work_time - config15["electionsStartBefore"]) + config15["validatorsElectedFor"],
            ),
        ),
    ]
    return '\n'.join(messages)
