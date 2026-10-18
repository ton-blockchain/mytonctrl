import json

import pytest

from mypylib.mypylib import Dict
from modules import general
from mytonctrl.warnings import WarningChecker
from mytonctrl import utils
from mytonctrl import mytonctrl as application
from mytonctrl import warnings
from tests.conftest import TestLocal, TestMyPyConsole


@pytest.fixture
def initializing_node(ton, tmp_path, monkeypatch):
    work = tmp_path / "ton-work"
    controller = work / "controller"
    controller.mkdir(parents=True)
    (controller / ".initializing").touch()  # Legacy marker remains readable.
    database = work / "db"
    database.mkdir()
    (database / "config.json").write_text(json.dumps({
        "addrs": [{"@type": "engine.addr", "port": 30303}],
    }))
    ton.local.db["paths"] = {"ton_work": str(work), "ton_db": str(database)}
    ton.local.db.pop("validatorConsole", None)
    ton._validator_console = None
    ton.local.db_path = str(tmp_path / "controller.db")
    with open(ton.local.db_path, "w") as config:
        json.dump(ton.local.db, config)
    monkeypatch.setattr(general, "is_container", lambda: True)
    monkeypatch.setattr(utils, "is_container", lambda: True)
    monkeypatch.setattr(application, "is_container", lambda: True)
    monkeypatch.setattr(warnings, "is_container", lambda: True)
    monkeypatch.setattr(general, "get_service_status", lambda name: False)
    monkeypatch.setattr(general, "get_service_state", lambda name: "STOPPED")
    monkeypatch.setattr(general, "get_service_uptime", lambda name: None)
    monkeypatch.setattr(general, "get_bin_git_hash", lambda *args, **kwargs: "ton-build")
    return work


def test_status_works_during_dump_before_validator_console_exists(cli, ton, initializing_node):
    cache = initializing_node / "dump-cache"
    cache.mkdir()
    (cache / "dump-state.json").write_text(json.dumps({
        "version": 1, "phase": "downloading", "archive_name": "dump.tar.lz",
        "archive_size": 263000000000,
    }))
    (initializing_node / "controller/installer-progress.json").write_text(json.dumps({
        "version": 1, "stage": "node_settings", "status": "running",
    }))

    output = cli.execute("status", no_color=True)

    assert "Traceback" not in output
    assert "ValidatorConsole is not initialized" not in output
    assert "Node status" in output
    assert "Initialization status: pending" in output
    assert "Installer stage: node_settings (running)" in output
    assert "Dump phase: downloading" in output
    assert f"Dump archive: {cache / 'dump.tar.lz'}" in output
    assert "Dump archive size: 263000000000 bytes" in output
    assert "Node ports: 30303" in output
    assert "Validator console: unavailable (not configured yet)" in output
    assert "Load average" in output
    assert "Memory load" in output
    assert "Mytoncore status: not working, uptime n/a" in output
    assert "Local validator status: not working, uptime n/a" in output
    assert "Local validator out of sync: n/a" in output
    assert "Masterchain out of sync: n/a" in output
    assert "Shardchain out of sync: n/a" in output


def test_container_status_displays_image_references_without_commit_or_branch(
    cli, initializing_node, monkeypatch,
):
    monkeypatch.setattr(general, "get_controller_image_ref", lambda: "ghcr.io/ton-blockchain/mytonctrl:v1.2.3")
    monkeypatch.setattr(general, "get_ton_image_ref", lambda: "ghcr.io/ton-blockchain/ton:v2026.10")
    monkeypatch.setattr(general, "get_git_hash", lambda *args, **kwargs: pytest.fail("container read Git hash"))
    monkeypatch.setattr(general, "get_git_branch", lambda *args, **kwargs: pytest.fail("container read Git branch"))
    monkeypatch.setattr(general, "get_bin_git_hash", lambda *args, **kwargs: pytest.fail("container read binary hash"))

    output = cli.execute("status fast", no_color=True)

    assert "Version mytonctrl: ghcr.io/ton-blockchain/mytonctrl:v1.2.3\n" in output
    assert "Version validator: ghcr.io/ton-blockchain/ton:v2026.10\n" in output
    assert "external image" not in output


