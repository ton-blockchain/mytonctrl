from __future__ import annotations

import typing
from pathlib import Path
import sys
from typing import List, Literal, Optional, Union

import pytest

from mypyconsole.mypyconsole import UsageError
from mypyconsole.command_parser import Annotated, Arg, CommandParser

MODES = ["validator", "liteserver"]
MODE_NAMES = ["validator", "nominator-pool", "liteserver"]


def coins(text: str):
    return text if text == "all" else float(text)


COINS = Annotated[Union[float, str], Arg(type=coins)]


def _run(name, handler):
    parser = CommandParser(name, handler)
    return parser.run, parser.short_usage()


def test_positionals_and_bool_flag():
    calls = []

    def set_settings(name: str, value: str, *, force: bool = False):
        calls.append((name, value, force))

    run, usage = _run("set", set_settings)
    assert usage == "[--force] name value"

    run(["stake", "1000"])
    run(["--force", "stake", "1000"])
    run(["stake", "1000", "--force"])
    assert calls == [("stake", "1000", False), ("stake", "1000", True), ("stake", "1000", True)]


def test_usage_error_carries_argparse_text():
    def set_settings(name: str, value: str, *, force: bool = False):
        raise AssertionError("must not be called")

    run, _ = _run("set", set_settings)
    with pytest.raises(UsageError) as info:
        run(["stake"])
    assert str(info.value) == (
        "usage: set [-h] [--force] name value\n"
        "set: error: the following arguments are required: value"
    )

    with pytest.raises(UsageError) as info:
        run(["a", "b", "c"])
    assert "set: error: unrecognized arguments: c" in str(info.value)


def test_help_prints_and_skips_handler(capsys):
    called = []

    def get_settings(name: str):
        called.append(name)

    run, _ = _run("get", get_settings)
    run(["-h"])
    assert called == []
    out = capsys.readouterr().out
    assert out.startswith("usage: get [-h] name")


def test_optional_positional_defaults_to_none():
    calls = []

    def reload_global_config(url: Optional[str] = None):
        calls.append(url)

    run, usage = _run("reload_global_config", reload_global_config)
    assert usage == "[url]"
    run([])
    run(["https://example.com/config.json"])
    assert calls == [None, "https://example.com/config.json"]


def test_int_conversion_and_default():
    calls = []

    def set_quic_port(port: int, category: int = 2):
        calls.append((port, category))

    run, usage = _run("set_quic_port", set_quic_port)
    assert usage == "port [category]"
    run(["1234"])
    run(["1234", "3"])
    run(["-1"])
    assert calls == [(1234, 2), (1234, 3), (-1, 2)]

    with pytest.raises(UsageError) as info:
        run(["abc"])
    assert "set_quic_port: error: argument port: invalid int value: 'abc'" in str(info.value)


def test_list_positional_requires_at_least_one():
    calls = []

    def vote_offer(offer_hashes: List[str]):
        calls.append(offer_hashes)

    run, usage = _run("vo", vote_offer)
    assert usage == "offer_hashes [offer_hashes ...]"
    run(["h1", "h2"])
    assert calls == [["h1", "h2"]]
    with pytest.raises(UsageError) as info:
        run([])
    assert "the following arguments are required: offer_hashes" in str(info.value)


def test_list_positional_with_default_accepts_nothing():
    calls = []

    def handler(names: List[str] = ()):
        calls.append(list(names))

    run, usage = _run("cmd", handler)
    assert usage in ("[names ...]", "[names [names ...]]")
    run([])
    run(["a"])
    assert calls == [[], ["a"]]


def test_var_positional():
    calls = []

    def handler(first: str, *rest: int):
        calls.append((first, rest))

    run, usage = _run("cmd", handler)
    assert usage in ("first [rest ...]", "first [rest [rest ...]]")
    run(["a"])
    run(["a", "1", "2"])
    assert calls == [("a", ()), ("a", (1, 2))]


def test_literal_choices():
    calls = []

    def status(mode: Literal["fast", "full"] = "full"):
        calls.append(mode)

    run, usage = _run("status", status)
    assert usage == "[{fast,full}]"
    run(["fast"])
    assert calls == ["fast"]
    with pytest.raises(UsageError) as info:
        run(["slow"])
    assert "argument mode: invalid choice: 'slow'" in str(info.value)


def test_bool_positional_accepts_only_true_and_false():
    calls = []

    def set_self_collate(value: bool):
        calls.append(value)

    run, _ = _run("set_self_collate", set_self_collate)
    run(["true"])
    run(["false"])
    assert calls == [True, False]
    for word in ["True", "yes", "on", "1", "maybe"]:
        with pytest.raises(UsageError) as info:
            run([word])
        assert f"argument value: expected true or false, got '{word}'" in str(info.value)


