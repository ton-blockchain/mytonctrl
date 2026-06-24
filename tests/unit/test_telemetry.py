from types import SimpleNamespace

import pytest

from mytoncore.telemetry import get_db_stats, get_validator_disk_name


def _fake_df(output: bytes):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout=output)
    return fake_run


def test_get_validator_disk_name_parses_device(monkeypatch):
    df_output = (
        b"Filesystem      Size  Used Avail Use% Mounted on\n"
        b"/dev/sda1       100G   40G   60G  40% /var/ton-work\n"
    )
    monkeypatch.setattr("mytoncore.telemetry.subprocess.run", _fake_df(df_output))
    assert get_validator_disk_name("/var/ton-work") == "/dev/sda1"


@pytest.mark.parametrize(
    "output",
    [
        b"",  # no output at all
        b"Filesystem      Size  Used Avail Use% Mounted on\n",  # header only, no data row
    ],
)
def test_get_validator_disk_name_returns_empty_on_short_output(monkeypatch, output):
    monkeypatch.setattr("mytoncore.telemetry.subprocess.run", _fake_df(output))
    assert get_validator_disk_name("/var/ton-work") == ""


def test_get_db_stats_parses_existing_files(tmp_path):
    (tmp_path / "db_stats.txt").write_text(
        "rocksdb.block.cache.miss COUNT : 100\n"
        "rocksdb.block.cache.hit COUNT : 0\n"  # zero values are dropped
        "rocksdb.db.get.micros P50 : 1.5 P95 : 3.0 COUNT : 10\n"
    )
    (tmp_path / "celldb").mkdir()
    (tmp_path / "celldb" / "db_stats.txt").write_text("celldb.get.count COUNT : 42\n")

    result = get_db_stats(tmp_path)

    assert result["rocksdb"]["ok"] is True
    assert result["rocksdb"]["data"] == {
        "rocksdb.block.cache.miss": 100.0,
        "rocksdb.db.get.micros": {"P50": 1.5, "P95": 3.0, "COUNT": 10.0},
    }
    assert result["celldb"]["ok"] is True
    assert result["celldb"]["data"] == {"celldb.get.count": 42.0}


def test_get_db_stats_reports_missing_files(tmp_path):
    result = get_db_stats(tmp_path)  # empty dir, no stats files

    assert result["rocksdb"]["ok"] is False
    assert result["rocksdb"]["message"] == "db stats file is not exists"
    assert result["celldb"]["ok"] is False
    assert result["celldb"]["message"] == "db stats file is not exists"
