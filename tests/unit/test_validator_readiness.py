import io
import json
import logging
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from mytoninstaller import settings
from mytoninstaller import __main__ as installer
from mytoninstaller.context import InstallerPaths


@pytest.fixture
def readiness(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    paths = InstallerPaths(ton_work_dir=str(tmp_path / "work") + "/")
    Path(paths.keys_dir).mkdir(parents=True)
    Path(paths.ton_db_dir).mkdir()
    for name in ("client", "client.pub", "server.pub"):
        (Path(paths.keys_dir) / name).write_bytes(b"original " + name.encode())
    Path(paths.vconfig_path).write_text(
        '{"control": [], "liteservers": [], "addrs": [{}]}'
    )
    core = tmp_path / "work/controller/mytoncore/mytoncore.db"
    core.parent.mkdir(parents=True)
    core.write_text('{"liteClient": {}}')
    ctx = SimpleNamespace(
        paths=paths,
        mconfig_path=str(core),
        user="root",
        validator_user="validator",
        ports=SimpleNamespace(validator_console=30004, quic=None),
        only_mtc=False,
        backup=None,
    )
    messages = []
    local = SimpleNamespace(add_log=lambda message, mode: messages.append(message))
    elapsed = [0.0]
    monkeypatch.setattr(settings.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(
        settings.time,
        "sleep",
        lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )
    monkeypatch.setattr(
        settings,
        "_ensure_node_key",
        lambda *args: ("server-id", Path(paths.ton_db_dir) / "keyring/server"),
    )
    monkeypatch.setattr(settings, "_ensure_client_key", lambda *args: "client-id")
    monkeypatch.setattr(settings, "_start_validator", lambda *args: None)
    events = []
    probes = []
    states = ["SubState=RUNNING\nMainPID=10\nExecMainStatus=0\n"]

    def run(args, **kwargs):
        if args[:3] == ["systemctl", "show", "validator"]:
            assert kwargs["timeout"] == 5
            assert kwargs["capture_output"] and kwargs["text"] and kwargs["check"]
            state = states.pop(0) if len(states) > 1 else states[0]
            return subprocess.CompletedProcess(args, 0, stdout=state, stderr="")
        assert args[0] == "chown"
        assert kwargs["check"]
        return subprocess.CompletedProcess(args, 0)

    def ready(cmd, timeout):
        assert cmd == "getstats" and timeout == 5
        probes.append(cmd)
        return "unixtime\t\t\t1720000000\nmasterchainblocktime\t\t\t0\n"

    console = SimpleNamespace(run=ready)
    console_args = []
    monkeypatch.setattr(settings.subprocess, "run", run)
    monkeypatch.setattr(
        settings, "ValidatorConsole", lambda *args: console_args.append(args) or console
    )
    monkeypatch.setattr(
        settings, "_run_as_installer_user", lambda *args: events.append(args)
    )
    return SimpleNamespace(
        ctx=ctx,
        local=local,
        elapsed=elapsed,
        messages=messages,
        events=events,
        probes=probes,
        states=states,
        console=console,
        console_args=console_args,
    )


def test_slow_start_runs_only_readonly_probes_before_event(readiness):
    runtime = readiness

    def slow(cmd, timeout):
        assert runtime.events == []
        assert cmd == "getstats" and timeout == 5
        runtime.probes.append(cmd)
        if len(runtime.probes) < 3:
            raise subprocess.TimeoutExpired(["validator-console", "getstats"], timeout)
        return "unixtime\t\t\t1720000000\n"

    runtime.console.run = slow
    settings.EnableValidatorConsole(runtime.local, runtime.ctx)
    assert runtime.probes == ["getstats", "getstats", "getstats"]
    assert len(runtime.events) == 1
    assert runtime.events[0][1][-1] == "enableVC"
    args = runtime.console_args[0]
    assert args[2:] == (
        str(Path(runtime.ctx.paths.keys_dir) / "client"),
        str(Path(runtime.ctx.paths.keys_dir) / "server.pub"),
        "127.0.0.1:30004",
    )
    assert any(
        "Waiting for validator console" in message for message in runtime.messages
    )


@pytest.mark.parametrize("state", ["FATAL", "EXITED", "STOPPED"])
def test_stopped_validator_aborts_with_log_reason_before_event(readiness, state):
    runtime = readiness
    runtime.states[:] = [f"SubState={state}\nMainPID=0\nExecMainStatus=1\n"]
    Path(runtime.ctx.paths.ton_log_path).write_text(
        "INFO opening DB\nFATAL RocksDB: manifest is corrupt\nINFO stopping\n"
    )
    with pytest.raises(RuntimeError, match="manifest is corrupt") as error:
        settings.EnableValidatorConsole(runtime.local, runtime.ctx)
    assert f"{state}, exit 1" in str(error.value)
    assert runtime.probes == []
    assert runtime.events == []


def test_repeated_pid_changes_abort_a_restart_loop(readiness):
    runtime = readiness
    runtime.states[:] = [
        f"SubState=STARTING\nMainPID={pid}\nExecMainStatus=1\n"
        for pid in (10, 11, 12, 13)
    ]
    Path(runtime.ctx.paths.ton_log_path).write_text(
        "ERROR Cannot open database: too many open files\n"
    )

    def unavailable(cmd, timeout):
        runtime.probes.append(cmd)
        raise subprocess.TimeoutExpired(["console", cmd], timeout)

    runtime.console.run = unavailable
    with pytest.raises(RuntimeError, match="repeatedly restarted") as error:
        settings.EnableValidatorConsole(runtime.local, runtime.ctx)
    assert "too many open files" in str(error.value)
    assert runtime.probes == []
    assert runtime.events == []


def test_starting_and_backoff_states_wait_without_console_queries(readiness):
    runtime = readiness
    runtime.states[:] = [
        "SubState=STARTING\nMainPID=10\nExecMainStatus=0\n",
        "SubState=BACKOFF\nMainPID=0\nExecMainStatus=1\n",
        "SubState=RUNNING\nMainPID=11\nExecMainStatus=0\n",
    ]
    settings.EnableValidatorConsole(runtime.local, runtime.ctx)
    assert runtime.probes == ["getstats"]
    assert len(runtime.events) == 1
    assert runtime.elapsed[0] == 4


def test_deadline_rejects_non_statistics_and_never_completes_stage(
    readiness, monkeypatch
):
    runtime = readiness
    monkeypatch.setattr(settings, "_VALIDATOR_CONSOLE_READY_TIMEOUT", 6)
    runtime.console.run = lambda *args, **kwargs: (
        "query failed: validator is not ready\n"
    )
    keys = {
        path.name: path.read_bytes()
        for path in Path(runtime.ctx.paths.keys_dir).iterdir()
    }
    marker = Path(runtime.ctx.paths.ton_work_dir) / "controller/node-initialized.json"
    marker.write_text('{"version": 1}')
    with pytest.raises(RuntimeError, match="within 6s"):
        installer._run_installation_stage(
            runtime.local,
            runtime.ctx,
            "validator_console",
            settings.EnableValidatorConsole,
        )
    progress = json.loads((marker.parent / "installer-progress.json").read_text())
    assert progress["status"] == "failed"
    assert "validator_console" not in progress["completed"]
    assert runtime.events == []
    assert json.loads(marker.read_text()) == {"version": 1}
    assert keys == {
        path.name: path.read_bytes()
        for path in Path(runtime.ctx.paths.keys_dir).iterdir()
    }
    assert not json.loads(Path(runtime.ctx.mconfig_path).read_text()).get(
        "containerEnableVcComplete"
    )


def test_waiting_status_is_periodic_during_slow_database_open(readiness, monkeypatch):
    runtime = readiness
    monkeypatch.setattr(settings, "_VALIDATOR_CONSOLE_POLL_INTERVAL", 10)
    count = [0]

    def slow(cmd, timeout):
        count[0] += 1
        if count[0] < 8:
            return "opening database"
        return "unixtime 1720000000\n"

    runtime.console.run = slow
    settings.EnableValidatorConsole(runtime.local, runtime.ctx)
    waits = [
        message
        for message in runtime.messages
        if message.startswith("Waiting for validator console")
    ]
    assert len(waits) == 3
    assert [
        f"({seconds}s elapsed)" in waits[index]
        for index, seconds in enumerate((0, 30, 60))
    ] == [True, True, True]
    assert len(runtime.events) == 1


def test_failure_keeps_bounded_full_tail_in_file_only(readiness, tmp_path):
    runtime = readiness
    path = Path(runtime.ctx.paths.ton_log_path)
    path.write_text(
        "old-log-line\n" * 2000 + "recent context\nERROR Cannot bind validator port\n"
    )
    stdout = io.StringIO()
    file = tmp_path / "installer.log"
    logger = logging.Logger("validator-readiness-test")
    logger.propagate = False
    console_handler = logging.StreamHandler(stdout)
    file_handler = logging.FileHandler(file)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    runtime.local.logger = logger
    try:
        failure = settings._validator_failure(runtime.local, "Validator stopped", path)
        assert "Cannot bind validator port" in str(failure)
        assert stdout.getvalue() == ""
        contents = file.read_text()
        assert "recent context\nERROR Cannot bind validator port" in contents
        assert len(contents) < 8192
        assert contents.count("old-log-line") < 40
    finally:
        file_handler.close()
        console_handler.close()


def test_start_failure_reports_ton_fatal_reason(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    monkeypatch.setenv("TON_WORK_DIR", str(tmp_path))
    (tmp_path / "log").write_text("FATAL Database error: No space left on device\n")
    local = SimpleNamespace(add_log=lambda *args: None)

    def fail(args, **kwargs):
        assert args == ["systemctl", "restart", "validator"] and kwargs["check"]
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(settings.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="No space left on device"):
        settings._start_validator(local)


def test_host_service_start_and_readiness_behavior_are_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "is_container", lambda: False)
    calls = []
    monkeypatch.setattr(settings, "StartValidator", lambda local: calls.append(local))

    def forbidden(*args, **kwargs):
        raise AssertionError("Container readiness must not run on a host install")

    monkeypatch.setattr(settings.subprocess, "run", forbidden)
    monkeypatch.setattr(settings, "GetConfig", forbidden)
    local = SimpleNamespace()
    settings._start_validator(local)
    settings._wait_validator_console(local, None)
    assert calls == [local]
