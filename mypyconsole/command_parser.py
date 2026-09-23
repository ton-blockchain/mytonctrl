# pyright: strict
from __future__ import annotations

import argparse
import inspect
import re
import sys
import typing
from dataclasses import dataclass
from typing import Any, Callable, List, Sequence, cast

if sys.version_info >= (3, 9):
    from typing import Annotated, get_args, get_origin, get_type_hints
else:
    from typing_extensions import Annotated, get_args, get_origin, get_type_hints


class UsageError(Exception):
    pass


_NEGATIVE_NUMBER_OR_RAW_ADDR = re.compile(r"^-\d+$|^-\d*\.\d+$|^-\d+:[0-9a-fA-F]{64}$")


class _HelpShown(Exception):
    pass


class _Choices(List[Any]):
    def __contains__(self, item: object) -> bool:
        if isinstance(item, (list, tuple)):
            contains = super().__contains__
            return all(contains(word) for word in cast("Sequence[Any]", item))
        return super().__contains__(item)


@dataclass(frozen=True)
class Arg:
    flag: str | None = None
    help: str | None = None
    choices: Sequence[Any] | None = None
    type: Callable[[str], Any] | None = None
    metavar: str | None = None


class CommandParser(argparse.ArgumentParser):
    def __init__(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str | None = None,
        *,
        forward_unknown: bool = False,
    ) -> None:
        no_color: dict[str, Any] = (
            {"color": False} if sys.version_info >= (3, 14) else {}
        )
        super().__init__(
            prog=name,
            description=description or None,
            epilog=inspect.getdoc(handler),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            allow_abbrev=False,
            **no_color,
        )
        self._negative_number_matcher = _NEGATIVE_NUMBER_OR_RAW_ADDR
        self.handler = handler
        self.params = list(inspect.signature(handler).parameters.values())
        self.forward_unknown = forward_unknown
        kinds = {p.kind for p in self.params}
        if forward_unknown and kinds - {inspect.Parameter.KEYWORD_ONLY} != {
            inspect.Parameter.VAR_POSITIONAL
        }:
            raise TypeError(
                f"{name}: forward_unknown needs a handler taking only *args "
                "and keyword-only options"
            )
        try:
            hints = get_type_hints(handler, include_extras=True)
        except TypeError as err:
            raise TypeError(
                f"{name}: {err}; use Optional[T] / List[T] instead"
            ) from None
        for p in self.params:
            try:
                self._add_parameter(p, hints.get(p.name, p.empty))
            except TypeError as err:
                raise TypeError(f"{name}.{p.name}: {err}") from None
        if forward_unknown:
            var_name = next(p.name for p in self.params if p.kind is p.VAR_POSITIONAL)
            usage = self.format_usage().split()[2:]
            self.usage = " ".join(["%(prog)s", *usage, f"[{var_name} ...]"])

    def run(self, args: list[str]) -> None:
        try:
            if self.forward_unknown:
                namespace, forwarded = self.parse_known_args(args)
                if "--" in forwarded:
                    forwarded.remove("--")
            else:
                namespace, forwarded = self.parse_args(args), []
        except _HelpShown:
            return
        values = vars(namespace)
        positional: list[Any] = []
        for p in self.params:
            if p.kind is p.VAR_POSITIONAL:
                positional += forwarded if self.forward_unknown else values.pop(p.name)
            elif p.kind is not p.KEYWORD_ONLY:
                positional.append(values.pop(p.name))
        try:
            self.handler(*positional, **values)
        except UsageError as err:
            self.error(str(err))

    def short_usage(self) -> str:
        return " ".join(self.format_usage().split()[3:])

    def error(self, message: str) -> typing.NoReturn:
        raise UsageError(f"{self.format_usage()}{self.prog}: error: {message}")

    def exit(self, status: int = 0, message: str | None = None) -> typing.NoReturn:
        raise _HelpShown()

    def _add_parameter(self, p: inspect.Parameter, annotation: Any) -> None:
        if p.kind is p.VAR_KEYWORD:
            raise TypeError(f"**{p.name} cannot be mapped to command-line arguments")
        if p.kind is p.VAR_POSITIONAL and self.forward_unknown:
            return
        if isinstance(p.default, Arg):
            raise TypeError("Arg(...) goes inside Annotated[...], not in the default")
        item, is_list, spec = _unwrap(annotation)
        required = p.default is p.empty
        if p.kind is p.KEYWORD_ONLY:
            flags = [spec.flag] if spec.flag else []
            flags.append("--" + p.name.rstrip("_").replace("_", "-"))
            if item is bool and p.default is not None:
                if p.default is True:
                    raise TypeError("a flag cannot default to True")
                self.add_argument(
                    *flags, dest=p.name, action="store_true", help=spec.help
                )
                return
            names: list[str] = flags
            kw: dict[str, Any] = {
                "dest": p.name,
                "required": required,
                "nargs": "+" if is_list else None,
            }
            if item is bool:
                kw["metavar"] = "{true,false}"
        else:
            names = [p.name]
            if p.kind is p.VAR_POSITIONAL:
                nargs = "*"
            elif is_list:
                nargs = "+" if required else "*"
            else:
                nargs = None if required else "?"
            kw = {"nargs": nargs}
        if not required:
            kw["default"] = p.default
        kw.update({"type": spec.type} if spec.type else _converter(item))
        if spec.choices is not None:
            kw["choices"] = _Choices(spec.choices)
        if spec.metavar is not None:
            kw["metavar"] = spec.metavar
        self.add_argument(*names, help=spec.help, **kw)


def _unwrap(annotation: Any) -> tuple[Any, bool, Arg]:
    is_list = False
    spec: Arg | None = None
    while True:
        origin = get_origin(annotation)
        if origin is Annotated:
            annotation, *extras = get_args(annotation)
            for extra in extras:
                if isinstance(extra, Arg):
                    if spec is not None:
                        raise TypeError("only one Arg(...) per parameter")
                    spec = extra
        elif origin is typing.Union:
            members = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(members) != 1:
                break
            annotation = members[0]
        elif origin is list and not is_list:
            annotation = get_args(annotation)[0]
            is_list = True
        else:
            break
    return annotation, is_list, spec or Arg()


def _converter(item: Any) -> dict[str, Any]:
    if item in (inspect.Parameter.empty, str):
        return {}
    if item is bool:
        return {"type": _parse_bool}
    if get_origin(item) is typing.Literal:
        choices = get_args(item)
        return {"choices": _Choices(choices)}
    if callable(item) and get_origin(item) is None:
        return {"type": item}
    raise TypeError(f"unsupported annotation {item!r}, use Arg(type=...)")


def _parse_bool(text: str) -> bool:
    if text == "true":
        return True
    if text == "false":
        return False
    raise argparse.ArgumentTypeError(f"expected true or false, got {text!r}")
