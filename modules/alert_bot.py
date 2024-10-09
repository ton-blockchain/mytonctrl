import dataclasses
import time
import requests

from modules.module import MtcModule
from mytoncore import get_hostname
from mytonctrl.utils import timestamp2utcdatetime


@dataclasses.dataclass
class Alert:
    severity: str
    text: str
    timeout: int


HOUR = 3600


ALERTS = {
    "low_wallet_balance": Alert(
        "low",
        "Validator wallet {wallet} balance is low: {balance} TON.",
        18*HOUR
    ),
    "db_usage_80": Alert(
        "high",
        """TON DB usage > 80%. Clean the TON database: 
        https://docs.ton.org/participate/nodes/node-maintenance-and-security#database-grooming 
        or (and) set node\'s archive ttl to lower value.""",
        24*HOUR
    ),
    "db_usage_95": Alert(
        "critical",
        """TON DB usage > 95%. Disk is almost full, clean the TON database immediately: 
        https://docs.ton.org/participate/nodes/node-maintenance-and-security#database-grooming 
        or (and) set node\'s archive ttl to lower value.""",
        6*HOUR
    ),
    "low_efficiency": Alert(
        "high",
        """Validator efficiency is low: {efficiency}%.""",
        12*HOUR
    ),
    "out_of_sync": Alert(
        "critical",
        "Node is out of sync on {sync} sec.",
        0
    ),
    "service_down": Alert(
        "critical",
        "validator.service is down.",
        0
    ),
    "adnl_connection_failed": Alert(
        "high",
        "ADNL connection to node failed",
        3*HOUR
    ),
    "zero_block_created": Alert(
        "critical",
        "Validator has not created any blocks in the last 6 hours.",
        6 * HOUR
    ),
    "validator_slashed": Alert(
        "high",
        "Validator has been slashed in previous round for {amount} TON",
        10*HOUR
    ),
}


class AlertBotModule(MtcModule):

    description = 'Telegram bot alerts'
    default_value = False

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)
        self.validator_module = None
        self.inited = False
        self.hostname = None
        self.token = self.ton.local.db.get("BotToken")
        self.chat_id = self.ton.local.db.get("ChatId")

    def send_message(self, text: str):
        if self.token is None:
            raise Exception("send_message error: token is not initialized")
        request_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {'chat_id': self.chat_id, 'text': text, 'parse_mode': 'HTML'}
        response = requests.post(request_url, data=data, timeout=3)
        if response.status_code != 200:
            raise Exception(f"send_message error: {response.text}")
        response = response.json()
        if not response['ok']:
            raise Exception(f"send_message error: {response}")

    def send_alert(self, alert_name: str, *args, **kwargs):
        last_sent = self.get_alert_sent(alert_name)
        time_ = timestamp2utcdatetime(int(time.time()))
        alert = ALERTS.get(alert_name)
        if alert is None:
            raise Exception(f"Alert {alert_name} not found")
        text = f'''
❗️ <b>MyTonCtrl Alert {alert_name}</b> ❗️

Hostname: <code>{self.hostname}</code>
Time: <code>{time_}</code> (<code>{int(time.time())}</code>)
Severity: <code>{alert.severity}</code>
Next alert of this type not earlier than: <code>{max(alert.timeout, 1000)} sec</code>

Alert text:
<blockquote> {alert.text.format(*args, **kwargs)} </blockquote>
'''
        if time.time() - last_sent > alert.timeout:
            self.send_message(text)
            self.set_alert_sent(alert_name)

    def init(self):
        if not self.ton.get_mode_value('alert-bot'):
            return
        if self.token is None or self.chat_id is None:
            raise Exception("BotToken or ChatId is not set")
        from modules.validator import ValidatorModule
        self.validator_module = ValidatorModule(self.ton, self.local)
        self.hostname = get_hostname()
        self.inited = True

    def set_alert_sent(self, alert_name: str):
        if 'alerts' not in self.ton.local.db:
            self.ton.local.db['alerts'] = {}
        self.ton.local.db['alerts'][alert_name] = int(time.time())

    def get_alert_sent(self, alert_name: str):
        if 'alerts' not in self.ton.local.db:
            return 0
        return self.ton.local.db['alerts'].get(alert_name, 0)

    def check_db_usage(self):
        usage = self.ton.GetDbUsage()
        if usage > 95:
            self.send_alert("db_usage_95")
        elif usage > 80:
            self.send_alert("db_usage_80")

    def check_validator_wallet_balance(self):
        if not self.ton.using_validator():
            return
        validator_wallet = self.ton.GetValidatorWallet()
        validator_account = self.ton.GetAccount(validator_wallet.addrB64)
        if validator_account.balance < 50:
            self.send_alert("low_wallet_balance", wallet=validator_wallet.addrB64, balance=validator_account.balance)

    def check_efficiency(self):
        if not self.ton.using_validator():
            return
        validator = self.validator_module.find_myself(self.ton.GetValidatorsList(fast=True))
        if validator is None or validator.is_masterchain is False or validator.efficiency is None:
            return
        config34 = self.ton.GetConfig34()
        if (time.time() - config34.startWorkTime) / (config34.endWorkTime - config34.startWorkTime) < 0.8:
            return  # less than 80% of round passed
        if validator.efficiency < 90:
            self.send_alert("low_efficiency", efficiency=validator.efficiency)

    def check_validator_working(self):
        validator_status = self.ton.GetValidatorStatus()
        if not validator_status.is_working:
            self.send_alert("service_down")

    def check_sync(self):
        validator_status = self.ton.GetValidatorStatus()
        if validator_status.is_working and validator_status.out_of_sync >= 20:
            self.send_alert("out_of_sync", sync=validator_status.out_of_sync)

    def check_zero_blocks_created(self):
        if not self.ton.using_validator():
            return
        validators = self.ton.GetValidatorsList(start=-6*HOUR, end=-60)
        validator = self.validator_module.find_myself(validators)
        if validator is None or validator.blocks_created > 0:
            return
        self.send_alert("zero_block_created")

    def check_slashed(self):
        if not self.ton.using_validator():
            return
        c = self.validator_module.get_my_complaint()
        if c is not None:
            self.send_alert("validator_slashed", amount=int(c['suggestedFine']))

    def check_status(self):
        if not self.inited:
            self.init()

        self.local.try_function(self.check_db_usage)
        self.local.try_function(self.check_validator_wallet_balance)
        self.local.try_function(self.check_efficiency)  # todo: alert if validator is going to be slashed
        self.local.try_function(self.check_validator_working)
        self.local.try_function(self.check_zero_blocks_created)
        self.local.try_function(self.check_sync)
        self.local.try_function(self.check_slashed)

    def add_console_commands(self, console):
        ...
