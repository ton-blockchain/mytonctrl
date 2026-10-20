import importlib.util
import io
from pathlib import Path
import tarfile

import pytest


SOURCE = Path(__file__).parents[2] / "docker/prepare-benchmark.py"
spec = importlib.util.spec_from_file_location("prepare_benchmark", SOURCE)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
REVISION = "3d478cbde854be03a18ab2a59f8fc3c565cf7d14"


def source_archive(extra=()):
    contents = io.BytesIO()
    with tarfile.open(fileobj=contents, mode="w:gz") as archive:
        for path in prepare.REQUIRED_FILES:
            item = tarfile.TarInfo(f"ton-{REVISION}/{path}")
            data = path.encode()
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
        for item, data in extra:
            archive.addfile(item, io.BytesIO(data) if data is not None else None)
    contents.seek(0)
    return tarfile.open(fileobj=contents, mode="r|gz")


def file_member(name, data):
    item = tarfile.TarInfo(f"ton-{REVISION}/{name}")
    item.size = len(data)
    return item, data


def test_build_source_contains_harness_resources_and_license_only(tmp_path):
    extras = [
        file_member("test/tontester/tests/tlb/schemas/special_cells.tlb", b"schema"),
        file_member("test/integration/bench_smoke.py", b"python"),
        file_member("validator-engine/validator-engine.cpp", b"C++ implementation"),
        file_member("build/tonlib/libtonlibjson.so", b"binary"),
        file_member(".git/config", b"repository"),
        file_member("test/tontester/.gitignore", b"git metadata"),
    ]
    with source_archive(extras) as archive:
        count = prepare.extract_source(archive, tmp_path, REVISION)
    assert count == len(prepare.REQUIRED_FILES) + 2
    assert (tmp_path / "TON_REVISION").read_text() == REVISION + "\n"
    assert (tmp_path / "LICENSE.LGPL").is_file()
    assert (tmp_path / "crypto/block/block.tlb").is_file()
    assert (tmp_path / "test/integration/bench_smoke.py").read_bytes() == b"python"
    assert not (tmp_path / "validator-engine").exists()
    assert not (tmp_path / "build").exists()
    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / "test/tontester/.gitignore").exists()


@pytest.mark.parametrize(
    "name",
    ["../escape.py", "/absolute.py", f"ton-{REVISION}/test/tontester/../../escape.py"],
)
def test_source_archive_rejects_paths_outside_pinned_tree(tmp_path, name):
    item = tarfile.TarInfo(name)
    item.size = 1
    with source_archive([(item, b"x")]) as archive:
        with pytest.raises(ValueError, match="archive path"):
            prepare.extract_source(archive, tmp_path, REVISION)
    assert not (tmp_path.parent / "escape.py").exists()


def test_source_archive_rejects_selected_symlinks(tmp_path):
    item = tarfile.TarInfo(f"ton-{REVISION}/test/tontester/src/extra.py")
    item.type = tarfile.SYMTYPE
    item.linkname = "/etc/passwd"
    with source_archive([(item, None)]) as archive:
        with pytest.raises(ValueError, match="source member"):
            prepare.extract_source(archive, tmp_path, REVISION)
    assert not (tmp_path / "test/tontester/src/extra.py").exists()


def test_incomplete_source_fails_build(tmp_path):
    contents = io.BytesIO()
    with tarfile.open(fileobj=contents, mode="w:gz"):
        pass
    contents.seek(0)
    with tarfile.open(fileobj=contents, mode="r|gz") as archive:
        with pytest.raises(ValueError, match="incomplete"):
            prepare.extract_source(archive, tmp_path, REVISION)
    assert not (tmp_path / "TON_REVISION").exists()


@pytest.mark.parametrize("revision", ["master", "dev", "", "abc", "0" * 39, "z" * 40])
def test_revision_must_be_pinned_before_download(tmp_path, monkeypatch, revision):
    monkeypatch.setattr(
        prepare,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("No fetch before validation"),
    )
    with pytest.raises(ValueError, match="40-character"):
        prepare.prepare_source(tmp_path, revision)
