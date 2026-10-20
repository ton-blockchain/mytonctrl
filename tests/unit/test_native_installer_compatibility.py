import json
import os
from pathlib import Path
import subprocess
import tarfile
from types import SimpleNamespace

import pytest

from mypylib.mypylib import Dict
from mytoncore import events
from mytoninstaller import __main__ as installer
from mytoninstaller import config, settings
from mytoninstaller.context import InstallerPaths


@pytest.fixture(autouse=True)
def native_installation(monkeypatch):
    for module in (installer, config, settings, events):
        monkeypatch.setattr(module, "is_container", lambda: False)
    monkeypatch.delenv("MYTONCTRL_CONTAINER", raising=False)


@pytest.fixture
def native_node(tmp_path):
    paths = InstallerPaths(
        bin_dir=str(tmp_path / "bin") + "/",
        src_dir=str(tmp_path / "src") + "/",
        ton_work_dir=str(tmp_path / "work") + "/",
    )
    Path(paths.ton_db_dir).mkdir(parents=True)
    Path(paths.keys_dir).mkdir()
    core = tmp_path / "core/mytoncore.db"
    core.parent.mkdir()
    core.write_text('{"liteClient": {}}')
    ctx = SimpleNamespace(
        only_mtc=False,
        only_node=False,
        validator_user="daemon",
        user="operator",
        paths=paths,
        mconfig_path=str(core),
        ports=SimpleNamespace(
            validator=30000, validator_console=31000, liteserver=32000, quic=33000
        ),
        archive_ttl=None,
        state_ttl=None,
        public_ip="192.0.2.10",
        mode="validator",
        dump=False,
        archive_blocks=None,
        add_shard=None,
        telemetry=False,
        backup=None,
    )
    local = SimpleNamespace(add_log=lambda *args: None)
    return ctx, local


@pytest.mark.parametrize("umask,mode", [(0o022, 0o644), (0o077, 0o600)])
def test_native_new_config_uses_original_open_permissions(tmp_path, umask, mode):
    target = tmp_path / "mytoncore.db"
    previous_umask = os.umask(umask)
    try:
        config.SetConfig(str(target), Dict(initialSync=True))
    finally:
        os.umask(previous_umask)
    assert target.stat().st_mode & 0o777 == mode
    assert config.GetConfig(str(target)) == {"initialSync": True}


def test_native_config_preserves_existing_inode_links_and_owner(tmp_path, monkeypatch):
    target = tmp_path / "mytoncore.db"
    target.write_text('{"initialSync": false}')
    target.chmod(0o640)
    hardlink = tmp_path / "hardlink.db"
    os.link(target, hardlink)
    symlink = tmp_path / "symlink.db"
    symlink.symlink_to(target)
    before = target.stat()

    def forbid_replace(*args, **kwargs):
        raise AssertionError(
            "Native configuration writes must update the existing file"
        )

    monkeypatch.setattr(config.os, "replace", forbid_replace)
    config.SetConfig(str(symlink), Dict(initialSync=True))
    after = target.stat()
    assert (after.st_ino, after.st_uid, after.st_gid, after.st_mode) == (
        before.st_ino,
        before.st_uid,
        before.st_gid,
        before.st_mode,
    )
    assert symlink.is_symlink()
    assert config.GetConfig(str(hardlink)) == {"initialSync": True}


