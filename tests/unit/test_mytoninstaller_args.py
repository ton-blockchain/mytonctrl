import pytest

from mytoninstaller.__main__ import _parse_general_args


def test_parse_general_args_accepts_shell_boolean_values():
    args = _parse_general_args([
        "-u",
        "alice",
        "-t",
        "false",
        "--dump",
        "true",
        "-m",
        "validator",
        "--only-mtc",
        "false",
        "--only-node",
        "true",
        "--backup",
        "none",
    ])

    assert args.user == "alice"
    assert args.telemetry is False
    assert args.dump is True
    assert args.mode == "validator"
    assert args.only_mtc is False
    assert args.only_node is True
    assert args.backup == "none"


def test_parse_general_args_accepts_flag_booleans():
    args = _parse_general_args(["-t", "--dump", "--only-mtc", "--only-node"])

    assert args.telemetry is False
    assert args.dump is True
    assert args.only_mtc is True
    assert args.only_node is True


@pytest.mark.parametrize("option", ["--user", "--command", "--event", "--mode"])
def test_parse_general_args_rejects_removed_long_options(option):
    with pytest.raises(SystemExit):
        _parse_general_args([option, "value"])
