from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from mypyconsole.command_parser import UsageError
from mypylib import color_print
from mytonctrl.utils import is_hex


def fix_git_config(git_path: str | Path):
    args = ["git", "status"]
    try:
        process = subprocess.run(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_path,
            timeout=3,
        )
        err = process.stderr.decode("utf-8")
    except Exception as e:
        err = str(e)
    if err:
        if "git config --global --add safe.directory" in err:
            args = ["git", "config", "--global", "--add", "safe.directory", git_path]
            subprocess.run(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3,
            )
        else:
            raise Exception(f"Failed to check git status: {err}")


_GITHUB_URL = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?(?:/tree/(?P<branch>.+?)/?)?"
)


@dataclass(frozen=True)
class GitTarget:
    author: str | None = None
    repo: str | None = None
    branch: str | None = None
    url: str | None = None


def parse_git_target(
    target: str | None,
    target_branch: str | None = None,
    *,
    branch: str | None = None,
    url: str | None = None,
) -> GitTarget:
    author = repo = git_url = given_branch = None
    if url is not None:
        if target is not None:
            raise UsageError("--url cannot be combined with a positional target")
        git_url, sharp, given_branch = url.partition("#")
        if sharp and not given_branch:
            raise UsageError("--url fragment after # is empty")
    elif target is not None and not target.startswith(("https://", "http://")):
        if target_branch is not None:
            raise UsageError(
                f"{target!r} is not a github url, a branch cannot follow it"
            )
        given_branch = target
    elif target is not None:
        match = _GITHUB_URL.fullmatch(target)
        if match is None:
            raise UsageError(
                f"expected https://github.com/<owner>/<repo>[/tree/<branch>], got {target!r}"
            )
        author, repo = match["owner"], match["repo"]
        if target_branch is not None and match["branch"] is not None:
            raise UsageError(
                f"branch given more than once: {target_branch}, {match['branch']}"
            )
        given_branch = target_branch or match["branch"]
    if given_branch and branch is not None:
        raise UsageError(f"branch given more than once: {given_branch}, {branch}")
    return GitTarget(author, repo, given_branch or branch, git_url)


def check_git(
    target: GitTarget,
    src_dir: Path,
    default_repo: str,
    text: str,
    default_branch: str = "master",
):
    git_path = str(src_dir)
    default_author = "ton-blockchain"
    if src_dir.exists():
        if not (src_dir / ".git").exists():
            raise Exception(f"{text} error: {git_path} is not a git repository")
        fix_git_config(git_path)

    if target.url is not None:
        return None, None, target.branch or default_branch, target.url

    if src_dir.exists():
        local_author, local_repo = get_git_author_and_repo(git_path)
        local_branch = get_git_branch(git_path)
    else:
        defaults = f"{default_author}/{default_repo}#{default_branch}"
        color_print(
            f"{{red}}{git_path} is not a git repository, falling back to defaults: {defaults}{{endc}}"
        )
        local_author = local_repo = local_branch = None

    need_author, need_repo, need_branch = target.author, target.repo, target.branch
    if src_dir.exists():
        if (need_author is None and local_author != default_author) or (
            need_repo is None and local_repo != default_repo
        ):
            remote_url = f"https://github.com/{local_author}/{local_repo}/tree/{need_branch if need_branch else local_branch}"
            raise Exception(
                f"{text} error: You are on {remote_url} remote url, to update to the tip use `{text} {remote_url}` command"
            )
        elif need_branch is None and local_branch != default_branch:
            raise Exception(
                f"{text} error: You are on {local_branch} branch, to update to the tip of {local_branch} branch use `{text} {local_branch}` command"
            )

    if need_author is None:
        need_author = local_author or default_author
    if need_repo is None:
        need_repo = local_repo or default_repo
    if need_branch is None:
        need_branch = local_branch or default_branch
    check_branch_exists(need_author, need_repo, need_branch)
    return need_author, need_repo, need_branch, None


def check_branch_exists(author, repo, branch):
    if len(branch) >= 6 and is_hex(branch):
        print("Hex name detected, skip branch existence check.")
        return
    url = f"https://github.com/{author}/{repo}.git"
    args = ["git", "ls-remote", "--heads", "--tags", url, branch]
    process = subprocess.run(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=3,
    )
    output = process.stdout.decode("utf-8")
    if branch not in output:
        raise Exception(f"Branch {branch} not found in {url}")


def get_git_url(git_path: str | Path) -> str | None:
    args = ["git", "remote", "-v"]
    output = ""
    try:
        process = subprocess.run(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=git_path,
            timeout=3,
        )
        output = process.stdout.decode("utf-8")
        err = process.stderr.decode("utf-8")
    except Exception as ex:
        err = str(ex)
    if len(err) > 0:
        return None
    lines = output.split("\n")
    url = None
    for line in lines:
        if "origin" in line:
            buff = line.split()
            url = buff[1]
    return url


def get_git_author_and_repo(git_path: str | Path) -> tuple[str | None, str | None]:
    author = None
    repo = None
    url = get_git_url(git_path)
    if url is not None:
        buff = url.split("/")
        if len(buff) == 5:
            author = buff[3]
            repo = buff[4]
            repo = repo.split(".")
            repo = repo[0]
    return author, repo


def _get_request(url: str) -> str:
    link = urlopen(url)
    data = link.read()
    text = data.decode("utf-8")
    return text


def get_git_last_remote_commit(
    git_path: str | Path, branch: str = "master"
) -> str | None:
    author, repo = get_git_author_and_repo(git_path)
    if author is None or repo is None:
        return
    url = f"https://api.github.com/repos/{author}/{repo}/branches/{branch}"
    sha = None
    try:
        text = _get_request(url)
        data = json.loads(text)
        sha = data["commit"]["sha"]
    except URLError:
        pass
    return sha


def check_git_update(git_path: str | Path) -> bool | None:
    branch = get_git_branch(git_path)
    if branch is None:
        return None
    new_hash = get_git_last_remote_commit(git_path, branch)
    old_hash = get_git_hash(git_path)
    result = False
    if old_hash != new_hash:
        result = True
    if old_hash is None or new_hash is None:
        result = None
    return result


def get_git_hash(git_path: Path | str, short: bool = False) -> str | None:
    args = ["git", "rev-parse", "HEAD"]
    if short is True:
        args.insert(2, "--short")
    process = subprocess.run(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=git_path,
        timeout=3,
    )
    output = process.stdout.decode("utf-8")
    err = process.stderr.decode("utf-8")
    if len(err) > 0:
        return
    buff = output.split("\n")
    return buff[0]


def get_git_branch(git_path: str | Path) -> str | None:
    args = ["git", "branch", "-v"]
    process = subprocess.run(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=git_path,
        timeout=3,
    )
    output = process.stdout.decode("utf-8")
    err = process.stderr.decode("utf-8")
    if len(err) > 0:
        return None
    lines = output.split("\n")
    branch = None
    for line in lines:
        if "*" in line:
            buff = line.split()
            branch = buff[1]
    return branch
