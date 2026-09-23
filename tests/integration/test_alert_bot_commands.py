"""Console commands of modules/alert_bot.py (Telegram alert bot).

These pin the behaviour of the commands: the alert state kept in
``local.db["alerts"]``, the bot credentials stored in the db, and the exact
Telegram Bot API requests that are sent.
"""
import pytest
from pytest_mock import MockerFixture

import modules.alert_bot as alert_bot_module
from mytoncore.models import Config15, Wallet
from mytoncore.mytoncore import MyTonCore


BOT_TOKEN = "123456:ABC-token"
CHAT_ID = "-1001234567"
ADNL = "AD" * 32
SEND_MESSAGE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

ALERT_BOT_COMMANDS = ["enable_alert", "disable_alert", "list_alerts", "test_alert", "setup_alert_bot"]


@pytest.fixture(autouse=True)
def _enable_alert_bot(monkeypatch):
    # autouse: must be applied before the `cli` fixture registers the modules
    monkeypatch.setattr(MyTonCore, "using_alert_bot", lambda self: True)
    # init_alerts() / AlertBotModule.init() rebind these module globals: restore them afterwards
    for name in ("ALERTS", "VALIDATION_PERIOD", "FREEZE_PERIOD", "ELECTIONS_START_BEFORE"):
        monkeypatch.setattr(alert_bot_module, name, getattr(alert_bot_module, name))


@pytest.fixture()
def telegram_post(monkeypatch, mocker: MockerFixture):
    response = mocker.Mock(status_code=200, text='{"ok": true}')
    response.json.return_value = {"ok": True}
    post_mock = mocker.Mock(return_value=response)
    monkeypatch.setattr(alert_bot_module.requests, "post", post_mock)
    return post_mock


def _alert_rows(output: str) -> list:
    rows = [line.split() for line in output.splitlines() if line.strip()]
    assert rows[0] == ["Name", "Enabled", "Last", "sent"]
    return rows[1:]


def test_alert_bot_commands_registered(cli):
    output = cli.execute("help", no_color=True)
    registered = {line.split()[0] for line in output.splitlines() if line.strip()}
    assert set(ALERT_BOT_COMMANDS) <= registered


def test_enable_disable_list_alerts(cli, ton):
    default_state = {"sent": 0, "enabled": True, "active": False, "resolved_sent": 0}

    # Bad args
    output = cli.execute("enable_alert", no_color=True)
    assert "usage: enable_alert [-h] alert_name" in output
    assert "enable_alert: error: the following arguments are required: alert_name" in output
    output = cli.execute("enable_alert low_efficiency out_of_sync", no_color=True)
    assert "enable_alert: error: unrecognized arguments: out_of_sync" in output
    output = cli.execute("disable_alert", no_color=True)
    assert "usage: disable_alert [-h] alert_name" in output
    assert "disable_alert: error: the following arguments are required: alert_name" in output
    output = cli.execute("disable_alert low_efficiency out_of_sync", no_color=True)
    assert "disable_alert: error: unrecognized arguments: out_of_sync" in output
    assert "alerts" not in ton.local.db

    output = cli.execute("disable_alert low_efficiency", no_color=True)
    assert "disable_alert - OK" in output
    assert ton.local.db["alerts"] == {"low_efficiency": dict(default_state, enabled=False)}

    # list_alerts shows every known alert and creates its default db entry
    ton.local.db["alerts"]["out_of_sync"] = dict(default_state, sent=1700000000)
    output = cli.execute("list_alerts", no_color=True)
    names = list(alert_bot_module.ALERTS)
    assert "low_efficiency" in names and "out_of_sync" in names
    rows = _alert_rows(output)
    assert [row[0] for row in rows] == names
    assert ["low_efficiency", "False", "0"] in rows
    assert ["out_of_sync", "True", "1700000000"] in rows
    assert ["service_down", "True", "0"] in rows
    assert set(ton.local.db["alerts"]) == set(names)
    assert ton.local.db["alerts"]["service_down"] == default_state

    output = cli.execute("enable_alert low_efficiency", no_color=True)
    assert "enable_alert - OK" in output
    assert ton.local.db["alerts"]["low_efficiency"]["enabled"] is True
    assert ["low_efficiency", "True", "0"] in _alert_rows(cli.execute("list_alerts", no_color=True))

    # alert names are not validated: an unknown name gets a db entry but is never listed
    output = cli.execute("disable_alert no_such_alert", no_color=True)
    assert "disable_alert - OK" in output
    assert ton.local.db["alerts"]["no_such_alert"] == dict(default_state, enabled=False)
    output = cli.execute("list_alerts", no_color=True)
    assert "no_such_alert" not in output

    output = cli.execute("list_alerts extra", no_color=True)
    assert "usage: list_alerts [-h]" in output
    assert "list_alerts: error: unrecognized arguments: extra" in output


