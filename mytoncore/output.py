# pyright: strict

from __future__ import annotations

from typing import Any, Iterable, List, Union, TypeVar

import json
import re

from mypylib.mypylib import parse


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


def parse_int(key: str, text: str):
    m = re.search(rf"\b{re.escape(key)}:(\d+)", text)
    if m is None:
        raise ValueError(f"Key {key} not found in text: {text}")
    return int(m.group(1))


def parse_nanograms(key: str, text: str) -> float:
    m = re.search(
        rf"\b{re.escape(key)}:\(nanograms\s+amount:\(var_uint\s+len:\d+\s+value:(\d+)\)",
        text,
    )
    if m is None:
        raise ValueError(f"Key {key!r} not found in text: {text!r}")
    return int(m.group(1)) / 10**9


def get_var_from_text(text: str | None, search: str | None):
    if search is None or text is None:
        return
    if search not in text:
        return
    text = text[text.find(search) + len(search):]
    if text and text[0] in ':= ':
        text = text[1:]
    search2 = ')'
    if search2 in text:
        text = text[:text.find(search2)]
    search2 = ' '
    if search2 in text:
        text = text[:text.find(search2)]
    return text


def get_var_from_worker_output(text: str | None, search: str):
    if ':' not in search:
        search += ':'
    if text is None:
        return None
    if search not in text:
        return None
    start = text.find(search) + len(search)
    count = 0
    bcount = 0
    text_len = len(text)
    end = text_len
    for i in range(start, text_len):
        letter = text[i]
        if letter == '(':
            count += 1
            bcount += 1
        elif letter == ')':
            count -= 1
        if letter == ')' and count < 1:
            end = i + 1
            break
        elif letter == '\n' and count < 1:
            end = i
            break
    result = text[start:end]
    if count != 0 and bcount == 0:
        result = result.replace(')', '')
    return result


def get_var_from_dict(data: dict[str, Any], search: str) -> str | None:
    arr = search.split('.')
    search2 = arr.pop()
    d = data
    for search in arr:
        d = get_item_from_dict(d, search)
    text = get_key_from_dict(d, search2)
    result = get_var_from_text(text, search2)
    return result


def get_int_from_dict(data: dict[str, Any], search: str) -> int | None:
    result = get_var_from_dict(data, search)
    return int(result) if result is not None else None


X = TypeVar("X")
def _find_in_dict(data: dict[str, X] | None, search: str):
  if data is None:
      return None, None
  for key, item in data.items():
      if search in key:
          return key, item
  return None, None


def get_item_from_dict(data: dict[str, X] | None, search: str) -> X | None:
    return _find_in_dict(data, search)[1]


def get_key_from_dict(data: dict[str, X] | None, search: str) -> str | None:
    return _find_in_dict(data, search)[0]


def get_cell_body(buff: Iterable[str]):
    body = ""
    for item in buff:
        if "x{" not in item:
            continue
        buff = item[item.index("x{") + 2 : item.index("}")]
        buff = buff.replace("_", "")
        if len(buff) % 2 == 1:
            buff = "0" + buff
        body += buff
    return body
