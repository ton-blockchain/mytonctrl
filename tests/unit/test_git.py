from pathlib import Path
from types import SimpleNamespace

import pytest

from mypyconsole.command_parser import UsageError
from mytonctrl import git as git_module
from mytonctrl.git import GitTarget, check_branch_exists, check_git, parse_git_target


@pytest.mark.parametrize("args, kwargs, expected", [
    ((None,), {}, GitTarget()),
    ((None,), {"branch": "dev"}, GitTarget(branch="dev")),
    (("dev",), {}, GitTarget(branch="dev")),
    (("https://github.com/x/y",), {}, GitTarget("x", "y")),
    (("https://github.com/x/y", "dev"), {}, GitTarget("x", "y", "dev")),
    (("https://github.com/x/y/tree/dev",), {}, GitTarget("x", "y", "dev")),
    (("https://github.com/x/y/tree/feature/foo",), {}, GitTarget("x", "y", "feature/foo")),
    (("https://github.com/x/y",), {"branch": "v1"}, GitTarget("x", "y", "v1")),
    (("https://github.com/x/y.git",), {}, GitTarget("x", "y")),
    (("https://github.com/x/y/",), {}, GitTarget("x", "y")),
    (("http://github.com/x/y",), {}, GitTarget("x", "y")),
    ((None,), {"url": "https://a/b"}, GitTarget(url="https://a/b")),
    ((None,), {"url": "https://a/b#c"}, GitTarget(branch="c", url="https://a/b")),
    ((None,), {"url": "https://a/b", "branch": "d"}, GitTarget(branch="d", url="https://a/b")),
])
def test_parse_git_target(args, kwargs, expected):
    assert parse_git_target(*args, **kwargs) == expected


@pytest.mark.parametrize("args, kwargs, error", [
    (("yungwine", "dev"), {}, "'yungwine' is not a github url, a branch cannot follow it"),
    (("https://github.com/",), {}, "expected https://github.com/<owner>/<repo>[/tree/<branch>], got 'https://github.com/'"),
    (("https://github.com/only-owner",), {}, "expected https://github.com/<owner>/<repo>"),
    (("https://github.com/x/y/tree/",), {}, "expected https://github.com/<owner>/<repo>"),
    (("https://github.com/x/y/blob/dev/README.md",), {}, "expected https://github.com/<owner>/<repo>"),
    (("https://gitlab.com/x/y",), {}, "expected https://github.com/<owner>/<repo>"),
    ((None,), {"url": "https://a/b#"}, "--url fragment after # is empty"),
    (("testnet",), {"url": "https://a/b"}, "--url cannot be combined with a positional target"),
    (("hotfix",), {"branch": "dev"}, "branch given more than once: hotfix, dev"),
    (("https://github.com/x/y/tree/dev", "v1"), {}, "branch given more than once: v1, dev"),
    (("https://github.com/x/y/tree/dev",), {"branch": "v1"}, "branch given more than once: dev, v1"),
    (("https://github.com/x/y", "dev"), {"branch": "v1"}, "branch given more than once: dev, v1"),
    ((None,), {"url": "https://a/b#c", "branch": "d"}, "branch given more than once: c, d"),
])
def test_parse_git_target_rejects_bad_input(args, kwargs, error):
    with pytest.raises(UsageError) as info:
        parse_git_target(*args, **kwargs)
    assert error in str(info.value)


