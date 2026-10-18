import argparse
import base64
import re

import pytest

from mytoncore.utils import raw_addr_to_b64
from mytonctrl.argtypes import adnl_address, coins_amount, tcp_port, ton_address, wallet_version


@pytest.mark.parametrize("text, expected", [("0", 0), ("8080", 8080), ("65535", 65535)])
def test_tcp_port_accepts_the_range(text, expected):
    assert tcp_port(text) == expected


@pytest.mark.parametrize(
    "text, message",
    [
        ("abc", "expected a port number, got 'abc'"),
        ("-1", "port must be between 0 and 65535, got -1"),
        ("65536", "port must be between 0 and 65535, got 65536"),
    ],
)
def test_tcp_port_rejects_with_a_message_argparse_prints_as_is(text, message):
    with pytest.raises(argparse.ArgumentTypeError, match=message):
        tcp_port(text)


@pytest.mark.parametrize("text, expected", [("10", 10.0), ("1.5", 1.5), ("0", 0.0), ("all", "all"), ("alld", "alld")])
def test_coins_amount_accepts_numbers_and_the_two_words(text, expected):
    assert coins_amount(text) == expected


@pytest.mark.parametrize(
    "text, message",
    [
        ("abc", "expected an amount in TON or all / alld, got 'abc'"),
        ("-5", "amount must be a non-negative number, got -5"),
        ("nan", "amount must be a non-negative number, got nan"),
        ("inf", "amount must be a non-negative number, got inf"),
        ("ALL", "expected an amount in TON or all / alld, got 'ALL'"),
    ],
)
def test_coins_amount_rejects(text, message):
    with pytest.raises(argparse.ArgumentTypeError, match=message):
        coins_amount(text)


RAW_ADDR = "-1:" + "3" * 64
B64_ADDR = raw_addr_to_b64(RAW_ADDR)
URL_ADDR_DASH = raw_addr_to_b64("0:9dd5ec3ec8a3233ab56b22457ef8b0540d59fb5567fe84c4d548eda03c2e8535")
URL_ADDR_UNDERSCORE = raw_addr_to_b64(RAW_ADDR, is_testnet=True)
BAD_CRC_ADDR = B64_ADDR[:-1] + ("A" if B64_ADDR[-1] != "A" else "B")


@pytest.mark.parametrize(
    "text",
    [
        RAW_ADDR,
        "0:" + "aB" * 32,
        B64_ADDR,
        raw_addr_to_b64(RAW_ADDR, bounceable=False),
        URL_ADDR_DASH,
        URL_ADDR_UNDERSCORE,
        URL_ADDR_DASH.replace("-", "+"),
        URL_ADDR_UNDERSCORE.replace("_", "/"),
    ],
)
def test_ton_address_accepts_raw_and_user_friendly_and_returns_it_unchanged(text):
    assert ton_address(text) == text


@pytest.mark.parametrize(
    "text",
    [
        BAD_CRC_ADDR,
        B64_ADDR[:-4],
        B64_ADDR + "AAAA",
        "-1:" + "3" * 63,
        "0:" + "3" * 66,
        "0:" + "x" * 64,
        "not_an_address",
        "",
    ],
)
def test_ton_address_rejects(text):
    message = f"expected a TON address (in user-friendly or raw form), got {text!r}"
    with pytest.raises(argparse.ArgumentTypeError, match=re.escape(message)):
        ton_address(text)


ADNL_HEX = "0123456789abcdefABCDEF" * 2 + "01234567890123456789"
ADNL_B64 = base64.b64encode(bytes(range(32))).decode()


@pytest.mark.parametrize("text", [ADNL_HEX, "A" * 64, ADNL_B64])
def test_adnl_address_accepts_hex_and_base64_and_returns_it_unchanged(text):
    assert adnl_address(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "A" * 62,
        "A" * 66,
        "g" * 64,
        ADNL_B64[:-4],
        base64.b64encode(bytes(33)).decode(),
        ADNL_B64.replace("A", "!"),
        "test_adnl",
        "",
    ],
)
def test_adnl_address_rejects(text):
    message = f"expected an ADNL address (64 hex characters or base64), got {text!r}"
    with pytest.raises(argparse.ArgumentTypeError, match=re.escape(message)):
        adnl_address(text)


@pytest.mark.parametrize("text", ["v1", "v2", "v3", "v1r3", "v2r2", "v3r2"])
def test_wallet_version_accepts_v1_to_v3_with_an_optional_revision(text):
    assert wallet_version(text) == text


@pytest.mark.parametrize("text", ["hv1", "v4", "V1", "v3r", "v3r22", "wallet", "v1 "])
def test_wallet_version_rejects_everything_else(text):
    with pytest.raises(argparse.ArgumentTypeError, match=f"expected a wallet version v1, v2 or v3, .*got {text!r}"):
        wallet_version(text)


def test_address_aliases_carry_the_converter():
    from typing import Optional

    from mypyconsole.command_parser import CommandParser, UsageError
    from mytonctrl.argtypes import AdnlAddress, TonAddress

    calls = []

    def handler(addr: TonAddress, adnl: Optional[AdnlAddress] = None):
        calls.append((addr, adnl))

    parser = CommandParser("cmd", handler)
    assert parser.short_usage() == "addr [adnl]"
    good = raw_addr_to_b64("0:" + "11" * 32)
    parser.run([good])
    parser.run([good, "ab" * 32])
    assert calls == [(good, None), (good, "ab" * 32)]
    with pytest.raises(UsageError, match="argument addr: expected a TON address"):
        parser.run(["nope"])
    with pytest.raises(UsageError, match="argument adnl: expected an ADNL address"):
        parser.run([good, "nope"])
