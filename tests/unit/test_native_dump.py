import hashlib
import io
import os
from pathlib import Path
import tarfile
from types import SimpleNamespace

import pytest

from mytoninstaller import dump


ARCHIVE_BYTES = b"native dump contents"


def forbidden(*args, **kwargs):
    raise AssertionError("Native dump refresh must not use container recovery state")


@pytest.fixture
def native(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    database = tmp_path / "db"
    cache.mkdir()
    database.mkdir()
    monkeypatch.setattr(dump, "is_container", lambda: False)
    monkeypatch.setenv("DUMP_CACHE_DIR", str(cache))
    monkeypatch.delenv("DUMP_VALIDATE_BEFORE_EXTRACT", raising=False)
    monkeypatch.setattr(dump, "is_testnet", lambda path: False)
    monkeypatch.setattr(dump, "read_dump_state", forbidden)
    monkeypatch.setattr(dump, "write_dump_state", forbidden)
    monkeypatch.setattr(dump.shutil, "which", forbidden)
    monkeypatch.setattr(dump, "check_dump_space", lambda *args: True)
    logs = []
    metadata = dump.DumpMetadata(
        "native.today.tar.lz", hashlib.sha256(ARCHIVE_BYTES).hexdigest(), len(ARCHIVE_BYTES), 4096,
    )
    harness = SimpleNamespace(
        cache=cache, database=database, metadata=metadata, metadata_calls=[],
        local=SimpleNamespace(add_log=lambda message, level: logs.append(message)),
        ctx=SimpleNamespace(paths=SimpleNamespace(
            ton_db_dir=str(database), ton_work_dir=str(tmp_path), global_config_path="global.json",
        )),
        commands=[], logs=logs, metadata_result=metadata, apt_result=0, download_result=0,
        create_archive=True, archive_contents=ARCHIVE_BYTES, checksum=True, validation_result=0,
        extraction_result=0, extractions=[],
    )

    def metadata_lookup(base_url, name):
        harness.metadata_calls.append((base_url, name))
        return harness.metadata_result

    def run(args, **kwargs):
        harness.commands.append(args)
        if args[0] == "apt":
            return SimpleNamespace(returncode=harness.apt_result)
        assert args[0] == "aria2c"
        archive = Path(args[args.index("-d") + 1]) / args[args.index("-o") + 1]
        # Native refresh still removes a previous download of today's archive.
        assert not archive.exists()
        assert not Path(str(archive) + ".aria2").exists()
        if harness.create_archive:
            archive.write_bytes(harness.archive_contents)
        Path(str(archive) + ".aria2").write_bytes(b"temporary aria2 control")
        return SimpleNamespace(returncode=harness.download_result)

    def extract(local, archive, destination):
        harness.extractions.append((Path(archive).name, Path(archive).read_bytes()))
        if harness.extraction_result == 0:
            (Path(destination) / "downloaded-data").write_bytes(Path(archive).read_bytes())
        return harness.extraction_result

    monkeypatch.setattr(dump, "get_dump_metadata", metadata_lookup)
    monkeypatch.setattr(dump.subprocess, "run", run)
    monkeypatch.setattr(dump, "verify_dump_checksum", lambda *args: harness.checksum)
    monkeypatch.setattr(dump, "validate_dump_archive", lambda *args: harness.validation_result)
    monkeypatch.setattr(dump, "extract_dump", extract)
    return harness


def test_native_repeated_dump_refresh_fetches_new_latest_and_ignores_old_checkpoint(native):
    stale_state = native.cache / "dump-state.json"
    stale_state.write_text("an old container checkpoint")
    stale_marker = native.database / dump.DUMP_COMPLETE_MARKER
    stale_marker.write_text("an old container extraction marker")
    assert dump.download_dump(native.local, native.ctx)

    newer_contents = b"newer native dump contents"
    native.metadata_result = dump.DumpMetadata(
        "native.tomorrow.tar.lz", hashlib.sha256(newer_contents).hexdigest(), len(newer_contents), 4096,
    )
    native.archive_contents = newer_contents
    assert dump.download_dump(native.local, native.ctx)
    assert native.metadata_calls == [("https://dump.ton.org/dumps", "latest")] * 2
    assert native.extractions == [
        ("native.today.tar.lz", ARCHIVE_BYTES), ("native.tomorrow.tar.lz", newer_contents),
    ]
    assert (native.database / "downloaded-data").read_bytes() == newer_contents
    assert [args[0] for args in native.commands] == ["apt", "aria2c", "apt", "aria2c"]
    assert stale_state.read_text() == "an old container checkpoint"
    assert stale_marker.read_text() == "an old container extraction marker"
    assert not (native.cache / "dump-state.lock").exists()
    assert not list(native.cache.glob("*.tar.lz*"))


def test_native_refresh_cleans_previous_latest_and_selected_archive(native):
    for directory in (native.cache, native.database):
        for filename in ("latest.tar.lz", native.metadata.archive_name):
            (directory / filename).write_bytes(b"previous incomplete archive")
            (directory / (filename + ".aria2")).write_bytes(b"previous control")
    assert dump.download_dump(native.local, native.ctx)
    for directory in (native.cache, native.database):
        assert not list(directory.glob("*.tar.lz*"))
    assert not (native.cache / "dump-state.json").exists()
    assert not (native.database / dump.DUMP_COMPLETE_MARKER).exists()


@pytest.mark.parametrize("failure", ["download", "missing", "size", "checksum", "validation", "extraction"])
def test_native_dump_failure_removes_archive_and_control(native, monkeypatch, failure):
    if failure == "download":
        native.download_result = 7
    elif failure == "missing":
        native.create_archive = False
    elif failure == "size":
        native.archive_contents = b"incomplete"
    elif failure == "checksum":
        native.checksum = False
    elif failure == "validation":
        monkeypatch.setenv("DUMP_VALIDATE_BEFORE_EXTRACT", "true")
        native.validation_result = 2
    elif failure == "extraction":
        native.extraction_result = 2
    assert not dump.download_dump(native.local, native.ctx)
    assert not (native.cache / native.metadata.archive_name).exists()
    assert not (native.cache / (native.metadata.archive_name + ".aria2")).exists()
    assert not (native.cache / "dump-state.json").exists()


def test_native_apt_failure_does_not_start_downloader(native):
    native.apt_result = 2
    assert not dump.download_dump(native.local, native.ctx)
    assert [args[0] for args in native.commands] == ["apt"]


def test_native_testnet_still_selects_fresh_testnet_metadata(native, monkeypatch):
    monkeypatch.setattr(dump, "is_testnet", lambda path: True)
    assert dump.download_dump(native.local, native.ctx)
    assert native.metadata_calls == [("https://dump.ton.org/dumps", "latest_testnet")]


def test_native_metadata_keeps_original_filename_and_checksum_forms(monkeypatch):
    monkeypatch.setattr(dump, "is_container", lambda: False)
    urls = []
    values = {
        "latest.tar.name.txt": "native+snapshot.tar",
        "native+snapshot.tar.sha256sum.txt": "A" * 64 + "  native+snapshot.tar.lz",
        "native+snapshot.tar.size.archive.txt": "8192",
        "native+snapshot.tar.size.disk.txt": "16384",
    }

    def fetch(url, **kwargs):
        urls.append(url)
        return values[url.rsplit("/", 1)[-1]]

    monkeypatch.setattr(dump, "dump_fetch_text", fetch)
    assert dump.get_dump_metadata("https://dump.ton.org/dumps", "latest") == dump.DumpMetadata(
        "native+snapshot.tar.lz", "A" * 64, 8192, 16384,
    )
    assert len(urls) == 4 and urls[0].endswith("latest.tar.name.txt")


def test_native_space_check_keeps_full_archive_and_database_requirement(monkeypatch, tmp_path):
    monkeypatch.setattr(dump, "is_container", lambda: False)
    monkeypatch.setattr(dump, "allocated_dump_bytes", forbidden)
    monkeypatch.setattr(dump, "allocated_database_bytes", forbidden)
    cache = tmp_path / "cache"
    database = tmp_path / "db"
    cache.mkdir()
    database.mkdir()
    (cache / "dump.tar.lz").write_bytes(b"already allocated archive")
    (database / "data").write_bytes(b"existing database")
    local = SimpleNamespace(add_log=lambda *args: None)
    metadata = dump.DumpMetadata("dump.tar.lz", "a" * 64, 8192, 16384)
    monkeypatch.setattr(dump.psutil, "disk_usage", lambda path: SimpleNamespace(free=8192 + 16384 - 1))
    assert not dump.check_dump_space(local, str(database), str(cache), metadata)
    monkeypatch.setattr(dump.psutil, "disk_usage", lambda path: SimpleNamespace(free=8192 + 16384))
    assert dump.check_dump_space(local, str(database), str(cache), metadata)


def test_native_tar_extraction_retains_original_archive_contents(monkeypatch, tmp_path):
    monkeypatch.setattr(dump, "is_container", lambda: False)
    monkeypatch.setenv("DUMP_EXTRACT_THREADS", "1")
    database = tmp_path / "db"
    database.mkdir()
    members = ["config.json", "keyring/private", "keys/client", "nodekeys/private", "celldb/data"]
    archive = tmp_path / "test.tar.lz"
    with tarfile.open(archive, "w") as tar:
        for name in members:
            member = tarfile.TarInfo(name)
            member.size = len(ARCHIVE_BYTES)
            tar.addfile(member, io.BytesIO(ARCHIVE_BYTES))
    tools = tmp_path / "bin"
    tools.mkdir()
    plzip = tools / "plzip"
    plzip.write_text('#!/bin/sh\nfor argument do :; done\ncat "$argument"\n')
    plzip.chmod(0o755)
    monkeypatch.setenv("PATH", str(tools) + os.pathsep + os.environ["PATH"])
    local = SimpleNamespace(add_log=lambda *args: None)
    assert dump.extract_dump(local, str(archive), str(database)) == 0
    for name in members:
        assert (database / name).read_bytes() == ARCHIVE_BYTES