@pytest.mark.parametrize("value", [None, "", " \t ", " 192.0.2.10\t"])
def test_native_public_ip_keeps_original_environment_semantics(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PUBLIC_IP", raising=False)
    else:
        monkeypatch.setenv("PUBLIC_IP", value)
    ctx = installer.get_context(installer._parse_general_args(["-m", "validator"]))
    assert ctx.public_ip == value


@pytest.mark.parametrize("only_mtc", [False, True])
def test_native_installation_keeps_logging_and_stage_order(
    native_node, monkeypatch, only_mtc
):
    ctx, _ = native_node
    ctx.only_mtc = only_mtc
    order = []
    local = SimpleNamespace(
        db=Dict(
            config=Dict(
                isWritingLogFile=True, isLimitLogFile=True, logFileSizeLines=100
            )
        ),
        log_file_name="original-native.log",
        exit=lambda: order.append("exit"),
    )
    monkeypatch.setattr(installer, "MyPyClass", lambda *args: local)
    monkeypatch.setattr(
        installer,
        "setup_logging",
        lambda *args: order.append(("logging", args)),
    )
    monkeypatch.setattr(installer, "_parse_general_args", lambda: order.append("parse"))
    monkeypatch.setattr(
        installer, "get_context", lambda args: order.append("context") or ctx
    )
    callbacks = [
        "FirstMytoncoreSettings",
        "write_paths",
        "FirstNodeSettings",
        "EnableValidatorConsole",
        "EnableLiteServer",
        "BackupMconfig",
        "CreateSymlinks",
        "EnableMode",
        "ConfigureFromBackup",
        "ConfigureOnlyNode",
        "SetInitialSync",
        "SetupCollator",
    ]
    for name in callbacks:
        monkeypatch.setattr(
            installer, name, lambda local, ctx, name=name: order.append(name)
        )
    installer.mytoninstaller()
    expected = callbacks.copy()
    if only_mtc:
        expected.remove("EnableLiteServer")
    assert order == [
        ("logging", ("debug", "original-native.log", 100)),
        "parse",
        "context",
        *expected,
        "exit",
    ]
    assert not (Path(ctx.paths.ton_work_dir) / "controller").exists()


def test_native_first_node_keeps_launch_options_and_unchecked_process_status(
    native_node, monkeypatch
):
    ctx, local = native_node
    ctx.archive_ttl = -1
    ctx.add_shard = "0:8000000000000000 -1:8000000000000000"
    units = []
    commands = []
    starts = []

    def run(args, **kwargs):
        commands.append((args, kwargs))
        return subprocess.CompletedProcess(args, 1)

    monkeypatch.setattr(settings.subprocess, "run", run)
    monkeypatch.setattr(settings, "add2systemd", lambda **kwargs: units.append(kwargs))
    monkeypatch.setattr(settings.psutil, "cpu_count", lambda: 8)
    monkeypatch.setattr(
        settings,
        "_container_validator_threads",
        lambda: pytest.fail("container CPU policy"),
    )
    monkeypatch.setattr(
        settings, "StartValidator", lambda local: starts.append("validator")
    )
    settings.FirstNodeSettings(local, ctx)
    command = units[0]["start"]
    assert units[0]["user"] == "daemon"
    assert units[0]["pre"] == "/bin/sleep 2"
    assert "--threads 7 --daemonize" in command
    assert f"--logname {ctx.paths.ton_log_path}" in command
    assert (
        "--permanent-celldb --state-ttl 1000000000 --archive-ttl 1000000000" in command
    )
    assert (
        " -M --add-shard 0:8000000000000000 --add-shard -1:8000000000000000" in command
    )
    initial, kwargs = next(
        item for item in commands if item[0][0] == ctx.paths.validator_app_path
    )
    assert initial[initial.index("--ip") + 1] == "192.0.2.10:30000"
    assert initial[initial.index("--logname") + 1] == ctx.paths.ton_log_path
    assert not kwargs.get("check", False)
    assert (["chown", "-R", "daemon:daemon", ctx.paths.ton_work_dir], {}) in commands
    assert starts == ["validator"]
    assert not (Path(ctx.paths.ton_work_dir) / "controller").exists()
    assert not any(args[:2] == ["systemctl", "stop"] for args, _ in commands)


def test_native_existing_node_keeps_original_early_return(native_node, monkeypatch):
    ctx, local = native_node
    Path(ctx.paths.vconfig_path).write_text("existing configuration left untouched")
    ctx.dump = True

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Existing native validator configuration must skip node setup"
        )

    monkeypatch.setattr(settings.subprocess, "run", forbidden)
    monkeypatch.setattr(settings, "download_dump", forbidden)
    monkeypatch.setattr(settings, "StartValidator", forbidden)
    settings.FirstNodeSettings(local, ctx)
    assert (
        Path(ctx.paths.vconfig_path).read_text()
        == "existing configuration left untouched"
    )


