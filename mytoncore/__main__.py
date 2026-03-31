import argparse
from mypylib import MyPyClass
from mytoncore.events import (
    enable_vc_event,
    enable_mode,
    enable_btc_teleport,
    setup_collator,
)
from mytoncore.functions import Init, General


def run_event(local: MyPyClass, event_name: str):
    if event_name == "enableVC":
        enable_vc_event(local)
    elif event_name.startswith("enable_mode"):
        enable_mode(local, event_name)
    elif event_name == "enable_btc_teleport":
        enable_btc_teleport(local)
    elif event_name.startswith("setup_collator"):
        setup_collator(local, event_name)
    else:
        raise Exception("Unknown event name")
    local.exit()


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
        run_event(local, args.e)
    else:
        Init(local)
        General(local)


if __name__ == "__main__":
    _main()
