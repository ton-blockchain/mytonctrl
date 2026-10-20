#!/opt/mytonctrl/venv/bin/python
"""Keep the normal console CLI, with optional defaults from docker --env-file."""
import os
import json
from pathlib import Path
import pwd
import sys

from mytonctrl_docker_args import installation_environment


def console_args(env):
    if "MYTONCTRL_SKIP_STARTUP_CHECKS" not in env:
        env = installation_environment(env)
    args = []
    for name, flag in (("MYTONCTRL_CONFIG", "--config"), ("MYTONCTRL_WALLETS", "--wallets"),
                       ("MYTONCTRL_CMD", "--cmd")):
        if env.get(name):
            args.extend((flag, env[name]))
    if env.get("MYTONCTRL_SKIP_STARTUP_CHECKS", "false").lower() in ("1", "true", "yes"):
        args.append("--no-startup-checks")
    return args


def main():
    options_file = Path("/run/mytonctrl-options.json")
    if options_file.is_file():
        os.environ.update(json.loads(options_file.read_text()))
    else:
        os.environ.update(installation_environment(os.environ))
    user = os.environ.get("MTC_USER", "root")
    account = pwd.getpwnam(user)
    if os.getuid() == 0 and account.pw_uid:
        os.initgroups(user, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    os.environ.update(HOME=account.pw_dir, USER=user, LOGNAME=user)
    os.environ["XDG_DATA_HOME"] = account.pw_dir + "/.local/share"
    work = os.environ.get("TON_WORK_DIR", "/var/ton-work")
    os.chdir(work + "/controller/mytoncore")
    python = "/opt/mytonctrl/venv/bin/python"
    os.execv(python, [python, "-m", "mytonctrl", *console_args(os.environ), *sys.argv[1:]])


if __name__ == "__main__":
    main()
