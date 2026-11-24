import os
from pathlib import Path

import pytest

from mypylib.mypylib import Dict
from mytoninstaller import config


@pytest.fixture(autouse=True)
def container_config(monkeypatch):
    monkeypatch.setattr(config, "is_container", lambda: True)


def test_config_update_preserves_symlink_and_file_permissions(tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"original": true}')
    target.chmod(0o640)
    previous = target.stat()
    link = tmp_path / "config-link.json"
    link.symlink_to(target)

    config.SetConfig(str(link), Dict(updated=True))

    assert link.is_symlink()
    assert config.GetConfig(str(target)) == {"updated": True}
    assert target.stat().st_mode == previous.st_mode
    assert (target.stat().st_uid, target.stat().st_gid) == (previous.st_uid, previous.st_gid)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["config-link.json", "config.json"]


def test_failed_config_publish_leaves_original_intact(tmp_path, monkeypatch):
    target = tmp_path / "config.json"
    original = '{"original": true}'
    target.write_text(original)

    def fail_publish(source, destination):
        assert Path(source).read_text()
        raise OSError("interrupted before replacing config")

    monkeypatch.setattr(os, "replace", fail_publish)
    with pytest.raises(OSError, match="interrupted"):
        config.SetConfig(str(target), Dict(updated=True))

    assert target.read_text() == original
    assert list(tmp_path.iterdir()) == [target]
