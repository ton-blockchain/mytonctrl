import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace

import pytest

from modules.general import GeneralModule
from mypylib.mypylib import Dict
from mytoncore import telemetry
from mytoncore.models import Paths
from mytonctrl import utils
from mytonctrl.warnings import WarningChecker
from mytoninstaller import dump, settings
from mytoninstaller.context import InstallerPaths
from mytoninstaller.mytoninstaller import InstallerCtrl
from mytoninstaller.scripts import ls_proxy, ton_storage


def forbidden(*args, **kwargs):
    raise AssertionError("This operation must not run inside the controller image")


@pytest.fixture
def container(monkeypatch):
    monkeypatch.setenv("MYTONCTRL_CONTAINER", "1")


def test_container_marker_survives_environment_reset(monkeypatch):
    monkeypatch.delenv("MYTONCTRL_CONTAINER", raising=False)
    monkeypatch.setattr(utils.os.path, "isfile", lambda path: path == "/etc/mytonctrl-container")
    assert utils.is_container()


@pytest.mark.parametrize("method,image,setting", [
    ("Update", "MyTonCtrl", "MYTONCTRL_IMAGE"),
    ("Upgrade", "TON binaries", "TON_IMAGE"),
])
def test_updates_refer_to_images_before_git_or_compiler_checks(container, monkeypatch, capsys, method, image, setting):
    monkeypatch.setattr("modules.general.check_git", forbidden)
    monkeypatch.setattr("modules.general.get_clang_major_version", forbidden)
    monkeypatch.setattr("modules.general.run_as_root", forbidden)
    monkeypatch.setattr("modules.general.get_package_resource_path", forbidden)
    monkeypatch.setattr("builtins.input", forbidden)
    module = GeneralModule(SimpleNamespace(get_paths=forbidden), SimpleNamespace(exit=forbidden))
    getattr(module, method)(["some-repository", "some-branch"])
    output = capsys.readouterr().out
    assert f"The {method.lower()} command is disabled inside this container." in output
    assert f"Update {image} using the appropriate Docker image" in output
    assert f"({setting} in .env)" in output


def test_startup_update_check_does_not_access_repositories(container, monkeypatch):
    monkeypatch.setattr("mytonctrl.warnings.check_git_update", forbidden)
    WarningChecker(None, SimpleNamespace(get_paths=forbidden)).check_mytonctrl_update()


def test_telemetry_reports_package_commit_without_git(container, monkeypatch):
    monkeypatch.setattr(telemetry, "fix_git_config", forbidden)
    monkeypatch.setattr(telemetry, "get_git_hash", forbidden)
    monkeypatch.setattr(telemetry, "get_bin_git_hash", lambda *args, **kwargs: "ton-commit")
    monkeypatch.setattr(telemetry, "get_validator_process_info", lambda: {})
    monkeypatch.setattr("mytonctrl.__commit__", "controller-commit")
    ton = SimpleNamespace(
        get_paths=lambda: Paths(),
        GetAdnlAddr=lambda: "adnl",
        GetValidatorStatus=lambda: {},
        GetStatistics=lambda name: None,
        GetDbUsage=lambda: 0,
        get_modes=lambda: {},
        GetValidatorConfig=lambda: SimpleNamespace(fullnode="fullnode"),
    )
    local = SimpleNamespace(db={}, try_function=lambda *args, **kwargs: None)
    data = telemetry.build_telemetry_payload(local, ton)
    assert data["gitHashes"] == {"mytonctrl": "controller-commit", "validator": "ton-commit"}


