import argparse
from mypylib import MyPyClass
from mypylib.logger import setup_logging


def _main():
    local = MyPyClass("mytoncore.py")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e",
        type=str,
        metavar="EVENT",
        help="event to run (enableVC, enable_mode*, enable_btc_teleport, setup_collator*)",
    )
    args = parser.parse_args()

    config = local.db.config
    if args.e is not None:
        setup_logging(config.logLevel)
        from mytoncore.events import run_event

        run_event(local, args.e)
    else:
        setup_logging(
            config.logLevel,
            local.log_file_name if config.isWritingLogFile else None,
            config.logFileSizeLines if config.isLimitLogFile else None,
        )
        local.run()
        from mytoncore.background_runner import BackgroundRunner

        BackgroundRunner(local).run()


if __name__ == "__main__":
    _main()
