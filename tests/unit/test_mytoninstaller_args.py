import pytest

from mytoninstaller.__main__ import _parse_general_args, get_context


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


@pytest.mark.parametrize("value", [None, "", " ", "\t \n"])
def test_empty_public_ip_uses_automatic_detection(monkeypatch, value):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    if value is None:
        monkeypatch.delenv("PUBLIC_IP", raising=False)
    else:
        monkeypatch.setenv("PUBLIC_IP", value)
    ctx = get_context(_parse_general_args(["-m", "validator"]))
    assert ctx.public_ip is None


def test_public_ip_removes_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    monkeypatch.setenv("PUBLIC_IP", " 192.0.2.10\t")
    ctx = get_context(_parse_general_args(["-m", "validator"]))
    assert ctx.public_ip == "192.0.2.10"
