from __future__ import annotations

import re


_RESULT_RE = re.compile(r"(?m)^[^\S\n]*result:[^\S\n]*")
_REMOTE_RESULT_RE = re.compile(r"(?m)^[^\S\n]*remote result(?: \(not to be trusted\))?:[^\S\n]*")


def parse_result_stack(output: str) -> list[str]:
    return _parse_section_stack(output, _RESULT_RE, "result")


def parse_remote_result_stack(output: str) -> list[str]:
    return _parse_section_stack(output, _REMOTE_RESULT_RE, "remote result")


def _parse_section_stack(output: str, section_re: re.Pattern[str], section_name: str) -> list[str]:
    match = section_re.search(output)
    if not match:
        raise ValueError(f"'{section_name}' section was not found")

    pos = _skip_ws(output, match.end())
    if output.startswith("error", pos):
        raise ValueError(output[pos:].splitlines()[0].strip())
    if output.startswith("<none>", pos):
        raise ValueError(f"{section_name} section does not contain a stack")

    values, pos = _parse_stack_as_strings(output, pos)
    pos = _skip_ws(output, pos)
    if pos != len(output):
        raise ValueError(f"unexpected text after {section_name} stack: {output[pos:pos + 40]!r}")
    return values


def _parse_stack_as_strings(text: str, pos: int = 0) -> tuple[list[str], int]:
    pos = _skip_ws(text, pos)
    if pos >= len(text) or text[pos] != "[":
        raise ValueError("expected stack opening '['")
    pos += 1

    values: list[str] = []
    while True:
        pos = _skip_ws(text, pos)
        if pos >= len(text):
            raise ValueError("unterminated stack")
        if text[pos] == "]":
            return values, pos + 1

        start = pos
        pos = _skip_value(text, pos)
        values.append(_clean_value(text[start:pos].strip()))


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _skip_value(text: str, pos: int) -> int:
    if pos >= len(text):
        raise ValueError("expected value")
    start = pos
    if text[pos] == '"':
        return _skip_string(text, pos)
    if text[pos] == "[":
        return _skip_balanced(text, pos, "[", "]")
    if text[pos] == "(":
        return _skip_balanced(text, pos, "(", ")")

    for prefix in ("CS{", "BC{", "C{", "Box{", "Cont{", "Object{"):
        if text.startswith(prefix, pos):
            return _skip_balanced(text, pos + len(prefix) - 1, "{", "}")

    while pos < len(text) and not text[pos].isspace() and text[pos] not in "])":
        pos += 1
    if pos == start:
        raise ValueError(f"unexpected character {text[pos]!r}")
    return pos


def _skip_balanced(text: str, pos: int, opening: str, closing: str) -> int:
    if text[pos] != opening:
        raise ValueError(f"expected {opening!r}")
    depth = 1
    pos += 1
    while pos < len(text):
        if text[pos] == '"':
            pos = _skip_string(text, pos)
            continue
        if text[pos] == opening:
            depth += 1
        elif text[pos] == closing:
            depth -= 1
            if depth == 0:
                return pos + 1
        pos += 1
    raise ValueError(f"unterminated {opening}{closing} value")


def _skip_string(text: str, pos: int) -> int:
    pos += 1
    end = text.find('"', pos)
    if end == -1:
        raise ValueError("unterminated string")
    return end + 1


def _skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos
