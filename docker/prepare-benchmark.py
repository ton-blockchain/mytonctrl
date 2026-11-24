#!/usr/bin/env python3
"""Fetch the pinned TON Python test harness and schemas during image creation."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
from urllib.request import Request, urlopen


SOURCE_PREFIXES = (
    "test/tontester/",
    "test/integration/",
    "tl/generate/scheme/",
)
SOURCE_SUFFIXES = {".py", ".tl", ".tlb", ".toml", ".typed"}
REQUIRED_FILES = (
    "LICENSE.LGPL",
    "crypto/block/block.tlb",
    "test/tontester/pyproject.toml",
    "test/tontester/generate_tl.py",
    "test/tontester/src/tontester/install.py",
    "test/tontester/src/tontester/network.py",
    "test/tontester/src/tontester/zerostate.py",
    "test/tontester/src/contract/__init__.py",
    "test/tontester/src/tonlib/tonlib_cdll.py",
    "tl/generate/scheme/lite_api.tl",
    "tl/generate/scheme/ton_api.tl",
    "tl/generate/scheme/tonlib_api.tl",
)
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_SOURCE_BYTES = 50 * 1024 * 1024


def validate_revision(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ValueError(
            "TON_BENCHMARK_REVISION must be a full 40-character Git commit"
        )
    return value.lower()


def selected_file(path: str) -> bool:
    return path in ("LICENSE.LGPL", "crypto/block/block.tlb") or (
        path.startswith(SOURCE_PREFIXES)
        and PurePosixPath(path).suffix in SOURCE_SUFFIXES
    )


def extract_source(archive: tarfile.TarFile, destination: Path, revision: str) -> int:
    root = f"ton-{validate_revision(revision)}"
    seen = set()
    total = 0
    for member in archive:
        name = PurePosixPath(member.name)
        if (
            name.is_absolute()
            or ".." in name.parts
            or not name.parts
            or name.parts[0] != root
        ):
            raise ValueError(f"Invalid TON source archive path: {member.name}")
        relative = PurePosixPath(*name.parts[1:])
        if not selected_file(str(relative)):
            continue
        if member.isdir():
            continue
        if not member.isfile() or str(relative) in seen:
            raise ValueError(f"Invalid TON benchmark source member: {member.name}")
        if member.size < 0 or member.size > MAX_FILE_BYTES:
            raise ValueError(f"TON benchmark source file is too large: {member.name}")
        total += member.size
        if total > MAX_SOURCE_BYTES:
            raise ValueError("TON benchmark source files exceed the expected size")
        seen.add(str(relative))
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError(f"Cannot read TON benchmark source file: {member.name}")
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o644)
    missing = [path for path in REQUIRED_FILES if path not in seen]
    if missing:
        raise ValueError(
            "TON benchmark source archive is incomplete: " + ", ".join(missing)
        )
    (destination / "TON_REVISION").write_text(revision.lower() + "\n")
    return len(seen)


def prepare_source(destination: Path, revision: str) -> None:
    revision = validate_revision(revision)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Benchmark source directory must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    request = Request(
        f"https://codeload.github.com/ton-blockchain/ton/tar.gz/{revision}",
        headers={"User-Agent": "MyTonCtrl-Docker-build"},
    )
    with urlopen(request, timeout=60) as response:
        with tarfile.open(fileobj=response, mode="r|gz") as archive:
            count = extract_source(archive, destination, revision)
    print(
        f"Prepared {count} TON benchmark Python/resource files from {revision}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    prepare_source(args.destination, args.revision)


if __name__ == "__main__":
    main()
