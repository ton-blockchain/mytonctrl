# pyright: strict

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from typing import TYPE_CHECKING, Any, List, Union

from fastcrc import crc16

from mypylib.mypylib import parse

if TYPE_CHECKING:
    from importlib.resources import as_file, files
elif sys.version_info >= (3, 9):
    from importlib.resources import as_file, files
else:
    from importlib_resources import as_file, files


def str2b64(s: str):
    b = s.encode("utf-8")
    b64 = base64.b64encode(b)
    b64 = b64.decode("utf-8")
    return b64


def b642str(b64: str):
    b = base64.b64decode(b64.encode())
    s = b.decode()
    return s


def dict2b64(d: dict[Any, Any]):
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


def nano_ton_to_ton(nano: int) -> float:
    return nano / 10**9

def ng2g(ng: int | None) -> float | None:
    if ng is None:
        return None
    return int(ng) / 10**9


def parse_db_stats(path: str):
    with open(path) as f:
        lines = f.readlines()
    result: dict[str, float | dict[str, float]] = {}
    for line in lines:
        s = line.strip().split(maxsplit=1)
        items = re.findall(r"(\S+)\s:\s(\S+)", s[1])
        if len(items) == 1:
            item = items[0]
            if float(item[1]) > 0:
                result[s[0]] = float(item[1])
        else:
            if any(float(v) > 0 for _, v in items):
                result[s[0]] = {}
                result[s[0]] = {k: float(v) for k, v in items}
    return result


def get_hostname() -> str:
    return subprocess.run(["hostname"], stdout=subprocess.PIPE).stdout.decode().strip()


def hex_shard_to_int(shard_id_str: str) -> dict[str, int]:
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


def raw_addr_to_b64(addr_full: str, bounceable: bool = True, is_testnet: bool = False):
    buff = addr_full.split(':')
    workchain = int(buff[0])
    addr = buff[1]
    if len(addr) != 64:
        raise Exception("Invalid length of hexadecimal address")

    # Create base64 address
    b = bytearray(36)
    b[0] = 0x51 - bounceable * 0x40 + is_testnet * 0x80
    b[1] = workchain % 256
    b[2:34] = bytearray.fromhex(addr)
    buff = bytes(b[:34])
    crc = crc16.xmodem(buff)
    b[34] = crc >> 8
    b[35] = crc & 0xff
    result = base64.b64encode(b)
    result = result.decode()
    result = result.replace('+', '-')
    result = result.replace('/', '_')
    return result

T = List[Union[str, int, "T"]]

def lc_result_to_list(text: str) -> T:
    buff = parse(text, "result:", "\n")
    if buff is None or "error" in buff:
        raise Exception(f'Failed to parse liteclient result: {text}')
    buff = buff.replace(')', ']')
    buff = buff.replace('(', '[')
    buff = buff.replace(']', ' ] ')
    buff = buff.replace('[', ' [ ')
    buff = buff.replace('bits:', '')
    buff = buff.replace('refs:', '')
    buff = buff.replace('.', '')
    buff = buff.replace(';', '')
    arr = buff.split()

    output = ""
    arrLen = len(arr)
    for i in range(arrLen):
        item = arr[i]
        if '{' in item or '}' in item:
            item = f"\"{item}\""
        if i + 1 < arrLen:
            nextItem = arr[i + 1]
        else:
            nextItem = None
        if item == '[':
            output += item
        elif nextItem == ']':
            output += item
        elif i + 1 == arrLen:
            output += item
        else:
            output += item + ', '

    data = json.loads(output)
    return data


def tlb_to_json(text: str) -> dict[str, Any]:
    # Replace brackets
    start = 0
    end = len(text)
    if '=' in text:
        start = text.find('=') + 1
    if text[start:].startswith(' x{'):  # param has no tlb scheme, return cell value
        end = text.rfind('}') + 1
        return {'_': text[start:end].strip()}
    if "x{" in text:
        end = text.find("x{")
    text = text[start:end]
    text = text.strip()
    text = text.replace('(', '{')
    text = text.replace(')', '}')

    # Add " to strings (step 1)
    buff = text
    buff = buff.replace('\r', ' ')
    buff = buff.replace('\n', ' ')
    buff = buff.replace('\t', ' ')
    buff = buff.replace('{', ' ')
    buff = buff.replace('}', ' ')
    buff = buff.replace(':', ' ')

    # Add " to strings (step 2)
    buff2 = ""
    item_list: list[str] = []
    for item in list(buff):
        if item == ' ':
            if len(buff2) > 0:
                item_list.append(buff2)
                buff2 = ""
            item_list.append(item)
        else:
            buff2 += item

    # Add " to strings (step 3)
    i = 0
    for item in item_list:
        l = len(item)
        if item == ' ':
            pass
        elif item.isdigit() is False:
            c = '"'
            item2 = c + item + c
            text = text[:i] + item2 + text[i + l:]
            i += 2
        i += l

    # set object type
    text = text.replace('{"', '{"_":"')

    # set comas
    while True:
        try:
            data = json.loads(text)
            break
        except json.JSONDecodeError as err:
            if "Expecting ',' delimiter" in err.msg:
                text = text[:err.pos] + ',' + text[err.pos:]
            elif "Expecting property name enclosed in double quotes" in err.msg:
                text = text[:err.pos] + '"_":' + text[err.pos:]
            else:
                raise err
    return data
