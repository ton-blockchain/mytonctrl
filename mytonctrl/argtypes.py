from __future__ import annotations

import argparse
import base64
import math
import re

from mypyconsole.command_parser import Annotated, Arg


def tcp_port(text: str) -> int:
    try:
        port = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a port number, got {text!r}"
        ) from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            f"port must be between 0 and 65535, got {port}"
        )
    return port


def coins_amount(text: str) -> float | str:
    if text in ("all", "alld"):
        return text
    try:
        amount = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected an amount in TON or all / alld, got {text!r}"
        ) from None
    if not math.isfinite(amount) or amount < 0:
        raise argparse.ArgumentTypeError(
            f"amount must be a non-negative number, got {text}"
        )
    return amount


def ton_address(text: str) -> str:
    from mytoncore.utils import parse_addr_b64, parse_addr_full

    try:
        parse_addr_b64(text)
        return text
    except Exception:
        pass
    try:
        parse_addr_full(text)
        return text
    except Exception:
        pass
    raise argparse.ArgumentTypeError(
        f"expected a TON address (in user-friendly or raw form), got {text!r}"
    )


def adnl_address(text: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F]{64}", text):
        return text
    try:
        if len(text) == 44 and len(base64.b64decode(text, validate=True)) == 32:
            return text
    except ValueError:
        pass
    raise argparse.ArgumentTypeError(
        f"expected an ADNL address (64 hex characters or base64), got {text!r}"
    )


def wallet_version(text: str) -> str:
    if re.fullmatch(r"v[123](r[0-9])?", text):
        return text
    raise argparse.ArgumentTypeError(
        f"expected a wallet version v1, v2 or v3, optionally with a revision like v3r2, got {text!r}"
    )


TonAddress = Annotated[str, Arg(type=ton_address)]
AdnlAddress = Annotated[str, Arg(type=adnl_address)]
WalletVersion = Annotated[str, Arg(type=wallet_version)]
