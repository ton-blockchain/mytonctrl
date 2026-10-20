import importlib.util
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


SPEC = importlib.util.spec_from_file_location(
    "docker_benchmark", Path(__file__).resolve().parents[2] / "docker/benchmark.py"
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


@pytest.fixture
def packaged_benchmark(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    python = runtime / "venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("packaged Python 3.14")
    python.chmod(0o755)
    monkeypatch.setattr(benchmark, "RUNTIME_ROOT", runtime)
    build = tmp_path / "ton-bin"
    source = tmp_path / "ton-resources"
    for name in benchmark.REQUIRED_BINARIES:
        executable = build / name
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("official image executable")
        executable.chmod(0o755)
    library = build / "tonlib/libtonlibjson.so"
    library.parent.mkdir()
    library.write_text("official image library")
    for name in ("crypto/fift/lib/Fift.fif", "crypto/smartcont/wallet-v3.fif"):
        resource = source / name
        resource.parent.mkdir(parents=True, exist_ok=True)
        resource.write_text("official image resource")
    work = tmp_path / "ton-work"
    for name in ("db/cells", "keys/client", "dump-cache/dump.tar.lz"):
        data = work / name
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_bytes(("production " + name).encode())
    return build, source, work, runtime


@pytest.mark.parametrize("option", [
    "--build-dir", "--source-dir", "--work-dir", "--build", "--source", "--work",
    "--b", "--s", "--w",
])
@pytest.mark.parametrize("equals", [False, True])
def test_managed_path_overrides_are_rejected_before_any_workload_or_cleanup(
    packaged_benchmark, monkeypatch, option, equals,
):
    build, source, work, _ = packaged_benchmark
    original = (work / "db/cells").read_bytes()
    args = [f"{option}={work / 'db'}"] if equals else [option, str(work / "db")]
    monkeypatch.setattr(benchmark, "run_process", lambda cmd: pytest.fail("workload started"))
    monkeypatch.setattr(
        benchmark.tempfile, "TemporaryDirectory", lambda **kwargs: pytest.fail("temporary storage created")
    )

    with pytest.raises(ValueError, match="container supplies"):
        benchmark.run_benchmark(build, source, work, args)

    assert (work / "db/cells").read_bytes() == original
    assert not (work / "tmp").exists()


@pytest.mark.parametrize("outcome", ["success", "failure", "exception"])
def test_benchmark_cleans_only_its_unique_child_directory(
    packaged_benchmark, monkeypatch, outcome,
):
    build, source, work, runtime = packaged_benchmark
    parent = work / "tmp"
    parent.mkdir()
    (parent / "existing-user-file").write_bytes(b"keep me")
    original = {str(path.relative_to(work)): path.read_bytes() for path in work.rglob("*") if path.is_file()}
    directories = []

    def run(cmd):
        assert cmd[:1] == [str(runtime / "venv/bin/python")]
        assert cmd[2:6] == ["--nodes", "2", "--duration", "60"]
        network = Path(cmd[cmd.index("--work-dir") + 1])
        resources = Path(cmd[cmd.index("--source-dir") + 1])
        assert parent in network.parents
        assert network.parent.name.startswith("benchmark-")
        assert resources.parent == network.parent
        assert (resources / "crypto").resolve() == (source / "crypto").resolve()
        assert cmd[-6:] == [
            "--build-dir", str(build.resolve()), "--source-dir", str(resources),
            "--work-dir", str(network),
        ]
        directories.append(network.parent)
        network.mkdir()
        (network / "test-network-data").write_bytes(b"temporary cells")
        if outcome == "exception":
            raise RuntimeError("benchmark crashed")
        return 0 if outcome == "success" else 1

    monkeypatch.setattr(benchmark, "run_process", run)
    args = ["--nodes", "2", "--duration", "60"]
    if outcome == "exception":
        with pytest.raises(RuntimeError, match="benchmark crashed"):
            benchmark.run_benchmark(build, source, work, args)
    else:
        assert benchmark.run_benchmark(build, source, work, args) == (0 if outcome == "success" else 1)

    assert args == ["--nodes", "2", "--duration", "60"]
    assert all(not directory.exists() for directory in directories)
    assert {str(path.relative_to(work)): path.read_bytes() for path in work.rglob("*") if path.is_file()} == original
    assert (source / "crypto/fift/lib/Fift.fif").read_text() == "official image resource"


@pytest.mark.parametrize("name", [
    "crypto/create-state", "dht-server/dht-server", "tonlib/libtonlibjson.so",
])
def test_missing_optional_artifacts_fail_before_launch_or_temporary_storage(
    packaged_benchmark, monkeypatch, name,
):
    build, source, work, _ = packaged_benchmark
    (build / name).unlink()
    monkeypatch.setattr(benchmark, "run_process", lambda cmd: pytest.fail("workload or download started"))
    monkeypatch.setattr(
        benchmark.tempfile, "TemporaryDirectory", lambda **kwargs: pytest.fail("temporary storage created")
    )

    with pytest.raises(ValueError, match="mounted TON") as error:
        benchmark.run_benchmark(build, source, work, [])

    assert name in str(error.value)
    assert not (work / "tmp").exists()


def test_default_temporary_parent_rejects_symlink(packaged_benchmark, tmp_path):
    _, _, work, _ = packaged_benchmark
    target = tmp_path / "outside"
    target.mkdir()
    (work / "tmp").symlink_to(target)

    with pytest.raises(ValueError, match="must be a directory"):
        benchmark.temporary_parent(work, None)

    assert list(target.iterdir()) == []


def test_custom_temporary_parent_resolves_symlinks(packaged_benchmark, monkeypatch, tmp_path):
    build, source, work, _ = packaged_benchmark
    target = tmp_path / "outside"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target)
    paths = []

    def run(cmd):
        network = Path(cmd[cmd.index("--work-dir") + 1])
        assert target.resolve() in network.parents
        assert alias not in network.parents
        paths.append(network.parent)
        return 0

    monkeypatch.setattr(benchmark, "run_process", run)
    assert benchmark.run_benchmark(build, source, work, ["--tmp-dir", str(alias), "--duration", "60"]) == 0
    assert paths and all(not path.exists() for path in paths)
    assert list(target.iterdir()) == []
    assert not (work / "tmp").exists()


def test_custom_storage_inside_node_database_preserves_existing_data(packaged_benchmark, monkeypatch):
    build, source, work, _ = packaged_benchmark
    database = work / "db"
    original = (database / "cells").read_bytes()

    def run(cmd):
        network = Path(cmd[cmd.index("--work-dir") + 1])
        assert database in network.parents and network.parent != database
        network.mkdir()
        (network / "cells").write_bytes(b"benchmark-only cells")
        return 0

    monkeypatch.setattr(benchmark, "run_process", run)

    assert benchmark.run_benchmark(build, source, work, [f"--tmp-dir={database}"]) == 0
    assert (database / "cells").read_bytes() == original
    assert list(database.iterdir()) == [database / "cells"]


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_uses_packaged_interpreter_without_ton_artifacts_or_work_directory(
    packaged_benchmark, monkeypatch, tmp_path, flag,
):
    _, _, _, runtime = packaged_benchmark
    calls = []
    monkeypatch.setattr(benchmark, "run_process", lambda cmd: calls.append(cmd) or 0)
    absent = tmp_path / "absent"

    assert benchmark.run_benchmark(absent, absent, absent, [flag]) == 0

    assert len(calls) == 1
    assert calls[0][0] == str(runtime / "venv/bin/python")
    assert calls[0][-1] == flag
    assert not absent.exists()


@pytest.mark.parametrize("outcome", ["success", "failure", "interrupt", "terminate"])
def test_subprocess_group_is_cleaned_on_completion_or_interruption(monkeypatch, outcome):
    initial = {"success": 0, "failure": 1, "interrupt": KeyboardInterrupt(), "terminate": SystemExit(143)}[outcome]
    child = SimpleNamespace(pid=12345, wait=Mock(side_effect=[initial, 0, 0, 0]))
    launches = []
    signals = []
    monkeypatch.setattr(benchmark.subprocess, "Popen", lambda cmd, **kwargs: launches.append((cmd, kwargs)) or child)
    monkeypatch.setattr(benchmark.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    if outcome == "terminate":
        with pytest.raises(SystemExit) as error:
            benchmark.run_process(["packaged-python", "benchmark.py"])
        assert error.value.code == 143
    else:
        assert benchmark.run_process(["packaged-python", "benchmark.py"]) == {"success": 0, "failure": 1, "interrupt": 130}[outcome]

    assert launches == [(["packaged-python", "benchmark.py"], {"start_new_session": True})]
    expected = [signal.SIGINT, signal.SIGTERM, signal.SIGKILL] if outcome == "interrupt" else [signal.SIGTERM, signal.SIGKILL]
    assert signals == [(12345, sig) for sig in expected]


def test_main_restores_sigterm_handler_after_interruption(monkeypatch, tmp_path):
    original = signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(sys, "argv", [
        "benchmark.py", "--build-dir", str(tmp_path), "--source-dir", str(tmp_path),
        "--work-root", str(tmp_path), "--", "--duration", "60",
    ])

    def terminate(*args):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler) and handler is not original
        handler(signal.SIGTERM, None)

    monkeypatch.setattr(benchmark, "run_benchmark", terminate)
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 143
    assert signal.getsignal(signal.SIGTERM) is original
