import subprocess
import sys

import pytest

from modules import general
from mytonctrl import utils


@pytest.fixture
def container_benchmark(ton, monkeypatch, tmp_path):
    work = tmp_path / "ton-work"
    controller = work / "controller"
    controller.mkdir(parents=True)
    (controller / "initialized.json").write_text("{}")
    ton.local.db["paths"] = {
        "ton_work": str(work),
        "ton_bin": str(tmp_path / "binaries"),
        "ton_src": str(tmp_path / "resources"),
    }
    monkeypatch.setattr(general, "is_container", lambda: True)
    monkeypatch.setattr(utils, "is_container", lambda: True)
    monkeypatch.setattr(general, "get_service_state", lambda name: "STOPPED")
    monkeypatch.setattr(general, "get_service_status", lambda name: pytest.fail("native service guard ran"))
    monkeypatch.setattr(general.shutil, "which", lambda name: pytest.fail("native uv lookup ran"))
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("container requested uv installation"))
    monkeypatch.setattr(general.shutil, "copytree", lambda *args: pytest.fail("native TON test tree copied"))
    calls = []

    def run(args, **kwargs):
        calls.append((list(args), kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(general.subprocess, "run", run)
    return work, calls


@pytest.mark.parametrize("state", ["STOPPED", "FATAL"])
def test_container_benchmark_runs_packaged_helper_without_native_setup(
    cli, ton, monkeypatch, container_benchmark, state,
):
    work, calls = container_benchmark
    monkeypatch.setattr(general, "get_service_state", lambda name: state)
    output = cli.execute("benchmark --nodes 4 --tps 1000 --duration 60", no_color=True)

    paths = ton.get_paths()
    assert calls == [([
        sys.executable, "/usr/local/lib/mytonctrl/benchmark.py",
        "--build-dir", str(paths.ton_bin),
        "--source-dir", str(paths.ton_src),
        "--work-root", str(work), "--",
        "--nodes", "4", "--tps", "1000", "--duration", "60",
    ], {"check": True})]
    assert "uv" not in output


@pytest.mark.parametrize("state", [
    "RUNNING", "STARTING", "BACKOFF", "STOPPING", "EXITED", "unknown", None,
])
def test_container_benchmark_rejects_validator_that_is_not_explicitly_stopped(
    cli, monkeypatch, container_benchmark, state,
):
    _, calls = container_benchmark
    monkeypatch.setattr(general, "get_service_state", lambda name: state)

    output = cli.execute("benchmark --duration 60", no_color=True)

    assert calls == []
    assert "docker compose exec" in output
    assert "systemctl stop validator" in output


def test_container_benchmark_requires_completed_initialization(cli, container_benchmark):
    work, calls = container_benchmark
    (work / "controller/initialized.json").unlink()
    (work / "controller/.initializing").write_text("{}")

    output = cli.execute("benchmark", no_color=True)

    assert calls == []
    assert "initialization" in output.lower()


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_container_benchmark_help_is_available_while_validator_runs(
    cli, monkeypatch, container_benchmark, flag,
):
    _, calls = container_benchmark
    monkeypatch.setattr(general, "get_service_state", lambda name: pytest.fail("help queried validator service"))

    cli.execute(f"benchmark -- {flag}", no_color=True)

    assert len(calls) == 1
    assert calls[0][0][-2:] == ["--", flag]


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_container_benchmark_console_help_does_not_query_validator(
    cli, monkeypatch, container_benchmark, flag,
):
    _, calls = container_benchmark
    monkeypatch.setattr(general, "get_service_state", lambda name: pytest.fail("help queried validator service"))

    output = cli.execute(f"benchmark {flag}", no_color=True)

    assert "usage: benchmark" in output
    assert "--tmp-dir" in output
    assert calls == []


def test_container_benchmark_forwards_parsed_tmp_dir(cli, container_benchmark):
    _, calls = container_benchmark

    cli.execute("benchmark --tmp-dir /mounted/benchmark --duration 60", no_color=True)

    assert len(calls) == 1
    assert calls[0][0][-5:] == ["--", "--tmp-dir", "/mounted/benchmark", "--duration", "60"]
