"""Console commands of modules/collator_config.py (collator options JSON).

These pin the behaviour of the console handlers: where the config is read from
(local file or HTTP), what is stored in the db, and the validator-engine-console
commands that are sent.
"""
import json

import pytest
from pytest_mock import MockerFixture

import modules.collator_config as collator_config_module


DEFAULT_URL = "https://raw.githubusercontent.com/ton-blockchain/ton-blockchain.github.io/main/default_collator_options.json"
CONFIG_URL = "https://example.com/collator_options.json"
CONFIG = {"deferring_enabled": True, "dispatch_phase_2_max_total": 150000}

COLLATOR_CONFIG_COMMANDS = ["set_collation_config", "update_collation_config", "print_collation_config"]


@pytest.fixture()
def vc(ton, mocker: MockerFixture):
    console = mocker.Mock()
    console.run.return_value = "success"
    ton._validator_console = console
    return console


@pytest.fixture()
def http_get(monkeypatch, mocker: MockerFixture):
    response = mocker.Mock(status_code=200, text=json.dumps(CONFIG))
    response.json.return_value = CONFIG
    get_mock = mocker.Mock(return_value=response)
    monkeypatch.setattr(collator_config_module.requests, "get", get_mock)
    return get_mock


def _write_config(tmp_path, config) -> str:
    path = tmp_path / "collator_options.json"
    path.write_text(json.dumps(config))
    return str(path)


def _pushed_config(ton) -> dict:
    with open(ton.tempDir + "/collator_config.json") as f:
        return json.load(f)


def test_collator_config_commands_registered(cli):
    # registered for validators (the default mode in the test db)
    output = cli.execute("help", no_color=True)
    registered = {line.split()[0] for line in output.splitlines() if line.strip()}
    assert set(COLLATOR_CONFIG_COMMANDS) <= registered


def test_set_collation_config(cli, ton, vc, http_get, tmp_path):
    path = _write_config(tmp_path, CONFIG)
    push_cmd = f"setcollatoroptionsjson {ton.tempDir}/collator_config.json"

    # Bad args
    output = cli.execute("set_collation_config", no_color=True)
    assert "usage: set_collation_config [-h] location" in output
    assert "set_collation_config: error: the following arguments are required: location" in output
    output = cli.execute(f"set_collation_config {path} extra", no_color=True)
    assert "set_collation_config: error: unrecognized arguments: extra" in output
    vc.run.assert_not_called()
    assert "collator_config" not in ton.local.db

    # local file
    output = cli.execute(f"set_collation_config {path}", no_color=True)
    assert "set_collator_config - OK" in output
    http_get.assert_not_called()
    vc.run.assert_called_once_with(push_cmd)
    assert _pushed_config(ton) == CONFIG
    assert ton.local.db["collator_config"] == path

    # URL: anything containing "http" is fetched
    vc.run.reset_mock()
    output = cli.execute(f"set_collation_config {CONFIG_URL}", no_color=True)
    assert "set_collator_config - OK" in output
    http_get.assert_called_once_with(CONFIG_URL, timeout=3)
    vc.run.assert_called_once_with(push_cmd)
    assert _pushed_config(ton) == CONFIG
    assert ton.local.db["collator_config"] == CONFIG_URL

    # the location is saved even when the validator console rejects the config
    vc.run.return_value = "error: bad options"
    output = cli.execute(f"set_collation_config {path}", no_color=True)
    assert "Failed to add collation config to validator console: error: bad options" in output
    assert "set_collator_config - ERROR" in output
    assert ton.local.db["collator_config"] == path

    # unreadable locations: nothing saved, nothing pushed
    vc.run.reset_mock()
    http_get.return_value.status_code = 404
    http_get.return_value.text = "Not Found"
    output = cli.execute(f"set_collation_config {CONFIG_URL}", no_color=True)
    assert f"Failed to get config from {CONFIG_URL}: 404 code; Not Found" in output
    assert "Error: Failed to get config" in output
    missing = str(tmp_path / "missing.json")
    output = cli.execute(f"set_collation_config {missing}", no_color=True)
    assert f"Failed to read config from {missing}" in output
    assert "Error: Failed to get config" in output
    vc.run.assert_not_called()
    assert ton.local.db["collator_config"] == path


def test_update_collation_config(cli, ton, vc, http_get, tmp_path):
    push_cmd = f"setcollatoroptionsjson {ton.tempDir}/collator_config.json"

    # nothing set yet: the default URL
    output = cli.execute("update_collation_config", no_color=True)
    assert "update_collator_config - OK" in output
    http_get.assert_called_once_with(DEFAULT_URL, timeout=3)
    vc.run.assert_called_once_with(push_cmd)
    assert _pushed_config(ton) == CONFIG
    assert "collator_config" not in ton.local.db

    # the location saved by set_collation_config
    other_config = {"deferring_enabled": False}
    ton.local.db["collator_config"] = _write_config(tmp_path, other_config)
    http_get.reset_mock()
    vc.run.reset_mock()
    output = cli.execute("update_collation_config", no_color=True)
    assert "update_collator_config - OK" in output
    http_get.assert_not_called()
    vc.run.assert_called_once_with(push_cmd)
    assert _pushed_config(ton) == other_config

    vc.run.return_value = "error: bad options"
    output = cli.execute("update_collation_config", no_color=True)
    assert "Failed to add collator config to validator console: error: bad options" in output
    assert "update_collator_config - ERROR" in output

    vc.run.reset_mock()
    output = cli.execute("update_collation_config extra", no_color=True)
    assert "usage: update_collation_config [-h]" in output
    assert "update_collation_config: error: unrecognized arguments: extra" in output
    vc.run.assert_not_called()


def test_print_collation_config(cli, ton, vc, tmp_path):
    current_path = f"{ton.tempDir}/current_collator_config.json"

    def fake_run(cmd):
        # validator-engine-console writes the current options to the given file
        with open(cmd.split()[1], "w") as f:
            json.dump(CONFIG, f)
        return f"saved config to {cmd.split()[1]}"

    vc.run.side_effect = fake_run
    output = cli.execute("print_collation_config", no_color=True)
    vc.run.assert_called_once_with(f"getcollatoroptionsjson {current_path}")
    assert f"Collator config location: {DEFAULT_URL}" in output
    assert "Collator config:\n" + json.dumps(CONFIG, indent=4) in output
    assert "get_collator_config - OK" in output

    ton.local.db["collator_config"] = str(tmp_path / "mine.json")
    vc.run.side_effect = None
    vc.run.return_value = "error: not a collator"
    output = cli.execute("print_collation_config", no_color=True)
    assert f"Collator config location: {tmp_path / 'mine.json'}" in output
    assert "Failed to get collator config: error: not a collator" in output
    assert "get_collator_config - ERROR" in output

    vc.run.reset_mock()
    output = cli.execute("print_collation_config extra", no_color=True)
    assert "usage: print_collation_config [-h]" in output
    assert "print_collation_config: error: unrecognized arguments: extra" in output
    vc.run.assert_not_called()
