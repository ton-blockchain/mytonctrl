"""Console commands of modules/collator.py (collator-only node).

These pin the behaviour of the legacy ``args: list[str]`` handlers: the exact
validator-engine-console commands each console command sends, and what it prints.
"""
import pytest
from pytest_mock import MockerFixture

from mypylib import Dict
from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import hex2base64


NEW_KEY = "0123456789ABCDEF" * 4
ADNL_1 = "A1" * 32
ADNL_2 = "B2" * 32

COLLATOR_COMMANDS = [
    "setup_collator",
    "print_local_collators",
    "add_validator_to_collation_wl",
    "delete_validator_from_collation_wl",
    "disable_collation_wl",
    "print_collation_whitelist",
    "stop_collator",
]


@pytest.fixture(autouse=True)
def _enable_collator(monkeypatch):
    # autouse: must be applied before the `cli` fixture registers the modules
    monkeypatch.setattr(MyTonCore, "using_collator", lambda self: True)


@pytest.fixture()
def vc(ton, mocker: MockerFixture):
    console = mocker.Mock()
    console.run.return_value = "success"
    ton._validator_console = console
    return console


@pytest.fixture()
def local_collators(monkeypatch, mocker: MockerFixture):
    """The `collators` list of the validator-engine config (base64 ADNL ids)."""
    get_config_mock = mocker.Mock(return_value=Dict({"collators": [hex2base64(ADNL_1), hex2base64(ADNL_2)]}))
    monkeypatch.setattr(MyTonCore, "GetValidatorConfig", get_config_mock)
    return get_config_mock


def test_collator_commands_registered(cli):
    output = cli.execute("help", no_color=True)
    registered = {line.split()[0] for line in output.splitlines() if line.strip()}
    assert set(COLLATOR_COMMANDS) <= registered


def test_setup_collator(cli, vc, mocker: MockerFixture):
    # validator-console replies, keyed by the console command name
    responses = {
        "newkey": f"created new key {NEW_KEY}\n",
        "addadnl": "success",
        "add-collator": "successfully added collator",
    }
    vc.run.side_effect = lambda cmd: responses[cmd.split()[0]]

    # Bad args
    output = cli.execute("setup_collator --adnl", no_color=True)
    assert "Bad args" in output
    output = cli.execute(f"setup_collator {ADNL_1}", no_color=True)
    assert "Bad args" in output
    output = cli.execute(f"setup_collator --adnl {ADNL_1} extra", no_color=True)
    assert "Bad args" in output
    output = cli.execute(f"setup_collator --foo {ADNL_1}", no_color=True)
    assert "Bad args" in output
    vc.run.assert_not_called()

    # without --adnl a new key is created and used as the collator ADNL
    output = cli.execute("setup_collator", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call("newkey"),
        mocker.call(f"addadnl {NEW_KEY} 0"),
        mocker.call(f"add-collator {NEW_KEY}"),
    ]
    assert f"Collator enabled with ADNL address {NEW_KEY}" in output
    assert f"`add_collator {NEW_KEY}`" in output
    assert "setup_collator - OK" in output

    # with --adnl the given address is used as typed
    vc.run.reset_mock()
    output = cli.execute(f"setup_collator --adnl {ADNL_1}", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call(f"addadnl {ADNL_1} 0"),
        mocker.call(f"add-collator {ADNL_1}"),
    ]
    assert "setup_collator - OK" in output

    # the addadnl result is not checked
    vc.run.reset_mock()
    responses["addadnl"] = "error: failed to add adnl"
    output = cli.execute(f"setup_collator --adnl {ADNL_2}", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call(f"addadnl {ADNL_2} 0"),
        mocker.call(f"add-collator {ADNL_2}"),
    ]
    assert "setup_collator - OK" in output

    # add-collator failure
    responses["add-collator"] = "error: collator already exists"
    output = cli.execute(f"setup_collator --adnl {ADNL_2}", no_color=True)
    assert "Failed to enable collator: add-collator query failed: error: collator already exists" in output
    assert "setup_collator - OK" not in output


def test_print_local_collators(cli, local_collators):
    output = cli.execute("print_local_collators", no_color=True)
    local_collators.assert_called_once_with()
    assert "Collators list:" in output
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert lines[lines.index("Collators list:") + 1:] == ["ADNL Address", ADNL_1, ADNL_2]

    local_collators.return_value = Dict({"collators": []})
    output = cli.execute("print_local_collators", no_color=True)
    assert "No collators found" in output

    # No usage check today: extra args are silently ignored
    output = cli.execute("print_local_collators extra", no_color=True)
    assert "No collators found" in output


def test_add_validator_to_collation_wl(cli, vc, mocker: MockerFixture):
    # Bad args
    output = cli.execute("add_validator_to_collation_wl", no_color=True)
    assert "Bad args" in output
    vc.run.assert_not_called()

    output = cli.execute(f"add_validator_to_collation_wl {ADNL_1}", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call("collator-whitelist-enable 1"),
        mocker.call(f"collator-whitelist-add {ADNL_1}"),
    ]
    assert "Collation whitelist enabled" in output
    assert "add_validator_to_collation_wl - OK" in output

    vc.run.reset_mock()
    output = cli.execute(f"add_validator_to_collation_wl {ADNL_1} {ADNL_2}", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call("collator-whitelist-enable 1"),
        mocker.call(f"collator-whitelist-add {ADNL_1}"),
        mocker.call(f"collator-whitelist-add {ADNL_2}"),
    ]
    assert "add_validator_to_collation_wl - OK" in output

    # the first failing add stops the loop (the enable result is not checked)
    vc.run.reset_mock()
    vc.run.side_effect = lambda cmd: "error: bad adnl" if ADNL_1 in cmd else "success"
    output = cli.execute(f"add_validator_to_collation_wl {ADNL_1} {ADNL_2}", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call("collator-whitelist-enable 1"),
        mocker.call(f"collator-whitelist-add {ADNL_1}"),
    ]
    assert "Failed to add validator to collation whitelist: error: bad adnl" in output
    assert "add_validator_to_collation_wl - OK" not in output


