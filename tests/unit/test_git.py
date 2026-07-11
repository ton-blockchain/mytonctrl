from pathlib import Path

import pytest

from mytonctrl import git as git_module
from mytonctrl.git import check_git


def test_check_git_url_threads_src_dir_and_parses_branch_fragment(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    captured = {}
    monkeypatch.setattr(git_module, "fix_git_config", lambda path: captured.__setitem__("path", path))

    result = check_git(
        ["--url", "https://github.com/foo/bar#dev"],
        tmp_path,
        default_repo="ton",
        text="upgrade",
    )

    # the configurable src_dir must reach fix_git_config as a plain string
    assert captured["path"] == str(tmp_path)
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


def test_check_git_falls_back_to_defaults_when_src_dir_absent(monkeypatch):
    # A missing src dir is not a git repo: resolve to the upstream defaults so
    # update/upgrade can re-clone, instead of aborting.
    monkeypatch.setattr(git_module, "check_branch_exists", lambda *a: None)

    result = check_git(
        [],
        Path("/no/such/dir/mytonctrl"),
        default_repo="mytonctrl",
        text="update",
        default_branch="master",
    )

    assert result == ("ton-blockchain", "mytonctrl", "master", None)


def test_check_git_args_override_defaults_when_src_dir_absent(monkeypatch):
    # User-supplied values still take precedence over the defaults on the
    # not-a-repo fallback path.
    monkeypatch.setattr(git_module, "check_branch_exists", lambda *a: None)

    result = check_git(
        ["mybranch"],
        Path("/no/such/dir/mytonctrl"),
        default_repo="mytonctrl",
        text="update",
    )

    assert result == ("ton-blockchain", "mytonctrl", "mybranch", None)


def test_check_git_rejects_existing_non_git_src_dir(tmp_path):
    with pytest.raises(Exception, match="update error: .* is not a git repository"):
        check_git([], tmp_path, default_repo="mytonctrl", text="update")


def test_check_git_propagates_operational_error_on_existing_repo(monkeypatch, tmp_path):
    # An existing checkout (.git present) whose git status fails for an
    # operational reason must NOT be silently reset to the upstream defaults:
    # the error has to propagate so the caller aborts and the tree is untouched.
    (tmp_path / ".git").mkdir()

    def boom(_path):
        raise Exception("Failed to check git status: fatal: bad index file")

    monkeypatch.setattr(git_module, "fix_git_config", boom)

    with pytest.raises(Exception, match="Failed to check git status"):
        check_git([], tmp_path, default_repo="ton", text="upgrade")
