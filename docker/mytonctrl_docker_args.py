"""Parse host installer flags from MYTONCTRL_ARGS without executing shell text."""
import argparse
from pathlib import Path
import re
import shlex


def argument_parser():
    parser = argparse.ArgumentParser(
        prog="mytonctrl-docker",
        description="Configure first initialization with installer flags in MYTONCTRL_ARGS.",
        allow_abbrev=False,
    )
    for short, long, help_text in (
        ("m", "mode", "Installation mode (default: validator)"),
        ("n", "network", "mainnet, testnet or custom (default: mainnet)"),
        ("c", "config", "Network configuration URL or mounted absolute file path"),
        ("u", "user", "Controller service user (default: root)"),
        ("p", "backup", "Mounted MyTonCtrl backup file"),
        ("B", "bin-dir", "Writable binary compatibility directory (default: /usr/bin)"),
        ("S", "src-dir", "Fift resource compatibility directory (default: /usr/src)"),
        ("W", "ton-work-dir", "Persistent node working directory (default: /var/ton-work)"),
        ("e", "env-file", "Mounted key=value file with installation parameters"),
    ):
        parser.add_argument(f"-{short}", f"--{long}", help=help_text,
                            choices=("mainnet", "testnet", "custom") if long == "network" else None)
    for short, long, help_text in (
        ("t", "telemetry", "Disable telemetry"),
        ("i", "ignore-reqs", "Skip installer CPU/RAM requirements"),
        ("d", "dump", "Use a pre-packaged blockchain dump"),
        ("o", "only-mtc", "Install controller only; requires -p BACKUP"),
        ("l", "only-node", "Install only the TON node"),
        ("s", "no-startup-checks", "Skip checks when opening the Docker console"),
    ):
        parser.add_argument(f"-{short}", f"--{long}", action="store_true", help=help_text)
    parser.add_argument("--archive", action="store_true", help="Full archive liteserver; requires -m liteserver")
    parser.add_argument("--print-env", action="store_true", help="Print resolved installation settings and exit")
    for short, long in (("a", "author"), ("r", "repo"), ("b", "branch"),
                        ("g", "node-repo"), ("v", "node-version")):
        parser.add_argument(f"-{short}", f"--{long}", help="Host-only source selection; select/build an image instead")
    return parser


def read_env_file(path):
    """Accept plain Docker-style variables; no expansion, sourcing, or eval."""
    values = {}
    for number, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid environment assignment at {path}:{number}")
        if value.startswith(("'", '"')):
            tokens = shlex.split(value)
            if len(tokens) != 1:
                raise ValueError(f"Invalid quoted environment value at {path}:{number}")
            value = tokens[0]
        values[name] = value
    return values


def installation_environment(env, argv=()):
    original = env.get("MYTONCTRL_ARGS", "")
    options = argument_parser().parse_args([*shlex.split(original), *argv])
    for name in ("author", "repo", "branch", "node_repo", "node_version"):
        if getattr(options, name) is not None:
            raise ValueError(f"--{name.replace('_', '-')} selects sources on a host install. "
                             "Build the chosen checkout or select MYTONCTRL_IMAGE/TON_IMAGE instead.")
    result = dict(env)
    if options.env_file:
        result.update(read_env_file(options.env_file))
    for option, name in (("mode", "MODE"), ("network", "NETWORK"), ("user", "MTC_USER"),
                         ("backup", "BACKUP"), ("bin_dir", "BIN_DIR"), ("src_dir", "SRC_DIR"),
                         ("ton_work_dir", "TON_WORK_DIR")):
        value = getattr(options, option)
        if value is not None:
            result[name] = value
    for option, name, value in (
        ("telemetry", "TELEMETRY", "false"), ("ignore_reqs", "IGNORE_MINIMAL_REQS", "true"),
        ("dump", "DUMP", "true"), ("archive", "ARCHIVE", "true"),
        ("only_mtc", "ONLY_MTC", "true"), ("only_node", "ONLY_NODE", "true"),
        ("no_startup_checks", "MYTONCTRL_SKIP_STARTUP_CHECKS", "true"),
        ("print_env", "MYTONCTRL_PRINT_ENV", "true"),
    ):
        if getattr(options, option):
            result[name] = value
    if options.config is not None:
        result.pop("GLOBAL_CONFIG_URL", None)
        result.pop("CONFIG_URL", None)
        result.pop("GLOBAL_CONFIG_FILE", None)
        if options.config.startswith(("https://", "http://")):
            result["GLOBAL_CONFIG_URL"] = options.config
        elif Path(options.config).is_absolute():
            result["GLOBAL_CONFIG_FILE"] = options.config
        else:
            raise ValueError("-c/--config requires a URL or mounted absolute file path")
    for name, value in (("MODE", "validator"), ("NETWORK", "mainnet"), ("MTC_USER", "root"),
                        ("BIN_DIR", "/usr/bin"), ("SRC_DIR", "/usr/src"), ("TON_WORK_DIR", "/var/ton-work")):
        result.setdefault(name, value)
    result["MYTONCTRL_ARGS"] = original
    return result
