import argparse
from mypylib import MyPyClass


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

    if args.e is not None:
        from mytoncore.events import run_event

        run_event(local, args.e)
    else:
        local.run()
        from mytoncore.background_runner import BackgroundRunner

        BackgroundRunner(local).run()


if __name__ == "__main__":
    _main()
