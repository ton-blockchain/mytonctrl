import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from types import SimpleNamespace

import pytest

from mytoninstaller import dump


ARCHIVE_NAME = "dump_20260926.tar.lz"
ARCHIVE_BYTES = b"original downloaded dump"
BASE_URL = "https://dump.ton.org/dumps"


def forbidden(*args, **kwargs):
    raise AssertionError("Must not fetch latest metadata or replace the pinned download")


@pytest.fixture
def harness(monkeypatch, tmp_path):
    cache = tmp_path / "dump-cache"
    database = tmp_path / "db"
    cache.mkdir()
    database.mkdir()
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    monkeypatch.setenv("DUMP_CACHE_DIR", str(cache))
    monkeypatch.delenv("DUMP_VALIDATE_BEFORE_EXTRACT", raising=False)
    monkeypatch.setattr(dump.shutil, "which", lambda tool: "/usr/bin/" + tool)
    monkeypatch.setattr(dump, "is_testnet", lambda path: False)
    monkeypatch.setattr(dump, "check_dump_space", lambda *args: True)
    logs = []
    local = SimpleNamespace(add_log=lambda message, level: logs.append(message))
    ctx = SimpleNamespace(paths=SimpleNamespace(
        ton_db_dir=str(database), ton_work_dir=str(tmp_path), global_config_path="global.json",
    ))
    metadata = dump.DumpMetadata(ARCHIVE_NAME, hashlib.sha256(ARCHIVE_BYTES).hexdigest(), len(ARCHIVE_BYTES), 4096)
    return SimpleNamespace(cache=cache, database=database, local=local, ctx=ctx, metadata=metadata, logs=logs)


def pin(harness, phase="downloading"):
    state = {
        "version": 1,
        "dump_name": "latest",
        "archive_name": ARCHIVE_NAME,
        "archive_url": BASE_URL + "/" + ARCHIVE_NAME,
        "sha256": harness.metadata.sha256,
        "archive_size": harness.metadata.archive_size,
        "disk_size": harness.metadata.disk_size,
        "dump_dir": str(harness.database),
        "phase": phase,
    }
    dump.write_dump_state(str(harness.cache), state)
    return state


def cached(harness, contents=ARCHIVE_BYTES):
    archive = harness.cache / ARCHIVE_NAME
    archive.write_bytes(contents)
    return archive


def test_pin_is_durable_before_downloader_and_failed_download_resumes_original(harness, monkeypatch):
    monkeypatch.setattr(dump, "get_dump_metadata", lambda *args: harness.metadata)
    monkeypatch.setattr(dump, "extract_dump", lambda *args: 0)
    actual_run = subprocess.run
    calls = []

    def downloader(args, **kwargs):
        if args[0] != "aria2c":
            return actual_run(args, **kwargs)
        state = dump.read_dump_state(str(harness.cache))
        assert state["archive_url"] == BASE_URL + "/" + ARCHIVE_NAME
        assert state["phase"] == "downloading"
        assert "-c" in args and state["archive_url"] in args
        calls.append(args)
        archive = harness.cache / ARCHIVE_NAME
        control = harness.cache / (ARCHIVE_NAME + ".aria2")
        if len(calls) == 1:
            archive.write_bytes(ARCHIVE_BYTES[:5])
            control.write_bytes(b"resume control")
            return SimpleNamespace(returncode=7)
        assert archive.read_bytes() == ARCHIVE_BYTES[:5]
        assert control.read_bytes() == b"resume control"
        archive.write_bytes(ARCHIVE_BYTES)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(dump.subprocess, "run", downloader)
    assert not dump.download_dump(harness.local, harness.ctx)
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    assert dump.download_dump(harness.local, harness.ctx)
    assert len(calls) == 2
    assert dump.read_dump_state(str(harness.cache))["phase"] == "extracted"
    assert (harness.cache / ARCHIVE_NAME).read_bytes() == ARCHIVE_BYTES