def test_setup_alert_bot(cli, ton, telegram_post):
    ton.local.db["adnlAddr"] = ADNL

    # Bad args
    output = cli.execute("setup_alert_bot", no_color=True)
    assert "usage: setup_alert_bot [-h] bot_token chat_id" in output
    assert "setup_alert_bot: error: the following arguments are required: bot_token, chat_id" in output
    output = cli.execute(f"setup_alert_bot {BOT_TOKEN}", no_color=True)
    assert "setup_alert_bot: error: the following arguments are required: chat_id" in output
    output = cli.execute(f"setup_alert_bot {BOT_TOKEN} {CHAT_ID} extra", no_color=True)
    assert "setup_alert_bot: error: unrecognized arguments: extra" in output
    telegram_post.assert_not_called()

    # Telegram rejects the welcome message: nothing is saved
    telegram_post.return_value.status_code = 400
    telegram_post.return_value.text = "Bad Request: chat not found"
    output = cli.execute(f"setup_alert_bot {BOT_TOKEN} {CHAT_ID}", no_color=True)
    assert "Error while sending welcome message: send_message error: Bad Request: chat not found" in output
    assert "make sure the bot is added to that chat group" in output
    assert "setup_alert_bot - Error" in output
    assert "BotToken" not in ton.local.db
    assert "ChatId" not in ton.local.db

    # HTTP 200 but {"ok": false} is an error as well
    telegram_post.return_value.status_code = 200
    telegram_post.return_value.json.return_value = {"ok": False, "description": "Forbidden"}
    output = cli.execute(f"setup_alert_bot {BOT_TOKEN} {CHAT_ID}", no_color=True)
    assert "send_message error: {'ok': False, 'description': 'Forbidden'}" in output
    assert "setup_alert_bot - Error" in output
    assert "BotToken" not in ton.local.db

    # welcome message delivered: credentials are saved as typed (chat id stays a string)
    telegram_post.reset_mock()
    telegram_post.return_value.json.return_value = {"ok": True}
    output = cli.execute(f"setup_alert_bot {BOT_TOKEN} {CHAT_ID}", no_color=True)
    assert "setup_alert_bot - OK" in output
    assert ton.local.db["BotToken"] == BOT_TOKEN
    assert ton.local.db["ChatId"] == CHAT_ID

    telegram_post.assert_called_once()
    assert telegram_post.call_args[0] == (SEND_MESSAGE_URL,)
    assert telegram_post.call_args[1]["timeout"] == 3
    payload = telegram_post.call_args[1]["json"]
    assert {key: value for key, value in payload.items() if key != "text"} == {
        "chat_id": CHAT_ID,
        "parse_mode": "HTML",
        "disable_notification": False,
        "link_preview_options": {"is_disabled": True},
    }
    assert f"You have connected validator with ADNL <code>{ADNL}</code>." in payload["text"]
    for alert in alert_bot_module.ALERTS.values():
        assert f"- {alert.description}\n" in payload["text"]


def test_test_alert(cli, ton, telegram_post, monkeypatch, mocker: MockerFixture):
    wallet = Wallet(-1, "ee" * 32, "wallet_001", ton.walletsDir + "wallet_001", "v3")
    get_wallet_mock = mocker.Mock(return_value=wallet)
    monkeypatch.setattr(MyTonCore, "GetValidatorWallet", get_wallet_mock)
    monkeypatch.setattr(MyTonCore, "get_node_ip", mocker.Mock(return_value="1.2.3.4"))
    monkeypatch.setattr(MyTonCore, "get_config_15", mocker.Mock(return_value=Config15(
        validators_elected_for=65536, elections_start_before=32768,
        elections_end_before=8192, stake_held_for=32768,
    )))
    monkeypatch.setattr(alert_bot_module, "get_hostname", lambda: "test-host")
    ton.local.db["adnlAddr"] = ADNL

    # init() checks the stored `alert-bot` mode, not using_alert_bot(): while the mode
    # is off in the db the bot is never initialised and sending fails
    ton.local.db["BotToken"] = BOT_TOKEN
    ton.local.db["ChatId"] = CHAT_ID
    output = cli.execute("test_alert", no_color=True)
    assert "send_message error: token is not initialized" in output
    telegram_post.assert_not_called()

    # mode on, credentials missing
    ton.local.db["modes"]["alert-bot"] = True
    del ton.local.db["BotToken"]
    output = cli.execute("test_alert", no_color=True)
    assert "BotToken or ChatId is not set" in output
    telegram_post.assert_not_called()

    ton.local.db["BotToken"] = BOT_TOKEN
    output = cli.execute("test_alert", no_color=True)
    telegram_post.assert_called_once_with(SEND_MESSAGE_URL, json={
        "chat_id": CHAT_ID,
        "text": "Test alert",
        "parse_mode": "HTML",
        "disable_notification": False,
        "link_preview_options": {"is_disabled": False},
    }, timeout=3)
    assert output.strip() == ""  # no confirmation line is printed
    get_wallet_mock.assert_called_once_with()

    # initialised once per console session
    telegram_post.reset_mock()
    cli.execute("test_alert", no_color=True)
    telegram_post.assert_called_once()
    get_wallet_mock.assert_called_once_with()

    # delivery failure
    telegram_post.return_value.status_code = 403
    telegram_post.return_value.text = "Forbidden: bot was blocked by the user"
    output = cli.execute("test_alert", no_color=True)
    assert "send_message error: Forbidden: bot was blocked by the user" in output

    telegram_post.reset_mock()
    telegram_post.return_value.status_code = 200
    output = cli.execute("test_alert extra", no_color=True)
    assert "usage: test_alert [-h]" in output
    assert "test_alert: error: unrecognized arguments: extra" in output
    telegram_post.assert_not_called()