def test_check_git_url_threads_src_dir_and_uses_the_target_branch(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    captured = {}
    monkeypatch.setattr(git_module, "fix_git_config", lambda path: captured.__setitem__("path", path))

    result = check_git(GitTarget(branch="dev", url="https://github.com/foo/bar"), tmp_path, default_repo="ton", text="upgrade")

    # the configurable src_dir must reach fix_git_config as a plain string
    assert captured["path"] == str(tmp_path)
    # author/repo are unknown for an explicit url; the branch is taken as is
    assert result == (None, None, "dev", "https://github.com/foo/bar")


def test_check_git_url_without_branch_defaults_to_master(monkeypatch):
    monkeypatch.setattr(git_module, "fix_git_config", lambda path: None)

    result = check_git(GitTarget(url="https://github.com/foo/bar"), Path("/usr/src/ton"), default_repo="ton", text="upgrade")

    assert result == (None, None, "master", "https://github.com/foo/bar")


def test_check_git_falls_back_to_defaults_when_src_dir_absent(monkeypatch):
    # A missing src dir is not a git repo: resolve to the upstream defaults so
    # update/upgrade can re-clone, instead of aborting.
    monkeypatch.setattr(git_module, "check_branch_exists", lambda *a: None)

    result = check_git(GitTarget(), Path("/no/such/dir/mytonctrl"), default_repo="mytonctrl", text="update", default_branch="master")

    assert result == ("ton-blockchain", "mytonctrl", "master", None)


def test_check_git_target_overrides_defaults_when_src_dir_absent(monkeypatch):
    # User-supplied values still take precedence over the defaults on the
    # not-a-repo fallback path.
    checked = {}
    monkeypatch.setattr(git_module, "check_branch_exists", lambda *a: checked.setdefault("args", a))

    assert check_git(GitTarget(branch="mybranch"), Path("/no/such/dir/mytonctrl"), default_repo="mytonctrl", text="update") == ("ton-blockchain", "mytonctrl", "mybranch", None)
    assert checked["args"] == ("ton-blockchain", "mytonctrl", "mybranch")
    assert check_git(GitTarget("foo", "bar", "dev"), Path("/no/such/dir/mytonctrl"), default_repo="mytonctrl", text="update") == ("foo", "bar", "dev", None)


def test_check_git_rejects_existing_non_git_src_dir(tmp_path):
    with pytest.raises(Exception, match="update error: .* is not a git repository"):
        check_git(GitTarget(), tmp_path, default_repo="mytonctrl", text="update")


def test_check_git_propagates_operational_error_on_existing_repo(monkeypatch, tmp_path):
    # An existing checkout (.git present) whose git status fails for an
    # operational reason must NOT be silently reset to the upstream defaults:
    # the error has to propagate so the caller aborts and the tree is untouched.
    (tmp_path / ".git").mkdir()

    def boom(_path):
        raise Exception("Failed to check git status: fatal: bad index file")

    monkeypatch.setattr(git_module, "fix_git_config", boom)

    with pytest.raises(Exception, match="Failed to check git status"):
        check_git(GitTarget(), tmp_path, default_repo="ton", text="upgrade")


@pytest.fixture()
def local_repo(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    state = {"author": "ton-blockchain", "repo": "mytonctrl", "branch": "master"}
    monkeypatch.setattr(git_module, "fix_git_config", lambda path: None)
    monkeypatch.setattr(git_module, "get_git_author_and_repo", lambda path: (state["author"], state["repo"]))
    monkeypatch.setattr(git_module, "get_git_branch", lambda path: state["branch"])
    monkeypatch.setattr(git_module, "check_branch_exists", lambda *a: None)
    return tmp_path, state


def test_check_git_on_a_fork_requires_an_explicit_url(local_repo):
    src_dir, state = local_repo
    state.update(author="yungwine", branch="dev")

    with pytest.raises(Exception, match=r"update error: You are on https://github.com/yungwine/mytonctrl/tree/dev remote url, to update to the tip use `update https://github.com/yungwine/mytonctrl/tree/dev` command"):
        check_git(GitTarget(), src_dir, default_repo="mytonctrl", text="update")
    with pytest.raises(Exception, match="You are on https://github.com/yungwine/mytonctrl/tree/hotfix remote url"):
        check_git(GitTarget(branch="hotfix"), src_dir, default_repo="mytonctrl", text="update")

    assert check_git(GitTarget("yungwine", "mytonctrl", "hotfix"), src_dir, default_repo="mytonctrl", text="update") == ("yungwine", "mytonctrl", "hotfix", None)
    # the fork url alone is not enough while the checkout is on a non-default branch
    with pytest.raises(Exception, match="You are on dev branch"):
        check_git(GitTarget("yungwine", "mytonctrl"), src_dir, default_repo="mytonctrl", text="update")


def test_check_git_on_a_non_default_branch_requires_an_explicit_branch(local_repo):
    src_dir, state = local_repo
    state.update(branch="dev")

    with pytest.raises(Exception, match=r"update error: You are on dev branch, to update to the tip of dev branch use `update dev` command"):
        check_git(GitTarget(), src_dir, default_repo="mytonctrl", text="update")

    assert check_git(GitTarget(branch="dev"), src_dir, default_repo="mytonctrl", text="update") == ("ton-blockchain", "mytonctrl", "dev", None)
    assert check_git(GitTarget(branch="master"), src_dir, default_repo="mytonctrl", text="update") == ("ton-blockchain", "mytonctrl", "master", None)


def test_check_git_on_the_default_branch_needs_no_target(local_repo):
    src_dir, _ = local_repo

    assert check_git(GitTarget(), src_dir, default_repo="mytonctrl", text="update") == ("ton-blockchain", "mytonctrl", "master", None)


def test_check_branch_exists(monkeypatch, capsys):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=b"abc123\trefs/heads/dev\n", stderr=b"")

    monkeypatch.setattr(git_module.subprocess, "run", fake_run)

    check_branch_exists("ton-blockchain", "mytonctrl", "dev")
    assert calls == [["git", "ls-remote", "--heads", "--tags", "https://github.com/ton-blockchain/mytonctrl.git", "dev"]]

    with pytest.raises(Exception, match="Branch nope not found in https://github.com/ton-blockchain/mytonctrl.git"):
        check_branch_exists("ton-blockchain", "mytonctrl", "nope")

    # a commit hash is not a ref: the remote check is skipped
    calls.clear()
    check_branch_exists("ton-blockchain", "mytonctrl", "abcdef0")
    assert calls == []
    assert "Hex name detected" in capsys.readouterr().out