def test_complete_legacy_archive_uses_exact_dated_metadata_and_no_downloader(harness, monkeypatch):
    archive = cached(harness)
    calls = []
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump, "get_archive_metadata", lambda base, name: calls.append((base, name)) or harness.metadata)
    monkeypatch.setattr(dump, "extract_dump", lambda *args: 0)
    actual_run = subprocess.run

    def checksum_only(args, **kwargs):
        assert args[0] == "sha256sum"
        return actual_run(args, **kwargs)

    monkeypatch.setattr(dump.subprocess, "run", checksum_only)
    assert dump.download_dump(harness.local, harness.ctx)
    assert calls == [(BASE_URL, ARCHIVE_NAME)]
    assert archive.read_bytes() == ARCHIVE_BYTES
    assert dump.read_dump_state(str(harness.cache))["archive_name"] == ARCHIVE_NAME


def test_legacy_archive_metadata_failure_preserves_data_without_latest_lookup(harness, monkeypatch):
    archive = cached(harness)
    control = harness.cache / (ARCHIVE_NAME + ".aria2")
    control.write_bytes(b"partial control")
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump.subprocess, "run", forbidden)

    def unavailable(*args):
        raise RuntimeError("dated metadata is no longer available")

    monkeypatch.setattr(dump, "get_archive_metadata", unavailable)
    assert not dump.download_dump(harness.local, harness.ctx)
    assert archive.read_bytes() == ARCHIVE_BYTES
    assert control.read_bytes() == b"partial control"
    assert any("dated metadata" in line for line in harness.logs)


def test_interrupted_extraction_reuses_verified_archive_and_existing_database(harness, monkeypatch):
    archive = cached(harness)
    state = pin(harness, "extracting")
    state["verified_file"] = dump.dump_file_fingerprint(str(archive))
    dump.write_dump_state(str(harness.cache), state)
    (harness.database / "config.json").write_text("original node identity")
    (harness.database / "partial-data").write_bytes(b"partially extracted")
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump, "verify_dump_checksum", forbidden)
    monkeypatch.setattr(dump.subprocess, "run", forbidden)
    attempts = []

    def extract(local, source, destination):
        assert Path(source).read_bytes() == ARCHIVE_BYTES
        assert (Path(destination) / "config.json").read_text() == "original node identity"
        assert (Path(destination) / "partial-data").read_bytes() == b"partially extracted"
        attempts.append(destination)
        return 9 if len(attempts) == 1 else 0

    monkeypatch.setattr(dump, "extract_dump", extract)
    assert not dump.download_dump(harness.local, harness.ctx)
    assert archive.exists()
    assert dump.read_dump_state(str(harness.cache))["phase"] == "extracting"
    assert dump.download_dump(harness.local, harness.ctx)
    assert len(attempts) == 2
    assert dump.dump_extraction_complete(str(harness.database), state)


def test_changed_verified_archive_requires_fresh_checksum_and_preserves_corruption(harness, monkeypatch):
    archive = cached(harness)
    state = pin(harness, "extracting")
    state["verified_file"] = dump.dump_file_fingerprint(str(archive))
    dump.write_dump_state(str(harness.cache), state)
    archive.write_bytes(b"x" * len(ARCHIVE_BYTES))
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump, "extract_dump", forbidden)
    assert not dump.download_dump(harness.local, harness.ctx)
    assert archive.read_bytes() == b"x" * len(ARCHIVE_BYTES)


def test_preallocated_partial_archive_uses_aria2_control_instead_of_discarding(harness, monkeypatch):
    archive = cached(harness, b"\0" * len(ARCHIVE_BYTES))
    (harness.cache / (ARCHIVE_NAME + ".aria2")).write_bytes(b"control")
    pin(harness)
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump, "extract_dump", lambda *args: 0)
    actual_run = subprocess.run

    def run(args, **kwargs):
        if args[0] == "aria2c":
            assert archive.read_bytes() == b"\0" * len(ARCHIVE_BYTES)
            assert (harness.cache / (ARCHIVE_NAME + ".aria2")).exists()
            archive.write_bytes(ARCHIVE_BYTES)
            return SimpleNamespace(returncode=0)
        return actual_run(args, **kwargs)

    monkeypatch.setattr(dump.subprocess, "run", run)
    assert dump.download_dump(harness.local, harness.ctx)


