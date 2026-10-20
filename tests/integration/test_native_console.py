import pytest

from modules import general
from mypylib.mypylib import Dict
from mytonctrl import mytonctrl as application
from mytonctrl import utils, warnings
from mytonctrl.warnings import WarningChecker
from tests.conftest import TestLocal, TestMyPyConsole


@pytest.fixture
def native_console(monkeypatch):
    for module in (application, general, utils, warnings):
        monkeypatch.setattr(module, "is_container", lambda: False)


@pytest.mark.parametrize("skip_checks", [False, True])
def test_native_interactive_start_does_not_add_status_requests(
    cli, ton, native_console, monkeypatch, capsys, skip_checks,
):
    calls = []
    monkeypatch.setattr(TestLocal, "run", lambda self: calls.append("local"))
    monkeypatch.setattr(TestMyPyConsole, "run", lambda self: calls.append("console"))
    monkeypatch.setattr(cli.mtc, "_pre_up", lambda: calls.append("checks"))
    monkeypatch.setattr(
        ton, "GetValidatorStatus", lambda: pytest.fail("unexpected startup status request")
    )
    monkeypatch.setattr(
        general.GeneralModule, "print_status", lambda *args: pytest.fail("unexpected startup summary")
    )

    cli.mtc.run(skip_startup_checks=skip_checks)

    assert calls == (["local", "console"] if skip_checks else ["local", "checks", "console"])
    assert "Node status" not in capsys.readouterr().out


def test_native_single_command_does_not_add_status_or_checks_when_disabled(
    cli, ton, native_console, monkeypatch,
):
    calls = []
    monkeypatch.setattr(TestLocal, "run", lambda self: None)
    monkeypatch.setattr(cli.mtc, "_pre_up", lambda: pytest.fail("startup checks ran"))
    monkeypatch.setattr(
        ton, "GetValidatorStatus", lambda: pytest.fail("unexpected validator query")
    )
    monkeypatch.setattr(
        cli, "run_cmd", lambda command: calls.append(command) or 0
    )

    cli.mtc.run(skip_startup_checks=True, cmd="help")

    assert calls == ["help"]


@pytest.mark.parametrize("configured", [False, True])
def test_native_pre_up_preserves_all_checks_and_their_order(
    cli, ton, native_console, monkeypatch, configured,
):
    if not configured:
        ton.local.db.pop("validatorConsole", None)
    ordered_checks = [
        "check_mytonctrl_update", "check_installer_user", "check_vport",
        "check_disk_usage", "check_sync", "check_adnl", "check_validator_balance",
        "check_vps", "check_tg_channel", "check_slashed", "check_ubuntu_version",
        "check_node_port", "check_ton_http_api_version", "check_nominator_pool_deprecated",
    ]
    calls = []
    for name in ordered_checks:
        monkeypatch.setattr(
            WarningChecker, name, lambda self, name=name: calls.append(name)
        )

    cli.mtc._pre_up()

    assert calls == ordered_checks


def test_native_status_uses_validator_without_container_checkpoint_or_refresh(
    ton, native_console, monkeypatch, tmp_path,
):
    ton.local.db.pop("validatorConsole", None)
    ton.local.db_path = str(tmp_path / "plain-controller.db")
    (tmp_path / "plain-controller.db").write_text("{}")
    calls = []
    status = Dict({"is_working": False})
    monkeypatch.setattr(ton, "GetValidatorStatus", lambda: calls.append("getstats") or status)
    monkeypatch.setattr(ton.local, "load_db", lambda: pytest.fail("container configuration refresh ran"))
    monkeypatch.setattr(
        general.GeneralModule, "print_local_status",
        lambda self, value, full: calls.append((value, full)),
    )

    general.GeneralModule(ton, ton.local).print_status("fast")

    assert calls == ["getstats", (status, False)]


def test_native_status_keeps_validator_errors_visible(ton, native_console, monkeypatch):
    def unavailable():
        raise RuntimeError("Native validator unavailable")

    monkeypatch.setattr(ton, "GetValidatorStatus", unavailable)

    with pytest.raises(RuntimeError, match="Native validator unavailable"):
        general.GeneralModule(ton, ton.local).print_status()