def test_installer_events_preserve_environment_and_target_user_home(container, monkeypatch):
    monkeypatch.setenv("PUBLIC_IP", "192.0.2.10")
    monkeypatch.setattr(settings.pwd, "getpwnam", lambda user: SimpleNamespace(pw_dir="/home/operator"))
    calls = []
    monkeypatch.setattr(settings.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    settings._run_as_installer_user("operator", ["/opt/venv/bin/python", "-m", "mytoncore", "-e", "enableVC"])
    args, kwargs = calls[0]
    assert args[:5] == ["su", "-p", "-s", "/bin/sh", "operator"]
    assert kwargs["env"]["PUBLIC_IP"] == "192.0.2.10"
    assert kwargs["env"]["HOME"] == "/home/operator"
    assert kwargs["env"]["XDG_DATA_HOME"] == "/home/operator/.local/share"
    assert kwargs["check"] is True


def test_failed_container_installer_event_aborts_initialization(container):
    with pytest.raises(subprocess.CalledProcessError) as error:
        settings._run_as_installer_user("root", [sys.executable, "-c", "raise SystemExit(23)"])
    assert error.value.returncode == 23


def test_node_ownership_does_not_recurse_into_controller_state(container, monkeypatch, tmp_path):
    paths = InstallerPaths(ton_work_dir=str(tmp_path / "ton-work") + "/")
    work = Path(paths.ton_work_dir)
    work.mkdir()
    (work / "log").write_text("initial validator log")
    (work / "log.1").write_text("rotated validator log")
    (work / "logs").mkdir()
    ctx = SimpleNamespace(
        only_mtc=False, validator_user="validator", user="operator", paths=paths,
        archive_ttl=None, state_ttl=None, mode="validator", add_shard=None,
        public_ip="192.0.2.10", ports=SimpleNamespace(validator=30000), dump=False, archive_blocks=None,
    )
    monkeypatch.setattr(settings, "add2systemd", lambda **kwargs: None)
    monkeypatch.setattr(settings, "_start_validator", lambda local: None)
    monkeypatch.setattr(settings.psutil, "cpu_count", lambda: 4)
    commands = []
    def run(args, **kwargs):
        commands.append(args)
        if args[0] == paths.validator_app_path:
            Path(paths.vconfig_path).write_text('{"addrs": [{}], "control": [], "liteservers": []}')

    monkeypatch.setattr(settings.subprocess, "run", run)
    settings.FirstNodeSettings(SimpleNamespace(add_log=lambda *args: None), ctx)
    assert ["chown", "validator:validator", paths.ton_work_dir] in commands
    ownership = next(command for command in commands if command[:3] == ["chown", "-R", "validator:validator"])
    assert ownership[3:] == [paths.ton_db_dir]
    log_ownership = next(command for command in commands
                         if command[:3] == ["chown", "validator:validator", paths.keys_dir])
    assert sorted(log_ownership[3:]) == [str(work / "log"), str(work / "log.1")]
    assert ["chown", "-R", "validator:validator", paths.ton_work_dir] not in commands


@pytest.mark.parametrize("affinity,quota,threads", [
    (192, "200000 100000", 1),
    (4, "max 100000", 3),
    (2, "400000 100000", 1),
    (192, "50000 100000", 1),
    (1, "max 100000", 1),
])
def test_validator_threads_respect_cpu_quota_and_affinity(monkeypatch, affinity, quota, threads):
    monkeypatch.setattr(settings.os, "sched_getaffinity", lambda pid: set(range(affinity)))
    monkeypatch.setattr(settings.Path, "read_text", lambda path: quota)
    assert settings._container_validator_threads() == threads


def test_initial_validator_failure_stops_before_dump_or_service_start(container, monkeypatch, tmp_path):
    paths = InstallerPaths(ton_work_dir=str(tmp_path / "ton-work") + "/")
    ctx = SimpleNamespace(
        only_mtc=False, validator_user="validator", paths=paths,
        archive_ttl=None, state_ttl=None, mode="validator", add_shard=None,
        public_ip="192.0.2.10", ports=SimpleNamespace(validator=30000), dump=True, archive_blocks=None,
    )
    monkeypatch.setattr(settings, "add2systemd", lambda **kwargs: None)
    monkeypatch.setattr(settings, "_start_validator", forbidden)
    monkeypatch.setattr(settings, "download_dump", forbidden)
    commands = []

    def run(args, check=False, **kwargs):
        commands.append(args)
        if args[0] == paths.validator_app_path:
            if check:
                raise subprocess.CalledProcessError(2, args)
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(settings.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError) as error:
        settings.FirstNodeSettings(SimpleNamespace(add_log=lambda *args: None), ctx)
    assert error.value.returncode == 2
    assert commands[-1][0] == paths.validator_app_path


def test_dump_missing_tools_fails_before_download_or_package_install(container, monkeypatch, tmp_path):
    monkeypatch.setattr(dump.shutil, "which", lambda tool: None if tool == "aria2c" else "/usr/bin/" + tool)
    monkeypatch.setattr(dump, "get_dump_metadata", forbidden)
    monkeypatch.setattr(dump.subprocess, "run", forbidden)
    logs = []
    local = SimpleNamespace(add_log=lambda message, level: logs.append(message))
    assert dump.download_dump(local, None) is False
    assert any("aria2c" in message for message in logs)


def test_dump_uses_preinstalled_tools_without_apt(container, monkeypatch, tmp_path):
    monkeypatch.setattr(dump.shutil, "which", lambda tool: "/usr/bin/" + tool)
    monkeypatch.setattr(dump, "is_testnet", lambda path: False)
    monkeypatch.setattr(dump, "get_dump_metadata", lambda *args: dump.DumpMetadata("dump.tar.lz", "a" * 64, 3, 3))
    monkeypatch.setattr(dump, "check_dump_space", lambda *args: True)
    monkeypatch.setattr(dump, "verify_dump_checksum", lambda *args: True)
    monkeypatch.setattr(dump, "extract_dump", lambda *args: 0)
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        assert args[0] == "aria2c"
        destination = Path(args[args.index("-d") + 1]) / args[args.index("-o") + 1]
        destination.write_bytes(b"abc")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(dump.subprocess, "run", run)
    local = SimpleNamespace(add_log=lambda *args: None)
    paths = SimpleNamespace(ton_db_dir=str(tmp_path / "db"), ton_work_dir=str(tmp_path), global_config_path="config.json")
    assert dump.download_dump(local, SimpleNamespace(paths=paths))
    assert len(commands) == 1


@pytest.mark.parametrize("addon", ["THA", "LSP"])
def test_optional_addons_fail_before_config_or_install_mutation(container, monkeypatch, addon):
    monkeypatch.setattr("mytoninstaller.mytoninstaller.run_as_root", forbidden)
    ctrl = InstallerCtrl.__new__(InstallerCtrl)
    ctrl.create_local_config_file = forbidden
    with pytest.raises(RuntimeError, match="installed separately"):
        ctrl.enable([addon])


def test_direct_optional_installer_cannot_clone_proxy(container, monkeypatch):
    monkeypatch.setattr(ls_proxy.subprocess, "run", forbidden)
    with pytest.raises(RuntimeError, match="does not clone or compile"):
        ls_proxy.enable_ls_proxy("root", "config.db", "/usr/src")


def test_automatic_http_api_setup_skips_package_install(container, monkeypatch):
    ctrl = InstallerCtrl.__new__(InstallerCtrl)
    ctrl.do_enable_ton_http_api = forbidden
    ctrl.enable_ton_http_api(update=True)


def test_ton_storage_requires_prebuilt_executable_at_custom_binary_root(container, monkeypatch, tmp_path):
    root = tmp_path / "custom-bin"
    monkeypatch.setattr(ton_storage, "GetConfig", lambda path: Dict({"paths": {"ton_bin": str(root)}}))
    monkeypatch.setattr(ton_storage.subprocess, "run", forbidden)
    with pytest.raises(RuntimeError, match="prebuilt tonutils-storage") as error:
        ton_storage.enable_ton_storage("root", "config.db", "global.json", "/usr/src")
    assert str(root / "tonutils-storage/tonutils-storage") in str(error.value)


def test_ton_storage_uses_mounted_executable_without_building(container, monkeypatch, tmp_path):
    root = tmp_path / "custom-bin"
    executable = root / "tonutils-storage/tonutils-storage"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    mconfig = Dict({"paths": {"ton_bin": str(root)}})
    monkeypatch.setattr(ton_storage, "GetConfig", lambda path: mconfig if path == "controller.db" else Dict())
    monkeypatch.setattr(ton_storage, "SetConfig", lambda *args, **kwargs: None)
    monkeypatch.setattr(ton_storage, "get_package_resource_path", forbidden)
    monkeypatch.setattr(ton_storage.os, "makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr(ton_storage.time, "sleep", lambda *args: None)
    monkeypatch.setattr(ton_storage, "get_own_ip", lambda: "192.0.2.10")
    commands = []
    monkeypatch.setattr(ton_storage.subprocess, "run", lambda args, **kwargs: commands.append(args))
    services = []
    monkeypatch.setattr(ton_storage, "add2systemd", lambda **kwargs: services.append(kwargs))
    ton_storage.enable_ton_storage("operator", "controller.db", "global.json", "/usr/src")
    assert services[0]["start"].startswith(str(executable) + " ")
    assert all(args[0] in ("chown", "systemctl") for args in commands)


def test_backup_restore_honors_public_ip_and_aborts_on_failure(container, monkeypatch, tmp_path):
    ctx = SimpleNamespace(
        backup="backup.tar.gz", mconfig_path=str(tmp_path / "controller/mytoncore.db"),
        paths=InstallerPaths(ton_work_dir=str(tmp_path / "ton-work") + "/"),
        only_mtc=False, public_ip="192.0.2.10", user="operator",
    )
    monkeypatch.setattr(settings, "get_own_ip", forbidden)
    monkeypatch.setattr(settings, "write_paths", forbidden)
    calls = []

    def restore(args, user):
        calls.append((args, user))
        return 42

    monkeypatch.setattr("modules.backups.BackupModule.run_restore_backup", restore)
    with pytest.raises(RuntimeError, match="exit code 42"):
        settings.ConfigureFromBackup(SimpleNamespace(add_log=lambda *args: None), ctx)
    args, user = calls[0]
    assert args[args.index("-i") + 1] == str(settings.ip2int(ctx.public_ip))
    assert user == "operator"


@pytest.fixture
def restore_command(tmp_path):
    source = Path(__file__).parents[2] / "mytonctrl/scripts/restore_backup.sh"
    script = tmp_path / "restore.sh"
    # Isolate the script's existing fixed scratch path while exercising its real commands.
    contents = source.read_text()
    assert 'tmp_dir="/tmp/mytoncore/backup"' in contents
    contents = contents.replace('tmp_dir="/tmp/mytoncore/backup"', f'tmp_dir="{tmp_path}/scratch"')
    script.write_text(contents)
    commands = tmp_path / "bin"
    commands.mkdir()
    for name, exit_code in (("systemctl", 1), ("chown", 0)):
        executable = commands / name
        record = 'printf "%s\\n" "$*" >> "$SERVICE_COMMANDS"\n' if name == "systemctl" else ""
        executable.write_text(f"#!/bin/sh\n{record}exit {exit_code}\n")
        executable.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(commands) + os.pathsep + env["PATH"]
    env["SERVICE_COMMANDS"] = str(tmp_path / "service-commands.log")
    data = tmp_path / "controller data"
    data.mkdir()
    link = tmp_path / "controller-link"
    link.symlink_to(data)
    work = tmp_path / "node work"
    work.mkdir()
    return ["bash", str(script), "-m", str(link), "-t", str(work), "-u", "operator"], env, data, work


def test_backup_script_restores_through_persisted_directory_symlink(container, restore_command, tmp_path):
    command, env, data, work = restore_command
    backup = tmp_path / "backup with spaces.tar.gz"
    with tarfile.open(backup, "w:gz") as archive:
        for name, content in (("db/config.json", b'{"addrs": [{"ip": 0}]}'),
                              ("db/keyring/key", b"private-key"), ("keys/client", b"client-key"),
                              ("mytoncore/mytoncore.db", b'{"restored": true}')):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    result = subprocess.run(command + ["-n", str(backup)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (data / "mytoncore.db").read_text() == '{"restored": true}'
    assert (work / "keys/client").read_bytes() == b"client-key"
    assert (tmp_path / "controller-link").is_symlink()
    commands = Path(env["SERVICE_COMMANDS"]).read_text().splitlines()
    assert "start validator" in commands
    assert "start mytoncore" not in commands


def test_backup_script_failed_extraction_never_copies_or_reports_success(container, restore_command, tmp_path):
    command, env, data, work = restore_command
    backup = tmp_path / "invalid.tar.gz"
    backup.write_bytes(b"not a tar archive")
    result = subprocess.run(command + ["-n", str(backup)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "failed during tar" in result.stderr
    assert "Started validator and mytoncore" not in result.stdout
    assert not (work / "db").exists()
    assert not (data / "mytoncore.db").exists()