@pytest.mark.parametrize("phase", ["extracting", "extracted"])
def test_completion_marker_skips_replay_after_restart_or_archive_cleanup(harness, monkeypatch, phase):
    state = pin(harness, phase)
    dump.write_dump_json(str(harness.database / dump.DUMP_COMPLETE_MARKER), dump.dump_identity(state))
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump, "extract_dump", forbidden)
    monkeypatch.setattr(dump.subprocess, "run", forbidden)
    assert dump.download_dump(harness.local, harness.ctx)
    assert dump.read_dump_state(str(harness.cache))["phase"] == "extracted"


def test_extracted_state_without_database_marker_reextracts_same_pinned_archive(harness, monkeypatch):
    cached(harness)
    pin(harness, "extracted")
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    extracts = []
    monkeypatch.setattr(dump, "extract_dump", lambda *args: extracts.append(args) or 0)
    assert dump.download_dump(harness.local, harness.ctx)
    assert len(extracts) == 1


@pytest.mark.parametrize("damage", ["network", "target", "json", "archive"])
def test_invalid_state_fails_closed_preserving_cached_archive(harness, monkeypatch, damage):
    archive = cached(harness)
    state = pin(harness)
    if damage == "network":
        state["dump_name"] = "latest_testnet"
    elif damage == "target":
        state["dump_dir"] = "/different/database"
    elif damage == "archive":
        state["archive_name"] = "../../nodekeys.tar.lz"
    if damage == "json":
        Path(dump.get_dump_state_path(str(harness.cache))).write_text("{")
    else:
        dump.write_dump_state(str(harness.cache), state)
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump.subprocess, "run", forbidden)
    assert not dump.download_dump(harness.local, harness.ctx)
    assert archive.read_bytes() == ARCHIVE_BYTES


