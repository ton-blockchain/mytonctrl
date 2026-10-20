import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docker"))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "docker" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


entrypoint = load_script("entrypoint")
console = load_script("console")
docker_args = load_script("mytonctrl_docker_args")


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def artifacts(self, root):
        sources = tuple(root / name for name in ("bin", "fift", "smartcont"))
        for source in sources:
            source.mkdir(parents=True)
        for name in entrypoint.REQUIRED_BINARIES:
            path = sources[0] / name
            path.write_text("original executable")
            path.chmod(0o755)
        for name in ("Fift.fif", "TonUtil.fif", "Asm.fif"):
            (sources[1] / name).write_text("original library")
        for name in ("wallet-v3.fif", "validator-elect-signed.fif"):
            (sources[2] / name).write_text("original contract")
        return sources

    def test_snapshot_keeps_binaries_and_resources_when_provider_updates(self):
        sources = self.artifacts(self.root / "provider")
        metadata = sources[0].parent / "image-ref"
        metadata.write_text("ghcr.io/ton-blockchain/ton:running\n")
        active = entrypoint.snapshot_artifacts(sources, self.root / "active")
        (sources[0] / "validator-engine").write_text("new executable")
        (sources[1] / "TonUtil.fif").write_text("new library")
        metadata.write_text("ghcr.io/ton-blockchain/ton:new\n")
        self.assertEqual((active / "bin/validator-engine").read_text(), "original executable")
        self.assertEqual((active / "fift/TonUtil.fif").read_text(), "original library")
        self.assertEqual((active / "bin/validator-engine").stat().st_mode & 0o222, 0)
        self.assertEqual((active / "image-ref").read_text(), "ghcr.io/ton-blockchain/ton:running\n")
        self.assertEqual((active / "image-ref").stat().st_mode & 0o222, 0)

    def test_existing_native_mounts_need_no_export_metadata(self):
        sources = self.artifacts(self.root / "native")
        env = dict(zip(("TON_BINARIES_DIR", "FIFT_LIB_DIR", "TON_SMARTCONT_DIR"), map(str, sources)))
        env["TON_ARTIFACTS_DIR"] = str(self.root / "absent")
        with patch.object(entrypoint, "mounted", return_value=True):
            self.assertEqual(entrypoint.artifact_sources(env), sources)
        active = entrypoint.snapshot_artifacts(sources, self.root / "active")
        self.assertFalse((active / "image-ref").exists())

    def test_missing_mount_fails_before_creating_runtime_or_state(self):
        with self.assertRaisesRegex(ValueError, "Missing TON artifact mount"):
            entrypoint.artifact_sources({"TON_BINARIES_DIR": str(self.root / "missing")})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_blank_or_missing_public_ip_is_detected_before_installation(self):
        for value in (None, "", " \t"):
            env = {} if value is None else {"PUBLIC_IP": value}
            with self.subTest(value=value), patch.object(entrypoint, "detect_public_ip", return_value="192.0.2.10") as detect:
                entrypoint.resolve_public_ip(env)
                detect.assert_called_once_with()
                self.assertEqual(env["PUBLIC_IP"], "192.0.2.10")

    def test_explicit_ipv4_is_trimmed_and_accepts_custom_network_addresses(self):
        for value in (" 192.0.2.10 ", "127.0.0.1", "10.0.0.5"):
            env = {"PUBLIC_IP": value}
            with self.subTest(value=value), patch.object(entrypoint, "detect_public_ip") as detect:
                entrypoint.resolve_public_ip(env)
                detect.assert_not_called()
                self.assertEqual(env["PUBLIC_IP"], value.strip())

    def test_invalid_explicit_public_ip_fails_without_discovery(self):
        for value in ("not-an-ip", "::1", "256.0.0.1"):
            env = {"PUBLIC_IP": value}
            with self.subTest(value=value), patch.object(entrypoint, "detect_public_ip") as detect:
                with self.assertRaises(ValueError):
                    entrypoint.resolve_public_ip(env)
                detect.assert_not_called()

    def test_failed_public_ip_discovery_explains_env_configuration(self):
        env = {"PUBLIC_IP": ""}
        with patch.object(entrypoint, "detect_public_ip", side_effect=OSError("discovery service unavailable")):
            with self.assertRaisesRegex(ValueError, "PUBLIC_IP.*\\.env"):
                entrypoint.resolve_public_ip(env)
        self.assertEqual(env["PUBLIC_IP"], "")

    def test_invalid_discovered_ip_cannot_reach_installer(self):
        for value in ("", "not-an-ip", "2001:db8::1"):
            env = {}
            with self.subTest(value=value), patch.object(entrypoint, "detect_public_ip", return_value=value):
                with self.assertRaises(ValueError):
                    entrypoint.resolve_public_ip(env)
            self.assertNotIn("PUBLIC_IP", env)

    def test_controller_only_restore_skips_public_ip_resolution(self):
        env = {"ONLY_MTC": "true", "PUBLIC_IP": ""}
        with patch.object(entrypoint, "detect_public_ip") as detect:
            entrypoint.resolve_public_ip(env)
            detect.assert_not_called()
        self.assertEqual(env["PUBLIC_IP"], "")

    def test_interrupted_initialization_restores_original_settings(self):
        pending = self.root / ".initializing"
        identity = {"MTC_USER": "root", "TON_WORK_DIR": str(self.root)}
        settings = {"MTC_USER": "root", "TON_WORK_DIR": str(self.root), "DUMP": "true",
                    "PUBLIC_IP": "192.0.2.10", "VALIDATOR_CONSOLE_PORT": "30304"}
        entrypoint.write_json(pending, {"version": 1, "identity": identity,
                                      "installer_environment": settings})
        archive = self.root / "downloaded.tar.lz"
        archive.write_bytes(b"downloaded dump")
        env = {"DUMP": "false", "PUBLIC_IP": "", "TON_IMAGE": "new-image", "ARCHIVE_BLOCKS": "100"}
        self.assertTrue(entrypoint.resume_settings(env, pending, identity))
        self.assertEqual({key: env[key] for key in settings}, settings)
        self.assertEqual(env["TON_IMAGE"], "new-image")
        self.assertNotIn("ARCHIVE_BLOCKS", env)
        self.assertEqual(archive.read_bytes(), b"downloaded dump")

    def test_legacy_empty_pending_marker_can_resume_without_removing_data(self):
        pending = self.root / ".initializing"
        pending.touch()
        env = {"DUMP": "true"}
        self.assertTrue(entrypoint.resume_settings(env, pending, {}))
        self.assertEqual(env, {"DUMP": "true"})
        self.assertTrue(pending.exists())

    def test_invalid_or_incompatible_resume_settings_are_rejected_without_overwriting(self):
        pending = self.root / ".initializing"
        values = ("broken JSON", json.dumps({"version": 1, "identity": {"MTC_USER": "other"},
                                            "installer_environment": {}}),
                  json.dumps({"version": 1, "identity": {}, "installer_environment": {"PATH": "/tmp"}}))
        for value in values:
            with self.subTest(value=value):
                pending.write_text(value)
                with self.assertRaises(ValueError):
                    entrypoint.resume_settings({}, pending, {})
                self.assertEqual(pending.read_text(), value)

    def test_resume_reuses_existing_node_ports_when_environment_is_blank(self):
        database = self.root / "db"
        database.mkdir()
        (database / "config.json").write_text(json.dumps({"addrs": [{"port": 30303}],
                                                        "control": [{"port": 30304}],
                                                        "liteservers": [{"port": 30305}]}))
        env = {"VALIDATOR_PORT": "", "VALIDATOR_CONSOLE_PORT": "", "LITESERVER_PORT": ""}
        entrypoint.pin_installer_ports(env, self.root)
        self.assertEqual(env, {"VALIDATOR_PORT": "30303", "VALIDATOR_CONSOLE_PORT": "30304",
                               "LITESERVER_PORT": "30305"})

    def test_random_ports_are_persisted_before_installer_launch(self):
        env = {}
        entrypoint.pin_installer_ports(env, self.root)
        pending = self.root / ".initializing"
        entrypoint.write_json(pending, {"version": 1, "identity": {}, "installer_environment": env})
        restored = {}
        entrypoint.resume_settings(restored, pending, {})
        self.assertEqual(restored, env)
        self.assertEqual(len(set(restored.values())), 3)

    def test_discovery_failure_precedes_pending_marker_and_installer_process(self):
        work = self.root / "node-work"
        env = {"PUBLIC_IP": "", "TON_WORK_DIR": str(work), "MTC_USER": "root"}
        with patch.object(entrypoint.sys, "argv", ["entrypoint.py", "run"]), \
             patch.object(entrypoint, "installation_environment", return_value=env), \
             patch.object(entrypoint, "artifact_sources", return_value=()), \
             patch.object(entrypoint, "snapshot_artifacts", return_value=self.root / "active"), \
             patch.object(entrypoint, "check_binaries"), \
             patch.object(entrypoint.os, "getuid", return_value=0), \
             patch.object(entrypoint.os, "environ", {}), \
             patch.object(entrypoint, "mounted", return_value=False), \
             patch.object(entrypoint, "check_requirements"), \
             patch.object(entrypoint, "detect_public_ip", side_effect=OSError("discovery unavailable")), \
             patch.object(entrypoint, "prepare_layout") as prepare, \
             patch.object(entrypoint.subprocess, "Popen") as process:
            with self.assertRaisesRegex(ValueError, "PUBLIC_IP.*\\.env"):
                entrypoint.main()
            prepare.assert_not_called()
            process.assert_not_called()
        self.assertFalse((work / "controller/.initializing").exists())
        self.assertFalse((work / "db").exists())

    def test_container_restart_resumes_initialization_and_handles_stale_marker(self):
        for scenario in ("legacy", "saved", "ready"):
            with self.subTest(scenario=scenario):
                complete = scenario == "ready"
                work = self.root / scenario
                state = work / "controller"
                (state / "mytoncore").mkdir(parents=True)
                (work / "db").mkdir()
                (work / "db/config.json").write_text('{}')
                (state / "mytoncore/mytoncore.db").write_text(json.dumps({
                    "validatorConsole": {"addr": "127.0.0.1:30304"},
                    "liteClient": {"liteServer": {"port": 30305}},
                }))
                archive = work / "downloaded.tar.lz"
                archive.write_bytes(b"keep downloaded archive")
                pending = state / ".initializing"
                pending.touch()
                identity = {"MTC_USER": "root", "BIN_DIR": "/usr/bin", "SRC_DIR": "/usr/src",
                            "TON_WORK_DIR": str(work)}
                if complete:
                    (state / "initialized.json").write_text(json.dumps(identity))
                runtime = work / "run"
                runtime.mkdir()
                env = {**identity, "PUBLIC_IP": "192.0.2.10", "DUMP": "true"}
                if scenario == "saved":
                    pending.write_text(json.dumps({
                        "version": 1, "identity": identity, "installer_environment": dict(env),
                    }))
                    env.update({"DUMP_CACHE_DIR": "/changed-cache", "ARCHIVE_BLOCKS": "100"})
                env["UNRELATED_RUNTIME_SETTING"] = "keep"
                supervisor = Mock(pid=12345)
                supervisor.poll.return_value = None
                supervisor.wait.return_value = 0
                installer = Mock(pid=12346)
                installer.poll.return_value = 0
                installer.wait.return_value = 0
                foreground = Mock(pid=12347)
                foreground.poll.return_value = 0
                foreground.wait.return_value = 0

                def path(value):
                    target = Path(value)
                    return runtime / target.relative_to("/run") if str(target).startswith("/run/") else target

                def spawn(argv, **kwargs):
                    if "mytoninstaller" in argv and scenario == "saved":
                        self.assertNotIn("DUMP_CACHE_DIR", entrypoint.os.environ)
                        self.assertNotIn("ARCHIVE_BLOCKS", entrypoint.os.environ)
                        self.assertEqual(entrypoint.os.environ["UNRELATED_RUNTIME_SETTING"], "keep")
                    if argv[0] == "/usr/bin/supervisord":
                        (runtime / "supervisor.sock").touch()
                        return supervisor
                    return installer if "mytoninstaller" in argv else foreground

                with patch.object(entrypoint, "Path", path), \
                     patch.object(entrypoint.sys, "argv", ["entrypoint.py", "console", "--cmd", "status"]), \
                     patch.object(entrypoint, "installation_environment", return_value=env), \
                     patch.object(entrypoint, "artifact_sources", return_value=()), \
                     patch.object(entrypoint, "snapshot_artifacts", return_value=self.root / "active"), \
                     patch.object(entrypoint, "check_binaries"), \
                     patch.object(entrypoint.os, "getuid", return_value=0), \
                     patch.object(entrypoint.os, "environ", dict(env)), \
                     patch.object(entrypoint.os, "killpg"), \
                     patch.object(entrypoint.signal, "signal"), \
                     patch.object(entrypoint, "mounted", return_value=False), \
                     patch.object(entrypoint, "check_requirements"), \
                     patch.object(entrypoint, "prepare_layout"), \
                     patch.object(entrypoint, "global_config"), \
                     patch.object(entrypoint, "customize_validator", return_value=False), \
                     patch.object(entrypoint.subprocess, "Popen", side_effect=spawn) as process, \
                     patch.object(entrypoint.subprocess, "run"), \
                     patch("mytoninstaller.dump.cleanup_completed_dump", create=True):
                    entrypoint.main()
                installs = [call for call in process.call_args_list if "mytoninstaller" in call.args[0]]
                self.assertEqual(len(installs), 0 if complete else 1)
                self.assertEqual(json.loads((state / "initialized.json").read_text()), identity)
                self.assertFalse(pending.exists())
                self.assertEqual(archive.read_bytes(), b"keep downloaded archive")

    def test_release_is_pinned_once_and_cannot_escape_volume(self):
        root = self.root / "artifacts"
        release = root / "releases/first"
        sources = self.artifacts(release)
        (root / "current").symlink_to("releases/first")
        with patch.object(entrypoint, "mounted", return_value=True):
            selected = entrypoint.artifact_sources({"TON_ARTIFACTS_DIR": str(root)})
        self.assertEqual(selected, sources)
        (root / "current").unlink()
        (root / "current").symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, "must stay inside"):
            entrypoint.artifact_sources({"TON_ARTIFACTS_DIR": str(root)})

    def test_missing_fift_resources_are_required_alongside_executables(self):
        sources = self.artifacts(self.root / "native")
        (sources[1] / "Asm.fif").unlink()
        with self.assertRaisesRegex(ValueError, "Asm.fif"):
            entrypoint.validate_artifacts(*sources)

    def test_env_maps_all_installer_arguments_without_a_shell(self):
        env = {"MTC_USER": "validator", "TELEMETRY": "false", "DUMP": "yes", "MODE": "single-nominator",
               "ONLY_MTC": "0", "ONLY_NODE": "true", "BACKUP": "none", "BIN_DIR": "/custom/bin",
               "SRC_DIR": "/custom/resources", "TON_WORK_DIR": "/custom/work"}
        self.assertEqual(entrypoint.installer_args(env), [
            "-u", "validator", "-t", "false", "--dump", "true", "-m", "single-nominator",
            "--only-mtc", "false", "--only-node", "true", "--backup", "none",
            "--bin-dir", "/custom/bin", "--src-dir", "/custom/resources", "--ton-work-dir", "/custom/work"])

    def test_default_mytonctrl_args_configure_the_installer(self):
        env = docker_args.installation_environment({"MYTONCTRL_ARGS": "-m validator -n mainnet -d"})
        args = entrypoint.installer_args(env)
        self.assertEqual(args[args.index("--dump") + 1], "true")
        self.assertEqual(args[args.index("-m") + 1], "validator")
        self.assertEqual(env["NETWORK"], "mainnet")
        self.assertEqual(console.console_args(env), [])

    def test_installer_long_and_short_arguments_are_equivalent(self):
        short = "-m liteserver -n testnet -u mtc -t -i -d -l -p /backup.tar.gz -B /bin-mount -S /resources -W /data -s"
        long = "--mode liteserver --network testnet --user mtc --telemetry --ignore-reqs --dump --only-node --backup /backup.tar.gz --bin-dir /bin-mount --src-dir /resources --ton-work-dir /data --no-startup-checks"
        first = docker_args.installation_environment({"MYTONCTRL_ARGS": short})
        second = docker_args.installation_environment({"MYTONCTRL_ARGS": long})
        first.pop("MYTONCTRL_ARGS")
        second.pop("MYTONCTRL_ARGS")
        self.assertEqual(first, second)
        self.assertEqual(first["TELEMETRY"], "false")
        self.assertEqual(first["IGNORE_MINIMAL_REQS"], "true")
        self.assertEqual(first["MTC_USER"], "mtc")
        self.assertEqual(first["TON_WORK_DIR"], "/data")
        self.assertEqual(console.console_args(first), ["--no-startup-checks"])

    def test_argument_config_selects_url_or_mounted_file(self):
        for config, name in (("https://example.org/global.json", "GLOBAL_CONFIG_URL"),
                             ("/mounted/custom network.json", "GLOBAL_CONFIG_FILE")):
            env = docker_args.installation_environment({"GLOBAL_CONFIG_FILE": "old-file",
                                                       "MYTONCTRL_ARGS": f"-c '{config}'"})
            self.assertEqual(env[name], config)
            if name == "GLOBAL_CONFIG_URL":
                self.assertNotIn("GLOBAL_CONFIG_FILE", env)

    def test_mounted_env_parameters_are_data_and_flags_take_precedence(self):
        path = self.root / "parameters.env"
        path.write_text("# Native parameters\nARCHIVE_TTL=123\nMODE=collator\n"
                        "PUBLIC_IP='127.0.0.1'\nPUBLIC_TEXT=$(touch should-not-exist)\n")
        env = docker_args.installation_environment({"MYTONCTRL_ARGS": f"-e '{path}' -m liteserver"})
        self.assertEqual(env["MODE"], "liteserver")
        self.assertEqual(env["ARCHIVE_TTL"], "123")
        self.assertEqual(env["PUBLIC_IP"], "127.0.0.1")
        self.assertEqual(env["PUBLIC_TEXT"], "$(touch should-not-exist)")
        self.assertFalse((self.root / "should-not-exist").exists())

    def test_literal_arguments_never_execute_shell_substitutions(self):
        marker = self.root / "unexpected"
        env = docker_args.installation_environment({"MYTONCTRL_ARGS": f"-o -p '$(touch {marker})'"})
        self.assertEqual(env["BACKUP"], f"$(touch {marker})")
        self.assertFalse(marker.exists())

    def test_source_selection_has_explicit_image_based_errors(self):
        for option in ("-a", "-r", "-b", "-g", "-v"):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, "select MYTONCTRL_IMAGE/TON_IMAGE"):
                docker_args.installation_environment({"MYTONCTRL_ARGS": f"{option} custom-source"})

    def test_direct_entrypoint_arguments_override_env_defaults(self):
        env = docker_args.installation_environment({"MYTONCTRL_ARGS": "-m validator -n mainnet"},
                                                  ["-m", "liteserver", "-n", "testnet"])
        self.assertEqual(env["MODE"], "liteserver")
        self.assertEqual(env["NETWORK"], "testnet")

    def test_archive_preserves_original_full_archive_settings(self):
        env = {"ARCHIVE": "true", "MODE": "liteserver", "STATE_TTL": "123"}
        entrypoint.installer_args(env)
        self.assertEqual(env["ARCHIVE_BLOCKS"], "1")
        self.assertEqual(env["ARCHIVE_TTL"], "-1")
        self.assertNotIn("STATE_TTL", env)

    def test_restore_mount_is_needed_only_during_initial_install(self):
        env = {"ONLY_MTC": "true", "BACKUP": str(self.root / "removed-backup.tar.gz")}
        entrypoint.installer_args(env, validate_backup=False)
        with self.assertRaisesRegex(ValueError, "Backup file is missing"):
            entrypoint.installer_args(env)

    def test_invalid_or_conflicting_flags_fail(self):
        for env in ({"MODE": "bogus"}, {"ONLY_NODE": "true", "ONLY_MTC": "true", "BACKUP": "x"},
                    {"ARCHIVE": "true"}, {"TELEMETRY": "perhaps"}, {"BIN_DIR": "relative"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                entrypoint.installer_args(env)

    def test_custom_args_are_data_and_cannot_replace_owned_paths(self):
        self.assertEqual(entrypoint.custom_validator_args({"CUSTOM_PARAMETERS": "--threads 2 --archive-ttl -1"}),
                         ["--threads", "2", "--archive-ttl", "-1"])
        for value in ("--db=/tmp/db", "--daemonize", "--global-config /tmp/config"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                entrypoint.custom_validator_args({"CUSTOM_PARAMETERS": value})

    def test_all_console_flags_and_quoting_pass_through(self):
        self.assertEqual(console.console_args({"MYTONCTRL_CONFIG": "/config/core.db", "MYTONCTRL_WALLETS": "/wallets",
                         "MYTONCTRL_CMD": "get sendTelemetry",
                         "MYTONCTRL_ARGS": "-m validator -n mainnet -d -s"}),
                         ["--config", "/config/core.db", "--wallets", "/wallets", "--cmd", "get sendTelemetry",
                          "--no-startup-checks"])

    def test_customized_unit_requires_restart_to_apply_parameters(self):
        state = self.root / "controller"
        services = state / "services"
        services.mkdir(parents=True)
        unit = services / "validator.service"
        unit.write_text("[Service]\nExecStart = /bin/validator-engine --threads 1\n")
        self.assertTrue(entrypoint.customize_validator({"CUSTOM_PARAMETERS": "--threads 2"}, state))
        self.assertIn("--threads 1 --threads 2", unit.read_text())
        self.assertFalse(entrypoint.customize_validator({}, state))

    def test_backup_metadata_is_checked_before_restoration(self):
        path = self.root / "backup.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, contents in (("./mytoncore/mytoncore.db", {"fift": {}, "liteClient": {}, "validatorConsole": {}}),
                                   ("./db/config.json", {"addrs": [], "control": []}), ("./keys/client", "key")):
                payload = json.dumps(contents).encode()
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        entrypoint.check_backup(path)
        invalid = self.root / "invalid.tar.gz"
        with tarfile.open(invalid, "w:gz"):
            pass
        with self.assertRaisesRegex(ValueError, "missing mytoncore"):
            entrypoint.check_backup(invalid)


if __name__ == "__main__":
    unittest.main()
