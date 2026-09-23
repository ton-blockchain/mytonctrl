from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from mypylib.mypylib import ip2int
from mytoncore.models import Paths
from mytoncore.utils import hex2base64
from mytoninstaller import mytoninstaller as installer_module
from mytoninstaller import node_args as node_args_module
from mytoninstaller.mytoninstaller import InstallerCtrl
from tests.conftest import TestLocal, TestMyPyConsole
from tests.helpers import remove_colors


INSTALLER_USAGES = {
    "status": "",
    "set_node_argument": "[-d] [arg_name_and_values ...]",
    "enable": "{DS,THA,LSP,TS}",
    "plsc": "",
    "clcf": "[path]",
    "print_ls_proxy_config": "",
    "drvcf": "",
    "ton_storage_list": "[api_port]",
}
INIT_BLOCK = {"seqno": 42, "rootHash": "00" * 32, "fileHash": "11" * 32}
LS_KEY = b"k" * 32
LS_IP = "1.2.3.4"
LS_PORT = 33333


class InstallerCli:
    def __init__(self, local: TestLocal, caplog, tmp_path: Path):
        self.local = local
        self.caplog = caplog
        ton_work = tmp_path / "ton-work"
        self.paths = Paths(
            ton_work=ton_work,
            ton_db=ton_work / "db",
            ton_keys=ton_work / "keys",
            ton_src=tmp_path / "src" / "ton",
            ton_bin=tmp_path / "bin" / "ton",
            mtc_src=tmp_path / "src" / "mytonctrl",
            src_dir=tmp_path / "src",
        )
        self.paths.ton_bin.mkdir(parents=True)
        self.paths.global_config_path.write_text(json.dumps({
            "liteservers": [],
            "validator": {"init_block": {"seqno": 1, "root_hash": "", "file_hash": ""}},
        }))
        pubkey_path = tmp_path / "liteserver.pub"
        pubkey_path.write_bytes(b"\0\0\0\0" + LS_KEY)
        self.ls_data = {"pubkeyPath": str(pubkey_path), "ip": LS_IP, "port": LS_PORT}
        self.mconfig_path = str(tmp_path / "mytoncore.db")
        self.statuses: list[int] = []

    def create(self) -> InstallerCtrl:
        console = TestMyPyConsole(self.local)
        console._caplog = self.caplog
        run_cmd = console.run_cmd

        def recording_run_cmd(line: str) -> int:
            status = run_cmd(line)
            self.statuses.append(status)
            return status

        console.run_cmd = recording_run_cmd
        return InstallerCtrl(
            self.local,
            mconfig_path=self.mconfig_path,
            paths=self.paths,
            ls_data=self.ls_data,
            get_init_block=lambda: dict(INIT_BLOCK),
            console=console,
        )

    def execute(self, command: str) -> str:
        installer = self.create()
        console = installer._console_engine
        output = console._run_capturing(lambda: installer.run(command))
        return remove_colors(output)

    @property
    def status(self) -> int:
        return self.statuses[-1]


@pytest.fixture()
def installer_cli(local, caplog, tmp_path, monkeypatch) -> InstallerCli:
    monkeypatch.setattr(TestLocal, "save", lambda *args, **kwargs: None)
    return InstallerCli(local, caplog, tmp_path)


@pytest.fixture()
def root_calls(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run_as_root(args):
        calls.append([str(arg) for arg in args])
        return 0

    monkeypatch.setattr(installer_module, "run_as_root", fake_run_as_root)
    monkeypatch.setattr(installer_module, "get_current_user", lambda: "operator")
    return calls


@pytest.fixture()
def node_arg_calls(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run_as_root(args):
        calls.append([str(arg) for arg in args])
        return 0

    monkeypatch.setattr(node_args_module, "run_as_root", fake_run_as_root)
    return calls


def _expected_ls_config() -> dict:
    return {
        "ip": ip2int(LS_IP),
        "port": LS_PORT,
        "id": {"@type": "pub.ed25519", "key": base64.b64encode(LS_KEY).decode()},
    }


def _assert_local_config(path: Path) -> None:
    config = json.loads(path.read_text())
    assert config["liteservers"] == [_expected_ls_config()]
    assert config["validator"]["init_block"] == {
        "seqno": INIT_BLOCK["seqno"],
        "root_hash": hex2base64(INIT_BLOCK["rootHash"]),
        "file_hash": hex2base64(INIT_BLOCK["fileHash"]),
    }


def test_help_lists_every_installer_command(installer_cli):
    output = installer_cli.execute("help")
    rows = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        name, _, rest = line.partition(" ")
        rows[name] = rest.strip()
    for name, usage in INSTALLER_USAGES.items():
        assert name in rows, name
        assert rows[name].startswith(usage), (name, rows[name])


@pytest.mark.parametrize(
    "command, script_args",
    [
        ("set_node_argument --archive-ttl 86400", ["--archive-ttl", "86400"]),
        ("set_node_argument -M", ["-M", ""]),
        (
            "set_node_argument --add-shard 0:2000000000000000 0:a000000000000000",
            ["--add-shard", "0:2000000000000000 0:a000000000000000"],
        ),
        ("set_node_argument --archive-ttl -d", ["--archive-ttl", "-d"]),
        ("set_node_argument --archive-ttl --delete", ["--archive-ttl", "-d"]),
        ("set_node_argument --archive-ttl 86400 -d", ["--archive-ttl", "86400 -d"]),
        ("set_node_argument --threads -1", ["--threads", "-1"]),
    ],
)
def test_set_node_argument_passes_the_same_script_arguments(installer_cli, node_arg_calls, command, script_args):
    output = installer_cli.execute(command)
    assert installer_cli.status == 0
    assert "set_node_argument - OK" in output
    assert len(node_arg_calls) == 1
    python, script, *args = node_arg_calls[0]
    assert python == sys.executable
    assert script.endswith("set_node_argument.py")
    assert args == script_args


@pytest.mark.parametrize("command", ["set_node_argument", "set_node_argument -d"])
def test_set_node_argument_requires_a_name(installer_cli, node_arg_calls, command):
    output = installer_cli.execute(command)
    assert installer_cli.status == 2
    assert "set_node_argument: error: expected the node argument name" in output
    assert node_arg_calls == []


def test_set_node_argument_help(installer_cli, node_arg_calls):
    output = installer_cli.execute("set_node_argument -h")
    assert installer_cli.status == 0
    assert output.startswith("usage: set_node_argument [-h] [-d] [arg_name_and_values ...]")
    assert "-d, --delete" in output
    assert node_arg_calls == []


def test_set_node_argument_through_mytonctrl_installer(cli, installer_cli, node_arg_calls, monkeypatch):
    monkeypatch.setattr(InstallerCtrl, "from_ton", classmethod(lambda cls, ton: installer_cli.create()))

    output = cli.execute("installer set_node_argument --archive-ttl -d", no_color=True)
    assert "set_node_argument - OK" in output
    assert node_arg_calls[-1][2:] == ["--archive-ttl", "-d"]

    output = cli.execute("installer -- set_node_argument -h", no_color=True)
    assert "usage: set_node_argument [-h] [-d] [arg_name_and_values ...]" in output
    assert len(node_arg_calls) == 1


@pytest.mark.parametrize(
    "mode, script, tail",
    [
        ("DS", "dht_server.py", lambda cli: ["validator", str(cli.paths.ton_bin), str(cli.paths.global_config_path)]),
        ("LSP", "ls_proxy.py", lambda cli: ["operator", cli.mconfig_path, str(cli.paths.src_dir)]),
        (
            "TS",
            "ton_storage.py",
            lambda cli: ["operator", cli.mconfig_path, str(cli.paths.global_config_path), str(cli.paths.src_dir)],
        ),
    ],
)
def test_enable_runs_the_mode_script(installer_cli, root_calls, mode, script, tail):
    installer_cli.execute(f"enable {mode}")
    assert installer_cli.status == 0
    assert len(root_calls) == 1
    python, script_path, *args = root_calls[0]
    assert python == sys.executable
    assert script_path.endswith(script)
    assert args == tail(installer_cli)


def test_enable_tha_creates_local_config_and_installs(installer_cli, root_calls):
    output = installer_cli.execute("enable THA")
    assert installer_cli.status == 0
    local_config_path = installer_cli.paths.local_config_path
    assert f"Local config file created: {local_config_path}" in output
    _assert_local_config(local_config_path)
    assert "do_enable_ton_http_api - OK" in output
    assert len(root_calls) == 1
    bash, script_path, *args = root_calls[0]
    assert bash == "bash"
    assert script_path.endswith("ton_http_api_installer.sh")
    assert args == [
        "-u", "operator",
        "-b", str(installer_cli.paths.ton_bin),
        "-c", str(local_config_path),
        "-p", sys.executable,
    ]


def test_enable_rejects_unknown_mode(installer_cli, root_calls):
    output = installer_cli.execute("enable XX")
    assert installer_cli.status == 2
    assert "usage: enable [-h] {DS,THA,LSP,TS}" in output
    assert "enable: error: argument mode_name: invalid choice: 'XX'" in output

    output = installer_cli.execute("enable")
    assert installer_cli.status == 2
    assert "enable: error: the following arguments are required: mode_name" in output
    assert root_calls == []


def test_clcf_default_path(installer_cli):
    output = installer_cli.execute("clcf")
    assert installer_cli.status == 0
    local_config_path = installer_cli.paths.local_config_path
    assert f"Local config file created: {local_config_path}" in output
    _assert_local_config(local_config_path)


def test_clcf_with_path(installer_cli, tmp_path):
    path = tmp_path / "custom.config.json"
    output = installer_cli.execute(f"clcf {path}")
    assert installer_cli.status == 0
    assert f"Local config file created: {path}" in output
    _assert_local_config(path)
    assert not installer_cli.paths.local_config_path.exists()

    output = installer_cli.execute(f"clcf {path} extra")
    assert installer_cli.status == 2
    assert "usage: clcf [-h] [path]" in output
    assert "clcf: error: unrecognized arguments: extra" in output


def test_status(installer_cli, monkeypatch):
    monkeypatch.setattr(installer_module, "get_node_args", lambda: {"--archive-ttl": ["86400"], "-M": []})
    output = installer_cli.execute("status")
    assert installer_cli.status == 0
    assert "Full node status: disabled" in output
    assert "Mytoncore status: disabled" in output
    assert "--archive-ttl: 86400" in output
    assert "\n-M\n" in output

    output = installer_cli.execute("status extra")
    assert installer_cli.status == 2
    assert "status: error: unrecognized arguments: extra" in output


def test_plsc(installer_cli):
    output = installer_cli.execute("plsc")
    assert installer_cli.status == 0
    assert json.loads(output.strip()) == _expected_ls_config()


def test_print_ls_proxy_config(installer_cli, monkeypatch):
    config = {"ip": 1, "port": "2", "id": {"@type": "pub.ed25519", "key": "abc"}}
    monkeypatch.setattr(installer_module, "get_ls_proxy_config", lambda: config)
    output = installer_cli.execute("print_ls_proxy_config")
    assert installer_cli.status == 0
    assert json.loads(output.strip()) == config


def test_drvcf(installer_cli, root_calls):
    installer_cli.execute("drvcf")
    assert installer_cli.status == 0
    assert len(root_calls) == 1
    python, script_path, *args = root_calls[0]
    assert python == sys.executable
    assert script_path.endswith("drvcf.py")
    assert args == [str(installer_cli.paths.keyring_dir), installer_cli.mconfig_path, str(installer_cli.paths.ton_db)]


def test_ton_storage_list(installer_cli, monkeypatch, mocker: MockerFixture):
    listing = {"bags": [{"bag_id": "ab"}]}
    response = mocker.Mock(status_code=200)
    response.json.return_value = listing
    get_mock = mocker.Mock(return_value=response)
    monkeypatch.setattr(installer_module.requests, "get", get_mock)
    monkeypatch.setattr(installer_module, "get_ton_storage_port", lambda local: 5555)

    output = installer_cli.execute("ton_storage_list 1234")
    assert installer_cli.status == 0
    get_mock.assert_called_once_with("http://127.0.0.1:1234/api/v1/list", timeout=3)
    assert json.loads(output.strip()) == listing

    get_mock.reset_mock()
    installer_cli.execute("ton_storage_list")
    assert installer_cli.status == 0
    get_mock.assert_called_once_with("http://127.0.0.1:5555/api/v1/list", timeout=3)

    get_mock.reset_mock()
    output = installer_cli.execute("ton_storage_list abc")
    assert installer_cli.status == 2
    assert "ton_storage_list: error: argument api_port: invalid int value: 'abc'" in output
    get_mock.assert_not_called()
