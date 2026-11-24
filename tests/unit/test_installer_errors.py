import io
import logging
import sys

import pytest

from mypylib.logger import LogFormatter, ROOT_LOGGER_NAME
from mytoninstaller import __main__ as installer


def test_container_failure_reports_summary_and_retains_file_traceback(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "is_container", lambda: True)
    monkeypatch.setattr(sys, "argv", ["mytoninstaller", "-m", "validator"])

    def fail():
        raise RuntimeError("validator exited: database permission denied")

    monkeypatch.setattr(installer, "mytoninstaller", fail)
    stdout = io.StringIO()
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    console_handler = logging.StreamHandler(stdout)
    console_handler.setFormatter(LogFormatter(colored=False, include_traceback=False))
    logger.addHandler(console_handler)
    file_handler = logging.FileHandler(tmp_path / "installer.log")
    file_handler.setFormatter(LogFormatter(colored=False))
    logger.addHandler(file_handler)

    with pytest.raises(SystemExit) as error:
        installer.main()

    assert error.value.code == 1
    assert "Initialization failed: validator exited: database permission denied" in stdout.getvalue()
    assert "Traceback" not in stdout.getvalue()
    file_handler.flush()
    assert "Traceback" in (tmp_path / "installer.log").read_text()


def test_host_installer_keeps_original_exception(monkeypatch):
    monkeypatch.setattr(installer, "is_container", lambda: False)
    monkeypatch.setattr(sys, "argv", ["mytoninstaller", "-m", "validator"])
    monkeypatch.setattr(installer, "mytoninstaller", lambda: (_ for _ in ()).throw(RuntimeError("failed")))
    with pytest.raises(RuntimeError, match="failed"):
        installer.main()
