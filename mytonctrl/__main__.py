import argparse
import logging
import os
import shutil

from mypyconsole.mypyconsole import MyPyConsole

from mypylib.mypylib import MyPyClass, color_text, bcolors
from mypylib.logger import setup_logging
from mytoncore import MyTonCore
from mytonctrl.mytonctrl import MyTonCtrl


def _parse_init_args():
    parser = argparse.ArgumentParser(prog="mytonctrl.py")
    parser.add_argument(
        "-c", "--config", dest="configfile", help="Custom `mytoncore.db` config file"
    )
    parser.add_argument("-w", "--wallets", dest="wallets", help="Custom wallets dir")
    parser.add_argument(
        "-s",
        "--no-startup-checks",
        dest="no_startup_checks",
        action="store_true",
        help="Skip startup checks (mytonctrl update, installer user, vport, warnings)",
    )
    parser.add_argument(
        "--cmd",
        dest="cmd",
        help="Run a single console command and exit (implies --no-startup-checks)",
    )
    args = parser.parse_args()

    if args.configfile is not None and not os.access(args.configfile, os.R_OK):
        parser.error("Configuration file " + args.configfile + " could not be opened")
    if args.wallets is not None:
        if not os.access(args.wallets, os.R_OK):
            parser.error("Wallets path " + args.wallets + " could not be opened")
        if not os.path.isdir(args.wallets):
            parser.error("Wallets path " + args.wallets + " is not a directory")
    return args


def _get_welcome_banner(version: str, commit: str) -> str:
    lines = [
        "{bold}{cyan}MyTonCtrl{endc}",
        f"{{dim}}version {version} ({commit}){{endc}}",
        "",
        "Welcome! Type `help` to see available commands.",
    ]
    lines = [color_text(line) for line in lines]

    def visible_len(s: str):
        return len(s) - sum(
            len(x)
            for x in [bcolors.endc, bcolors.bold, bcolors.cyan, bcolors.dim]
            if x and x in s
        )

    width = max(visible_len(line) for line in lines) + 2
    width = min(width, shutil.get_terminal_size().columns - 2)
    top = f"╭{'─' * width}╮"
    bottom = f"╰{'─' * width}╯"
    res = [top]
    for line in lines:
        padding = width - visible_len(line) - 1
        res.append(f"│ {line}{' ' * padding}│")
    res.append(bottom)
    return "\n".join(res)


def _main():
    from mytonctrl import __version__, __commit__

    local = MyPyClass("mytonctrl.py")
    mytoncore_local = MyPyClass("mytoncore.py")
    args = _parse_init_args()
    if args.configfile is not None:
        mytoncore_local.db_path = args.configfile
        mytoncore_local.load_db()
    ton = MyTonCore(mytoncore_local)
    if args.wallets is not None:
        ton.walletsDir = args.wallets

    if args.cmd is None:
        try:
            welcome_text = _get_welcome_banner(__version__, __commit__)
            print(welcome_text)
        except Exception:
            welcome_text = (
                "Welcome to the console. Enter `help` to display the help menu. MyTonCtrl version: "
                + __commit__
            )
            print(welcome_text)

    debug = ton.GetSettings("debug")
    mc_config = mytoncore_local.db.config
    config = local.db.config
    setup_logging(
        mc_config.logLevel,
        local.log_file_name if config.isWritingLogFile else None,
        config.logFileSizeLines if config.isLimitLogFile else None,
    )
    local.logger.setLevel(logging.DEBUG if debug else logging.INFO)
    console = MyPyConsole(local, "MyTonCtrl", debug)

    mtc = MyTonCtrl(local, ton, console)

    mtc.run(
        skip_startup_checks=args.no_startup_checks or args.cmd is not None,
        cmd=args.cmd,
    )


if __name__ == "__main__":
    _main()
