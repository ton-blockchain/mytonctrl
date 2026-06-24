from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mypylib.mypylib import Dict
from mytoncore.models import Paths
from mytoncore.mytoncore import MyTonCore
from mytoninstaller.context import InstallerPaths
from mytoninstaller.settings import get_paths_dict, update_client_path_settings


def test_paths_defaults():
    paths = Paths()
    assert paths.ton_work == Path("/var/ton-work")
    assert paths.ton_db == Path("/var/ton-work/db")
    assert paths.ton_keys == Path("/var/ton-work/keys")
    assert paths.ton_bin == Path("/usr/bin/ton")
    assert paths.ton_src == Path("/usr/src/ton")
    assert paths.mtc_src == Path("/usr/src/mytonctrl")
    assert paths.src_dir == Path("/usr/src")


def test_paths_derived_properties():
    paths = Paths()
    assert paths.keyring_dir == Path("/var/ton-work/db/keyring")
    assert paths.vconfig_path == Path("/var/ton-work/db/config.json")
    assert paths.global_config_path == Path("/usr/bin/ton/global.config.json")
    assert paths.local_config_path == Path("/usr/bin/ton/local.config.json")


def test_paths_is_frozen():
    paths = Paths()
    with pytest.raises(FrozenInstanceError):
        setattr(paths, "ton_work", Path("/tmp"))


def test_from_dict_overrides_roots_and_derives_props():
    data = {
        "ton_work": "/data/ton-work",
        "ton_db": "/data/ton-work/db",
        "ton_keys": "/data/ton-work/keys",
        "ton_src": "/opt/src/ton",
        "ton_bin": "/opt/bin/ton",
        "mtc_src": "/opt/src/mytonctrl",
        "src_dir": "/opt/src",
    }
    paths = Paths.from_dict(data)
    assert isinstance(paths.ton_work, Path)
    assert paths.ton_bin == Path("/opt/bin/ton")
    # derived properties follow the overridden roots
    assert paths.global_config_path == Path("/opt/bin/ton/global.config.json")
    assert paths.keyring_dir == Path("/data/ton-work/db/keyring")


def test_from_dict_partial_keeps_defaults():
    paths = Paths.from_dict({"ton_bin": "/opt/bin/ton"})
    assert paths.ton_bin == Path("/opt/bin/ton")
    assert paths.ton_work == Paths().ton_work  # untouched -> default


def test_from_dict_ignores_unknown_keys():
    paths = Paths.from_dict({"ton_bin": "/opt/bin/ton", "bogus": "/nope"})
    assert paths.ton_bin == Path("/opt/bin/ton")
    assert not hasattr(paths, "bogus")


def test_get_paths_returns_defaults_without_db_entry(ton: MyTonCore):
    ton.local.db.pop("paths", None)
    assert ton.get_paths() == Paths()


def test_get_paths_reads_db_entry(ton: MyTonCore):
    ton.local.db["paths"] = {"ton_bin": "/opt/bin/ton", "ton_work": "/data/ton-work"}
    paths = ton.get_paths()
    assert paths.ton_bin == Path("/opt/bin/ton")
    assert paths.ton_work == Path("/data/ton-work")


def test_installer_paths_bridge_matches_runtime_defaults():
    # the installer's default dirs must round-trip to the runtime Paths defaults;
    # this locks the get_paths_dict <-> Paths.from_dict key mapping against drift
    assert Paths.from_dict(get_paths_dict(InstallerPaths())) == Paths()


def test_installer_paths_bridge_maps_custom_roots_to_right_fields():
    # custom install dirs must land on the matching runtime field, not a sibling
    # (e.g. keys_dir -> ton_keys, not ton_db) — guards against a wrong-field map
    installer = InstallerPaths(bin_dir="/opt/bin/", src_dir="/opt/src/", ton_work_dir="/data/ton-work/")
    paths = Paths.from_dict(get_paths_dict(installer))
    assert paths.ton_bin == Path("/opt/bin/ton")
    assert paths.ton_src == Path("/opt/src/ton")
    assert paths.mtc_src == Path("/opt/src/mytonctrl")
    assert paths.src_dir == Path("/opt/src")
    assert paths.ton_work == Path("/data/ton-work")
    assert paths.ton_db == Path("/data/ton-work/db")
    assert paths.ton_keys == Path("/data/ton-work/keys")


def test_update_client_path_settings_rewrites_known_sections():
    db = Dict({
        "fift": {"appPath": "x", "libsPath": "x", "smartcontsPath": "x"},
        "liteClient": {
            "appPath": "x",
            "configPath": "x",
            "liteServer": {"pubkeyPath": "x", "ip": "127.0.0.1", "port": 1},
        },
        "validatorConsole": {"appPath": "x", "privKeyPath": "x", "pubKeyPath": "x"},
    })
    update_client_path_settings(db, Paths())

    assert db["fift"]["appPath"] == "/usr/bin/ton/crypto/fift"
    assert db["fift"]["libsPath"] == "/usr/src/ton/crypto/fift/lib"
    assert db["fift"]["smartcontsPath"] == "/usr/src/ton/crypto/smartcont"
    assert db["liteClient"]["appPath"] == "/usr/bin/ton/lite-client/lite-client"
    assert db["liteClient"]["configPath"] == "/usr/bin/ton/global.config.json"
    assert db["liteClient"]["liteServer"]["pubkeyPath"] == "/var/ton-work/keys/liteserver.pub"
    assert db["validatorConsole"]["appPath"] == "/usr/bin/ton/validator-engine-console/validator-engine-console"
    assert db["validatorConsole"]["privKeyPath"] == "/var/ton-work/keys/client"
    assert db["validatorConsole"]["pubKeyPath"] == "/var/ton-work/keys/server.pub"
    # unrelated fields are left untouched
    assert db["liteClient"]["liteServer"]["port"] == 1


def test_update_client_path_settings_skips_missing_sections():
    db = Dict()
    update_client_path_settings(db, Paths())  # must not raise on absent sections
    assert db == {}