@pytest.mark.parametrize("masterchain,shardchain", [(60, 9000), (None, 9000), (60, None)])
def test_container_block_sync_reports_seconds_and_blocks_with_correct_units(
    cli, ton, initializing_node, monkeypatch, masterchain, shardchain,
):
    (initializing_node / "controller/initialized.json").write_text("{}")
    with open(ton.local.db_path) as stream:
        config = json.load(stream)
    config["validatorConsole"] = {
        "appPath": "/usr/bin/ton/validator-engine-console/validator-engine-console",
        "privKeyPath": "/var/ton-work/keys/client",
        "pubKeyPath": "/var/ton-work/keys/server.pub",
        "addr": "127.0.0.1:30304",
    }
    with open(ton.local.db_path, "w") as stream:
        json.dump(config, stream)
    status = Dict({"is_working": False, "out_of_sync": 9000,
                   "masterchain_out_of_sync": masterchain,
                   "shardchain_out_of_sync": shardchain})
    monkeypatch.setattr(ton, "GetValidatorStatus", lambda: status)
    monkeypatch.setattr(ton, "in_initial_sync", lambda: True)

    output = cli.execute("status fast", no_color=True)

    assert "Syncing blocks" in output
    assert "9000 s ago" not in output
    assert "None" not in output
    if masterchain is not None:
        assert "masterchain is 60 sec behind" in output
    if shardchain is not None:
        assert "shardchain is 9000 blocks behind" in output


def test_status_reports_failure_and_ready_marker_overrides_old_failure(cli, initializing_node):
    controller = initializing_node / "controller"
    (controller / "installer-progress.json").write_text(json.dumps({
        "version": 1, "stage": "node_settings", "status": "failed",
        "error": "Dump extraction failed",
    }))
    output = cli.execute("status fast", no_color=True)
    assert "Initialization status: failed" in output
    assert "Initialization error: Dump extraction failed" in output

    (controller / "initialized.json").write_text("{}")
    output = cli.execute("status fast", no_color=True)
    assert "Initialization status: ready" in output
    assert "Initialization error:" not in output


@pytest.mark.parametrize("saved_cache", [None, "custom-cache"])
def test_status_uses_pending_dump_cache_instead_of_changed_container_environment(
    cli, initializing_node, monkeypatch, saved_cache,
):
    environment = {"MODE": "validator"}
    cache = initializing_node / (saved_cache or "dump-cache")
    if saved_cache:
        environment["DUMP_CACHE_DIR"] = str(cache)
    (initializing_node / "controller/.initializing").write_text(json.dumps({
        "version": 1, "installer_environment": environment,
    }))
    cache.mkdir()
    (cache / "dump-state.json").write_text(json.dumps({
        "version": 1, "phase": "extracting", "archive_name": "pinned.tar.lz",
    }))
    changed_cache = initializing_node / "changed-cache"
    changed_cache.mkdir()
    (changed_cache / "dump-state.json").write_text(json.dumps({
        "version": 1, "phase": "downloading", "archive_name": "other.tar.lz",
    }))
    monkeypatch.setenv("DUMP_CACHE_DIR", str(changed_cache))

    output = cli.execute("status fast", no_color=True)

    assert "Dump phase: extracting" in output
    assert f"Dump cache: {cache}" in output
    assert f"Dump archive: {cache / 'pinned.tar.lz'}" in output
    assert "other.tar.lz" not in output
    assert str(changed_cache) not in output


