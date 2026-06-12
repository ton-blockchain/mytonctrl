import argparse
import os
import random
import sys
from pathlib import Path

from mytoncore.utils import str2bool

from mypylib.mypylib import MyPyClass
from mytonctrl.utils import get_current_user

from mytoninstaller.context import InstallerContext, InstallerPaths, InstallerPorts
from mytoninstaller.settings import (
    FirstNodeSettings,
    FirstMytoncoreSettings,
    EnableValidatorConsole,
    EnableLiteServer,
    CreateSymlinks,
    EnableMode, ConfigureFromBackup, ConfigureOnlyNode, SetInitialSync, SetupCollator, write_paths
)
from mytoninstaller.config import (
    BackupMconfig,
)


def _build_general_arg_parser():
    parser = argparse.ArgumentParser(prog="mytoninstaller", allow_abbrev=False)
    parser.add_argument("-u", dest="user", help="user to be used for MyTonCtrl installation")
    parser.add_argument(
        "-t",
        dest="telemetry",
        nargs="?",
        const="false",
        type=str2bool,
        help="set telemetry boolean; without a value disables telemetry",
    )
    parser.add_argument(
        "--dump",
        nargs="?",
        const="true",
        type=str2bool,
        help="set whether to use pre-packaged dump",
    )
    parser.add_argument("-m", dest="mode", help="installation mode")
    parser.add_argument(
        "--only-mtc",
        nargs="?",
        const="true",
        type=str2bool,
        help="install only MyTonCtrl",
    )
    parser.add_argument(
        "--only-node",
        nargs="?",
        const="true",
        type=str2bool,
        help="install only TON node",
    )
    parser.add_argument("--backup", help="backup file for MyTonCtrl installation")
    parser.add_argument("--bin-dir", dest="bin_dir", help="directory with binaries (default /usr/bin/)")
    parser.add_argument("--src-dir", dest="src_dir", help="directory with sources (default /usr/src/)")
    parser.add_argument("--ton-work-dir", dest="ton_work_dir", help="TON node working directory (default /var/ton-work/)")
    return parser


def _parse_general_args(argv=None):
    parser = _build_general_arg_parser()
    args = parser.parse_args(argv)
    return args


def _normalize_dir(path: str) -> str:
    return os.path.join(Path(path).absolute(), "")


def get_context(args) -> InstallerContext:
    user = get_current_user()
    vuser = "validator"
    telemetry = False or args.telemetry
    dump = False or args.dump

    if args.user is not None:
        user = args.user

    vc_port_env = os.getenv('VALIDATOR_CONSOLE_PORT')
    vc_port = int(vc_port_env) if vc_port_env else random.randint(2000, 65000)
    ls_port_env = os.getenv('LITESERVER_PORT')
    ls_port = int(ls_port_env) if ls_port_env else random.randint(2000, 65000)
    v_port_env = os.getenv('VALIDATOR_PORT')
    v_port = int(v_port_env) if v_port_env else random.randint(2000, 64000)
    quic_port_env = os.getenv('QUIC_PORT')
    quic_port = int(quic_port_env) if quic_port_env else None
    ports = InstallerPorts(vc_port, ls_port, v_port, quic_port)

    archive_ttl_env = os.getenv('ARCHIVE_TTL')
    archive_ttl = int(archive_ttl_env) if archive_ttl_env else None
    state_ttl_env = os.getenv('STATE_TTL')
    state_ttl = int(state_ttl_env) if state_ttl_env else None
    public_ip = os.getenv('PUBLIC_IP')
    add_shard = os.getenv('ADD_SHARD')
    archive_blocks = os.getenv('ARCHIVE_BLOCKS')
    collate_shard = os.getenv('COLLATE_SHARD', '')

    backup = None
    if args.backup is not None:
        if args.backup != "none":
            backup = args.backup

    paths_kwargs = {}
    if args.bin_dir:
        paths_kwargs["bin_dir"] = _normalize_dir(args.bin_dir)
    if args.src_dir:
        paths_kwargs["src_dir"] = _normalize_dir(args.src_dir)
    if args.ton_work_dir:
        paths_kwargs["ton_work_dir"] = _normalize_dir(args.ton_work_dir)
    paths = InstallerPaths(**paths_kwargs)
    return InstallerContext(user, vuser, paths, ports, telemetry, dump, args.mode, args.only_mtc, args.only_node, backup,
                           archive_ttl, state_ttl, public_ip, add_shard, archive_blocks, collate_shard)


def mytoninstaller():
    local = MyPyClass(__file__)
    local.db.config.logLevel = "debug"
    args = _parse_general_args()
    ctx = get_context(args)
    FirstMytoncoreSettings(local, ctx)
    write_paths(local, ctx)
    FirstNodeSettings(local, ctx)
    EnableValidatorConsole(local, ctx)
    if not ctx.only_mtc:
        EnableLiteServer(local, ctx)
    BackupMconfig(local, ctx)
    CreateSymlinks(local, ctx)
    EnableMode(local, ctx)
    ConfigureFromBackup(local, ctx)
    ConfigureOnlyNode(local, ctx)
    SetInitialSync(local, ctx)
    SetupCollator(local, ctx)
    local.exit()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        raise Exception("No installation arguments provided")
    mytoninstaller()
