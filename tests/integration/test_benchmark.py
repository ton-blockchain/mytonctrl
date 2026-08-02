import shutil
import subprocess
import stat
from pathlib import Path
from unittest.mock import MagicMock
from modules.general import GeneralModule
from modules import general as general_module


def test_benchmark_uv_not_installed_decline(cli, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append(args))

    cli.execute("benchmark", no_color=True)
    assert len(calls) == 0


def test_benchmark_uv_not_installed_install(cli, monkeypatch):
    installed = {"uv": False}

    def fake_which(name):
        if name == "uv" and installed["uv"]:
            return "/usr/bin/uv"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    calls = []

    def fake_subprocess_run(args, **kwargs):
        calls.append([str(a) for a in args])
        if args[0] == "sh":
            installed["uv"] = True
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    monkeypatch.setattr(general_module, "get_service_status", lambda name: True)

    output = cli.execute("benchmark", no_color=True)
    assert calls[0][:4] == ["curl", "-LsSf", "https://astral.sh/uv/install.sh", "-o"]
    assert calls[0][4] != "/tmp/uv_install.sh"
    assert calls[1] == ["sh", calls[0][4]]


def test_benchmark_validator_running(cli, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(general_module, "get_service_status", lambda name: name == "validator")

    output = cli.execute("benchmark", no_color=True)
    assert "validator service is running" in output


def test_benchmark_tmp_rejects_symlink(cli, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(general_module, "get_service_status", lambda name: False)

    class FakeStat:
        st_mode = stat.S_IFLNK | 0o777

    monkeypatch.setattr(general_module.os, "lstat", lambda path: FakeStat())

    root_calls = []
    monkeypatch.setattr(general_module, "run_as_root", lambda args: root_calls.append(args) or 0)

    output = cli.execute("benchmark", no_color=True)

    assert "benchmark temp path is not a directory" in output
    assert root_calls == []


def test_benchmark_resolves_symlinked_tmp_dir(cli, monkeypatch, tmp_path):
    # Regression: when the temp dir path contains a symlink (e.g. ton_work is a
    # symlink like /var/ton-work -> /mnt/data/ton-work), the cwd passed to uv must be
    # resolved. Otherwise uv's getcwd() (real path) differs from the symlink-prefixed
    # tontester_dir argument, its in-tree workspace-member check fails, and tontester
    # installs non-editable -- hiding the generated `tonapi` package (ModuleNotFoundError).
    # Real filesystem setup FIRST, before Path.mkdir is patched to a no-op below,
    # otherwise real_dir is never created and `link` becomes a dangling symlink.
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)  # symlink prefix, like a symlinked ton_work

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(shutil, "copytree", lambda src, dst: None)
    monkeypatch.setattr(shutil, "copy", lambda src, dst: None)

    # Only pretend the benchmark temp parent is missing; delegate every other path to the
    # real lstat, otherwise a globally-broken os.lstat would also break Path.resolve()
    # (which follows symlinks via lstat) -- the very behavior under test.
    real_lstat = general_module.os.lstat

    def fake_lstat(path):
        if str(path) == "/var/ton-work/tmp":
            raise FileNotFoundError
        return real_lstat(path)

    monkeypatch.setattr(general_module.os, "lstat", fake_lstat)
    monkeypatch.setattr(general_module, "run_as_root", lambda args: 0)
    monkeypatch.setattr(Path, "mkdir", lambda *a, **kw: None)
    monkeypatch.setattr(Path, "glob", lambda self, pattern: [])

    class FakeTemporaryDirectory:
        def __init__(self, dir=None):
            pass

        def __enter__(self):
            return str(link_dir)

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

    monkeypatch.setattr(general_module.tempfile, "TemporaryDirectory", FakeTemporaryDirectory)

    calls = []

    def fake_subprocess_run(args, **kwargs):
        calls.append({"args": [str(a) for a in args], "kwargs": kwargs})
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    cli.execute("benchmark", no_color=True)

    resolved = str(real_dir.resolve())
    assert resolved != str(link_dir)  # sanity: symlink path really differs from its target
    # every uv invocation must run from the resolved real path, never the symlink prefix
    for call in calls:
        assert str(call["kwargs"].get("cwd")) == resolved
    # and the tontester path argument lives under that same resolved dir, so uv's
    # in-tree containment check succeeds and it installs editable
    add_args = calls[1]["args"]
    assert add_args[:3] == ["uv", "add", "--editable"]
    assert add_args[3].startswith(resolved)


def test_benchmark_runs(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(shutil, "copytree", lambda src, dst: None)
    monkeypatch.setattr(shutil, "copy", lambda src, dst: None)

    def fake_lstat(path):
        raise FileNotFoundError

    monkeypatch.setattr(general_module.os, "lstat", fake_lstat)

    root_calls = []

    def fake_run_as_root(args):
        root_calls.append([str(arg) for arg in args])
        return 0

    monkeypatch.setattr(general_module, "run_as_root", fake_run_as_root)

    temp_parent_dirs = []
    benchmark_tmp_dir = tmp_path / "benchmark"
    benchmark_tmp_dir.mkdir()

    class FakeTemporaryDirectory:
        def __init__(self, dir=None):
            temp_parent_dirs.append(dir)

        def __enter__(self):
            return str(benchmark_tmp_dir)

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

    monkeypatch.setattr(general_module.tempfile, "TemporaryDirectory", FakeTemporaryDirectory)

    # mock Path.mkdir and Path.glob used for tl schemes
    monkeypatch.setattr(Path, "mkdir", lambda *a, **kw: None)

    fake_tl = MagicMock()
    fake_tl.__truediv__ = lambda self, other: fake_tl
    fake_tl.glob = lambda pattern: []
    monkeypatch.setattr(Path, "glob", lambda self, pattern: [])

    calls = []

    def fake_subprocess_run(args, **kwargs):
        calls.append({"args": [str(a) for a in args], "kwargs": kwargs})
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    cli.execute("benchmark --nodes 4 --tps 1000", no_color=True)

    assert root_calls == [["mkdir", "-m", "777", "/var/ton-work/tmp"]]
    assert temp_parent_dirs == ["/var/ton-work/tmp"]
    assert len(calls) == 4

    # uv init
    assert calls[0]["args"] == ["uv", "init", "--python", "3.14", "--no-workspace", "--name", "benchmark"]
    assert "cwd" in calls[0]["kwargs"]
    tmp_dir = str(calls[0]["kwargs"]["cwd"])

    # uv add --editable tontester
    add_args = calls[1]["args"]
    assert add_args[:3] == ["uv", "add", "--editable"]
    assert "tontester" in add_args[3]

    # uv run generate_tl.py
    assert calls[2]["args"][:2] == ["uv", "run"]
    assert "generate_tl.py" in calls[2]["args"][2]

    # uv run benchmark.py
    run_args = calls[3]["args"]
    assert run_args[:3] == ["uv", "run", "benchmark.py"]
    assert "--build-dir" in run_args
    assert run_args[run_args.index("--build-dir") + 1] == "/usr/bin/ton"
    assert "--source-dir" in run_args
    assert run_args[run_args.index("--source-dir") + 1] == "/usr/src/ton"
    assert "--work-dir" in run_args
    assert run_args[run_args.index("--work-dir") + 1].endswith("/test/integration/.network")
    assert "--nodes" in run_args
    assert "4" in run_args
    assert "--tps" in run_args
    assert "1000" in run_args
