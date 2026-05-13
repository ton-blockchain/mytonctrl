import subprocess
from pathlib import Path
from setuptools.build_meta import *  # re-export all PEP 517 hooks
from setuptools import build_meta as _orig


_PROJECT_ROOT = Path(__file__).resolve().parent


class GitCommitError(Exception):
    pass


def _write_version():
    commit_path = _PROJECT_ROOT / "mytonctrl" / "_commit.py"
    try:
        git_root = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=_PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        ).resolve()
        if git_root != _PROJECT_ROOT:
            raise GitCommitError
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        commit = f'__commit__ = "{sha}"'
    except (subprocess.CalledProcessError, FileNotFoundError, GitCommitError):
        if commit_path.exists():
            return
        commit = '__commit__ = "unknown"'
    commit_path.write_text(f"{commit}\n")


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _write_version()
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _write_version()
    return _orig.build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    _write_version()
    return _orig.build_editable(wheel_directory, config_settings, metadata_directory)