@pytest.mark.parametrize(
    "error", [RuntimeError("failed"), SystemExit(42), KeyboardInterrupt()]
)
def test_native_stage_propagates_original_failure_without_checkpoint(
    native_node, error
):
    ctx, local = native_node

    def fail(local, ctx):
        raise error

    with pytest.raises(type(error)) as raised:
        installer._run_installation_stage(local, ctx, "node_settings", fail)
    assert raised.value is error
    assert not (Path(ctx.paths.ton_work_dir) / "controller").exists()


def test_native_console_keeps_key_config_event_and_service_sequence(
    native_node, monkeypatch
):
    ctx, local = native_node
    Path(ctx.paths.vconfig_path).write_text('{"control": [], "liteservers": []}')
    order = []

    def run(args, **kwargs):
        if Path(args[0]).name == "generate-random-id":
            name = Path(args[-1]).name
            return SimpleNamespace(stdout=f"{name}-hash {name}-b64\n".encode())
        if args[0] == "su":
            core = config.GetConfig(ctx.mconfig_path)
            node = config.GetConfig(ctx.paths.vconfig_path)
            assert core.validatorConsole.addr == "127.0.0.1:31000"
            assert node.control[0].allowed[0].id == "client-b64"
            order.append(("event", args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(settings.subprocess, "run", run)
    monkeypatch.setattr(
        settings, "StartValidator", lambda local: order.append("validator")
    )
    monkeypatch.setattr(settings, "StartMytoncore", lambda local: order.append("core"))
    monkeypatch.setattr(
        settings,
        "_wait_validator_console",
        lambda *args: pytest.fail(
            "Container readiness must not run on native installs"
        ),
    )
    settings.EnableValidatorConsole(local, ctx)
    assert order == [
        "validator",
        (
            "event",
            [
                "su",
                "-l",
                "operator",
                "-c",
                f'{settings.sys.executable} -m mytoncore -e "enableVC_33000"',
            ],
            {},
        ),
        "core",
    ]
    assert config.GetConfig(ctx.paths.vconfig_path).control[0].id == "server-b64"


def test_native_core_unit_still_overwrites_existing_service(native_node, monkeypatch):
    ctx, local = native_node
    units = []
    monkeypatch.setattr(settings, "add2systemd", lambda **kwargs: units.append(kwargs))
    settings.FirstMytoncoreSettings(local, ctx)
    assert units == [
        dict(
            name="mytoncore",
            user="operator",
            start=f"{settings.sys.executable} -m mytoncore",
            force=True,
        )
    ]


def test_native_backup_keeps_auto_ip_and_restart_after_restore_error(
    native_node, monkeypatch
):
    ctx, local = native_node
    ctx.backup = "backup.tar.gz"
    calls = []
    monkeypatch.setattr(settings, "get_own_ip", lambda: "198.51.100.20")
    monkeypatch.setattr(settings, "StartMytoncore", lambda local: calls.append("core"))

    def restore(args, user):
        calls.append((args, user))
        return 42

    monkeypatch.setattr("modules.backups.BackupModule.run_restore_backup", restore)
    settings.ConfigureFromBackup(local, ctx)
    args, user = calls[0]
    assert args[args.index("-i") + 1] == str(settings.ip2int("198.51.100.20"))
    assert user == "operator"
    assert calls[-1] == "core"
    assert config.GetConfig(ctx.mconfig_path).paths.ton_work == ctx.paths.ton_work_dir


def test_native_validator_event_keeps_original_wallet_and_adnl_order(monkeypatch):
    order = []
    local = SimpleNamespace(
        db=Dict(
            validatorWalletName="existing-wallet",
            adnlAddr="previous-adnl",
            containerEnableVcComplete=True,
        ),
        add_log=lambda *args: None,
        save=lambda: order.append(("save", local.db["adnlAddr"])),
    )

    def add_adnl(key):
        assert local.db["adnlAddr"] == "previous-adnl"
        order.append(("add", key))
        return False

    ton = SimpleNamespace(
        CreateNewKey=lambda: order.append("new-key") or "new-adnl",
        add_adnl_addr=add_adnl,
    )
    wallet = SimpleNamespace(
        create_wallet=lambda name, workchain: (
            order.append(("wallet", name, workchain)) or SimpleNamespace(name=name)
        )
    )
    monkeypatch.setattr(events, "MyTonCore", lambda local: ton)
    monkeypatch.setattr(events, "WalletModule", lambda *args: wallet)
    monkeypatch.setattr(
        events,
        "GeneralModule",
        lambda *args: SimpleNamespace(
            set_quic_port=lambda args: order.append(("quic", args))
        ),
    )
    events.enable_vc_event(local, "enableVC_33000")
    assert order == [
        ("wallet", "validator_wallet_001", -1),
        "new-key",
        ("add", "new-adnl"),
        ("save", "new-adnl"),
        ("quic", 33000),
    ]
    assert local.db["validatorWalletName"] == "validator_wallet_001"


def test_native_failed_adnl_attachment_keeps_previous_identity(monkeypatch):
    local = SimpleNamespace(
        db=Dict(adnlAddr="previous-adnl"),
        add_log=lambda *args: None,
        save=lambda: pytest.fail("Failed native event must not save configuration"),
    )

    def fail_attach(key):
        raise RuntimeError("validator unavailable")

    monkeypatch.setattr(
        events,
        "MyTonCore",
        lambda local: SimpleNamespace(
            CreateNewKey=lambda: "new-adnl", add_adnl_addr=fail_attach
        ),
    )
    monkeypatch.setattr(
        events,
        "WalletModule",
        lambda *args: SimpleNamespace(
            create_wallet=lambda *args: SimpleNamespace(name="validator_wallet_001")
        ),
    )
    with pytest.raises(RuntimeError, match="validator unavailable"):
        events.enable_vc_event(local, "enableVC")
    assert local.db["adnlAddr"] == "previous-adnl"


@pytest.mark.parametrize("valid_archive", [True, False])
def test_native_restore_script_keeps_service_and_failure_behavior(
    tmp_path, valid_archive
):
    source = Path(__file__).parents[2] / "mytonctrl/scripts/restore_backup.sh"
    script = tmp_path / "restore.sh"
    script.write_text(
        source.read_text()
        .replace('tmp_dir="/tmp/mytoncore/backup"', f'tmp_dir="{tmp_path}/scratch"')
        .replace("/etc/mytonctrl-container", str(tmp_path / "no-container-marker"))
    )
    tools = tmp_path / "bin"
    tools.mkdir()
    services = tmp_path / "services.log"
    for name in ("systemctl", "chown", "readlink"):
        executable = tools / name
        if name == "systemctl":
            text = f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{services}"\nexit 1\n'
        elif name == "readlink":
            text = "#!/bin/sh\necho Unexpected container path resolution >&2\nexit 99\n"
        else:
            text = "#!/bin/sh\nexit 0\n"
        executable.write_text(text)
        executable.chmod(0o755)
    donor = tmp_path / "donor"
    for name in ("db/keyring", "keys", "mytoncore"):
        (donor / name).mkdir(parents=True)
    (donor / "db/config.json").write_text('{"addrs": [{"ip": 0}]}')
    (donor / "db/keyring/key").write_bytes(b"node-key")
    (donor / "keys/client").write_bytes(b"controller-key")
    (donor / "mytoncore/mytoncore.db").write_text('{"restored": true}')
    backup = tmp_path / "backup.tar.gz"
    if valid_archive:
        with tarfile.open(backup, "w:gz") as archive:
            for path in donor.iterdir():
                archive.add(path, arcname=path.name)
    else:
        backup.write_bytes(b"invalid backup archive")
    work = tmp_path / "work"
    work.mkdir()
    core = tmp_path / "core"
    core.mkdir()
    env = dict(
        os.environ,
        PATH=str(tools) + os.pathsep + os.environ["PATH"],
        MYTONCTRL_CONTAINER="0",
    )
    result = subprocess.run(
        [
            "bash",
            str(script),
            "-n",
            str(backup),
            "-m",
            str(core),
            "-t",
            str(work),
            "-u",
            "operator",
            "-i",
            "123",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert services.read_text().splitlines() == [
        "stop validator",
        "stop mytoncore",
        "start validator",
        "start mytoncore",
    ]
    assert "Backup restoration failed during" not in result.stderr
    if valid_archive:
        assert (core / "mytoncore.db").read_text() == '{"restored": true}'
        assert (
            json.loads((work / "db/config.json").read_text())["addrs"][0]["ip"] == 123
        )
    else:
        assert not (core / "mytoncore.db").exists()
