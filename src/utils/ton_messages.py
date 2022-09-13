import click

from typing import Dict, Final
from src.utils.click_messages import message


MESSAGE: Final[str] = '''--------------------
TPS AVERAGE:
\t
--------------------'''


def print_ton_status(
    start_work_time: int,
    total_validators: int,
    online_validators: int,
    shards_number: int,
    offers_number: Dict,
    complaints_number: Dict,
    tps_average: Dict,
):
    tps_1 = tps_average[0]
    tps_5 = tps_average[1]
    tps_15 = tps_average[2]
    all_validators = total_validators
    new_offers = offers_number.get('new')
    all_offers = offers_number.get('all')
    new_complaints = complaints_number.get('new')
    all_complaints = complaints_number.get('all')
    
    if start_work_time == 0:
        election_text = 'closed'
    else:
        election_text = 'open'
    message(election_text)