def test_concurrent_installer_is_rejected_before_network_or_archive_changes(harness, monkeypatch):
    archive = cached(harness)
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    with open(harness.cache / "dump-state.lock", "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not dump.download_dump(harness.local, harness.ctx)
    assert archive.read_bytes() == ARCHIVE_BYTES


@pytest.mark.parametrize("phase,marker", [("downloading", False), ("extracting", True), ("extracted", False)])
def test_cleanup_does_not_remove_incomplete_or_unconfirmed_archive(harness, phase, marker):
    archive = cached(harness)
    state = pin(harness, phase)
    if marker:
        dump.write_dump_json(str(harness.database / dump.DUMP_COMPLETE_MARKER), dump.dump_identity(state))
    assert not dump.cleanup_completed_dump(str(harness.cache), str(harness.database))
    assert archive.exists()


def test_cleanup_removes_only_pinned_archive_after_completed_initialization(harness):
    archive = cached(harness)
    control = harness.cache / (ARCHIVE_NAME + ".aria2")
    control.write_bytes(b"control")
    unrelated = harness.cache / "unrelated.tar.lz"
    unrelated.write_bytes(b"keep")
    state = pin(harness, "extracted")
    dump.write_dump_json(str(harness.database / dump.DUMP_COMPLETE_MARKER), dump.dump_identity(state))
    assert dump.cleanup_completed_dump(str(harness.cache), str(harness.database))
    assert not archive.exists() and not control.exists()
    assert unrelated.read_bytes() == b"keep"
    assert dump.read_dump_state(str(harness.cache)) == state
    assert dump.dump_extraction_complete(str(harness.database), state)


def test_resume_space_check_credits_allocated_archive_and_database_blocks(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    cache = tmp_path / "cache"
    database = tmp_path / "db"
    cache.mkdir()
    database.mkdir()
    (cache / ARCHIVE_NAME).write_bytes(b"a" * 8192)
    (database / "partial").write_bytes(b"b" * 8192)
    metadata = dump.DumpMetadata(ARCHIVE_NAME, "a" * 64, 8192, 16384)
    logs = []
    local = SimpleNamespace(add_log=lambda message, level: logs.append(message))
    monkeypatch.setattr(dump.psutil, "disk_usage", lambda path: SimpleNamespace(free=8192))
    assert dump.check_dump_space(local, str(database), str(cache), metadata)
    (cache / ARCHIVE_NAME).unlink()
    with open(cache / ARCHIVE_NAME, "wb") as sparse:
        sparse.truncate(8192)
    assert not dump.check_dump_space(local, str(database), str(cache), metadata)


@pytest.mark.parametrize("cache_name", ["cache", "."])
def test_cache_inside_database_is_not_counted_as_extracted_data(monkeypatch, tmp_path, cache_name):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    database = tmp_path / "db"
    cache = database / cache_name
    cache.mkdir(parents=True)
    (cache / ARCHIVE_NAME).write_bytes(b"a" * 8192)
    (database / "partial").write_bytes(b"b" * 8192)
    metadata = dump.DumpMetadata(ARCHIVE_NAME, "a" * 64, 8192, 16384)
    local = SimpleNamespace(add_log=lambda *args: None)
    monkeypatch.setattr(dump.psutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    assert not dump.check_dump_space(local, str(database), str(cache), metadata)
    monkeypatch.setattr(dump.psutil, "disk_usage", lambda path: SimpleNamespace(free=8192))
    assert dump.check_dump_space(local, str(database), str(cache), metadata)


@pytest.mark.parametrize("prefix", ["", "./"])
def test_real_tar_extraction_protects_node_config_and_keys(monkeypatch, tmp_path, prefix):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    database = tmp_path / "db"
    database.mkdir()
    protected = ["config.json", "keyring/private", "keys/client", "nodekeys/private", dump.DUMP_COMPLETE_MARKER]
    for name in protected:
        path = database / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original identity")
    archive = tmp_path / "test.tar.lz"
    with tarfile.open(archive, "w") as tar:
        for name in protected + ["celldb/data"]:
            contents = b"dump contents"
            member = tarfile.TarInfo(prefix + name)
            member.size = len(contents)
            tar.addfile(member, io.BytesIO(contents))
    tools = tmp_path / "bin"
    tools.mkdir()
    plzip = tools / "plzip"
    plzip.write_text('#!/bin/sh\nfor argument do :; done\ncat "$argument"\n')
    plzip.chmod(0o755)
    monkeypatch.setenv("PATH", str(tools) + os.pathsep + os.environ["PATH"])
    local = SimpleNamespace(add_log=lambda *args: None)
    assert dump.extract_dump(local, str(archive), str(database)) == 0
    assert (database / "celldb/data").read_bytes() == b"dump contents"
    for name in protected:
        assert (database / name).read_bytes() == b"original identity"


def test_exact_archive_metadata_never_reads_latest_pointer(monkeypatch):
    urls = []
    metadata_name = ARCHIVE_NAME[:-3]
    values = {
        ".sha256sum.txt": hashlib.sha256(ARCHIVE_BYTES).hexdigest() + "  " + ARCHIVE_NAME,
        ".size.archive.txt": str(len(ARCHIVE_BYTES)),
        ".size.disk.txt": "4096",
    }

    def fetch(url, **kwargs):
        urls.append(url)
        return values[url.split(metadata_name)[1]]

    monkeypatch.setattr(dump, "dump_fetch_text", fetch)
    metadata = dump.get_archive_metadata(BASE_URL, ARCHIVE_NAME)
    assert metadata.archive_name == ARCHIVE_NAME
    assert len(urls) == 3
    assert not any("latest" in url for url in urls)
