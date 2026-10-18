import argparse
import os
import random
import sys
from pathlib import Path

from mytoncore.utils import str2bool

from mypylib.mypylib import MyPyClass
from mypylib.logger import get_logger, setup_logging
from mytonctrl.utils import get_current_user, is_container

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
    BackupMconfig, GetConfig, SetConfig,
)
from mypylib.mypylib import Dict


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
    if is_container():
        public_ip = (public_ip or '').strip() or None
    add_shard = os.getenv('ADD_SHARD')
    archive_blocks = os.getenv('ARCHIVE_BLOCKS')

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
                           archive_ttl, state_ttl, public_ip, add_shard, archive_blocks)


def _run_installation_stage(local, ctx, stage, callback):
    if not is_container():
        return callback(local, ctx)
    path = Path(ctx.paths.ton_work_dir) / "controller/installer-progress.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    progress = GetConfig(str(path)) if path.exists() else Dict(version=1, completed=[])
    if progress.get("version") != 1 or not isinstance(progress.get("completed"), list):
        raise RuntimeError(f"Invalid installer progress checkpoint: {path}")
    completed = progress["completed"]
    if stage == "node_settings" and stage in completed and ctx.backup and "backup_restore" not in completed:
        # An interrupted restore can temporarily remove the donor keyring.
        # Reach the restore retry before attempting to activate the validator.
        local.add_log("Deferring validator activation until backup restoration completes", "info")
        return
    # Revisit node setup to start the validator in a fresh supervisor process.
    # Its own completion checkpoint prevents repeated downloads or key creation.
    if stage in completed and stage != "node_settings":
        local.add_log(f"Installation stage {stage} already completed; continuing", "info")
        return
    progress.update(stage=stage, status="running")
    progress.pop("error", None)
    SetConfig(str(path), progress)
    path.chmod(0o644)
    try:
        result = callback(local, ctx)
    except BaseException as error:
        progress.update(status="failed", error=str(error))
        SetConfig(str(path), progress)
        path.chmod(0o644)
        raise
    if stage not in completed:
        completed.append(stage)
    progress.update(status="complete")
    SetConfig(str(path), progress)
    path.chmod(0o644)
    return result


def _configure_controller(local, ctx):
    FirstMytoncoreSettings(local, ctx)
    write_paths(local, ctx)


def _setup_installer_logging(local):
    setup_logging(
        local.db.config.logLevel,
        local.log_file_name if local.db.config.isWritingLogFile else None,
        local.db.config.logFileSizeLines if local.db.config.isLimitLogFile else None,
    )


def mytoninstaller():
    local = MyPyClass(__file__)
    local.db.config.logLevel = "debug"
    container = is_container()
    if not container:
        _setup_installer_logging(local)
    args = _parse_general_args()
    ctx = get_context(args)
    if container:
        log_path = Path(ctx.paths.ton_work_dir) / "controller/mytoninstaller.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        local.log_file_name = str(log_path)
        _setup_installer_logging(local)
    _run_installation_stage(local, ctx, "controller_settings", _configure_controller)
    _run_installation_stage(local, ctx, "node_settings", FirstNodeSettings)
    _run_installation_stage(local, ctx, "validator_console", EnableValidatorConsole)
    if not ctx.only_mtc:
        _run_installation_stage(local, ctx, "liteserver", EnableLiteServer)
    _run_installation_stage(local, ctx, "backup_config", BackupMconfig)
    _run_installation_stage(local, ctx, "symlinks", CreateSymlinks)
    _run_installation_stage(local, ctx, "mode", EnableMode)
    _run_installation_stage(local, ctx, "backup_restore", ConfigureFromBackup)
    _run_installation_stage(local, ctx, "only_node", ConfigureOnlyNode)
    _run_installation_stage(local, ctx, "initial_sync", SetInitialSync)
    _run_installation_stage(local, ctx, "collator", SetupCollator)
    local.exit()


def main():
    if len(sys.argv) == 1:
        raise Exception("No installation arguments provided")
    try:
        mytoninstaller()
    except Exception as error:
        if not is_container():
            raise
        if not get_logger().handlers:
            setup_logging()
        get_logger("mytoninstaller").error("Initialization failed: %s", error, exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