def test_status_ignores_partial_state_files_and_missing_database(cli, ton, initializing_node, monkeypatch):
    controller = initializing_node / "controller"
    (controller / "installer-progress.json").write_text('{"stage":')
    cache = initializing_node / "dump-cache"
    cache.mkdir()
    (cache / "dump-state.json").write_text("[]")
    monkeypatch.setattr(ton, "GetDbUsage", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    output = cli.execute("status fast", no_color=True)
    assert "Traceback" not in output
    assert "Initialization status: pending" in output
    assert "Mytoncore status: not working" in output
    assert "Local validator database size:" in output
    assert "n/a" in output


def test_status_refreshes_console_configuration_written_after_console_opens(cli, ton, initializing_node, monkeypatch):
    assert ton._validator_console is None
    with open(ton.local.db_path) as file:
        config = json.load(file)
    config["validatorConsole"] = {
        "appPath": "/usr/bin/ton/validator-engine-console/validator-engine-console",
        "privKeyPath": "/var/ton-work/keys/client",
        "pubKeyPath": "/var/ton-work/keys/server.pub",
        "addr": "127.0.0.1:30304",
    }
    with open(ton.local.db_path, "w") as file:
        json.dump(config, file)
    monkeypatch.setattr(ton, "GetValidatorStatus", lambda: Dict({"is_working": False}))

    output = cli.execute("status fast", no_color=True)

    assert ton.validatorConsole.addr == "127.0.0.1:30304"
    assert "Validator console: unavailable" in output
    assert "not configured yet" not in output
    assert "Local validator out of sync: n/a" in output
    assert "Traceback" not in output


def test_interactive_start_shows_status_even_with_startup_checks_disabled(cli, ton, initializing_node, monkeypatch, capsys):
    monkeypatch.setattr(TestLocal, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(TestMyPyConsole, "run", lambda self: None)
    monkeypatch.setattr(cli.mtc, "_pre_up", lambda: pytest.fail("startup checks ran"))
    cli.mtc.run(skip_startup_checks=True)
    output = capsys.readouterr().out
    assert "Node status" in output
    assert "Initialization status: pending" in output
    assert "Validator console: unavailable" in output


def test_incomplete_console_skips_unavailable_validator_warnings(cli, ton, initializing_node, monkeypatch):
    for name in ("check_sync", "check_adnl", "check_validator_balance", "check_slashed", "check_node_port"):
        monkeypatch.setattr(WarningChecker, name, lambda self: pytest.fail("validator warning ran"))
    monkeypatch.setattr(WarningChecker, "check_mytonctrl_update", lambda self: None)
    monkeypatch.setattr(WarningChecker, "check_installer_user", lambda self: pytest.fail("user check ran"))
    monkeypatch.setattr(WarningChecker, "check_vport", lambda self: pytest.fail("port check ran"))
    output = cli.run_pre_up(no_color=True)
    assert "validator warning ran" not in output
    assert "user check ran" not in output
    assert "port check ran" not in output
    assert "ValidatorConsole is not initialized" not in output


@pytest.mark.parametrize("progress", ["running", "failed"])
def test_configured_console_does_not_query_validator_before_initialization_finishes(
    cli, ton, initializing_node, monkeypatch, progress,
):
    (initializing_node / "controller/installer-progress.json").write_text(json.dumps({
        "version": 1, "stage": "validator_console", "status": progress,
    }))
    with open(ton.local.db_path) as file:
        config = json.load(file)
    config["validatorConsole"] = {
        "appPath": "/usr/bin/ton/validator-engine-console/validator-engine-console",
        "privKeyPath": "/var/ton-work/keys/client",
        "pubKeyPath": "/var/ton-work/keys/server.pub",
        "addr": "127.0.0.1:30304",
    }
    with open(ton.local.db_path, "w") as file:
        json.dump(config, file)
    for name in ("GetValidatorStatus", "GetValidatorConfig"):
        monkeypatch.setattr(ton, name, lambda: pytest.fail("premature validator request"))
    output = cli.execute("status fast", no_color=True)
    assert "Initialization status:" in output
    assert "Validator console: unavailable" in output
    assert "Node ports: 30303" in output
    assert "premature validator request" not in output
    assert "timed out" not in output

    for name in ("check_sync", "check_adnl", "check_validator_balance", "check_slashed", "check_node_port",
                 "check_installer_user", "check_vport"):
        monkeypatch.setattr(WarningChecker, name, lambda self: pytest.fail("premature validator warning"))
    monkeypatch.setattr(WarningChecker, "check_mytonctrl_update", lambda self: None)
    output = cli.run_pre_up(no_color=True)
    assert "premature validator warning" not in output
    assert "timed out" not in output


def test_completed_initialization_restores_validator_requests(cli, ton, initializing_node, monkeypatch):
    (initializing_node / "controller/initialized.json").write_text("{}")
    with open(ton.local.db_path) as file:
        config = json.load(file)
    config["validatorConsole"] = {"addr": "127.0.0.1:30304"}
    with open(ton.local.db_path, "w") as file:
        json.dump(config, file)
    calls = []
    monkeypatch.setattr(ton, "GetValidatorStatus", lambda: calls.append("getstats") or Dict({"is_working": False}))
    output = cli.execute("status fast", no_color=True)
    assert "Initialization status: ready" in output
    assert calls == ["getstats"]


@pytest.mark.parametrize("state, detail", [
    ("STARTING", "starting"), ("BACKOFF", "restarting"), ("EXITED", "failed"),
    ("FATAL", "failed"), ("RUNNING", "running (initializing)"),
])
def test_pending_status_reports_actual_supervisor_state(
    cli, initializing_node, monkeypatch, state, detail,
):
    monkeypatch.setattr(general, "get_service_status", lambda name: state == "RUNNING")
    monkeypatch.setattr(general, "get_service_state", lambda name: state)
    output = cli.execute("status fast", no_color=True)
    assert f"Local validator status: {detail}" in output
    assert "Local validator status: working" not in output
