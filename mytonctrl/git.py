from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from mytonctrl.utils import pop_arg_from_args, GetItemFromList, is_hex

import subprocess


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


def check_git(
    input_args: list[str],
    src_dir: Path,
    default_repo: str,
    text: str,
    default_branch: str = "master",
):
    git_path = str(src_dir)
    fix_git_config(git_path)
    default_author = "ton-blockchain"

    branch = pop_arg_from_args(input_args, "--branch")

    if "--url" in input_args:
        git_url = pop_arg_from_args(input_args, "--url")
        if not git_url:
            raise Exception("git url is empty after --url flag")
        if branch is None:
            if "#" in git_url:
                ref_fragment = git_url.rsplit("#", 1)[1]
                if not ref_fragment:
                    raise Exception("--url fragment after # is empty")
                branch = ref_fragment
            else:
                branch = default_branch
        if "#" in git_url:
            git_url = git_url.split("#", 1)[0]
        return None, None, branch, git_url

    local_author, local_repo = get_git_author_and_repo(git_path)
    local_branch = get_git_branch(git_path)

    # Set author, repo, branch
    data = GetAuthorRepoBranchFromArgs(input_args)
    need_author = data.get("author")
    need_repo = data.get("repo")
    need_branch = data.get("branch") or branch

    # Check if remote repo is different from default
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
        need_author = local_author
    if need_repo is None:
        need_repo = local_repo
    if need_branch is None:
        need_branch = local_branch
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


def GetAuthorRepoBranchFromArgs(args: list[str]):
    data = dict()
    arg1 = GetItemFromList(args, 0)
    arg2 = GetItemFromList(args, 1)
    if arg1:
        if "https://" in arg1:
            buff = arg1[8:].split("/")
            print(f"buff: {buff}")
            data["author"] = buff[1]
            data["repo"] = buff[2]
            tree = GetItemFromList(buff, 3)
            if tree:
                data["branch"] = GetItemFromList(buff, 4)
        else:
            data["branch"] = arg1
    if arg2:
        data["branch"] = arg2
    return data


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