def test_option_with_value_and_trailing_underscore():
    calls = []

    def handler(name: str, *, tmp_dir: Optional[str] = None, all_: bool = False):
        calls.append((name, tmp_dir, all_))

    run, usage = _run("cmd", handler)
    assert usage == "[--tmp-dir TMP_DIR] [--all] name"
    run(["x"])
    run(["x", "--tmp-dir", "/tmp/y", "--all"])
    assert calls == [("x", None, False), ("x", "/tmp/y", True)]


def test_required_option():
    def handler(*, adnl: str):
        pass

    run, usage = _run("cmd", handler)
    assert usage == "--adnl ADNL"
    with pytest.raises(UsageError) as info:
        run([])
    assert "the following arguments are required: --adnl" in str(info.value)


def test_optional_bool_option_takes_a_true_or_false_value():
    calls = []

    def handler(*, self_collate: Optional[bool] = None):
        calls.append(self_collate)

    run, usage = _run("cmd", handler)
    assert usage == "[--self-collate {true,false}]"
    run([])
    run(["--self-collate", "true"])
    run(["--self-collate", "false"])
    assert calls == [None, True, False]
    with pytest.raises(UsageError) as info:
        run(["--self-collate"])
    assert "argument --self-collate: expected one argument" in str(info.value)
    with pytest.raises(UsageError) as info:
        run(["--self-collate", "yes"])
    assert "argument --self-collate: expected true or false, got 'yes'" in str(info.value)


def test_bool_option_default_true_is_rejected():
    def handler(*, bounce: bool = True):
        pass

    with pytest.raises(TypeError, match=r"cmd\.bounce: a flag cannot default to True"):
        CommandParser("cmd", handler)


def test_path_and_float_types():
    calls = []

    def handler(path: Path, amount: float):
        calls.append((path, amount))

    run, _ = _run("cmd", handler)
    run(["/tmp/x", "1.5"])
    assert calls == [(Path("/tmp/x"), 1.5)]


def test_unannotated_parameter_is_str():
    calls = []

    def handler(name):
        calls.append(name)

    run, _ = _run("cmd", handler)
    run(["42"])
    assert calls == ["42"]


def test_bound_method_skips_self():
    class Module:
        def __init__(self):
            self.calls = []

        def handler(self, name: str, *, force: bool = False):
            self.calls.append((name, force))

    module = Module()
    run, usage = _run("cmd", module.handler)
    assert usage == "[--force] name"
    run(["x", "--force"])
    assert module.calls == [("x", True)]


def test_var_keyword_is_rejected_at_registration():
    def handler(**kwargs):
        pass

    with pytest.raises(TypeError, match=r"\*\*kwargs"):
        CommandParser("cmd", handler)


@pytest.mark.parametrize(
    "annotation", [Union[int, str], Optional[Union[int, str]], typing.Dict[str, int]]
)
def test_unsupported_annotation_is_rejected_at_registration(annotation):
    def handler(value):
        pass

    handler.__annotations__["value"] = annotation
    with pytest.raises(TypeError, match=r"cmd\.value: unsupported annotation .*Arg\(type=\.\.\.\)"):
        CommandParser("cmd", handler)


def test_parser_description_and_docstring_epilog(capsys):
    def handler(name: str):
        """Longer explanation of the command."""

    parser = CommandParser("cmd", handler, description="Short description")
    assert parser.description == "Short description"
    assert parser.epilog == "Longer explanation of the command."
    assert parser.short_usage() == "name"


def test_option_abbreviations_are_rejected():
    def set_settings(name: str, value: str, *, force: bool = False):
        raise AssertionError("must not be called")

    run, _ = _run("set", set_settings)
    with pytest.raises(UsageError) as info:
        run(["--for", "stake", "1000"])
    assert "unrecognized arguments: --for" in str(info.value)


def test_raw_address_and_negative_numbers_are_values():
    calls = []

    def handler(addr: str, amount: float = 0.0):
        calls.append((addr, amount))

    run, _ = _run("vas", handler)
    raw = "-1:" + "5" * 64
    run([raw])
    run([raw, "-0.5"])
    assert calls == [(raw, 0.0), (raw, -0.5)]


