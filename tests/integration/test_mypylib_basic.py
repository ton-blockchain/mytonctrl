import json
import sys
from pathlib import Path

import pytest

from mypylib.mypylib import Dict, MyPyClass
from mypylib.logger import setup_logging, DEBUG, INFO


@pytest.fixture
def local(tmp_path: Path, monkeypatch) -> MyPyClass:
    home_dir = tmp_path / "home"
    temp_dir = tmp_path / "tmp"
    home_dir.mkdir()
    temp_dir.mkdir()

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(MyPyClass, "check_root_permission", lambda self: False)
    monkeypatch.setattr(MyPyClass, "get_my_temp_dir", lambda self: str(temp_dir) + '/')

    file_path = tmp_path / "tests_runner.py"
    file_path.write_text("# integration test runner\n")
    return MyPyClass(str(file_path))


def test_mypyclass_initializes_runtime_paths_and_defaults(local, tmp_path):
    expected_work_dir = tmp_path / "home" / ".local" / "share" / "tests_runner"

    assert local.working is True
    assert local.my_name == "tests_runner"
    assert local.my_full_name == "tests_runner.py"
    assert local.my_path == str(tmp_path / "tests_runner.py")
    assert local.my_work_dir == str(expected_work_dir) + '/'
    assert local.my_temp_dir == str(tmp_path / "tmp") + '/'
    assert local.db_path == str(expected_work_dir / "tests_runner.db")
    assert local.log_file_name == str(expected_work_dir / "tests_runner.log")
    assert local.pid_file_path == str(expected_work_dir / "tests_runner.pid")
    assert Path(local.db_path).is_file()

    assert local.db.config.logLevel == INFO
    assert local.db.config.isLimitLogFile is True
    assert local.db.config.isDeleteOldLogFile is False
    assert local.db.config.isStartOnlyOneProcess is True
    assert local.db.config.isLocaldbSaving is False
    assert local.db.config.isWritingLogFile is True
    assert local.db.config.logFileSizeLines == 16384


def test_mypyclass_save_db_syncs_local_and_disk_changes(local):
    db_path = Path(local.db_path)

    local.db.runtime = Dict(enabled=True)
    local.db.config.memoryUsinglimit = 123
    local.save_db()

    persisted = json.loads(db_path.read_text())
    assert persisted["runtime"]["enabled"] is True
    assert persisted["config"]["memoryUsinglimit"] == 123
    assert local.old_db.runtime.enabled is True

    persisted["external"] = {"source": "disk"}
    persisted["config"]["logLevel"] = DEBUG
    db_path.write_text(json.dumps(persisted))

    local.save_db()

    assert local.db.runtime.enabled is True
    assert local.db.external.source == "disk"
    assert local.db.config.logLevel == DEBUG
    assert local.old_db.external.source == "disk"
    assert local.old_db.config.logLevel == DEBUG


def test_mypyclass_file_logging_writes_and_rotates(local):
    local.db.config.logFileSizeLines = 1  # tiny budget forces rotation
    setup_logging(local.db.config.logLevel, local.log_file_name, local.db.config.logFileSizeLines)

    for i in range(500):
        local.add_log(f"log line {i}")

    log_path = Path(local.log_file_name)
    contents = log_path.read_text()

    assert log_path.is_file()
    # The most recent line stays in the active log file...
    assert "log line 499" in contents
    # ...the size cap triggered rotation into a backup file...
    assert Path(str(log_path) + ".1").exists()
    # ...and the file keeps the ANSI color codes (colored output, as before).
    assert "\033" in contents


def test_mypyclass_exit_persists_state_and_cleans_up_pid_file(local, monkeypatch):
    db_path = Path(local.db_path)
    log_path = Path(local.log_file_name)
    pid_path = Path(local.pid_file_path)

    local.db.shutdown = "graceful"
    setup_logging(local.db.config.logLevel, local.log_file_name, local.db.config.logFileSizeLines)
    local.add_log("shutting down")
    local.write_pid()
    assert pid_path.is_file()

    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code=0: exit_codes.append(code))

    local.exit()

    persisted = json.loads(db_path.read_text())
    assert local.working is False
    assert exit_codes == [0]
    assert not pid_path.exists()
    assert persisted["shutdown"] == "graceful"
    assert "shutting down" in log_path.read_text()
