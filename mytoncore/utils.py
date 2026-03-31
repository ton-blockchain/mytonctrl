from __future__ import annotations

import base64
import json
import re
import subprocess

try:
    # Python 3.9+
    from importlib.resources import files, as_file
except ImportError:
    # Python < 3.9
    from importlib_resources import files, as_file  # pyright: ignore[reportMissingImports]


def str2b64(s: str):
    b = s.encode("utf-8")
    b64 = base64.b64encode(b)
    b64 = b64.decode("utf-8")
    return b64


def b642str(b64: str):
    b = base64.b64decode(b64.encode())
    s = b.decode()
    return s


def dict2b64(d: dict):
    s = json.dumps(d)
    b64 = str2b64(s)
    return b64


def b642dict(b64: str):
    s = b642str(b64)
    d = json.loads(s)
    return d


def hex2b64(inp: str):  # TODO: remove duplicates
    hex_bytes = bytes.fromhex(inp)
    b64_bytes = base64.b64encode(hex_bytes)
    b64_string = b64_bytes.decode()
    return b64_string


def b642hex(inp: str):
    b64_bytes = inp.encode()
    hex_bytes = base64.b64decode(b64_bytes)
    hex_string = hex_bytes.hex()
    return hex_string


def xhex2hex(x: str) -> str | None:
    try:
        b = x[1:]
        h = b.lower()
        return h
    except Exception:
        return None


def hex2base64(h: str):  # TODO: remove duplicates
    b = bytes.fromhex(h)
    b64 = base64.b64encode(b)
    s = b64.decode("utf-8")
    return s


def str2bool(s: str):
    if s == "true":
        return True
    return False


def ng2g(ng: int | None) -> float | None:
    if ng is None:
        return None
    return int(ng) / 10**9


def parse_db_stats(path: str):
    with open(path) as f:
        lines = f.readlines()
    result = {}
    for line in lines:
        s = line.strip().split(maxsplit=1)
        items = re.findall(r"(\S+)\s:\s(\S+)", s[1])
        if len(items) == 1:
            item = items[0]
            if float(item[1]) > 0:
                result[s[0]] = float(item[1])
        else:
            if any(float(v) > 0 for k, v in items):
                result[s[0]] = {}
                result[s[0]] = {k: float(v) for k, v in items}
    return result


def get_hostname() -> str:
    return subprocess.run(["hostname"], stdout=subprocess.PIPE).stdout.decode().strip()


def hex_shard_to_int(shard_id_str: str) -> dict:
    try:
        wc, shard_hex = shard_id_str.split(":")
        wc = int(wc)
        shard = int(shard_hex, 16)
        if shard >= 2**63:
            shard -= 2**64
        return {"workchain": wc, "shard": shard}
    except (ValueError, IndexError):
        raise Exception(f'Invalid shard ID "{shard_id_str}"')


def signed_int_to_hex64(value: int):
    if value < 0:
        value = (1 << 64) + value
    return f"{value:016X}"


_MASK64 = (1 << 64) - 1


def _to_unsigned64(v: int) -> int:
    return v & _MASK64


def _lower_bit64(u: int) -> int:
    if u == 0:
        return 0
    return u & ((-u) & _MASK64)


def _bits_negate64(u: int) -> int:
    return ~u + 1


def shard_prefix_len(shard_id: int):
    def _count_trailing_zeroes64(value: int) -> int:
        u = value & _MASK64
        if u == 0:
            return 64
        return ((u & -u).bit_length()) - 1

    return 63 - _count_trailing_zeroes64(_to_unsigned64(shard_id))


def shard_prefix(shard_id: int, length_: int):
    def _to_signed64(v: int) -> int:
        return v - (1 << 64) if v >= (1 << 63) else v

    if not (0 <= length_ <= 63):
        raise ValueError("length must be between 0 and 63 inclusive")
    u = _to_unsigned64(shard_id)
    x = _lower_bit64(u)
    y = 1 << (63 - length_)
    if y < x:
        raise ValueError(
            "requested prefix length is longer (more specific) than current shard id"
        )
    mask_non_lower = (~(y - 1)) & _MASK64  # equals -y mod 2^64; clears bits below y
    res_u = (u & mask_non_lower) | y
    return _to_signed64(res_u)


def shard_contains(parent: int, child: int) -> bool:
    parent = _to_unsigned64(parent)
    child = _to_unsigned64(child)
    x = _lower_bit64(parent)
    mask = (_bits_negate64(x) << 1) & _MASK64
    return not ((parent ^ child) & mask)


def shard_is_ancestor(parent: int, child: int) -> bool:
    up = _to_unsigned64(parent)
    uc = _to_unsigned64(child)
    x = _lower_bit64(up)
    y = _lower_bit64(uc)
    mask = (_bits_negate64(x) << 1) & _MASK64
    return x >= y and not ((up ^ uc) & mask)


def get_package_resource_path(package: str, resource: str):
    ref = files(package) / resource
    return as_file(ref)