def test_arg_marker_adds_short_flag_help_choices_and_converter():
    calls = []

    def handler(
        mode: Annotated[str, Arg(choices=MODES, help="node mode")],
        amount: Annotated[Union[float, str], Arg(type=coins)],
        *,
        user: Annotated[Optional[str], Arg("-u", help="run as this user")] = None,
        no_bounce: Annotated[bool, Arg("-n")] = False,
    ):
        calls.append((mode, amount, user, no_bounce))

    run, usage = _run("cmd", handler)
    assert usage == "[-u USER] [-n] {validator,liteserver} amount"
    run(["validator", "all", "-u", "yungwine", "-n"])
    run(["liteserver", "1.5", "--user", "x", "--no-bounce"])
    assert calls == [("validator", "all", "yungwine", True), ("liteserver", 1.5, "x", True)]
    with pytest.raises(UsageError) as info:
        run(["collator", "1"])
    assert "argument mode: invalid choice: 'collator'" in str(info.value)
    with pytest.raises(UsageError) as info:
        run(["validator", "abc"])
    assert "argument amount: invalid coins value: 'abc'" in str(info.value)
    parser = CommandParser("cmd", handler)
    assert "run as this user" in parser.format_help()


def test_arg_metavar_names_the_value_in_the_usage():
    calls = []

    def handler(mode_name: Annotated[str, Arg(choices=MODE_NAMES, metavar="mode_name", help="one of: %(choices)s")],
                *, user: Annotated[Optional[str], Arg("-u", metavar="NAME")] = None):
        calls.append((mode_name, user))

    run, usage = _run("enable_mode", handler)
    assert usage == "[-u NAME] mode_name"
    run(["liteserver", "-u", "x"])
    assert calls == [("liteserver", "x")]
    with pytest.raises(UsageError) as info:
        run(["collator"])
    assert "argument mode_name: invalid choice: 'collator'" in str(info.value)
    assert "nominator-pool" in str(info.value)
    assert "one of: validator, nominator-pool, liteserver" in CommandParser("enable_mode", handler).format_help()


def test_arg_choices_keep_the_annotation_converter():
    calls = []

    def handler(category: Annotated[int, Arg(choices=[0, 1, 2])]):
        calls.append(category)

    run, _ = _run("cmd", handler)
    run(["2"])
    assert calls == [2]
    with pytest.raises(UsageError) as info:
        run(["3"])
    assert "argument category: invalid choice:" in str(info.value)


def test_arg_type_keeps_list_and_optional():
    calls = []

    def handler(amounts: Annotated[List[Union[float, str]], Arg(type=coins)], *, fee: Annotated[Optional[float], Arg(type=coins)] = None):
        calls.append((amounts, fee))

    run, usage = _run("cmd", handler)
    assert usage == "[--fee FEE] amounts [amounts ...]"
    run(["1.5", "all"])
    run(["2", "--fee", "all"])
    assert calls == [([1.5, "all"], None), ([2.0], "all")]


def test_annotated_handler_keeps_real_defaults_for_direct_calls():
    def handler(dest: Annotated[Optional[str], Arg(help="path")] = None, *, user: Annotated[Optional[str], Arg("-u")] = None, force: Annotated[bool, Arg("-f")] = False):
        return dest, user, force

    CommandParser("cmd", handler)
    assert handler() == (None, None, False)
    assert handler("x", user="u") == ("x", "u", False)


def test_arg_in_default_is_rejected_at_registration():
    def handler(user: Optional[str] = Arg("-u")):  # pyright: ignore[reportArgumentType]
        pass

    with pytest.raises(TypeError, match=r"cmd\.user: Arg\(\.\.\.\) goes inside Annotated"):
        CommandParser("cmd", handler)


def test_only_one_arg_per_annotated_and_foreign_metadata_is_ignored():
    def two(name: Annotated[str, Arg(help="a"), Arg(help="b")]):
        pass

    def nested(name: Annotated[Optional[COINS], Arg(help="b")] = None):
        pass

    for handler in (two, nested):
        with pytest.raises(TypeError, match=r"cmd\.name: only one Arg"):
            CommandParser("cmd", handler)

    calls = []

    def foreign(port: Annotated[int, "not our metadata"]):
        calls.append(port)

    run, usage = _run("cmd", foreign)
    assert usage == "port"
    run(["8080"])
    assert calls == [8080]


def test_alias_inside_optional_and_list():
    calls = []

    def handler(amounts: List[COINS], *, fee: Optional[COINS] = None):
        calls.append((amounts, fee))

    run, usage = _run("cmd", handler)
    assert usage == "[--fee FEE] amounts [amounts ...]"
    run(["1.5", "all"])
    run(["2", "--fee", "all"])
    assert calls == [([1.5, "all"], None), ([2.0], "all")]
    with pytest.raises(UsageError) as info:
        run(["abc"])
    assert "argument amounts: invalid coins value: 'abc'" in str(info.value)


