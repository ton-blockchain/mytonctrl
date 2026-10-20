"""Run the packaged benchmark framework against the mounted TON binaries."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile

from mypylib.mypylib import run_as_root
from mytoncore.utils import get_package_resource_path


RUNTIME_ROOT = Path("/opt/mytonctrl/benchmark")
REQUIRED_BINARIES = (
    "crypto/create-state", "utils/generate-random-id", "dht-server/dht-server",
    "validator-engine/validator-engine", "validator-engine-console/validator-engine-console",
)
MANAGED_OPTIONS = ("--build-dir", "--source-dir", "--work-dir")


def benchmark_arguments(args):
    """Keep the workload's destructive work directory inside our temporary child."""
    workload = []
    parent = None
    iterator = iter(args)
    for arg in iterator:
        option, separator, value = arg.partition("=")
        if option.startswith("--") and any(name.startswith(option) for name in MANAGED_OPTIONS):
            raise ValueError(f"The container supplies {option}; use --tmp-dir to select benchmark storage")
        if option == "--tmp-dir":
            parent = value if separator else next(iterator, None)
            if not parent or parent.startswith("--"):
                raise ValueError("--tmp-dir requires a directory")
        else:
            workload.append(arg)
    return workload, parent


def check_artifacts(build_dir, source_dir):
    for name in REQUIRED_BINARIES:
        path = build_dir / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"Benchmark requires the mounted TON executable {path}; re-export the TON image artifacts")
    library = build_dir / "tonlib/libtonlibjson.so"
    if not library.is_file() or not os.access(library, os.R_OK):
        raise ValueError(f"Benchmark requires the mounted TON library {library}; re-export the TON image artifacts")
    for name in ("crypto/fift/lib/Fift.fif", "crypto/smartcont/wallet-v3.fif"):
        if not (source_dir / name).is_file():
            raise ValueError(f"Benchmark requires the mounted TON resource {source_dir / name}")


def temporary_parent(work_root, override):
    if override is not None:
        parent = Path(override).expanduser().resolve()
        parent.mkdir(parents=True, exist_ok=True)
    else:
        parent = work_root / "tmp"
        try:
            parent.lstat()
        except FileNotFoundError:
            if run_as_root(["mkdir", "-m", "1777", "--", str(parent)]) != 0:
                raise ValueError(f"Could not create benchmark temporary directory {parent}")
    if not stat.S_ISDIR(parent.lstat().st_mode):
        raise ValueError(f"Benchmark temporary path must be a directory: {parent}")
    return parent


def signal_group(child, sig):
    try:
        os.killpg(child.pid, sig)
    except ProcessLookupError:
        pass


def run_process(cmd):
    # The test nodes inherit this separate process group. Cleanup covers them
    # even if the Python benchmark crashes or the console is interrupted.
    child = subprocess.Popen(cmd, start_new_session=True)
    try:
        try:
            return child.wait()
        except KeyboardInterrupt:
            signal_group(child, signal.SIGINT)
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            return 130
    finally:
        signal_group(child, signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        finally:
            signal_group(child, signal.SIGKILL)
            child.wait()


def run_benchmark(build_dir, source_dir, work_root, args):
    args, override = benchmark_arguments(args)
    python = RUNTIME_ROOT / "venv/bin/python"
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError("The controller image is missing its benchmark runtime; use an image built with benchmark support")
    with get_package_resource_path("mytonctrl", "scripts/benchmark.py") as script:
        if any(arg in ("--help", "-h") for arg in args):
            return run_process([str(python), str(script), *args])
        check_artifacts(build_dir, source_dir)
        parent = temporary_parent(work_root, override)
        with tempfile.TemporaryDirectory(prefix="benchmark-", dir=parent) as directory:
            temporary = Path(directory).resolve()
            resources = temporary / "source"
            resources.mkdir()
            (resources / "crypto").symlink_to((source_dir / "crypto").resolve(), target_is_directory=True)
            cmd = [str(python), str(script), *args,
                   "--build-dir", str(build_dir.resolve()),
                   "--source-dir", str(resources),
                   "--work-dir", str(temporary / "network")]
            return run_process(cmd)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    args = options.args[1:] if options.args[:1] == ["--"] else options.args

    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        return run_benchmark(options.build_dir, options.source_dir, options.work_root, args)
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        sys.exit(1)
