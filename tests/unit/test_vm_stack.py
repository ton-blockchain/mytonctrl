"""Tests for parsing lite-client `runmethodx` output.

`runmethodx` prints the locally re-run stack under "result:" (which may fail
with a virtualization error on the pruned state proof) and then the
server-side stack under "remote result (not to be trusted):". The error and
empty forms drop the parenthesized part: "remote result: error N" and
"remote result: <none>".
"""
import pytest

from mytoncore.vm_stack import parse_remote_result_stack, parse_result_stack


RUNMETHODX_OK = (
    "arguments:  [ 104128 ] \n"
    "gas used: 1298\n"
    "result:  [ 297 ] \n"
    "remote result (not to be trusted):  [ 297 ] \n"
)

RUNMETHODX_LOCAL_RUN_FAILED = (
    "arguments:  [ 104128 ] \n"
    "gas used: 0\n"
    "result: error -1001\n"
    "remote result (not to be trusted):  [ 297 1000000000 C{ABCD} () ] \n"
)


def test_parse_remote_result_stack_ok():
    assert parse_remote_result_stack(RUNMETHODX_OK) == ["297"]


def test_parse_remote_result_stack_ignores_failed_local_rerun():
    stack = parse_remote_result_stack(RUNMETHODX_LOCAL_RUN_FAILED)
    assert stack == ["297", "1000000000", "C{ABCD}", "()"]


def test_parse_remote_result_stack_raises_on_remote_error():
    output = (
        "arguments:  [ 104128 ] \n"
        "gas used: 542\n"
        "result: error 11\n"
        "remote result: error 11\n"
    )
    with pytest.raises(ValueError, match="error 11"):
        parse_remote_result_stack(output)


def test_parse_remote_result_stack_raises_on_empty_remote_result():
    output = "arguments:  [ 104128 ] \nremote result: <none>\n"
    with pytest.raises(ValueError, match="does not contain a stack"):
        parse_remote_result_stack(output)


def test_parse_remote_result_stack_raises_when_section_missing():
    output = "arguments:  [ 104128 ] \ngas used: 1298\nresult:  [ 297 ] \n"
    with pytest.raises(ValueError, match="'remote result' section was not found"):
        parse_remote_result_stack(output)


def test_parse_result_stack_still_parses_runmethodfull_output():
    output = "arguments:  [ 85143 ] \ngas used: 1298\nresult:  [ 297 () ] \n"
    assert parse_result_stack(output) == ["297", "()"]


def test_parse_result_stack_does_not_match_remote_result_line():
    # only the remote section is present -> the local "result:" parser must not
    # silently pick it up
    output = "arguments:  [ 85143 ] \nremote result (not to be trusted):  [ 297 ] \n"
    with pytest.raises(ValueError, match="'result' section was not found"):
        parse_result_stack(output)
