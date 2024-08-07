import base64
import json
import re


def str2b64(s):
    b = s.encode("utf-8")
    b64 = base64.b64encode(b)
    b64 = b64.decode("utf-8")
    return b64
# end define


def b642str(b64):
    b64 = b64.encode("utf-8")
    b = base64.b64decode(b64)
    s = b.decode("utf-8")
    return s
# end define


def dict2b64(d):
    s = json.dumps(d)
    b64 = str2b64(s)
    return b64
# end define


def b642dict(b64):
    s = b642str(b64)
    d = json.loads(s)
    return d
# end define


def hex2b64(input):  # TODO: remove duplicates
    hexBytes = bytes.fromhex(input)
    b64Bytes = base64.b64encode(hexBytes)
    b64String = b64Bytes.decode()
    return b64String
# end define


def b642hex(input):
    b64Bytes = input.encode()
    hexBytes = base64.b64decode(b64Bytes)
    hexString = hexBytes.hex()
    return hexString
# end define


def xhex2hex(x):
    try:
        b = x[1:]
        h = b.lower()
        return h
    except:
        return None
#end define

def hex2base64(h):  # TODO: remove duplicates
    b = bytes.fromhex(h)
    b64 = base64.b64encode(b)
    s = b64.decode("utf-8")
    return s
#end define


def str2bool(str):
    if str == "true":
        return True
    return False
# end define


def ng2g(ng):
    if ng is None:
        return
    return int(ng)/10**9
#end define


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
# end define