def test_annotated_var_positional_gets_help():
    def update(*target: Annotated[str, Arg(help="repo url and/or branch")], branch: Annotated[Optional[str], Arg(help="git branch")] = None):
        pass

    parser = CommandParser("update", update)
    assert parser.short_usage() == "[--branch BRANCH] [target ...]" or parser.short_usage() == "[--branch BRANCH] [target [target ...]]"
    assert "repo url and/or branch" in parser.format_help()
    assert "git branch" in parser.format_help()


def test_double_dash_passes_option_like_tokens_to_var_positional():
    calls = []

    def vote_offer(*offer_hashes: str, force: bool = False):
        calls.append((force, list(offer_hashes)))

    run, _ = _run("vo", vote_offer)
    run(["--force", "--", "-x", "--y"])
    assert calls == [(True, ["-x", "--y"])]
    with pytest.raises(UsageError) as info:
        run(["-x"])
    assert "unrecognized arguments: -x" in str(info.value)


def test_forward_unknown_passes_foreign_tokens_in_order(capsys):
    calls = []

    def benchmark(*benchmark_args: str, tmp_dir: Optional[str] = None):
        calls.append((tmp_dir, list(benchmark_args)))

    parser = CommandParser("benchmark", benchmark, forward_unknown=True)
    assert parser.short_usage() == "[--tmp-dir TMP_DIR] [benchmark_args ...]"
    parser.run([])
    parser.run(["--nodes", "4", "--tmp-dir", "/x", "--tps", "1000", "-1", "run"])
    parser.run(["--tmp-dir", "/x", "--", "--tmp-dir", "/y", "-h"])
    assert calls == [
        (None, []),
        ("/x", ["--nodes", "4", "--tps", "1000", "-1", "run"]),
        ("/x", ["--tmp-dir", "/y", "-h"]),
    ]

    parser.run(["-h"])
    assert len(calls) == 3
    assert capsys.readouterr().out.startswith(
        "usage: benchmark [-h] [--tmp-dir TMP_DIR] [benchmark_args ...]"
    )

    with pytest.raises(UsageError) as info:
        parser.run(["--tmp-dir"])
    assert "argument --tmp-dir: expected one argument" in str(info.value)


def test_forward_unknown_requires_only_var_positional_and_options():
    def with_positional(name: str, *rest: str):
        pass

    def without_var_positional(*, force: bool = False):
        pass

    for handler in (with_positional, without_var_positional):
        with pytest.raises(TypeError, match="forward_unknown needs a handler taking only"):
            CommandParser("cmd", handler, forward_unknown=True)


@pytest.mark.skipif(sys.version_info >= (3, 10), reason="PEP 604 evaluates fine on 3.10+")
def test_pep604_annotation_is_rejected_with_a_hint_below_310():
    def handler(url: str | None = None):
        pass

    with pytest.raises(TypeError, match="Optional"):
        CommandParser("cmd", handler)


def test_var_positional_literal_accepts_no_words():
    calls = []

    def vl(*words: Literal["past", "fast"], json_: bool = False):
        calls.append((words, json_))

    run, usage = _run("vl", vl)
    assert usage in ("[--json] [{past,fast} ...]", "[--json] [{past,fast} [{past,fast} ...]]")
    run([])
    run(["past", "fast", "--json"])
    run(["--json", "past"])
    assert calls == [((), False), (("past", "fast"), True), (("past",), True)]
    with pytest.raises(UsageError) as info:
        run(["hash"])
    assert "argument words: invalid choice: 'hash'" in str(info.value)


def test_list_of_literal_with_an_empty_default():
    calls = []

    def handler(words: List[Literal["a", "b"]] = ()):
        calls.append(list(words))

    run, _ = _run("cmd", handler)
    run([])
    run(["a", "b"])
    assert calls == [[], ["a", "b"]]
    with pytest.raises(UsageError):
        run(["c"])


@pytest.mark.skipif(sys.version_info < (3, 14), reason="argparse colours help only on 3.14+")
def test_usage_strings_are_never_coloured(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")

    def handler(name: str, *, flag: bool = False) -> None: ...

    parser = CommandParser("cmd", handler)
    assert parser.short_usage() == "[--flag] name"
    assert parser.format_usage() == "usage: cmd [-h] [--flag] name\n"
