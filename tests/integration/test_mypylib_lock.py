import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from mypylib.mypylib import MyPyClass

# flock is scoped to a process, so cross-process behaviour needs real children.
_mp = multiprocessing.get_context("fork")


def _bare_instance() -> MyPyClass:
    # lock_file() touches no instance state, so a bare instance exercises it fully.
    return object.__new__(MyPyClass)


def _hold_lock(target: str, acquired_marker: str, hold_seconds: float) -> None:
    """Child-process body: acquire the lock, announce it, then keep holding it."""
    with _bare_instance().lock_file(target):
        Path(acquired_marker).touch()
        time.sleep(hold_seconds)


def _wait_for_file(path: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not os.path.exists(path):
        if time.monotonic() >= deadline:
            raise AssertionError(f"timed out waiting for {path!r}")
        time.sleep(0.01)


@pytest.fixture
def target(tmp_path) -> str:
    return str(tmp_path / "node.db")


def test_lock_creates_and_keeps_sidecar(target):
    lock_path = target + ".lock"
    with _bare_instance().lock_file(target):
        assert os.path.isfile(lock_path)
    # The sidecar is a persistent flock anchor — it must outlive the lock scope.
    assert os.path.isfile(lock_path)


def test_lock_can_be_reacquired_after_release(target):
    inst = _bare_instance()
    with inst.lock_file(target):
        pass
    with inst.lock_file(target):  # must not raise or block
        pass


def test_lock_is_released_even_if_body_raises(target):
    inst = _bare_instance()
    with pytest.raises(ValueError):
        with inst.lock_file(target):
            raise ValueError("boom")
    # The lock must be free again — re-acquiring it must succeed immediately.
    start = time.monotonic()
    with inst.lock_file(target, timeout=1.0):
        pass
    assert time.monotonic() - start < 0.5


def test_preexisting_lock_file_does_not_block(target):
    # A .lock file left behind by a crashed process must not block acquisition:
    # the flock, not the file's existence, is what holds the lock.
    Path(target + ".lock").touch()
    start = time.monotonic()
    with _bare_instance().lock_file(target, timeout=3.0):
        pass
    assert time.monotonic() - start < 1.0


def test_nested_acquisition_times_out(target):
    inst = _bare_instance()
    with inst.lock_file(target):
        start = time.monotonic()
        with pytest.raises(Exception, match="time out"):
            with inst.lock_file(target, timeout=0.2):
                pass
        elapsed = time.monotonic() - start
        assert 0.19 <= elapsed < 2.0


def test_lock_blocks_another_process(tmp_path, target):
    marker = str(tmp_path / "acquired")
    holder = _mp.Process(target=_hold_lock, args=(target, marker, 1.0))
    holder.start()
    try:
        _wait_for_file(marker)
        start = time.monotonic()
        with pytest.raises(Exception, match="time out"):
            with _bare_instance().lock_file(target, timeout=0.3):
                pass
        assert time.monotonic() - start >= 0.29
    finally:
        holder.join(timeout=10)
    assert holder.exitcode == 0


def test_lock_released_when_holder_is_killed(tmp_path, target):
    marker = str(tmp_path / "acquired")
    holder = _mp.Process(target=_hold_lock, args=(target, marker, 30.0))
    holder.start()
    try:
        _wait_for_file(marker)
        holder.kill()  # SIGKILL the holder while it still holds the lock
        holder.join(timeout=10)
        assert not holder.is_alive()
        # The kernel drops the flock on process death — no stale lock remains.
        start = time.monotonic()
        with _bare_instance().lock_file(target, timeout=3.0):
            pass
        assert time.monotonic() - start < 1.0
    finally:
        if holder.is_alive():
            holder.kill()
            holder.join()


def test_write_db_writes_under_the_lock(tmp_path):
    inst = _bare_instance()
    inst.db_path = str(tmp_path / "node.db")
    inst.write_db({"alpha": 1, "beta": [2, 3]})

    assert json.loads(Path(inst.db_path).read_text()) == {"alpha": 1, "beta": [2, 3]}
    assert os.path.isfile(os.path.realpath(inst.db_path) + ".lock")
