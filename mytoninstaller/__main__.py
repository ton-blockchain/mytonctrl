import argparse
import os
import random
import sys

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
    EnableMode, ConfigureFromBackup, ConfigureOnlyNode, SetInitialSync, SetupCollator
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
    return parser


def _parse_general_args(argv=None):
    parser = _build_general_arg_parser()
    args = parser.parse_args(argv)
    return args


def get_context(args) -> InstallerContext:
    user = get_current_user()
    vuser = "validator"
    telemetry = False or args.telemetry
    dump = False or args.dump

    if args.user is not None:
        user = args.user

    vc_port = int(
        os.getenv('VALIDATOR_CONSOLE_PORT') if os.getenv('VALIDATOR_CONSOLE_PORT') else random.randint(2000, 65000))
    ls_port = int(os.getenv('LITESERVER_PORT') if os.getenv('LITESERVER_PORT') else random.randint(2000, 65000))
    v_port = int(os.getenv('VALIDATOR_PORT') if os.getenv('VALIDATOR_PORT') else random.randint(2000, 64000))
    quic_port = int(os.getenv('QUIC_PORT')) if os.getenv('QUIC_PORT') else None
    ports = InstallerPorts(vc_port, ls_port, v_port, quic_port)

    archive_ttl = int(os.getenv('ARCHIVE_TTL')) if os.getenv('ARCHIVE_TTL') else None
    state_ttl = int(os.getenv('STATE_TTL')) if os.getenv('STATE_TTL') else None
    public_ip = os.getenv('PUBLIC_IP')
    add_shard = os.getenv('ADD_SHARD')
    archive_blocks = os.getenv('ARCHIVE_BLOCKS')
    collate_shard = os.getenv('COLLATE_SHARD', '')

    backup = None
    if args.backup is not None:
        if args.backup != "none":
            backup = args.backup

    paths = InstallerPaths()
    return InstallerContext(user, vuser, paths, ports, telemetry, dump, args.mode, args.only_mtc, args.only_node, backup,
                           archive_ttl, state_ttl, public_ip, add_shard, archive_blocks, collate_shard)


def mytoninstaller():
    local = MyPyClass(__file__)
    local.db.config.logLevel = "debug"
    args = _parse_general_args()
    ctx = get_context(args)
    FirstMytoncoreSettings(local, ctx)
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
