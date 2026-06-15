from pathlib import Path

from mytonctrl import git as git_module
from mytonctrl.git import check_git


def test_check_git_url_threads_src_dir_and_parses_branch_fragment(monkeypatch):
    captured = {}
    monkeypatch.setattr(git_module, "fix_git_config", lambda path: captured.__setitem__("path", path))

    result = check_git(
        ["--url", "https://github.com/foo/bar#dev"],
        Path("/opt/src/ton"),
        default_repo="ton",
        text="upgrade",
    )

    # the configurable src_dir must reach fix_git_config as a plain string
    assert captured["path"] == "/opt/src/ton"
    # author/repo are unknown for an explicit url; branch comes from the # fragment
    assert result == (None, None, "dev", "https://github.com/foo/bar")


def test_check_git_url_without_fragment_defaults_to_master(monkeypatch):
    monkeypatch.setattr(git_module, "fix_git_config", lambda path: None)

    result = check_git(
        ["--url", "https://github.com/foo/bar"],
        Path("/usr/src/ton"),
        default_repo="ton",
        text="upgrade",
    )

    assert result == (None, None, "master", "https://github.com/foo/bar")