def test_delete_validator_from_collation_wl(cli, vc, mocker: MockerFixture):
    # Bad args
    output = cli.execute("delete_validator_from_collation_wl", no_color=True)
    assert "Bad args" in output
    vc.run.assert_not_called()

    output = cli.execute(f"delete_validator_from_collation_wl {ADNL_1} {ADNL_2}", no_color=True)
    assert vc.run.call_args_list == [
        mocker.call(f"collator-whitelist-del {ADNL_1}"),
        mocker.call(f"collator-whitelist-del {ADNL_2}"),
    ]
    assert "delete_validator_from_collation_wl - OK" in output

    vc.run.reset_mock()
    vc.run.side_effect = lambda cmd: "error: not found" if ADNL_1 in cmd else "success"
    output = cli.execute(f"delete_validator_from_collation_wl {ADNL_1} {ADNL_2}", no_color=True)
    vc.run.assert_called_once_with(f"collator-whitelist-del {ADNL_1}")
    assert "Failed to delete validator from collation whitelist: error: not found" in output
    assert "delete_validator_from_collation_wl - OK" not in output


def test_disable_collation_wl(cli, vc):
    # Bad args
    output = cli.execute("disable_collation_wl extra", no_color=True)
    assert "Bad args" in output
    vc.run.assert_not_called()

    output = cli.execute("disable_collation_wl", no_color=True)
    vc.run.assert_called_once_with("collator-whitelist-enable 0")
    assert "disable_collation_validator_wl - OK" in output

    vc.run.return_value = "error: failed"
    output = cli.execute("disable_collation_wl", no_color=True)
    assert "Failed to disable collation validator whitelist: error: failed" in output
    assert "- OK" not in output


def test_print_collation_whitelist(cli, vc):
    vc.run.return_value = 'connecting to [127.0.0.1:44444]\nconn ready\n{\n  "enabled": true\n}\n'
    output = cli.execute("print_collation_whitelist", no_color=True)
    vc.run.assert_called_once_with("collator-whitelist-show")
    assert '{\n  "enabled": true\n}' in output

    # the text after "conn ready" is printed as-is; without it the handler crashes
    vc.run.return_value = "error: timeout"
    output = cli.execute("print_collation_whitelist", no_color=True)
    assert "list index out of range" in output

    # No usage check today: extra args are silently ignored
    vc.run.return_value = "conn ready\nwhitelist"
    output = cli.execute("print_collation_whitelist extra", no_color=True)
    assert "whitelist" in output


def test_stop_collator(cli, vc, local_collators, monkeypatch, mocker: MockerFixture):
    input_mock = mocker.Mock(return_value="y")
    monkeypatch.setattr("builtins.input", input_mock)
    vc.run.return_value = "Successfully removed collator"

    # Bad args
    output = cli.execute(f"stop_collator {ADNL_1} {ADNL_2}", no_color=True)
    assert "Bad args" in output
    vc.run.assert_not_called()
    input_mock.assert_not_called()

    # with adnl: no confirmation, one del-collator with the address as typed
    output = cli.execute(f"stop_collator {ADNL_1}", no_color=True)
    vc.run.assert_called_once_with(f"del-collator {ADNL_1}")
    input_mock.assert_not_called()
    local_collators.assert_not_called()
    assert "stop_collator - OK" in output

    vc.run.reset_mock()
    vc.run.return_value = "error: collator not found"
    output = cli.execute(f"stop_collator {ADNL_1}", no_color=True)
    assert "Failed to disable collator: del-collator query failed: error: collator not found" in output
    assert "stop_collator - OK" not in output

    # without adnl: asks for confirmation, then removes every local collator
    vc.run.reset_mock()
    vc.run.return_value = "successfully removed collator"
    output = cli.execute("stop_collator", no_color=True)
    assert "WARNING: This action will stop and delete all local collation broadcasts from this node." in output
    input_mock.assert_called_once_with("Continue anyway? [Y/n]\n")
    assert vc.run.call_args_list == [
        mocker.call(f"del-collator {ADNL_1}"),
        mocker.call(f"del-collator {ADNL_2}"),
    ]
    assert "stop_collator - OK" in output

    # an empty answer means yes
    vc.run.reset_mock()
    input_mock.return_value = ""
    output = cli.execute("stop_collator", no_color=True)
    assert vc.run.call_count == 2
    assert "stop_collator - OK" in output

    # anything else aborts before reading the node config
    vc.run.reset_mock()
    local_collators.reset_mock()
    input_mock.return_value = "n"
    output = cli.execute("stop_collator", no_color=True)
    assert "aborted." in output
    local_collators.assert_not_called()
    vc.run.assert_not_called()

    # every collator is attempted, failures are reported together
    input_mock.return_value = "y"
    vc.run.side_effect = lambda cmd: "error: busy" if ADNL_1 in cmd else "success"
    output = cli.execute("stop_collator", no_color=True)
    assert vc.run.call_count == 2
    assert "Failed to delete some collators: error: busy" in output
    assert "stop_collator - OK" not in output

    # nothing to stop
    vc.run.reset_mock()
    local_collators.return_value = Dict({"collators": []})
    output = cli.execute("stop_collator", no_color=True)
    assert "No collators found" in output
    vc.run.assert_not_called()
