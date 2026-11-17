import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys

import pytest

from mypylib.mypylib import Dict
from mytoncore.utils import hex2b64
from mytoninstaller import config as installer_config
from mytoninstaller.scripts.drvcf import find_keyring_id
from mytoninstaller.utils import get_ed25519_pubkey_b64, get_pubkey_file_short_id


PK_ED25519_TL_TAG = bytes.fromhex("17236849")

# `.pub` file and short id printed by a real `generate-random-id --mode keys` run
PUB_FILE = bytes.fromhex("c6b41348") + base64.b64decode("gFXc6X6+hQtQUh0ivhHktSIb34Dj1S14LPcWd/Ronoo=")
SHORT_ID = "453E2C83203A89D05EB8730106199AD5483F304CDAE24EDA2E39492ABD289DB4"

FAKE_GENERATE_RANDOM_ID = '''import base64, hashlib, json, os, stat, sys
args = sys.argv[1:]
assert args[:3] == ["--mode", "id", "--key"], args
key_path = args[3]
data = open(key_path, "rb").read()
with open(os.environ["FAKE_GRID_RECORD"], "w") as f:
    json.dump({"path": key_path, "mode": stat.S_IMODE(os.stat(key_path).st_mode), "data": data.hex()}, f)
pub = base64.b64encode(hashlib.sha256(data[4:]).digest()).decode()
print(json.dumps({"@type": "pk.ed25519", "key": base64.b64encode(data[4:]).decode()}))
print(json.dumps({"@type": "pub.ed25519", "key": pub}))
print(json.dumps({"@type": "adnl.id.short", "id": "x"}))
'''


def _fake_pubkey(seed: bytes) -> str:
    return base64.b64encode(hashlib.sha256(seed).digest()).decode()


@pytest.fixture
def fake_ton_bin(tmp_path, monkeypatch):
    utils_dir = tmp_path / "ton_bin" / "utils"
    utils_dir.mkdir(parents=True)
    script = tmp_path / "fake_generate_random_id.py"
    script.write_text(FAKE_GENERATE_RANDOM_ID)
    binary = utils_dir / "generate-random-id"
    binary.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} "$@"\n')
    binary.chmod(0o755)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_GRID_RECORD", str(record))
    return tmp_path / "ton_bin", record


def test_pubkey_file_short_id_matches_generate_random_id(tmp_path):
    pub_path = tmp_path / "client.pub"
    pub_path.write_bytes(PUB_FILE)
    assert get_pubkey_file_short_id(str(pub_path)) == SHORT_ID


def test_find_keyring_id(tmp_path):
    pub_path = tmp_path / "server.pub"
    pub_path.write_bytes(PUB_FILE)
    other = "AB" * 32
    assert find_keyring_id([other, SHORT_ID], str(pub_path)) == hex2b64(SHORT_ID)
    assert find_keyring_id([other, SHORT_ID.lower()], str(pub_path)) == hex2b64(SHORT_ID)
    assert find_keyring_id([other], str(pub_path)) is None


def test_get_ed25519_pubkey_b64_uses_private_temp_key_file(fake_ton_bin):
    ton_bin, record = fake_ton_bin
    seed = bytes(range(32))
    pubkey = get_ed25519_pubkey_b64(str(ton_bin / "utils" / "generate-random-id"), seed)
    assert pubkey == _fake_pubkey(seed)

    seen = json.loads(record.read_text())
    assert bytes.fromhex(seen["data"]) == PK_ED25519_TL_TAG + seed
    assert seen["mode"] == 0o600
    assert not os.path.exists(seen["path"])


def test_get_ed25519_pubkey_b64_rejects_bad_seed(fake_ton_bin):
    ton_bin, _ = fake_ton_bin
    with pytest.raises(ValueError):
        get_ed25519_pubkey_b64(str(ton_bin / "utils" / "generate-random-id"), b"\x00" * 64)


def test_get_ed25519_pubkey_b64_reports_binary_failure(tmp_path):
    binary = tmp_path / "generate-random-id"
    binary.write_text("#!/bin/sh\necho 'failed to import private key' >&2\nexit 2\n")
    binary.chmod(0o755)
    with pytest.raises(Exception, match="failed to import private key"):
        get_ed25519_pubkey_b64(str(binary), bytes(32))


def test_get_ls_proxy_config(fake_ton_bin, monkeypatch):
    ton_bin, _ = fake_ton_bin
    seed = bytes(range(100, 132))
    ls_proxy_config = Dict({
        "ListenAddr": "0.0.0.0:12345",
        "Clients": [{"Name": "default", "PrivateKey": base64.b64encode(seed).decode()}],
    })
    monkeypatch.setattr(installer_config, "GetConfig", lambda path: ls_proxy_config)
    monkeypatch.setattr(installer_config, "get_own_ip", lambda: "1.2.3.4")

    result = installer_config.get_ls_proxy_config(str(ton_bin))

    assert result == {
        "ip": installer_config.ip2int("1.2.3.4"),
        "port": "12345",
        "id": {"@type": "pub.ed25519", "key": _fake_pubkey(seed)},
    }


@pytest.mark.skipif(not os.getenv("GENERATE_RANDOM_ID"), reason="set GENERATE_RANDOM_ID to a real generate-random-id binary")
def test_real_generate_random_id(tmp_path):
    binary = os.environ["GENERATE_RANDOM_ID"]
    name = tmp_path / "key"
    output = subprocess.run([binary, "--mode", "keys", "--name", str(name)], check=True,
                            stdout=subprocess.PIPE, text=True).stdout
    printed_short_id = output.split()[0]
    priv = name.read_bytes()
    pub = (tmp_path / "key.pub").read_bytes()

    assert priv[:4] == PK_ED25519_TL_TAG
    assert get_pubkey_file_short_id(str(tmp_path / "key.pub")) == printed_short_id
    assert get_ed25519_pubkey_b64(binary, priv[4:]) == base64.b64encode(pub[4:]).decode()
