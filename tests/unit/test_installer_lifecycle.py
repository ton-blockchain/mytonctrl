import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from mypylib.mypylib import Dict
from mytoninstaller import __main__ as installer
from mytoninstaller import settings
from mytoninstaller.context import InstallerPaths
from mytoncore import events


@pytest.fixture
def lifecycle(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")
    paths = InstallerPaths(bin_dir=str(tmp_path / "bin") + "/", ton_work_dir=str(tmp_path / "work") + "/")
    Path(paths.ton_db_dir).mkdir(parents=True)
    Path(paths.keyring_dir).mkdir()
    Path(paths.keys_dir).mkdir()
    core = tmp_path / "work/controller/mytoncore/mytoncore.db"
    core.parent.mkdir(parents=True)
    core.write_text('{"liteClient": {"existingSetting": true}}')
    Path(paths.vconfig_path).write_text(json.dumps({"addrs": [{"ip": 0, "port": 30000}], "control": [], "liteservers": []}))
    ctx = SimpleNamespace(
        only_mtc=False, only_node=False, validator_user="validator", user="root", paths=paths,
        archive_ttl=None, state_ttl=None, mode="validator", add_shard=None, public_ip="192.0.2.10",
        ports=SimpleNamespace(validator=30000, validator_console=31000, liteserver=32000, quic=None),
        dump=True, archive_blocks=None, mconfig_path=str(core), telemetry=False, backup=None,
    )
    local = SimpleNamespace(add_log=lambda *args: None)
    commands = []

    def run(args, **kwargs):
        commands.append((args, kwargs))
        assert kwargs.get("check") is True
        if Path(args[0]).name == "generate-random-id":
            private = Path(args[args.index("--name") + 1])
            seed = hashlib.sha256(private.name.encode()).digest()
            private.write_bytes(bytes.fromhex("17236849") + seed)
            public = settings._public_key_from_private(private)
            private.with_name(private.name + ".pub").write_bytes(public)
        return SimpleNamespace(returncode=0, stdout=b"")

    monkeypatch.setattr(settings.subprocess, "run", run)
    monkeypatch.setattr(settings, "add2systemd", lambda **kwargs: None)
    monkeypatch.setattr(settings, "_start_validator", lambda local: None)
    monkeypatch.setattr(settings, "_wait_validator_console", lambda local, ctx: None)
    monkeypatch.setattr(settings, "_run_as_installer_user", lambda *args: None)
    return ctx, local, commands


def test_existing_node_resumes_dump_and_preserves_config_and_keys(lifecycle, monkeypatch):
    ctx, local, commands = lifecycle
    config = Path(ctx.paths.vconfig_path).read_bytes()
    original_key = Path(ctx.paths.keyring_dir) / "existing-node-key"
    original_key.write_bytes(b"existing private key")
    marker = Path(ctx.paths.ton_work_dir) / "controller/node-initialized.json"
    downloads = []

    def download(local, context):
        assert not marker.exists()
        downloads.append(context)
        return True

    monkeypatch.setattr(settings, "download_dump", download)
    settings.FirstNodeSettings(local, ctx)
    settings.FirstNodeSettings(local, ctx)
    assert len(downloads) == 1
    assert json.loads(marker.read_text()) == {"version": 1}
    assert Path(ctx.paths.vconfig_path).read_bytes() == config
    assert original_key.read_bytes() == b"existing private key"
    assert all(args[0] != ctx.paths.validator_app_path for args, _ in commands)


def test_failed_dump_can_retry_without_node_regeneration(lifecycle, monkeypatch):
    ctx, local, commands = lifecycle
    marker = Path(ctx.paths.ton_work_dir) / "controller/node-initialized.json"
    monkeypatch.setattr(settings, "download_dump", lambda *args: False)
    with pytest.raises(SystemExit):
        settings.FirstNodeSettings(local, ctx)
    assert not marker.exists()
    assert Path(ctx.paths.vconfig_path).is_file()
    monkeypatch.setattr(settings, "download_dump", lambda *args: True)
    settings.FirstNodeSettings(local, ctx)
    assert marker.is_file()
    assert all(args[0] != ctx.paths.validator_app_path for args, _ in commands)


def test_validator_start_failure_never_marks_node_completed(lifecycle, monkeypatch):
    ctx, local, _ = lifecycle
    ctx.dump = False

    def fail(local):
        raise subprocess.CalledProcessError(1, ["systemctl", "restart", "validator"])

    monkeypatch.setattr(settings, "_start_validator", fail)
    with pytest.raises(subprocess.CalledProcessError):
        settings.FirstNodeSettings(local, ctx)
    assert not (Path(ctx.paths.ton_work_dir) / "controller/node-initialized.json").exists()


def test_node_resume_preserves_nonroot_console_key_ownership(lifecycle, monkeypatch):
    ctx, local, commands = lifecycle
    ctx.user = "operator"
    ctx.dump = False
    client = Path(ctx.paths.keys_dir) / "client"
    client.write_bytes(b"existing controller private key")
    settings.FirstNodeSettings(local, ctx)
    settings.FirstNodeSettings(local, ctx)
    assert sum(args == ["chown", "operator:operator", str(client)] for args, _ in commands) == 2
    assert all(not (args[:2] == ["chown", "-R"] and ctx.paths.keys_dir in args) for args, _ in commands)
    assert client.read_bytes() == b"existing controller private key"


def test_console_retry_reuses_keys_and_existing_port(lifecycle, monkeypatch):
    ctx, local, commands = lifecycle

    def interrupted(local):
        raise RuntimeError("interrupted after node configuration")

    monkeypatch.setattr(settings, "_start_validator", interrupted)
    with pytest.raises(RuntimeError, match="interrupted"):
        settings.EnableValidatorConsole(local, ctx)
    keys = {path: path.read_bytes() for path in Path(ctx.paths.keys_dir).iterdir()}
    keyring = {path: path.read_bytes() for path in Path(ctx.paths.keyring_dir).iterdir()}
    assert "validatorConsole" not in json.loads(Path(ctx.mconfig_path).read_text())
    monkeypatch.setattr(settings, "_start_validator", lambda local: None)
    ctx.ports.validator_console = 41000
    settings.EnableValidatorConsole(local, ctx)
    settings.EnableValidatorConsole(local, ctx)
    assert all(path.read_bytes() == data for path, data in keys.items())
    assert all(path.read_bytes() == data for path, data in keyring.items())
    config = json.loads(Path(ctx.paths.vconfig_path).read_text())
    assert len(config["control"]) == 1
    assert len(config["control"][0]["allowed"]) == 1
    assert config["control"][0]["port"] == 31000
    assert json.loads(Path(ctx.mconfig_path).read_text())["validatorConsole"]["addr"] == "127.0.0.1:31000"
    assert sum(Path(args[0]).name == "generate-random-id" for args, _ in commands) == 2


def test_console_recovers_missing_public_keys_from_existing_private_keys(lifecycle):
    ctx, local, commands = lifecycle
    settings.EnableValidatorConsole(local, ctx)
    server_public = Path(ctx.paths.keys_dir) / "server.pub"
    client_public = Path(ctx.paths.keys_dir) / "client.pub"
    expected = server_public.read_bytes(), client_public.read_bytes()
    server_public.unlink()
    client_public.unlink()
    settings.EnableValidatorConsole(local, ctx)
    assert (server_public.read_bytes(), client_public.read_bytes()) == expected
    assert sum(Path(args[0]).name == "generate-random-id" for args, _ in commands) == 2


def test_key_generation_interruption_reuses_already_written_private_key(lifecycle, monkeypatch):
    ctx, local, commands = lifecycle
    original = settings.subprocess.run
    private = Path(ctx.paths.keys_dir) / "server"
    original_bytes = bytes.fromhex("17236849") + b"x" * 32

    def interrupted(args, **kwargs):
        if Path(args[0]).name == "generate-random-id" and args[-1] == str(private):
            private.write_bytes(original_bytes)
            raise subprocess.CalledProcessError(1, args)
        return original(args, **kwargs)

    monkeypatch.setattr(settings.subprocess, "run", interrupted)
    with pytest.raises(subprocess.CalledProcessError):
        settings.EnableValidatorConsole(local, ctx)
    assert private.read_bytes() == original_bytes
    monkeypatch.setattr(settings.subprocess, "run", original)
    settings.EnableValidatorConsole(local, ctx)
    assert original_bytes in [path.read_bytes() for path in Path(ctx.paths.keyring_dir).iterdir()]
    assert sum(Path(args[0]).name == "generate-random-id" for args, _ in commands) == 1


def test_missing_existing_server_private_key_is_never_replaced(lifecycle):
    ctx, local, commands = lifecycle
    settings.EnableValidatorConsole(local, ctx)
    public = (Path(ctx.paths.keys_dir) / "server.pub").read_bytes()
    key_hash = hashlib.sha256(public).digest()
    (Path(ctx.paths.keyring_dir) / key_hash.hex().upper()).unlink()
    with pytest.raises(RuntimeError, match="Missing or mismatched existing node key"):
        settings.EnableValidatorConsole(local, ctx)
    assert sum(Path(args[0]).name == "generate-random-id" for args, _ in commands) == 2


def test_liteserver_retry_finishes_controller_config_without_rotating_key(lifecycle, monkeypatch):
    ctx, local, commands = lifecycle
    original = settings.SetConfig

    def interrupted(path, data):
        if path == ctx.mconfig_path:
            raise RuntimeError("interrupted writing controller settings")
        return original(path, data)

    monkeypatch.setattr(settings, "SetConfig", interrupted)
    with pytest.raises(RuntimeError, match="interrupted"):
        settings.EnableLiteServer(local, ctx)
    keyring = {path: path.read_bytes() for path in Path(ctx.paths.keyring_dir).iterdir()}
    monkeypatch.setattr(settings, "SetConfig", original)
    ctx.ports.liteserver = 42000
    settings.EnableLiteServer(local, ctx)
    settings.EnableLiteServer(local, ctx)
    config = json.loads(Path(ctx.paths.vconfig_path).read_text())
    core = json.loads(Path(ctx.mconfig_path).read_text())
    assert len(config["liteservers"]) == 1
    assert core["liteClient"]["liteServer"]["port"] == 32000
    assert core["liteClient"]["existingSetting"] is True
    assert all(path.read_bytes() == data for path, data in keyring.items())
    assert sum(Path(args[0]).name == "generate-random-id" for args, _ in commands) == 1


def test_completed_stages_skip_backup_restore_but_bring_validator_online(lifecycle):
    ctx, local, _ = lifecycle
    calls = []

    def callback(local, ctx):
        calls.append("called")

    installer._run_installation_stage(local, ctx, "backup_restore", callback)
    installer._run_installation_stage(local, ctx, "backup_restore", callback)
    installer._run_installation_stage(local, ctx, "node_settings", callback)
    installer._run_installation_stage(local, ctx, "node_settings", callback)
    progress = json.loads((Path(ctx.paths.ton_work_dir) / "controller/installer-progress.json").read_text())
    assert calls == ["called", "called", "called"]
    assert progress["completed"] == ["backup_restore", "node_settings"]
    assert progress["status"] == "complete"


def test_failed_stage_retains_progress_and_retries(lifecycle):
    ctx, local, _ = lifecycle
    calls = []

    def callback(local, ctx):
        calls.append("called")
        if len(calls) == 1:
            raise RuntimeError("download interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        installer._run_installation_stage(local, ctx, "node_settings", callback)
    path = Path(ctx.paths.ton_work_dir) / "controller/installer-progress.json"
    assert json.loads(path.read_text()) == {
        "version": 1, "completed": [], "stage": "node_settings", "status": "failed", "error": "download interrupted",
    }
    installer._run_installation_stage(local, ctx, "node_settings", callback)
    assert json.loads(path.read_text())["completed"] == ["node_settings"]
    assert "error" not in json.loads(path.read_text())


def test_pending_backup_restore_retries_before_activating_validator(lifecycle):
    ctx, local, _ = lifecycle
    ctx.backup = "mounted-donor-backup.tar.gz"
    keyring = Path(ctx.paths.keyring_dir)
    keyring.rmdir()  # A prior restore removed the old keyring before it was interrupted.
    config = Path(ctx.paths.vconfig_path).read_bytes()
    progress = Path(ctx.paths.ton_work_dir) / "controller/installer-progress.json"
    progress.write_text(json.dumps({
        "version": 1, "completed": ["node_settings", "validator_console", "liteserver"],
        "stage": "backup_restore", "status": "failed", "error": "copy interrupted",
    }))
    calls = []

    def activate(local, ctx):
        assert (keyring / "donor-key").read_bytes() == b"original donor private key"
        calls.append("activate")

    def restore(local, ctx):
        assert calls == []
        keyring.mkdir()
        (keyring / "donor-key").write_bytes(b"original donor private key")
        calls.append("restore")

    installer._run_installation_stage(local, ctx, "node_settings", activate)
    assert calls == []
    installer._run_installation_stage(local, ctx, "backup_restore", restore)
    installer._run_installation_stage(local, ctx, "node_settings", activate)
    assert calls == ["restore", "activate"]
    assert Path(ctx.paths.vconfig_path).read_bytes() == config
    assert "backup_restore" in json.loads(progress.read_text())["completed"]


def test_core_background_start_is_deferred_in_container(lifecycle, monkeypatch):
    ctx, local, _ = lifecycle
    calls = []
    units = []
    monkeypatch.setattr(settings, "StartMytoncore", lambda local: calls.append("started"))
    monkeypatch.setattr(settings, "add2systemd", lambda **kwargs: units.append(kwargs))
    settings.FirstMytoncoreSettings(local, ctx)
    settings.SetInitialSync(local, ctx)
    settings._start_mytoncore(local)
    assert calls == []
    assert units[0]["force"] is False


def test_host_stage_and_service_behavior_remains_direct(lifecycle, monkeypatch):
    ctx, local, _ = lifecycle
    monkeypatch.setattr(installer, "is_container", lambda: False)
    monkeypatch.setattr(settings, "is_container", lambda: False)
    calls = []
    monkeypatch.setattr(settings, "StartMytoncore", lambda local: calls.append("core"))
    installer._run_installation_stage(local, ctx, "backup_restore", lambda *args: calls.append("backup"))
    settings._start_mytoncore(local)
    assert calls == ["backup", "core"]
    assert not (Path(ctx.paths.ton_work_dir) / "controller/installer-progress.json").exists()


def test_enable_vc_retry_reuses_wallet_and_saved_adnl_key(lifecycle, monkeypatch):
    _, _, _ = lifecycle
    local = SimpleNamespace(db=Dict(), add_log=lambda *args: None, save=lambda: None)
    calls = []
    attached = []
    ton = SimpleNamespace(
        CreateNewKey=lambda: calls.append("new-key") or "existing-adnl",
        add_adnl_addr=lambda key: attached.append(key) or len(attached) > 1,
        GetLocalWallet=lambda name: SimpleNamespace(name=name),
    )
    wallet_module = SimpleNamespace(create_wallet=lambda name, workchain: SimpleNamespace(name=name))
    monkeypatch.setattr(events, "MyTonCore", lambda local: ton)
    monkeypatch.setattr(events, "WalletModule", lambda ton, local: wallet_module)
    with pytest.raises(RuntimeError, match="retained for retry"):
        events.enable_vc_event(local, "enableVC")
    assert local.db["adnlAddr"] == "existing-adnl"
    assert not local.db.get("containerEnableVcComplete")
    events.enable_vc_event(local, "enableVC")
    events.enable_vc_event(local, "enableVC")
    assert calls == ["new-key"]
    assert attached == ["existing-adnl", "existing-adnl"]
    assert local.db["validatorWalletName"] == "validator_wallet_001"
    assert local.db["containerEnableVcComplete"] is True


def test_legacy_enable_vc_preserves_existing_wallet_and_adnl(lifecycle, monkeypatch):
    local = SimpleNamespace(
        db=Dict(validatorWalletName="existing_v3_wallet", adnlAddr="existing-adnl"),
        add_log=lambda *args: None, save=lambda: None,
    )
    wallets = []

    def forbidden(*args):
        raise AssertionError("Existing wallet and ADNL identities must be reused")

    ton = SimpleNamespace(
        CreateNewKey=forbidden, add_adnl_addr=lambda key: key == "existing-adnl",
        GetLocalWallet=lambda name: wallets.append(name) or SimpleNamespace(name=name),
    )
    monkeypatch.setattr(events, "MyTonCore", lambda local: ton)
    monkeypatch.setattr(events, "WalletModule", lambda *args: SimpleNamespace(create_wallet=forbidden))
    events.enable_vc_event(local, "enableVC")
    assert wallets == ["existing_v3_wallet"]
    assert local.db["validatorWalletName"] == "existing_v3_wallet"
    assert local.db["adnlAddr"] == "existing-adnl"
    assert local.db["containerEnableVcComplete"] is True
