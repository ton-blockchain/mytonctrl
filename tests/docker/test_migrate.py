"""Check migration safeguards with disposable legacy data and fake Docker calls."""

import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MIGRATE_SCRIPT = ROOT / "docker/migrate.sh"


def load_wizard():
    """Load the standalone script's embedded Python without invoking its CLI."""
    source = MIGRATE_SCRIPT.read_text()
    match = re.search(r"<<'PY'\n(.*?)\nPY(?:\n|$)", source, re.DOTALL)
    if match is None:
        raise AssertionError("migrate.sh must contain its standalone Python wizard")
    module = types.ModuleType("migration_wizard_test")
    sys.modules[module.__name__] = module
    exec(compile(match.group(1), str(MIGRATE_SCRIPT), "exec"), module.__dict__)
    return module


def file_digests(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file() and not path.is_symlink()
    }


NODE_CONFIG = {
    "addrs": [
        {"@type": "engine.addr", "ip": 1547602011, "port": 40303},
        {"@type": "engine.quicAddr", "ip": 1547602011, "port": 41303},
    ],
    "control": [{"port": 40304, "id": "console-key", "allowed": ["client-key"]}],
    "liteservers": [{"port": 40305, "id": "lite-key"}],
    "fullnode": "original-fullnode-key",
}

CORE_CONFIG = {
    "fift": {"appPath": "/usr/bin/ton/crypto/fift"},
    "liteClient": {
        "appPath": "/usr/bin/ton/lite-client/lite-client",
        "configPath": "/usr/bin/ton/global.config.json",
        "liteServer": {"ip": "192.0.2.1", "port": 30003,
                       "pubkeyPath": "/var/ton-work/keys/liteserver.pub"},
    },
    "validatorConsole": {
        "appPath": "/usr/bin/ton/validator-engine-console/validator-engine-console",
        "addr": "192.0.2.1:30002",
        "privKeyPath": "/var/ton-work/keys/client",
        "pubKeyPath": "/var/ton-work/keys/server.pub",
    },
    "validatorWalletName": "existing-wallet",
    "adnlAddr": "original-validator-adnl",
    "modes": {"validator": True, "nominator-pool": True, "liteserver": False},
    "customPools": ["original-pool"],
}

STAKING_MODES = ("single-nominator", "nominator-pool-v2", "nominator-pool", "liquid-staking")


class MigrationFixture(unittest.TestCase):
    def setUp(self):
        self.wizard = load_wizard()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.donor = self.root / "donor"
        self.donor.mkdir()
        self.node = copy.deepcopy(NODE_CONFIG)
        self.core = copy.deepcopy(CORE_CONFIG)

    def create_legacy_data(self):
        files = {
            "ton-work/db/config.json": json.dumps(self.node),
            "ton-work/db/keyring/node-key": "unchanged-node-private-key",
            "ton-work/db/archive/history": "retained-block-history",
            "ton-work/db/celldb/state": "retained-cell-database",
            "ton-work/db/import/archive.slice": "retained-import-progress",
            "ton-work/keys/client": "unchanged-console-private-key",
            "ton-work/keys/server.pub": "unchanged-console-public-key",
            "ton-work/keys/liteserver.pub": "unchanged-liteserver-public-key",
            "ton-work/dump-cache/saved-dump.tar.lz": "retained-dump-cache",
            "mytoncore/mytoncore.db": json.dumps(self.core),
            "mytoncore/wallets/existing-wallet.pk": "unchanged-wallet-private-key",
            "mytoncore/wallets/existing-wallet.addr": "unchanged-wallet-address",
            "mytoncore/contracts/pool.json": "unchanged-contract-settings",
            "mytonctrl/mytonctrl.db": "retained-console-settings",
            "ton-runtime/global.config.json": json.dumps({"@type": "config.global", "validator": {}}),
            "ton-runtime/local.config.json": json.dumps({"@type": "config.local", "liteservers": []}),
        }
        for name, contents in files.items():
            destination = self.donor / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(contents)
        (self.donor / "mytoncore/mytoncore.log").symlink_to("/proc/999999/fd/1")
        return file_digests(self.donor)

    def stage_identity(self):
        before = self.create_legacy_data()
        migration = self.root / "migration"
        migration.mkdir()
        shutil.copytree(self.donor / "ton-work", migration / "ton-work", symlinks=True)
        shutil.copytree(self.donor, migration / "legacy", symlinks=True)
        identity = migration / "identity"
        identity.mkdir()
        shutil.copytree(self.donor / "mytoncore", identity / "mytoncore", symlinks=True)
        shutil.copytree(self.donor / "ton-work/keys", identity / "keys", symlinks=True)
        (identity / "db").mkdir()
        shutil.copyfile(self.donor / "ton-work/db/config.json", identity / "db/config.json")
        shutil.copytree(self.donor / "ton-work/db/keyring", identity / "db/keyring", symlinks=True)
        return migration, before

    def test_environment_values_stay_literal_and_cannot_execute_shell_code(self):
        marker = self.root / "must-not-exist"
        values = self.wizard.parse_env(
            "# Legacy settings\n"
            "NETWORK=testnet\n"
            "MYTONCTRL_ARGS='-m validator -n testnet'\n"
            f"UNTRUSTED=$(touch {marker})\n"
            f"BACKTICKS=`touch {marker}`\n"
        )
        self.assertEqual(values["NETWORK"], "testnet")
        self.assertEqual(values["MYTONCTRL_ARGS"], "-m validator -n testnet")
        self.assertIn("$(touch", values["UNTRUSTED"])
        self.assertIn("`touch", values["BACKTICKS"])
        self.assertFalse(marker.exists())

    def test_destination_refuses_ancestor_descendant_equal_and_symlink_overlap(self):
        source = self.donor / "ton-work"
        source.mkdir()
        alias = self.root / "source-alias"
        alias.symlink_to(source, target_is_directory=True)
        for destination in (source, source / "new-deployment", source.parent, alias / "new"):
            with self.subTest(destination=destination):
                with self.assertRaises(self.wizard.MigrationError):
                    self.wizard.ensure_destination_isolated(destination, [str(source)])
        isolated = self.root / "independent-storage" / "migration"
        isolated.parent.mkdir()
        self.assertEqual(self.wizard.ensure_destination_isolated(isolated, [str(source)]), isolated.resolve())
        self.assertFalse(isolated.exists(), "The guard must not create destination directories")

    def test_container_selection_suggests_the_first_legacy_node_or_running_container(self):
        cases = (
            ([{"Names": "legacy-node", "Image": "ghcr.io/ton-blockchain/ton-docker-ctrl:mainnet"}],
             "\n", "legacy-node"),
            ([{"Names": "gton", "Image": "gton:latest"},
              {"Names": "first-legacy", "Image": "ton-docker-ctrl:testnet"},
              {"Names": "second-legacy", "Image": "ton-docker-ctrl:mainnet"}],
             "\n", "first-legacy"),
            ([{"Names": "first-running", "Image": "custom-ton:latest"},
              {"Names": "second-running", "Image": "another-node:latest"}],
             "\n", "first-running"),
            ([{"Names": "suggested-node", "Image": "ton-docker-ctrl:mainnet"}],
             "manually-selected-node\n", "manually-selected-node"),
        )
        for records, answer, expected in cases:
            with self.subTest(containers=records, answer=repr(answer)):
                wizard = self.wizard.Wizard(tty=io.StringIO(answer))
                table = "NAMES  IMAGE  STATUS\nCurrent running container table\n"

                def ps(args):
                    self.assertEqual(args[:2], ["docker", "ps"])
                    return "\n".join(json.dumps(record) for record in records) if args[-1] == "{{json .}}" else table

                output = io.StringIO()
                with mock.patch.object(self.wizard, "run", side_effect=ps), redirect_stdout(output):
                    selected = wizard.select_container()
                self.assertEqual(selected, expected)
                self.assertIn(table, output.getvalue())
                suggested = next((item["Names"] for item in records if "ton-docker-ctrl" in item["Image"]), records[0]["Names"])
                self.assertIn("[" + suggested + "]", output.getvalue())

    def test_no_running_containers_fail_before_asking_for_a_donor(self):
        wizard = self.wizard.Wizard(tty=io.StringIO("unused-answer\n"))

        def ps(args):
            return "" if args[-1] == "{{json .}}" else "NAMES  IMAGE  STATUS\n"

        with mock.patch.object(self.wizard, "run", side_effect=ps), mock.patch.object(wizard, "ask") as ask, \
                redirect_stdout(io.StringIO()), self.assertRaises(self.wizard.MigrationError):
            wizard.select_container()
        ask.assert_not_called()

    def test_missing_destination_parents_can_be_validated_without_creating_them(self):
        destination = self.root / "new-storage" / "customer" / "migration"
        self.assertEqual(self.wizard.ensure_destination_isolated(destination, [self.donor], require_parent=False),
                         destination.resolve())
        self.assertFalse((self.root / "new-storage").exists())
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.ensure_destination_isolated(destination, [self.donor])

    def test_directory_creation_requires_explicit_yes_and_creates_missing_parents(self):
        destination = self.root / "new-storage" / "customer" / "migration"
        wizard = self.wizard.Wizard(tty=io.StringIO(str(destination) + "\nyes\n"))
        output = io.StringIO()
        original_confirm = wizard.confirm

        def confirm_before_creating(message):
            self.assertFalse((self.root / "new-storage").exists(), "No directory may be created before consent")
            original_confirm(message)

        old_mask = os.umask(0o022)
        try:
            with mock.patch.object(wizard, "confirm", side_effect=confirm_before_creating), redirect_stdout(output):
                selected = wizard.select_destination([self.donor])
        finally:
            os.umask(old_mask)
        self.assertEqual(selected, destination.resolve())
        self.assertTrue(destination.is_dir())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
        self.assertIn("Specified directory does not exist: " + str(destination), output.getvalue())
        self.assertIn("including missing parents", output.getvalue())
        self.assertEqual(list(destination.iterdir()), [])

    def test_declined_default_or_eof_directory_confirmation_creates_nothing(self):
        for index, answer in enumerate(("no\n", "\n", "")):
            with self.subTest(answer=repr(answer)):
                parent = self.root / f"unapproved-storage-{index}"
                destination = parent / "customer" / "migration"
                wizard = self.wizard.Wizard(tty=io.StringIO(str(destination) + "\n" + answer))
                with redirect_stdout(io.StringIO()), self.assertRaises(self.wizard.MigrationError):
                    wizard.select_destination([self.donor])
                self.assertFalse(parent.exists())

    def test_invalid_destination_is_rejected_before_any_creation_confirmation(self):
        occupied = self.root / "occupied"
        occupied.mkdir()
        (occupied / "database").write_bytes(b"existing customer data")
        parent_file = self.root / "not-a-directory"
        parent_file.write_bytes(b"existing customer file")
        cases = (self.donor, self.donor / "new-parent" / "migration", self.root,
                 occupied, parent_file / "migration", self.root / "path with spaces", Path("relative/path"))
        before = file_digests(self.root)
        for destination in cases:
            with self.subTest(destination=destination):
                wizard = self.wizard.Wizard(tty=io.StringIO(str(destination) + "\nyes\n"))
                with mock.patch.object(wizard, "confirm", side_effect=self.wizard.MigrationError("Unexpected creation")) as confirm, \
                        redirect_stdout(io.StringIO()), \
                        self.assertRaises(self.wizard.MigrationError):
                    wizard.select_destination([self.donor])
                confirm.assert_not_called()
                self.assertEqual(file_digests(self.root), before)
                self.assertFalse((self.donor / "new-parent").exists())
                self.assertFalse((self.root / "path with spaces").exists())

    def test_existing_valid_destination_needs_no_creation_prompt_or_permission_change(self):
        for index, has_env in enumerate((False, True)):
            with self.subTest(has_env=has_env):
                destination = self.root / f"existing-{index}"
                destination.mkdir(mode=0o750)
                if has_env:
                    (destination / "deployment").mkdir(mode=0o750)
                    (destination / "deployment/.env").write_text("EXISTING=preserved\n")
                before = file_digests(destination)
                wizard = self.wizard.Wizard(tty=io.StringIO(str(destination) + "\n"))
                with mock.patch.object(wizard, "confirm") as confirm, redirect_stdout(io.StringIO()):
                    self.assertEqual(wizard.select_destination([self.donor]), destination.resolve())
                confirm.assert_not_called()
                self.assertEqual(file_digests(destination), before)
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o750)

    def test_broken_parent_symlink_is_rejected_before_confirmation_without_creating_its_target(self):
        missing_target = self.root / "missing-storage-target"
        parent_link = self.root / "broken-storage-link"
        parent_link.symlink_to(missing_target, target_is_directory=True)
        destination = parent_link / "customer" / "migration"
        wizard = self.wizard.Wizard(tty=io.StringIO(str(destination) + "\nyes\n"))
        with mock.patch.object(wizard, "confirm", side_effect=self.wizard.MigrationError("Unexpected creation")) as confirm, \
                redirect_stdout(io.StringIO()), self.assertRaises(self.wizard.MigrationError):
            wizard.select_destination([self.donor])
        confirm.assert_not_called()
        self.assertFalse(missing_target.exists())
        self.assertTrue(parent_link.is_symlink())
        self.assertEqual(os.readlink(parent_link), str(missing_target))

    def test_blank_destination_input_uses_the_documented_default(self):
        existing = self.root / "default-location"
        existing.mkdir()
        wizard = self.wizard.Wizard(tty=io.StringIO("\n"))
        output = io.StringIO()
        with mock.patch.object(self.wizard.Path, "cwd", return_value=self.root), \
                mock.patch.object(self.wizard, "ensure_destination_isolated", return_value=existing) as guard, \
                mock.patch.object(wizard, "confirm") as confirm, redirect_stdout(output):
            self.assertEqual(wizard.select_destination([self.donor]), existing)
        self.assertEqual(Path(guard.call_args_list[0].args[0]), self.root / "migration")
        self.assertIn("[" + str(self.root / "migration") + "]", output.getvalue())
        confirm.assert_not_called()

    def test_work_storage_defaults_to_independent_host_directory_without_creating_it_before_consent(self):
        for answer in ("\n\n", "1\n\n"):
            with self.subTest(answer=repr(answer)):
                wizard = self.wizard.Wizard(tty=io.StringIO(answer))
                wizard.root = self.root / "migration"
                wizard.root.mkdir(exist_ok=True)
                wizard.docker_root = self.root
                output = io.StringIO()
                with redirect_stdout(output), mock.patch.object(self.wizard, "run") as run:
                    wizard.select_work_storage([self.donor])
                run.assert_not_called()
                self.assertEqual(wizard.work_path, wizard.root / "ton-work")
                self.assertEqual(wizard.work_volume, "")
                self.assertEqual(wizard.settings["TON_WORK_HOST_DIR"], str(wizard.root / "ton-work"))
                self.assertFalse(wizard.work_path.exists())
                self.assertIn("[directory]", output.getvalue())
                self.assertIn("[" + str(wizard.root / "ton-work") + "]", output.getvalue())

    def test_storage_type_can_be_selected_before_any_destination_is_available(self):
        for answer, expected in (("\n", "directory"), ("directory\n", "directory"),
                                 ("1\n", "directory"), ("volume\n", "volume"),
                                 ("2\n", "volume"), ("invalid\nvolume\n", "volume")):
            with self.subTest(answer=repr(answer)):
                wizard = self.wizard.Wizard(tty=io.StringIO(answer))
                with redirect_stdout(io.StringIO()), mock.patch.object(self.wizard, "run") as run:
                    self.assertEqual(wizard.select_work_storage_type(), expected)
                run.assert_not_called()
                self.assertIsNone(wizard.root)
                self.assertIsNone(wizard.work_dir)
                self.assertEqual(wizard.work_volume, "")

    def test_volume_metadata_directory_is_automatic_and_not_created_or_confirmed_during_selection(self):
        wizard = self.wizard.Wizard(tty=io.StringIO())
        output = io.StringIO()
        destination = self.root / "migration"
        with mock.patch.object(self.wizard.Path, "cwd", return_value=self.root), \
                mock.patch.object(wizard, "ask") as ask, mock.patch.object(wizard, "confirm") as confirm, \
                redirect_stdout(output):
            selected = wizard.select_destination([self.donor], storage_type="volume")
        self.assertEqual(selected, destination)
        self.assertFalse(destination.exists())
        ask.assert_not_called()
        confirm.assert_not_called()
        self.assertIn(str(destination), output.getvalue())

    def test_automatic_volume_metadata_directory_refuses_existing_data_without_touching_it(self):
        before = self.create_legacy_data()
        destination = self.root / "migration"
        destination.mkdir()
        retained = destination / "customer-data"
        retained.write_bytes(b"must-retain-prior-deployment")
        previous_mode = stat.S_IMODE(destination.stat().st_mode)
        wizard = self.wizard.Wizard(tty=io.StringIO())
        with mock.patch.object(self.wizard.Path, "cwd", return_value=self.root), \
                mock.patch.object(wizard, "ask") as ask, mock.patch.object(wizard, "confirm") as confirm, \
                redirect_stdout(io.StringIO()), self.assertRaises(self.wizard.MigrationError):
            wizard.select_destination([self.donor], storage_type="volume")
        ask.assert_not_called()
        confirm.assert_not_called()
        self.assertEqual(retained.read_bytes(), b"must-retain-prior-deployment")
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), previous_mode)
        self.assertEqual(file_digests(self.donor), before)

    def test_supplied_storage_type_does_not_repeat_type_question_when_requesting_work_destination(self):
        for storage in ("directory", "volume"):
            with self.subTest(storage=storage):
                wizard = self.wizard.Wizard(tty=io.StringIO("\n"))
                wizard.root = self.root / "migration"
                wizard.docker_root = self.root
                output = io.StringIO()
                with mock.patch.object(self.wizard, "run", return_value=""), redirect_stdout(output):
                    wizard.select_work_storage([self.donor], storage_type=storage)
                self.assertNotIn("Where should TON work data be copied", output.getvalue())
                self.assertEqual(wizard.work_volume, "mytonctrl-ton-work" if storage == "volume" else "")

    def test_named_volume_choice_suggests_standard_name_and_only_lists_volumes_before_consent(self):
        for answer in ("volume\n\n", "2\n\n", "invalid\nvolume\n\n"):
            with self.subTest(answer=repr(answer)):
                wizard = self.wizard.Wizard(tty=io.StringIO(answer))
                wizard.root = self.root / "migration"
                wizard.root.mkdir(exist_ok=True)
                wizard.docker_root = self.root
                output = io.StringIO()
                with redirect_stdout(output), mock.patch.object(self.wizard, "run", return_value="") as run:
                    wizard.select_work_storage([self.donor])
                run.assert_called_once_with(["docker", "volume", "ls", "--format", "{{.Name}}"])
                self.assertEqual(wizard.work_volume, "mytonctrl-ton-work")
                self.assertEqual(wizard.settings["TON_WORK_HOST_DIR"], "")
                self.assertEqual(wizard.settings["TON_WORK_VOLUME"], wizard.work_volume)
                self.assertIn("[mytonctrl-ton-work]", output.getvalue())
                self.assertIsNone(wizard.work_dir)

    def test_invalid_work_volume_name_never_creates_or_lists_any_volume(self):
        for name in ("/absolute/path", "../existing", "bad name", "-option"):
            with self.subTest(name=name):
                wizard = self.wizard.Wizard(tty=io.StringIO("volume\n" + name + "\n"))
                wizard.root = self.root / "migration"
                with redirect_stdout(io.StringIO()), mock.patch.object(self.wizard, "run") as run, \
                        self.assertRaises(self.wizard.MigrationError):
                    wizard.select_work_storage([self.donor])
                run.assert_not_called()
                self.assertEqual(wizard.work_volume, "")

    def test_predicted_new_volume_location_refuses_source_overlap_or_existing_data_before_creation(self):
        for name, occupied in (("source-overlap-work", False), ("occupied-work", True)):
            with self.subTest(occupied=occupied):
                wizard = self.wizard.Wizard(tty=io.StringIO("volume\n" + name + "\n"))
                wizard.root = self.root / "migration"
                wizard.root.mkdir(exist_ok=True)
                wizard.docker_root = self.root / "docker-root"
                parent = wizard.docker_root / "volumes" / name
                parent.mkdir(parents=True)
                mountpoint = parent / "_data"
                sources = [parent]
                if occupied:
                    mountpoint.mkdir()
                    (mountpoint / "retained-file").write_bytes(b"existing-customer-data")
                    sources = [self.donor]
                before = file_digests(wizard.docker_root)
                with redirect_stdout(io.StringIO()), mock.patch.object(self.wizard, "run", return_value="") as run, \
                        self.assertRaises(self.wizard.MigrationError):
                    wizard.select_work_storage(sources)
                run.assert_called_once_with(["docker", "volume", "ls", "--format", "{{.Name}}"])
                self.assertEqual(file_digests(wizard.docker_root), before)
                self.assertFalse(any(call.args[0][:3] == ["docker", "volume", "create"] for call in run.call_args_list))

    def test_work_volume_cannot_reuse_artifact_or_script_volume_names(self):
        before = self.create_legacy_data()
        for suffix in ("-artifacts", "-scripts"):
            with self.subTest(volume=suffix):
                wizard = self.wizard.Wizard()
                wizard.root = self.root / "migration"
                wizard.docker_root = self.root / "docker-root"
                name = wizard.storage_id + suffix
                wizard.tty = io.StringIO("volume\n" + name + "\n")
                with redirect_stdout(io.StringIO()), mock.patch.object(self.wizard, "run") as run, \
                        self.assertRaisesRegex(self.wizard.MigrationError, "volume names must be different"):
                    wizard.select_work_storage([self.donor])
                run.assert_not_called()
                self.assertFalse(wizard.donor_stopped)
                self.assertEqual(wizard.work_volume, "")
                self.assertFalse(wizard.docker_root.exists())
                self.assertEqual(file_digests(self.donor), before)

    def test_host_directory_selection_refuses_docker_managed_volume_storage(self):
        before = self.create_legacy_data()
        for index, nested in enumerate((False, True)):
            with self.subTest(nested=nested):
                wizard = self.wizard.Wizard()
                wizard.root = self.root / "migration"
                wizard.docker_root = self.root / ("docker-root-" + str(index))
                volumes = wizard.docker_root / "volumes"
                selected = volumes / "future-artifacts/_data" if nested else volumes
                selected.mkdir(parents=True)
                wizard.tty = io.StringIO("directory\n" + str(selected) + "\n")
                previous_mode = stat.S_IMODE(selected.stat().st_mode)
                with redirect_stdout(io.StringIO()), mock.patch.object(self.wizard, "run") as run, \
                        self.assertRaisesRegex(self.wizard.MigrationError, "outside Docker volume storage"):
                    wizard.select_work_storage([self.donor])
                run.assert_not_called()
                self.assertFalse(wizard.donor_stopped)
                self.assertEqual(list(selected.iterdir()), [])
                self.assertEqual(stat.S_IMODE(selected.stat().st_mode), previous_mode)
                self.assertEqual(file_digests(self.donor), before)

    def test_testnet_validator_ports_and_finite_retention_are_retained(self):
        self.core["modes"] = {"validator": True, "liteserver": False}
        service = (
            "[Service]\nExecStart=/usr/bin/ton/validator-engine/validator-engine "
            "--threads 127 --global-config /usr/bin/ton/global.config.json "
            "--db /var/ton-work/db --archive-ttl 86400 --state-ttl 3600 -M\n"
        )
        settings = self.wizard.infer_settings(self.core, self.node, service, {"TON_BRANCH": "testnet"})
        expected = {
            "MODE": "validator", "NETWORK": "testnet", "PUBLIC_IP": "92.62.136.91",
            "VALIDATOR_PORT": "40303", "VALIDATOR_CONSOLE_PORT": "40304",
            "LITESERVER_PORT": "40305", "QUIC_PORT": "41303",
            "ARCHIVE_TTL": "90000", "STATE_TTL": "3600", "ADD_SHARD": "",
        }
        for name, value in expected.items():
            with self.subTest(setting=name):
                self.assertEqual(str(settings[name]), value)

    def test_archive_liteserver_preserves_permanent_storage_without_downloader(self):
        self.core["modes"] = {"validator": False, "liteserver": True}
        service = (
            "[Service]\nExecStart=/usr/bin/ton/validator-engine/validator-engine "
            "--permanent-celldb --archive-ttl 1000000000 --state-ttl 1000000000\n"
        )
        settings = self.wizard.infer_settings(self.core, self.node, service, {"NETWORK": "mainnet"})
        self.assertEqual(settings["MODE"], "liteserver")
        self.assertEqual(settings["NETWORK"], "mainnet")
        self.assertEqual(str(settings["ARCHIVE_TTL"]), "-1")
        self.assertFalse(settings.get("STATE_TTL"))
        self.assertNotIn("ARCHIVE_BLOCKS", settings)
        self.assertNotIn("ARCHIVE", settings)
        self.assertNotIn("DUMP", settings)
        self.assertNotIn("ADD_SHARD", settings)

    def test_liteserver_missing_validator_mode_is_staged_disabled_before_startup(self):
        self.core["modes"] = {"liteserver": True}
        migration, before = self.stage_identity()
        self.wizard.normalize_identity(migration)
        staged = json.loads((migration / "identity/mytoncore/mytoncore.db").read_text())
        self.assertEqual(staged["modes"], {"liteserver": True, "validator": False})
        original = json.loads((self.donor / "mytoncore/mytoncore.db").read_text())
        self.assertEqual(original["modes"], {"liteserver": True})
        self.assertEqual(file_digests(self.donor), before)

    def test_unknown_legacy_mode_schema_requires_review(self):
        self.core["modes"] = ["liteserver"]
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.infer_settings(self.core, self.node,
                                       ["/usr/bin/ton/validator-engine/validator-engine"], {})

    def test_saved_role_flags_take_precedence_over_missing_or_stale_environment_modes(self):
        for role in ("liteserver", "collator", *STAKING_MODES):
            core = copy.deepcopy(self.core)
            core["modes"] = {"validator": role in STAKING_MODES, "liteserver": False, "collator": False, role: True}
            before = copy.deepcopy(core)
            for declared in (None, "validator", "unsupported-mode", role):
                with self.subTest(role=role, declared=declared):
                    env = {} if declared is None else {"MODE": declared}
                    settings = self.wizard.infer_settings(core, self.node,
                                                          ["/usr/bin/ton/validator-engine/validator-engine"], env)
                    self.assertEqual(settings["MODE"], role)
                    self.assertEqual(core, before, "Inferring a mode must not change saved controller settings")

    def test_declared_active_staking_role_is_preserved_and_generic_validator_has_predictable_priority(self):
        core = copy.deepcopy(self.core)
        core["modes"] = {"validator": True, "liteserver": False, "collator": False,
                         **{role: True for role in STAKING_MODES}}
        command = ["/usr/bin/ton/validator-engine/validator-engine"]
        for role in STAKING_MODES:
            with self.subTest(declared=role):
                self.assertEqual(self.wizard.infer_settings(core, self.node, command, {"MODE": role})["MODE"], role)
        self.assertEqual(self.wizard.infer_settings(core, self.node, command, {"MODE": "validator"})["MODE"],
                         "single-nominator")

    def test_paused_staking_role_is_recognized_without_reenabling_validator(self):
        for role in STAKING_MODES:
            with self.subTest(role=role):
                core = copy.deepcopy(self.core)
                core["modes"] = {"validator": False, "liteserver": False, role: True}
                before = copy.deepcopy(core)
                settings = self.wizard.infer_settings(core, self.node,
                                                      ["/usr/bin/ton/validator-engine/validator-engine"], {"MODE": "validator"})
                self.assertEqual(settings["MODE"], role)
                self.assertEqual(core, before)

    def test_staking_role_with_missing_validator_flag_is_rejected_without_mutating_saved_settings(self):
        for role in STAKING_MODES:
            with self.subTest(role=role):
                core = copy.deepcopy(self.core)
                core["modes"] = {role: True}
                before = copy.deepcopy(core)
                with self.assertRaises(self.wizard.MigrationError):
                    self.wizard.infer_settings(core, self.node, ["/usr/bin/ton/validator-engine/validator-engine"], {})
                self.assertEqual(core, before)

    def test_collator_or_liteserver_with_enabled_validator_requires_review(self):
        for conflicting in ("collator", "liteserver"):
            with self.subTest(conflicting=conflicting):
                core = copy.deepcopy(self.core)
                core["modes"] = {"validator": True, conflicting: True}
                before = copy.deepcopy(core)
                with self.assertRaises(self.wizard.MigrationError):
                    self.wizard.infer_settings(core, self.node, ["/usr/bin/ton/validator-engine/validator-engine"],
                                               {"MODE": conflicting})
                self.assertEqual(core, before)

    def test_actual_native_mode_functions_skip_new_events_for_migration_backup_arguments(self):
        # Exercise the actual installer functions without requiring the native
        # TON/Python dependency stack merely to test this event-dispatch guard.
        path = ROOT / "mytoninstaller/settings.py"
        source = ast.parse(path.read_text(), filename=str(path))
        definitions = [node for node in source.body if isinstance(node, ast.FunctionDef)
                       and node.name in ("EnableMode", "SetupCollator")]
        self.assertEqual({node.name for node in definitions}, {"EnableMode", "SetupCollator"})
        isolated = ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            *definitions,
        ], type_ignores=[])
        runner = mock.Mock()
        module = {"sys": sys, "_run_as_installer_user": runner, "is_container": mock.Mock()}
        exec(compile(ast.fix_missing_locations(isolated), str(path), "exec"), module)
        local = types.SimpleNamespace(add_log=mock.Mock())
        for container in (False, True):
            with self.subTest(container=container):
                module["is_container"].return_value = container
                ctx = types.SimpleNamespace(user="root", mode="none", backup="/migration/backup.tar.gz")
                module["EnableMode"](local, ctx)
                module["SetupCollator"](local, ctx)
                runner.assert_not_called()
        # Native collator setup retains its original dispatch behavior. The
        # wizard skips it by choosing mode=none when restoring an existing node.
        module["is_container"].return_value = False
        ctx = types.SimpleNamespace(user="native-user", mode="collator", backup="existing-backup.tar.gz")
        module["EnableMode"](local, ctx)
        runner.assert_not_called()
        module["SetupCollator"](local, ctx)
        runner.assert_called_once_with("native-user", [sys.executable, "-m", "mytoncore", "-e", "setup_collator"])

    def test_multiple_endpoints_require_review_instead_of_silently_rekeying(self):
        self.node["control"].append({"port": 40314, "id": "second-console-key"})
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.infer_settings(self.core, self.node, "[Service]\nExecStart=/bin/validator\n", {})

    def test_normalized_backup_keeps_wallets_keys_settings_and_complete_work_copy(self):
        migration, before = self.stage_identity()
        (migration / "identity/mytoncore/wallets/existing-wallet.pk").chmod(0o600)
        (migration / "identity/mytoncore/venv").mkdir()
        (migration / "identity/mytoncore/venv/stale-interpreter").write_text("old image executable")
        self.wizard.normalize_identity(migration)
        self.assertEqual(file_digests(self.donor), before)
        self.assertEqual(file_digests(migration / "ton-work/db"),
                         file_digests(self.donor / "ton-work/db"))
        core = json.loads((migration / "identity/mytoncore/mytoncore.db").read_text())
        self.assertEqual(core["validatorConsole"]["addr"], "127.0.0.1:40304")
        self.assertEqual(core["liteClient"]["liteServer"]["ip"], "127.0.0.1")
        self.assertEqual(core["liteClient"]["liteServer"]["port"], 40305)
        for name in ("modes", "validatorWalletName", "adnlAddr", "customPools"):
            self.assertEqual(core[name], self.core[name])
        node = json.loads((migration / "identity/db/config.json").read_text())
        self.assertEqual(node, self.node)
        archive_path = self.wizard.create_backup(migration)
        self.assertEqual(stat.S_IMODE(archive_path.stat().st_mode), 0o600)
        docker_dir = ROOT / "docker"
        with mock.patch.object(sys, "path", [str(docker_dir), *sys.path]):
            spec = importlib.util.spec_from_file_location("migration_actual_entrypoint", docker_dir / "entrypoint.py")
            entrypoint = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(entrypoint)
            entrypoint.check_backup(archive_path)
        with tarfile.open(archive_path, "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers()}
            self.assertNotIn("mytoncore/mytoncore.log", members)
            self.assertFalse(any(name.startswith("mytoncore/venv") for name in members))
            self.assertFalse(any(member.issym() or member.islnk() for member in members.values()))
            self.assertEqual(archive.extractfile("mytoncore/wallets/existing-wallet.pk").read(),
                             b"unchanged-wallet-private-key")
            self.assertEqual(members["mytoncore/wallets/existing-wallet.pk"].mode, 0o600)
            self.assertEqual(archive.extractfile("db/keyring/node-key").read(),
                             b"unchanged-node-private-key")
            self.assertEqual(archive.extractfile("keys/client").read(), b"unchanged-console-private-key")
        self.assertEqual(file_digests(self.donor), before)
        for name in ("archive/history", "celldb/state", "import/archive.slice"):
            self.assertEqual((migration / "ton-work/db" / name).read_bytes(),
                             (self.donor / "ton-work/db" / name).read_bytes())

    def test_backup_rejects_custom_escaping_symlink_and_preserves_source(self):
        migration, before = self.stage_identity()
        (migration / "identity/mytoncore/wallets/external.pk").symlink_to("/etc/shadow")
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.create_backup(migration)
        self.assertEqual(file_digests(self.donor), before)

    def test_help_and_noninteractive_execution_cannot_touch_docker(self):
        tools = self.root / "bin"
        tools.mkdir()
        docker_log = self.root / "docker-called"
        docker = tools / "docker"
        docker.write_text(
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            f"Path({str(docker_log)!r}).write_text('unexpected Docker call')\n"
            "raise SystemExit(99)\n"
        )
        docker.chmod(0o755)
        environment = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
        help_result = subprocess.run(
            ["bash", str(MIGRATE_SCRIPT), "--help"], input="", capture_output=True,
            text=True, timeout=10, cwd=self.root, env=environment,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--branch", help_result.stdout)
        run_result = subprocess.run(
            ["bash", str(MIGRATE_SCRIPT)], input="", capture_output=True,
            text=True, timeout=10, cwd=self.root, env=environment,
        )
        self.assertNotEqual(run_result.returncode, 0)
        self.assertFalse(docker_log.exists())

    def test_failure_or_interrupt_stops_destination_and_leaves_donor_stopped(self):
        for failure in (self.wizard.MigrationError("injected verification failure"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                tty = io.StringIO()
                wizard = self.wizard.Wizard(tty=tty)
                wizard.root = self.root
                wizard.old_id = "original-donor"
                wizard.donor_stopped = True
                wizard.destination_attempted = True
                wizard.compose_run = mock.Mock()
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(self.wizard, "Wizard", return_value=wizard), \
                        mock.patch.object(wizard, "execute", side_effect=failure), \
                        mock.patch.object(self.wizard, "run") as run, \
                        mock.patch.object(self.wizard.signal, "signal"), \
                        mock.patch("builtins.open", return_value=tty), \
                        mock.patch.object(sys, "argv", ["migrate.sh"]), \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    self.assertEqual(self.wizard.main(), 1)
                wizard.compose_run.assert_called_once_with(["stop", "--timeout", "120"], capture=True)
                self.assertFalse(wizard.destination_attempted)
                self.assertTrue(wizard.donor_stopped)
                run.assert_called_once_with(["docker", "stop", "--timeout", "120", "original-donor"], capture=False)
                self.assertIn("original container", stdout.getvalue())
                self.assertIn("remain stopped", stdout.getvalue())

    def test_failed_destination_stop_never_claims_rollback_is_safe(self):
        tty = io.StringIO()
        wizard = self.wizard.Wizard(tty=tty)
        wizard.root = self.root
        wizard.old_id = "original-donor"
        wizard.donor_stopped = True
        wizard.destination_attempted = True
        wizard.compose_run = mock.Mock(side_effect=self.wizard.MigrationError("injected stop failure"))
        stderr = io.StringIO()
        with mock.patch.object(self.wizard, "Wizard", return_value=wizard), \
                mock.patch.object(wizard, "execute", side_effect=self.wizard.MigrationError("failed migration")), \
                mock.patch.object(self.wizard, "run") as run, \
                mock.patch.object(self.wizard.signal, "signal"), \
                mock.patch("builtins.open", return_value=tty), \
                mock.patch.object(sys, "argv", ["migrate.sh"]), \
                redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            self.assertEqual(self.wizard.main(), 1)
        self.assertTrue(wizard.destination_attempted)
        self.assertTrue(wizard.donor_stopped)
        run.assert_not_called()
        self.assertIn("Keep the original node stopped", stderr.getvalue())

    def test_key_verification_refuses_symlinks_and_changed_private_keys(self):
        migration, before = self.stage_identity()
        hashes = self.wizard.normalize_identity(migration)
        work = migration / "ton-work"
        self.wizard.copy_controller(migration / "identity/mytoncore", work / "controller/mytoncore")
        self.wizard.verify_keys(work, hashes)
        private_key = work / "keys/client"
        private_key.write_text("different private key")
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.verify_keys(work, hashes)
        private_key.unlink()
        private_key.symlink_to(self.donor / "ton-work/keys/client")
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.verify_keys(work, hashes)
        self.assertEqual(file_digests(self.donor), before)

    def test_donor_probe_inventories_full_history_and_refuses_external_wallet_links(self):
        self.create_legacy_data()
        ignored = self.donor / "mytoncore/venv/ignored-interpreter"
        ignored.parent.mkdir()
        with ignored.open("wb") as output:
            output.truncate(4 * 2**20)
        sparse = self.donor / "ton-work/db/sparse-data"
        with sparse.open("wb") as output:
            output.truncate(8 * 2**20)
        before = file_digests(self.donor)
        proc = self.root / "proc" / "1234"
        proc.mkdir(parents=True)
        (proc / "cmdline").write_bytes(
            b"/usr/bin/ton/validator-engine/validator-engine\0--db\0/var/ton-work/db\0"
        )
        mappings = {
            "/proc": proc.parent,
            "/var/ton-work": self.donor / "ton-work",
            "/usr/local/bin/mytoncore": self.donor / "mytoncore",
            "/usr/local/bin/mytonctrl": self.donor / "mytonctrl",
            "/usr/bin/ton": self.donor / "ton-runtime",
        }

        def isolated_path(value):
            value = str(value)
            for prefix, destination in mappings.items():
                if value == prefix:
                    return destination
                if value.startswith(prefix + "/"):
                    return destination / value[len(prefix) + 1:]
            return type(self.root)(value)

        stdout = io.StringIO()
        with mock.patch("pathlib.Path", side_effect=isolated_path), redirect_stdout(stdout):
            exec(compile(self.wizard.SOURCE_PROBE, "donor-probe", "exec"), {})
        probe = json.loads(stdout.getvalue())
        for name in ("archive/history", "celldb/state", "import/archive.slice"):
            self.assertIn("ton-work/db/" + name, probe["sizes"])
        self.assertIn("mytoncore/wallets/existing-wallet.pk", probe["hashes"])
        self.assertIn("ton-work/db/keyring/node-key", probe["hashes"])
        self.assertNotIn("mytoncore/venv/ignored-interpreter", probe["sizes"])
        self.assertGreaterEqual(probe["copy_totals"]["mytoncore"]["bytes"], ignored.stat().st_size)
        self.assertEqual(probe["sizes"]["ton-work/db/sparse-data"], sparse.stat().st_size)
        self.assertGreaterEqual(probe["copy_totals"]["ton-work"]["bytes"], sparse.stat().st_size)
        self.assertGreater(probe["copy_totals"]["ton-work"]["entries"], 1)
        self.assertEqual(probe["config_bytes"], sum(path.stat().st_size for path in
                                                  (self.donor / "ton-runtime").glob("*.config.json")))
        self.assertEqual(file_digests(self.donor), before)
        (self.donor / "mytoncore/wallets/external.pk").symlink_to("/etc/shadow")
        with mock.patch("pathlib.Path", side_effect=isolated_path), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                exec(compile(self.wizard.SOURCE_PROBE, "donor-probe", "exec"), {})
        self.assertEqual(file_digests(self.donor), before)

    def exercise_wizard(self, fail_at=None, core_update=None, node_update=None, restart_policy=None,
                        existing_env=None, env_consent="yes", legacy_env=None, extra_files=None,
                        active_services="", runtime_core_update=None, runtime_node_update=None,
                        deployment_collision=None, storage="directory", work_directory=None,
                        work_volume="", volume_existing=False, volume_inspect_update=None,
                        volume_attached=False):
        """Run the real workflow, substituting only host tools and image processes."""
        self.create_legacy_data()
        for name, contents in (extra_files or {}).items():
            path = self.donor / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents if isinstance(contents, bytes) else contents.encode())
        latest_core = {**copy.deepcopy(self.core), **(core_update or {})}
        latest_node = {**copy.deepcopy(self.node), **(node_update or {})}
        (self.donor / "mytoncore/mytoncore.db").write_text(json.dumps(latest_core))
        (self.donor / "ton-work/db/config.json").write_text(json.dumps(latest_node))
        global_config = {"validator": {"zero_state": {"root_hash": "main-root", "file_hash": "main-file"}}}
        (self.donor / "ton-runtime/global.config.json").write_text(json.dumps(global_config))
        before = file_digests(self.donor)
        before_modes = {str(path.relative_to(self.donor)): stat.S_IMODE(path.stat().st_mode)
                        for path in self.donor.rglob("*") if not path.is_symlink()}
        migration = self.root / ("migration" if storage == "volume" else "automatic-migration")
        answers = ["", storage]
        if storage == "directory":
            answers.append(str(migration))
        if existing_env is not None:
            (migration / "deployment").mkdir(parents=True)
            (migration / "deployment/.env").write_bytes(existing_env)
        elif storage == "directory":
            answers.append("no" if fail_at == "directory-cancel" else "yes")
        answers.extend((str(work_directory or "") if storage == "directory" else work_volume,
                        "", "", "yes"))
        if existing_env is not None:
            answers.append(env_consent)
        answers.extend(("yes", "yes"))
        wizard = self.wizard.Wizard(tty=io.StringIO("\n".join(answers) + "\n"))
        command = ["/usr/bin/ton/validator-engine/validator-engine", "--threads", "127",
                   "--global-config", "/usr/bin/ton/global.config.json", "--db", "/var/ton-work/db",
                   "--archive-ttl", "86400", "--state-ttl", "3600", "-M"]
        mappings = {"/var/ton-work": self.donor / "ton-work",
                    "/usr/local/bin/mytoncore": self.donor / "mytoncore",
                    "/usr/local/bin/mytonctrl": self.donor / "mytonctrl",
                    "/usr/bin/ton": self.donor / "ton-runtime"}
        inspected = {"Id": "donor-id", "State": {"Running": True},
                     "Config": {"Env": [key + "=" + value for key, value in {"NETWORK": "mainnet", **(legacy_env or {})}.items()]},
                     "HostConfig": {},
                     "GraphDriver": {"Name": "overlay2", "Data": {"UpperDir": str(self.root)}},
                     "Mounts": [{"Destination": name, "Source": str(source)}
                                for name, source in mappings.items() if name != "/usr/bin/ton"]}
        if restart_policy is not None:
            inspected["HostConfig"]["RestartPolicy"] = restart_policy
        sizes = {name: (self.donor / name).stat().st_size for name in before
                 if not name.startswith("ton-runtime/")}
        hashes = {name: digest for name, digest in before.items()
                  if name.startswith(("ton-work/db/keyring/", "ton-work/keys/", "mytoncore/wallets/"))}
        copy_totals = {}
        for name in ("ton-work", "mytoncore", "mytonctrl"):
            paths = list((self.donor / name).rglob("*"))
            copy_totals[name] = {"bytes": sum(path.lstat().st_size for path in paths
                                              if path.is_file() or path.is_symlink()), "entries": len(paths) + 1}
        config_bytes = sum(path.stat().st_size for path in (self.donor / "ton-runtime").glob("*.config.json"))
        state = {"writer_running": True, "container_running": True, "probes": 0,
                 "pulled": False, "deployment_checks": 0, "volumes": {}}
        calls = []

        def probe():
            state["probes"] += 1
            totals = copy.deepcopy(copy_totals)
            if fail_at == "offline-space" and not state["writer_running"]:
                totals["ton-work"]["bytes"] += 2**45
            return {"core": copy.deepcopy(self.core if state["probes"] == 1 else latest_core),
                    "node": copy.deepcopy(self.node if state["probes"] == 1 else latest_node),
                    "command": command if state["writer_running"] else None,
                    "sizes": sizes, "hashes": hashes, "log_links": [],
                    "copy_totals": totals, "config_bytes": config_bytes,
                    "configs": {"global.config.json": "/usr/bin/ton/global.config.json",
                                "local.config.json": "/usr/bin/ton/local.config.json"}}

        def download(url):
            if url.endswith("testnet-global.config.json"):
                return json.dumps({"validator": {"zero_state": {"root_hash": "test-root", "file_hash": "test-file"}}}).encode()
            if url.endswith("global.config.json"):
                return json.dumps(global_config).encode()
            if url.endswith("/.env.example"):
                return (ROOT / ".env.example").read_bytes()
            if url.endswith("/docker/compose.yml"):
                return (ROOT / "docker/compose.yml").read_bytes()
            raise AssertionError("Unexpected download: " + url)

        def run(args, capture=True, **kwargs):
            args = [str(value) for value in args]
            calls.append(args)
            if args[:2] == ["docker", "compose"]:
                operation = args[len(wizard.compose):]
                if operation == ["pull"] and fail_at == "pull":
                    raise self.wizard.MigrationError("injected image pull failure")
                if operation == ["pull"]:
                    state["pulled"] = True
                if operation and operation[0] == "up":
                    (wizard.work_path / "controller/initialized.json").write_text("{}")
                    for name, updates in (("controller/mytoncore/mytoncore.db", runtime_core_update),
                                          ("db/config.json", runtime_node_update)):
                        if updates:
                            path = wizard.work_path / name
                            data = json.loads(path.read_text())
                            data.update(updates)
                            path.write_text(json.dumps(data))
                if operation[:4] == ["exec", "-T", "mytonctrl", "python3"]:
                    return json.dumps([command])
                if operation[:5] == ["exec", "-T", "mytonctrl", "systemctl", "show"]:
                    return "active\n"
                return ""
            if args[:2] == ["docker", "ps"]:
                if args[-1] == "{{json .}}":
                    return json.dumps({"Names": "original-node", "Image": "ton-docker-ctrl:legacy"})
                return "original-node legacy:image Up"
            if args[:3] == ["docker", "volume", "ls"] and "--filter" not in args:
                return (work_volume or "mytonctrl-ton-work") if volume_existing else ""
            if args[:3] == ["docker", "volume", "create"]:
                name = args[-1]
                location = self.root / "volumes" / name / "_data"
                location.mkdir(parents=True)
                label = args[args.index("--label") + 1]
                state["volumes"][name] = {
                    "Name": name, "Driver": "local", "Scope": "local", "Options": None,
                    "Labels": dict([label.split("=", 1)]), "Mountpoint": str(location),
                }
                return name
            if args[:3] == ["docker", "volume", "inspect"]:
                volume = {**state["volumes"][args[-1]], **(volume_inspect_update or {})}
                return json.dumps([volume])
            if args[:3] == ["docker", "container", "ls"] and any(value.startswith("volume=") for value in args):
                return "unexpected-writer" if volume_attached else ""
            if args[:3] in (["docker", "container", "ls"], ["docker", "network", "ls"],
                            ["docker", "volume", "ls"]):
                is_name = "name=^/mytonctrl$" in args
                expected = ["docker", args[1], "ls"]
                if args[1] == "container":
                    expected.append("--all")
                expected.extend(("--filter", "name=^/mytonctrl$" if is_name else
                                 "label=com.docker.compose.project=mytonctrl", "--format",
                                 "{{.ID}}" if args[1] == "container" else "{{.Name}}"))
                self.assertEqual(args, expected)
                collision = "name" if is_name else args[1]
                if is_name:
                    state["deployment_checks"] += 1
                requested_collision, requested_check = (deployment_collision if isinstance(deployment_collision, tuple)
                                                        else (deployment_collision, 1))
                return ("existing-resource" if requested_collision == collision
                        and state["deployment_checks"] == requested_check else "")
            if args[:2] == ["docker", "info"]:
                self.assertEqual(args[-1], "{{.DockerRootDir}}")
                return str(self.root)
            if args[:2] == ["docker", "inspect"]:
                return json.dumps([inspected]) if len(args) == 3 else str(state["container_running"]).lower()
            if args[:4] == ["docker", "exec", "donor-id", "cat"]:
                return json.dumps(global_config)
            if args[:4] == ["docker", "exec", "donor-id", "systemctl"]:
                if args[-2:] == ["stop", "validator"]:
                    state["writer_running"] = False
                if "list-units" in args:
                    return active_services
                return ""
            if args[:2] == ["docker", "stop"]:
                self.assertEqual(args[2:4], ["--timeout", "120"])
                state["container_running"] = False
                return ""
            if args[:2] == ["docker", "update"]:
                return ""
            if args[0] == "findmnt":
                self.assertTrue(Path(args[-1]).exists(), "Filesystem discovery must use an existing ancestor")
                return "/mnt/data /dev/data ext4"
            if args[:2] == ["docker", "cp"]:
                if fail_at == "copy":
                    raise self.wizard.MigrationError("injected offline copy failure")
                source = args[-2].split(":", 1)[1]
                if source.endswith("/."):
                    source = source[:-2]
                original = next(base / source[len(prefix):].lstrip("/") for prefix, base in mappings.items()
                                if source == prefix or source.startswith(prefix + "/"))
                destination = Path(args[-1])
                if original.is_dir():
                    shutil.copytree(original, destination, dirs_exist_ok=True, symlinks=True)
                else:
                    shutil.copy2(original, destination)
                return ""
            if args[:2] == ["docker", "run"]:
                if "du" in args:
                    return "1024 /usr/local/bin\n512 /usr/lib/fift\n256 /usr/share/ton/smartcont\n"
                if "--mount" in args:
                    self.assertTrue((migration / "backup.tar.gz").is_file())
                else:
                    self.assertTrue(state["writer_running"])
                    self.assertTrue(state["container_running"])
                    self.assertFalse(wizard.work_path.exists() and any(wizard.work_path.iterdir()),
                                     "Image compatibility must be checked before copying any node data")
                    if fail_at == "image-probe":
                        raise self.wizard.MigrationError("injected missing image migration helper")
                return ""
            raise AssertionError("Unexpected command: " + repr(args))

        def logs(args, stdout, stderr, check):
            self.assertEqual(args[:2], ["docker", "logs"])
            stdout.write("saved legacy stdout log\n")
            return subprocess.CompletedProcess(args, 0)

        def capacity(path):
            free = 2**40
            if fail_at == "after-pull-space" and state["pulled"]:
                free = 0
            if fail_at == "current-space" and state["probes"] >= 2:
                free = 0
            return types.SimpleNamespace(free=free)

        output = io.StringIO()
        with mock.patch.object(self.wizard.Path, "cwd", return_value=self.root), \
                mock.patch.object(wizard, "validate_host"), mock.patch.object(wizard, "probe", side_effect=probe), \
                mock.patch.object(wizard, "check_ports"), mock.patch.object(self.wizard, "download", side_effect=download), \
                mock.patch.object(wizard, "measure_logs", return_value=128), \
                mock.patch.object(self.wizard.shutil, "disk_usage", side_effect=capacity), \
                mock.patch.object(self.wizard, "run", side_effect=run), \
                mock.patch.object(self.wizard.time, "sleep", side_effect=AssertionError("Unexpected service wait")), \
                mock.patch.object(self.wizard.subprocess, "run", side_effect=logs), redirect_stdout(output):
            if fail_at in ("env-cancel", "runtime"):
                errors = io.StringIO()
                host_open = open

                def open_terminal(path, *args, **kwargs):
                    return wizard.tty if str(path) == "/dev/tty" else host_open(path, *args, **kwargs)

                with mock.patch.object(self.wizard, "Wizard", return_value=wizard), \
                        mock.patch("builtins.open", side_effect=open_terminal), \
                        mock.patch.object(sys, "argv", ["migrate.sh"]), \
                        mock.patch.object(self.wizard.signal, "signal"), redirect_stderr(errors):
                    self.assertEqual(self.wizard.main(), 1)
                state["error"] = errors.getvalue()
            elif fail_at:
                with self.assertRaises(self.wizard.MigrationError):
                    wizard.execute()
            else:
                wizard.execute()
        self.assertEqual(file_digests(self.donor), before)
        self.assertEqual({str(path.relative_to(self.donor)): stat.S_IMODE(path.stat().st_mode)
                          for path in self.donor.rglob("*") if not path.is_symlink()}, before_modes)
        state["output"] = output.getvalue()
        return wizard, calls, state

    def assert_default_ton_image(self, machine, architecture):
        with mock.patch.object(self.wizard.platform, "machine", return_value=machine):
            wizard, _, _ = self.exercise_wizard()
        expected = "ghcr.io/ton-blockchain/ton:v2026.08-" + architecture
        env = self.wizard.parse_env((wizard.root / "deployment/.env").read_text())
        self.assertEqual(wizard.settings["TON_IMAGE"], expected)
        self.assertEqual(env["TON_IMAGE"], expected)
        self.assertEqual(json.loads((wizard.root / "migration.json").read_text())["phase"], "verified")

    def test_enter_accepts_amd64_ton_image_on_x86_64(self):
        self.assert_default_ton_image("x86_64", "amd64")

    def test_enter_accepts_amd64_ton_image_on_amd64(self):
        self.assert_default_ton_image("AMD64", "amd64")

    def test_enter_accepts_arm64_ton_image_on_aarch64(self):
        self.assert_default_ton_image("aarch64", "arm64")

    def test_enter_accepts_arm64_ton_image_on_arm64(self):
        self.assert_default_ton_image("ARM64", "arm64")

    def test_fixed_container_name_and_project_keep_artifact_storage_independent(self):
        wizard, calls, _ = self.exercise_wizard()
        self.assertEqual(wizard.project, "mytonctrl")
        self.assertEqual(wizard.compose[:4], ["docker", "compose", "--project-name", "mytonctrl"])
        override = json.loads((wizard.root / "deployment/migration.override.json").read_text())
        self.assertEqual(override["services"]["mytonctrl"]["container_name"], "mytonctrl")
        env = self.wizard.parse_env((wizard.root / "deployment/.env").read_text())
        artifact = env["TON_ARTIFACTS_VOLUME"]
        scripts = env["TON_SCRIPTS_VOLUME"]
        unused_work = env["TON_WORK_VOLUME"]
        self.assertEqual(len({artifact, scripts, unused_work}), 3)
        self.assertNotIn(artifact, ("mytonctrl-artifacts", "mytonctrl-ton-artifacts"))
        self.assertNotIn(scripts, ("mytonctrl-scripts", "mytonctrl-ton-scripts"))
        checks = [index for index, call in enumerate(calls)
                  if call[:3] == ["docker", "container", "ls"] and "name=^/mytonctrl$" in call]
        pull = next(index for index, call in enumerate(calls) if call[len(wizard.compose):] == ["pull"])
        stop = next(index for index, call in enumerate(calls) if call[:2] == ["docker", "stop"])
        start = next(index for index, call in enumerate(calls) if call[len(wizard.compose):][:1] == ["up"])
        self.assertEqual(len(checks), 3)
        self.assertLess(checks[0], pull)
        self.assertTrue(any(pull < index < stop for index in checks))
        self.assertTrue(any(stop < index < start for index in checks))

    def test_fixed_name_or_existing_project_refuses_before_pulls_or_donor_downtime(self):
        original_root, original_donor = self.root, self.donor
        try:
            for collision in ("name", "container", "network", "volume"):
                with self.subTest(existing_resource=collision):
                    self.root = original_root / ("collision-" + collision)
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    wizard, calls, state = self.exercise_wizard(fail_at="deployment-collision",
                                                              deployment_collision=collision)
                    self.assertIsNone(wizard.root)
                    self.assertFalse(wizard.donor_stopped)
                    self.assertFalse(wizard.destination_attempted)
                    self.assertFalse(state["pulled"])
                    self.assertTrue(state["writer_running"])
                    self.assertTrue(state["container_running"])
                    self.assertFalse(any(call[:2] == ["docker", "compose"]
                                         or call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                                         or call[-2:-1] == ["stop"] for call in calls))
        finally:
            self.root, self.donor = original_root, original_donor

    def test_completion_and_rollback_instructions_include_both_console_commands(self):
        wizard, _, state = self.exercise_wizard()
        output = io.StringIO()
        with redirect_stdout(output):
            wizard.rollback_instructions()
        recovery = output.getvalue()
        console = "sudo " + shlex.join(wizard.compose + ["exec", "mytonctrl", "mytonctrl"])
        direct = "sudo docker exec -it mytonctrl mytonctrl"
        self.assertIn("Console: " + console, recovery)
        self.assertIn("Direct console: " + direct, recovery)
        self.assertIn("Console: " + console, state["output"])
        self.assertIn("Direct console: " + direct, state["output"])
        self.assertIn(shlex.join(wizard.compose), state["output"])
        self.assertIn("Review status", state["output"])
        self.assertEqual(shlex.split(console)[1:], wizard.compose + ["exec", "mytonctrl", "mytonctrl"])
        self.assertIn("Logs: sudo " + shlex.join(wizard.compose + ["logs", "--tail", "100"]), recovery)
        self.assertIn("Rollback: sudo bash " + shlex.quote(str(wizard.root / "rollback.sh")), recovery)

    def test_new_name_collision_is_rechecked_before_donor_stop_and_destination_start(self):
        original_root, original_donor = self.root, self.donor
        try:
            for check in (2, 3):
                with self.subTest(collision_on_check=check):
                    self.root = original_root / ("late-collision-" + str(check))
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    wizard, calls, state = self.exercise_wizard(fail_at="late-deployment-collision",
                                                              deployment_collision=("name", check))
                    self.assertTrue(state["pulled"])
                    self.assertFalse(wizard.destination_attempted)
                    self.assertEqual(wizard.donor_stopped, check == 3)
                    self.assertEqual(state["writer_running"], check == 2)
                    self.assertEqual(state["container_running"], check == 2)
                    self.assertFalse(any(call[:2] == ["docker", "compose"]
                                         and "up" in call[len(wizard.compose):] for call in calls))
                    self.assertFalse(any(call[:2] == ["docker", "compose"]
                                         and "stop" in call[len(wizard.compose):] for call in calls))
        finally:
            self.root, self.donor = original_root, original_donor

    def test_cancelled_directory_creation_does_not_pull_images_or_modify_the_donor(self):
        wizard, calls, state = self.exercise_wizard(fail_at="directory-cancel")
        self.assertIsNone(wizard.root)
        self.assertFalse((self.root / "automatic-migration").exists())
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(state["pulled"])
        self.assertFalse(any(call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_image_pull_failure_does_not_stop_or_copy_the_original_node(self):
        wizard, calls, state = self.exercise_wizard(fail_at="pull")
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] == ["docker", "stop"] or call[:2] == ["docker", "cp"]
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_failed_offline_copy_keeps_original_storage_and_both_nodes_stopped(self):
        wizard, calls, state = self.exercise_wizard(fail_at="copy")
        self.assertTrue(wizard.donor_stopped)
        self.assertFalse(wizard.destination_attempted)
        self.assertFalse(state["writer_running"])
        self.assertFalse(state["container_running"])
        self.assertFalse(any(call[:2] == ["docker", "start"] for call in calls))
        self.assertFalse(any("up" in call for call in calls))

    def test_incompatible_controller_image_is_rejected_before_donor_downtime(self):
        wizard, calls, state = self.exercise_wizard(fail_at="image-probe")
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] == ["docker", "stop"] or call[:2] == ["docker", "cp"]
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_automatic_migration_copies_data_and_verifies_identity_before_starting(self):
        wizard, calls, state = self.exercise_wizard()
        self.assertFalse(state["container_running"])
        migration = wizard.root
        self.assertEqual(json.loads((migration / "migration.json").read_text())["phase"], "verified")
        self.assertEqual(file_digests(migration / "ton-work/db"), file_digests(self.donor / "ton-work/db"))
        self.assertEqual((migration / "ton-work/controller/mytoncore/wallets/existing-wallet.pk").read_bytes(),
                         (self.donor / "mytoncore/wallets/existing-wallet.pk").read_bytes())
        self.assertEqual((migration / "ton-work/dump-cache/saved-dump.tar.lz").read_bytes(),
                         (self.donor / "ton-work/dump-cache/saved-dump.tar.lz").read_bytes())
        env = self.wizard.parse_env((migration / "deployment/.env").read_text())
        self.assertEqual(env["ARCHIVE_TTL"], "90000")
        self.assertEqual(env["STATE_TTL"], "3600")
        self.assertNotIn("-d", env["MYTONCTRL_ARGS"].split())
        self.assertNotIn("ARCHIVE_BLOCKS", env)
        stop = next(index for index, call in enumerate(calls) if call[:2] == ["docker", "stop"])
        controller_stop = next(index for index, call in enumerate(calls)
                               if call == ["docker", "exec", "donor-id", "systemctl", "stop", "mytoncore"])
        image_probe = next(index for index, call in enumerate(calls)
                           if call[:2] == ["docker", "run"] and "--mount" not in call)
        first_copy = next(index for index, call in enumerate(calls) if call[:2] == ["docker", "cp"])
        start = next(index for index, call in enumerate(calls) if "up" in call)
        self.assertLess(stop, first_copy)
        self.assertLess(first_copy, start)
        self.assertLess(image_probe, controller_stop)
        self.assertLess(image_probe, first_copy)

    def assert_work_storage_preserves_node(self, wizard):
        work = wizard.work_path
        self.assertEqual(file_digests(work / "db"), file_digests(self.donor / "ton-work/db"))
        self.assertEqual(file_digests(work / "keys"), file_digests(self.donor / "ton-work/keys"))
        for name in ("db/archive/history", "db/celldb/state", "db/import/archive.slice",
                     "dump-cache/saved-dump.tar.lz", "keys/client", "db/keyring/node-key"):
            self.assertEqual((work / name).read_bytes(), (self.donor / "ton-work" / name).read_bytes())
        for name in ("wallets/existing-wallet.pk", "wallets/existing-wallet.addr", "contracts/pool.json"):
            self.assertEqual((work / "controller/mytoncore" / name).read_bytes(),
                             (self.donor / "mytoncore" / name).read_bytes())
        self.assertEqual(json.loads((wizard.root / "migration.json").read_text())["phase"], "verified")

    def test_custom_work_directory_copies_directly_to_selected_storage_and_sets_host_environment(self):
        work = self.root / "mounted-data-disk" / "node-data"
        wizard, calls, state = self.exercise_wizard(work_directory=work)
        self.assertEqual(wizard.work_path, work)
        self.assertEqual(wizard.work_volume, "")
        self.assert_work_storage_preserves_node(wizard)
        self.assertFalse((wizard.root / "ton-work").exists(), "Do not create a second complete database staging copy")
        env = self.wizard.parse_env((wizard.root / "deployment/.env").read_text())
        self.assertEqual(env["TON_WORK_HOST_DIR"], str(work))
        node_copies = [call for call in calls if call[:2] == ["docker", "cp"]
                       and call[-2] == "donor-id:/var/ton-work/."]
        self.assertEqual(len(node_copies), 1)
        self.assertEqual(node_copies[0][-1], str(work))
        self.assertFalse(state["container_running"])
        self.assertFalse(any(call[:3] == ["docker", "volume", "create"] for call in calls))

    def test_directory_workflow_asks_storage_type_before_metadata_and_host_directory(self):
        wizard, _, state = self.exercise_wizard()
        output = state["output"]
        storage = output.index("Where should TON work data be copied")
        metadata = output.index("New migration directory on the mounted data disk")
        host = output.index("TON work host directory (TON_WORK_HOST_DIR)")
        self.assertLess(storage, metadata)
        self.assertLess(metadata, host)
        self.assertEqual(output.count("Where should TON work data be copied"), 1)
        self.assertEqual(wizard.work_volume, "")

    def test_default_volume_workflow_has_no_directory_questions_and_uses_cwd_migration(self):
        wizard, _, state = self.exercise_wizard(storage="volume")
        output = state["output"]
        self.assertEqual(wizard.root, self.root / "migration")
        self.assertEqual(wizard.work_volume, "mytonctrl-ton-work")
        self.assertEqual(wizard.work_path, self.root / "volumes/mytonctrl-ton-work/_data")
        self.assert_work_storage_preserves_node(wizard)
        self.assertEqual(output.count("Where should TON work data be copied"), 1)
        self.assertNotIn("New migration directory on the mounted data disk", output)
        self.assertNotIn("Specified directory does not exist", output)
        self.assertNotIn("TON work host directory (TON_WORK_HOST_DIR)", output)
        self.assertIn("[mytonctrl-ton-work]", output)
        env = self.wizard.parse_env((wizard.root / "deployment/.env").read_text())
        self.assertEqual(env["TON_WORK_HOST_DIR"], "")
        self.assertEqual(env["TON_WORK_VOLUME"], "mytonctrl-ton-work")

    def test_existing_default_work_volume_preserves_source_and_creates_no_migration_directory(self):
        wizard, calls, state = self.exercise_wizard(fail_at="existing-volume", storage="volume", volume_existing=True)
        self.assertEqual(wizard.root, self.root / "migration")
        self.assertFalse(wizard.root.exists())
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(state["pulled"])
        self.assertEqual(state["volumes"], {})
        self.assertFalse(any(call[:3] == ["docker", "volume", "create"] or call[:2] == ["docker", "cp"]
                             or call[:2] == ["docker", "stop"] for call in calls))

    def test_named_work_volume_copies_directly_preserves_all_data_and_is_external_to_compose(self):
        name = "selected-node-work"
        wizard, calls, state = self.exercise_wizard(storage="volume", work_volume=name)
        self.assertEqual(wizard.work_volume, name)
        self.assertEqual(wizard.work_path, self.root / "volumes" / name / "_data")
        self.assert_work_storage_preserves_node(wizard)
        self.assertFalse((wizard.root / "ton-work").exists(), "Named-volume migration must not also stage a full database")
        env = self.wizard.parse_env((wizard.root / "deployment/.env").read_text())
        self.assertEqual(env["TON_WORK_HOST_DIR"], "")
        self.assertEqual(env["TON_WORK_VOLUME"], name)
        override = json.loads((wizard.root / "deployment/migration.override.json").read_text())
        self.assertTrue(override["volumes"]["ton-work"]["external"])
        self.assertEqual(override["volumes"]["ton-work"]["name"], name)
        creation = next(index for index, call in enumerate(calls) if call[:3] == ["docker", "volume", "create"])
        stop = next(index for index, call in enumerate(calls) if call[:2] == ["docker", "stop"])
        copies = [call for call in calls if call[:2] == ["docker", "cp"]
                  and call[-2] == "donor-id:/var/ton-work/."]
        self.assertLess(creation, stop)
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0][-1], str(wizard.work_path))
        self.assertFalse(any(call[:3] == ["docker", "volume", "rm"] for call in calls))
        self.assertFalse(state["container_running"])

    def test_failed_named_volume_copy_retains_destination_volume_and_leaves_original_data_unchanged(self):
        wizard, calls, state = self.exercise_wizard(fail_at="copy", storage="volume", work_volume="copy-failed-work")
        self.assertTrue(wizard.work_path.is_dir())
        self.assertIn("copy-failed-work", state["volumes"])
        self.assertTrue(wizard.donor_stopped)
        self.assertFalse(wizard.destination_attempted)
        self.assertFalse(state["writer_running"])
        self.assertFalse(state["container_running"])
        self.assertFalse(any(call[:3] == ["docker", "volume", "rm"] or call[:2] == ["docker", "start"]
                             for call in calls))

    def test_existing_named_volume_is_rejected_before_pulls_or_donor_stop(self):
        wizard, calls, state = self.exercise_wizard(fail_at="existing-volume", storage="volume",
                                                   work_volume="existing-node-work", volume_existing=True)
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(state["pulled"])
        self.assertFalse(any(call[:3] == ["docker", "volume", "create"] or call[:2] == ["docker", "cp"]
                             or call[:2] == ["docker", "stop"] for call in calls))

    def test_custom_directory_refuses_donor_overlap_or_existing_files_without_stopping_original(self):
        original_root, original_donor = self.root, self.donor
        try:
            for kind in ("same-source", "source-descendant", "source-ancestor", "existing-data", "metadata", "docker-volume"):
                with self.subTest(destination=kind):
                    self.root = original_root / ("work-directory-" + kind)
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    if kind == "same-source":
                        path = self.donor / "ton-work"
                    elif kind == "source-descendant":
                        path = self.donor / "ton-work/new-node"
                    elif kind == "source-ancestor":
                        path = self.donor
                    elif kind == "metadata":
                        path = self.root / "automatic-migration/deployment"
                    elif kind == "docker-volume":
                        path = self.root / "volumes/future-artifacts/_data"
                    else:
                        path = self.root / "already-used"
                        path.mkdir()
                        (path / "customer-data").write_bytes(b"must-never-be-replaced")
                    wizard, calls, state = self.exercise_wizard(fail_at="unsafe-directory", work_directory=path)
                    self.assertFalse(wizard.donor_stopped)
                    self.assertTrue(state["writer_running"])
                    self.assertTrue(state["container_running"])
                    self.assertFalse(state["pulled"])
                    self.assertFalse(any(call[:2] == ["docker", "stop"] or call[:2] == ["docker", "cp"] for call in calls))
                    if kind == "existing-data":
                        self.assertEqual((path / "customer-data").read_bytes(), b"must-never-be-replaced")
        finally:
            self.root, self.donor = original_root, original_donor

    def test_environment_replacement_decline_does_not_create_selected_work_storage(self):
        original_root, original_donor = self.root, self.donor
        try:
            for storage in ("directory", "volume"):
                with self.subTest(storage=storage):
                    self.root = original_root / ("storage-consent-" + storage)
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    custom = self.root / "unapproved-data-disk/customer-node"
                    wizard, calls, state = self.exercise_wizard(
                        fail_at="env-cancel", existing_env=b"EXISTING=keep\n", env_consent="no",
                        storage=storage, work_directory=custom, work_volume="unapproved-work",
                    )
                    self.assertFalse(custom.exists())
                    self.assertFalse(wizard.donor_stopped)
                    self.assertFalse(state["pulled"])
                    self.assertEqual(state["volumes"], {})
                    self.assertFalse(any(call[:3] == ["docker", "volume", "create"] for call in calls))
        finally:
            self.root, self.donor = original_root, original_donor

    def test_nonlocal_or_rebound_new_volumes_are_rejected_before_donor_changes(self):
        original_root, original_donor = self.root, self.donor
        cases = ({"Driver": "remote-plugin"}, {"Scope": "global"},
                 {"Options": {"type": "none", "device": str(self.donor), "o": "bind"}},
                 {"Labels": {}}, {"Mountpoint": str(self.donor / "ton-work")})
        try:
            for index, updates in enumerate(cases):
                with self.subTest(volume_inspect=updates):
                    self.root = original_root / ("unsafe-volume-" + str(index))
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    wizard, calls, state = self.exercise_wizard(fail_at="unsafe-volume", storage="volume",
                                                               work_volume="guarded-node-work", volume_inspect_update=updates)
                    self.assertFalse(wizard.donor_stopped)
                    self.assertTrue(state["writer_running"])
                    self.assertTrue(state["container_running"])
                    self.assertFalse(any(call[:2] == ["docker", "stop"] or call[:2] == ["docker", "cp"]
                                         or call[:3] == ["docker", "volume", "rm"] for call in calls))
        finally:
            self.root, self.donor = original_root, original_donor

    def test_attached_new_named_volume_refuses_before_stopping_donor(self):
        wizard, calls, state = self.exercise_wizard(fail_at="attached-volume", storage="volume",
                                                   work_volume="attached-node-work", volume_attached=True)
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] == ["docker", "stop"] or call[:2] == ["docker", "cp"] for call in calls))

    def test_all_requested_roles_migrate_without_losing_staking_files_wallets_or_mode_settings(self):
        original_root, original_donor, original_core, original_node = self.root, self.donor, self.core, self.node
        cases = [(role, False) for role in ("liteserver", "collator", *STAKING_MODES)]
        cases.extend((role, True) for role in STAKING_MODES)
        for role, paused in cases:
            with self.subTest(role=role, paused=paused):
                try:
                    self.root = original_root / (role + ("-paused" if paused else ""))
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    self.core = copy.deepcopy(CORE_CONFIG)
                    modes = {name: False for name in ("validator", "liteserver", "collator", *STAKING_MODES)}
                    modes.update({role: True, "validator": role in STAKING_MODES and not paused,
                                  "alert-bot": True, "prometheus": False})
                    retained = {
                        "modes": modes, "validatorWalletName": "existing-wallet", "adnlAddr": "original-validator-adnl",
                        "customPools": ["original-pool", "retained-staking-pool"],
                        "stake": 45000, "stakePercent": 63, "maxFactor": 1.5,
                        "liquid_pool_addr": "retained-liquid-pool-address", "min_loan": 42000,
                        "max_loan": 47000, "max_interest_percent": 1.7,
                        "user_controllers_list": ["user-controller"], "using_controllers": ["active-controller"],
                        "old_controllers": ["old-controller"], "stop_controllers_list": ["stopped-controller"],
                        "user_controllers": {"user-controller": {"stake": 41000}},
                    }
                    self.core.update(retained)
                    self.node = copy.deepcopy(NODE_CONFIG)
                    extra_files = {
                        "mytoncore/pools/retained-pool.addr": b"\x80retained-pool-address\x00",
                        "mytoncore/pools/retained-pool.boc": b"\xb5\xee\x9c\x72retained-pool-contract",
                        "mytoncore/contracts/nominator-pool/func/new-pool.fif": b"retained-v1-contract-script",
                        "mytoncore/contracts/nominator-pool-v2/pool-contract.boc": b"retained-v2-contract",
                        "mytoncore/contracts/single-nominator-pool/single-nominator-code.hex": b"retained-single-contract",
                        "mytoncore/contracts/jetton_pool/controller.fif": b"retained-liquid-controller-script",
                        "mytoncore/wallets/pool-owner.pk": b"retained-pool-owner-private-key",
                        "mytoncore/wallets/pool-owner.addr": b"retained-pool-owner-address",
                    }
                    if role == "collator":
                        self.node.update({
                            "adnl": [{"id": "original-collator-adnl", "category": 0}],
                            "collators": ["original-collator-adnl"],
                            "extraconfig": {"collator_node_whitelist": {"enabled": True,
                                                                       "adnl_ids": ["retained-validator-adnl"]}},
                        })
                        extra_files.update({
                            "ton-work/db/keyring/collator-key": b"original-collator-private-key",
                            "ton-work/db/collators-list.json": json.dumps({"collators": [{"adnl_id": "retained-peer"}]}),
                            "ton-work/db/collator-options.json": json.dumps({"max_collators": 7, "max_parallel_collations": 3}),
                        })
                    wizard, calls, state = self.exercise_wizard(legacy_env={"MODE": "validator"}, extra_files=extra_files)
                    self.assertEqual(wizard.settings["MODE"], role)
                    env = self.wizard.parse_env((wizard.root / "deployment/.env").read_text())
                    arguments = shlex.split(env["MYTONCTRL_ARGS"])
                    self.assertEqual(arguments[arguments.index("-m") + 1], "none" if role == "collator" else role)
                    self.assertEqual(arguments[arguments.index("-p") + 1], "/migration/backup.tar.gz")
                    self.assertNotIn("-d", arguments)
                    staged = json.loads((wizard.root / "ton-work/controller/mytoncore/mytoncore.db").read_text())
                    for name, value in retained.items():
                        self.assertEqual(staged[name], value, "Saved staking setting changed: " + name)
                    self.assertEqual(json.loads((wizard.root / "ton-work/db/config.json").read_text()), self.node)
                    with tarfile.open(wizard.root / "backup.tar.gz", "r:gz") as backup:
                        core = json.load(backup.extractfile("mytoncore/mytoncore.db"))
                        for name, value in retained.items():
                            self.assertEqual(core[name], value, "Backup staking setting changed: " + name)
                        self.assertEqual(json.load(backup.extractfile("db/config.json")), self.node)
                        self.assertEqual(backup.extractfile("mytoncore/wallets/existing-wallet.pk").read(),
                                         (self.donor / "mytoncore/wallets/existing-wallet.pk").read_bytes())
                        self.assertEqual(backup.extractfile("mytoncore/wallets/existing-wallet.addr").read(),
                                         (self.donor / "mytoncore/wallets/existing-wallet.addr").read_bytes())
                        for name in extra_files:
                            member = name[len("ton-work/"):] if name.startswith("ton-work/") else name
                            target = wizard.root / "ton-work" / (
                                "controller/" + name if name.startswith("mytoncore/") else member)
                            self.assertEqual(target.read_bytes(), (self.donor / name).read_bytes())
                            self.assertEqual(backup.extractfile(member).read(), (self.donor / name).read_bytes())
                    self.assertFalse(any("setup_collator" in argument or "enable_mode_" in argument
                                         for call in calls for argument in call))
                    self.assertFalse(state["container_running"])
                    self.assertEqual(json.loads((wizard.root / "migration.json").read_text())["phase"], "verified")
                finally:
                    self.root, self.donor, self.core, self.node = original_root, original_donor, original_core, original_node

    def test_standalone_collator_service_is_rejected_before_images_or_donor_downtime(self):
        self.core["modes"] = {"validator": False, "liteserver": False, "collator": True}
        wizard, calls, state = self.exercise_wizard(fail_at="auxiliary",
                                                   active_services="collator.service loaded active running Standalone collator\n")
        self.assertFalse(wizard.donor_stopped)
        self.assertFalse(state["pulled"])
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_conflicting_saved_node_modes_are_rejected_before_any_donor_changes(self):
        original_root, original_donor, original_core = self.root, self.donor, self.core
        for conflicting in ("liteserver", "collator"):
            with self.subTest(conflicting=conflicting):
                try:
                    self.root = original_root / (conflicting + "-conflict")
                    self.root.mkdir()
                    self.donor = self.root / "donor"
                    self.donor.mkdir()
                    self.core = copy.deepcopy(CORE_CONFIG)
                    self.core["modes"] = {"validator": True, conflicting: True}
                    wizard, calls, state = self.exercise_wizard(fail_at="mode-conflict", legacy_env={"MODE": conflicting})
                    self.assertIsNone(wizard.root)
                    self.assertFalse(wizard.donor_stopped)
                    self.assertFalse(state["pulled"])
                    self.assertTrue(state["writer_running"])
                    self.assertTrue(state["container_running"])
                    self.assertFalse(any(call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                                         or call[-2:-1] == ["stop"] for call in calls))
                finally:
                    self.root, self.donor, self.core = original_root, original_donor, original_core

    def test_ambiguous_staking_validator_flag_is_rejected_before_any_donor_changes(self):
        self.core["modes"] = {"nominator-pool-v2": True}
        wizard, calls, state = self.exercise_wizard(fail_at="ambiguous-validator")
        self.assertIsNone(wizard.root)
        self.assertFalse(wizard.donor_stopped)
        self.assertFalse(state["pulled"])
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                             or call[-2:-1] == ["stop"] for call in calls))

    def assert_changed_collator_state_stops_destination(self, updates):
        self.core["modes"] = {"validator": False, "liteserver": False, "collator": True}
        self.node.update({"collators": ["saved-collator-adnl"],
                          "extraconfig": {"collator_node_whitelist": {"enabled": True,
                                                                     "adnl_ids": ["saved-validator"]}}})
        wizard, calls, state = self.exercise_wizard(fail_at="runtime", runtime_node_update=updates)
        self.assertTrue(wizard.donor_stopped)
        self.assertFalse(wizard.destination_attempted)
        self.assertFalse(state["container_running"])
        self.assertIn("collator", state["error"].lower())
        self.assertTrue(any(call[-3:] == ["stop", "--timeout", "120"] for call in calls))
        self.assertFalse(any(call[:2] == ["docker", "start"] for call in calls))

    def test_changed_runtime_collator_adnl_stops_the_destination(self):
        self.assert_changed_collator_state_stops_destination({"collators": ["new-unexpected-collator-adnl"]})

    def test_changed_runtime_collator_whitelist_stops_the_destination(self):
        self.assert_changed_collator_state_stops_destination({
            "extraconfig": {"collator_node_whitelist": {"enabled": False, "adnl_ids": ["saved-validator"]}},
        })

    def test_changed_runtime_collator_whitelist_ids_stop_the_destination(self):
        self.assert_changed_collator_state_stops_destination({
            "extraconfig": {"collator_node_whitelist": {"enabled": True, "adnl_ids": ["unexpected-validator"]}},
        })

    def test_new_runtime_collator_setting_stops_the_destination(self):
        self.assert_changed_collator_state_stops_destination({"collator_whitelist": ["unexpected-validator"]})

    def test_runtime_certificate_metadata_changes_and_whitelist_order_do_not_change_collator_permissions(self):
        self.core["modes"] = {"validator": False, "liteserver": False, "collator": True}
        self.node.update({"collators": ["saved-collator-adnl"],
                          "extraconfig": {"collator_node_whitelist": {"enabled": True,
                                                                     "adnl_ids": ["first-validator", "second-validator"]},
                                          "fast_sync_certificate": {"expires_at": 100}}})
        updates = {"extraconfig": {"collator_node_whitelist": {"enabled": True,
                                                               "adnl_ids": ["second-validator", "first-validator"]},
                                   "fast_sync_certificate": {"expires_at": 200}}}
        wizard, _, _ = self.exercise_wizard(runtime_node_update=updates)
        self.assertEqual(json.loads((wizard.root / "migration.json").read_text())["phase"], "verified")
        self.assertTrue(wizard.destination_attempted)

    def test_disabled_empty_whitelist_serialization_formats_preserve_the_same_permissions(self):
        for extra in (None, {}, {"collator_node_whitelist": None},
                      {"collator_node_whitelist": {"enabled": False, "adnl_ids": []}}):
            with self.subTest(extraconfig=extra):
                self.assertEqual(self.wizard.collator_whitelist({"extraconfig": extra}),
                                 self.wizard.collator_whitelist({}))

    def test_recent_background_metadata_changes_are_copied_from_offline_controller(self):
        updates = {"lastScan": 123456, "customPools": ["updated-pool"], "statistics": {"load": 42}}
        wizard, _, _ = self.exercise_wizard(core_update=updates)
        migrated = json.loads((wizard.root / "ton-work/controller/mytoncore/mytoncore.db").read_text())
        for name, value in updates.items():
            self.assertEqual(migrated[name], value)

    def test_identity_change_during_planning_refuses_copy_and_destination_start(self):
        wizard, calls, _ = self.exercise_wizard(fail_at="identity-change", core_update={"adnlAddr": "new-identity"})
        self.assertTrue(wizard.donor_stopped)
        self.assertFalse(any(call[:2] == ["docker", "cp"] for call in calls))
        self.assertFalse(any("up" in call for call in calls))

    def test_endpoint_change_during_planning_refuses_copy_and_destination_start(self):
        changed = [{"port": 40314, "id": "console-key", "allowed": ["client-key"]}]
        wizard, calls, _ = self.exercise_wizard(fail_at="identity-change", node_update={"control": changed})
        self.assertTrue(wizard.donor_stopped)
        self.assertFalse(any(call[:2] == ["docker", "cp"] for call in calls))
        self.assertFalse(any("up" in call for call in calls))

    def test_rollback_stop_ignores_later_environment_overrides(self):
        wizard, _, _ = self.exercise_wizard()
        tools = self.root / "rollback-tools"
        tools.mkdir()
        log = self.root / "rollback-docker.json"
        docker = tools / "docker"
        docker.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\nfrom pathlib import Path\n"
            f"Path({str(log)!r}).write_text(json.dumps({{'args': sys.argv[1:], 'host_dir': os.environ.get('TON_WORK_HOST_DIR'), "
            "'compose_file': os.environ.get('COMPOSE_FILE'), 'image': os.environ.get('MYTONCTRL_IMAGE')}))\n"
        )
        docker.chmod(0o755)
        stop_line = next(line for line in (wizard.root / "rollback.sh").read_text().splitlines()
                         if line.startswith("env "))
        environment = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"],
                       "TON_WORK_HOST_DIR": "/different-data", "COMPOSE_FILE": "/different-compose.yml",
                       "MYTONCTRL_IMAGE": "different:image"}
        result = subprocess.run(shlex.split(stop_line), env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        invoked = json.loads(log.read_text())
        self.assertIsNone(invoked["host_dir"])
        self.assertIsNone(invoked["compose_file"])
        self.assertIsNone(invoked["image"])
        self.assertEqual(invoked["args"][-3:], ["stop", "--timeout", "120"])
        self.assertIn(str(wizard.root / "deployment/.env"), invoked["args"])

    def test_donor_restart_policy_is_disabled_before_downtime_and_restored_after_destination_stop(self):
        wizard, calls, _ = self.exercise_wizard(
            restart_policy={"Name": "always", "MaximumRetryCount": 0}
        )
        disable = next(index for index, call in enumerate(calls)
                       if call == ["docker", "update", "--restart", "no", "donor-id"])
        controller_stop = next(index for index, call in enumerate(calls)
                               if call == ["docker", "exec", "donor-id", "systemctl", "stop", "mytoncore"])
        first_copy = next(index for index, call in enumerate(calls) if call[:2] == ["docker", "cp"])
        self.assertLess(disable, controller_stop)
        self.assertLess(controller_stop, first_copy)
        rollback = (wizard.root / "rollback.sh").read_text().splitlines()
        stop = next(index for index, line in enumerate(rollback) if line.startswith("env "))
        restore = next(index for index, line in enumerate(rollback)
                       if shlex.split(line) == ["docker", "update", "--restart", "always", "donor-id"])
        start = next(index for index, line in enumerate(rollback)
                     if shlex.split(line) == ["docker", "start", "donor-id"])
        self.assertLess(stop, restore)
        self.assertLess(restore, start)

    def test_private_umask_allows_engine_network_config_access_and_keeps_wallets_private(self):
        previous_umask = os.umask(0o077)
        try:
            wizard, _, _ = self.exercise_wizard()
        finally:
            os.umask(previous_umask)
        controller = wizard.root / "ton-work/controller"
        self.assertEqual(stat.S_IMODE(controller.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((controller / "global.config.json").stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((controller / "local.config.json").stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((controller / "mytoncore").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((controller / "mytoncore/wallets").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((controller / "mytoncore/wallets/existing-wallet.pk").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.donor / "ton-runtime/global.config.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.donor / "ton-runtime/local.config.json").stat().st_mode), 0o600)

    def space_probe(self):
        return {
            "sizes": {
                "ton-work/db/archive/history": 8 * 2**30,
                "ton-work/db/config.json": 512,
                "ton-work/db/keyring/key": 128,
                "ton-work/keys/client": 64,
                "mytoncore/mytoncore.db": 2 * 2**20,
                "mytoncore/wallets/wallet.pk": 64,
                "mytonctrl/mytonctrl.db": 256,
            },
            "copy_totals": {
                "ton-work": {"bytes": 8 * 2**30 + 704, "entries": 12},
                "mytoncore": {"bytes": 2**30 + 2 * 2**20 + 64, "entries": 8},
                "mytonctrl": {"bytes": 256, "entries": 3},
            },
            "config_bytes": 1024,
        }

    def test_space_budget_includes_complete_copy_and_identity_copies_without_compression_credit(self):
        probe = self.space_probe()
        plan = self.wizard.migration_space_plan(probe, log_bytes=4096)
        self.assertGreaterEqual(plan["copy"], 9 * 2**30 + 4096 + probe["config_bytes"])
        identity = sum(size for name, size in probe["sizes"].items()
                       if name.startswith(("mytoncore/", "ton-work/keys/", "ton-work/db/keyring/"))
                       or name == "ton-work/db/config.json")
        core = 2 * 2**20 + 64
        self.assertGreaterEqual(plan["stage"], identity + 256 + probe["config_bytes"])
        self.assertGreater(plan["archive"], identity)
        self.assertGreaterEqual(plan["restore"], identity)
        self.assertGreaterEqual(plan["prime"], core)
        self.assertGreaterEqual(plan["startup"], core)
        self.assertGreaterEqual(plan["reserve"], 2**30)
        # Ignored venv bytes are retained by docker cp but do not enter the
        # identity archive or controller's additional copies.
        more_venv = copy.deepcopy(probe)
        more_venv["copy_totals"]["mytoncore"]["bytes"] += 2**30
        larger = self.wizard.migration_space_plan(more_venv, log_bytes=4096)
        self.assertEqual(larger["copy"] - plan["copy"], 2**30)
        for phase in ("stage", "archive", "prime", "startup", "restore"):
            self.assertEqual(larger[phase], plan[phase])

    def test_disk_space_combines_requirements_on_the_same_device(self):
        data = self.root / "data"
        docker = self.root / "docker"
        with mock.patch.object(Path, "stat", autospec=True, return_value=types.SimpleNamespace(st_dev=1)), \
                mock.patch.object(self.wizard.shutil, "disk_usage", return_value=types.SimpleNamespace(free=100)), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(self.wizard.MigrationError):
                self.wizard.check_disk_space([("migration data", data, 70), ("Docker restore", docker, 60)])

    def test_disk_space_checks_separate_devices_independently(self):
        data = self.root / "data"
        docker = self.root / "docker"
        def device(path):
            return types.SimpleNamespace(st_dev=1 if path == data else 2)
        with mock.patch.object(Path, "stat", autospec=True, side_effect=device), \
                mock.patch.object(self.wizard.shutil, "disk_usage", return_value=types.SimpleNamespace(free=100)), \
                redirect_stdout(io.StringIO()):
            self.wizard.check_disk_space([("migration data", data, 70), ("Docker restore", docker, 60)])

    def test_post_pull_low_space_preserves_running_donor_and_restart_policy(self):
        wizard, calls, state = self.exercise_wizard(
            fail_at="after-pull-space", restart_policy={"Name": "always", "MaximumRetryCount": 0}
        )
        self.assertTrue(state["pulled"])
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_current_pre_downtime_low_space_preserves_running_donor_and_restart_policy(self):
        wizard, calls, state = self.exercise_wizard(
            fail_at="current-space", restart_policy={"Name": "always", "MaximumRetryCount": 0}
        )
        self.assertGreaterEqual(state["probes"], 2)
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(any(call[:2] in (["docker", "stop"], ["docker", "update"], ["docker", "cp"])
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_offline_source_growth_is_rejected_before_copying(self):
        wizard, calls, state = self.exercise_wizard(fail_at="offline-space")
        self.assertTrue(wizard.donor_stopped)
        self.assertFalse(state["writer_running"])
        self.assertFalse(state["container_running"])
        self.assertFalse(any(call[:2] == ["docker", "cp"] for call in calls))
        self.assertFalse(any("up" in call for call in calls))

    def test_remaining_space_rechecks_do_not_charge_completed_phases_again(self):
        wizard = self.wizard.Wizard()
        wizard.root = self.root / "migration"
        wizard.docker_root = self.root / "docker"
        wizard.docker_root.mkdir()
        wizard.log_bytes = 4096
        wizard.artifact_bytes = 2048
        requests = []
        probe = self.space_probe()
        plan = self.wizard.migration_space_plan(probe, log_bytes=4096)
        with mock.patch.object(self.wizard.os, "statvfs", return_value=types.SimpleNamespace(f_frsize=4096)), \
                mock.patch.object(self.wizard, "check_disk_space", side_effect=lambda requirements: requests.append(requirements)):
            for phase in ("copy", "stage", "archive", "startup"):
                wizard.check_space(probe, phase)
        budgets = [sum(item[2] for item in requirements[:2]) for requirements in requests]
        self.assertEqual(budgets[0] - budgets[1], plan["copy"])
        self.assertEqual(budgets[1] - budgets[2], plan["stage"])
        self.assertEqual(requests[3][0][2], plan["metadata_reserve"])
        self.assertEqual(requests[3][1][2], plan["startup"] + plan["work_reserve"])
        self.assertEqual({sum(item[2] for item in requirements[2:]) for requirements in requests},
                         {sum(item[2] for item in requests[0][2:])})
        self.assertGreaterEqual(sum(item[2] for item in requests[0][2:]),
                                plan["restore"] + 2 * wizard.artifact_bytes + 2**30)

    def test_space_budget_charges_complete_node_to_chosen_directory_or_pending_named_volume(self):
        migration = self.root / "migration-metadata"
        work = self.root / "independent-work-filesystem"
        docker = self.root / "docker-storage"
        volumes = docker / "volumes"
        for path in (migration, work, volumes):
            path.mkdir(parents=True)
        probe = self.space_probe()
        requests = []
        for storage in ("directory", "volume"):
            wizard = self.wizard.Wizard()
            wizard.root = migration
            wizard.docker_root = docker
            wizard.docker_volumes = volumes
            wizard.docker_writable = docker
            if storage == "directory":
                wizard.work_dir = work
            else:
                wizard.work_volume = "future-node-work"
            with mock.patch.object(self.wizard.os, "statvfs", return_value=types.SimpleNamespace(f_frsize=4096)), \
                    mock.patch.object(self.wizard, "check_disk_space", side_effect=requests.append):
                wizard.check_space(probe)
        plan = self.wizard.migration_space_plan(probe)
        self.assertEqual(requests[0][1][1], work)
        self.assertEqual(requests[1][1][1], volumes)
        for request in requests:
            self.assertEqual(request[0][1], migration)
            self.assertGreaterEqual(request[1][2], probe["copy_totals"]["ton-work"]["bytes"])
            self.assertLess(request[0][2], probe["copy_totals"]["ton-work"]["bytes"],
                            "Migration metadata filesystem must not be charged another complete node copy")
            self.assertEqual(sum(item[2] for item in request[:2]),
                             sum(plan[name] for name in ("copy", "stage", "archive", "prime", "startup"))
                             + plan["metadata_reserve"] + plan["work_reserve"])

    def test_insufficient_selected_work_filesystem_is_rejected_even_with_ample_metadata_and_docker_space(self):
        wizard = self.wizard.Wizard()
        wizard.root = self.root / "migration-files"
        wizard.work_dir = self.root / "chosen-node-disk"
        wizard.docker_root = self.root / "docker-data"
        for path in (wizard.root, wizard.work_dir, wizard.docker_root):
            path.mkdir()

        def device(path, **kwargs):
            return types.SimpleNamespace(st_dev=2 if path == wizard.work_dir else 1)

        def free_space(path):
            return types.SimpleNamespace(free=2**30 if path == wizard.work_dir else 2**40)

        output = io.StringIO()
        with mock.patch.object(Path, "stat", autospec=True, side_effect=device), \
                mock.patch.object(self.wizard.os, "statvfs", return_value=types.SimpleNamespace(f_frsize=4096)), \
                mock.patch.object(self.wizard.shutil, "disk_usage", side_effect=free_space), \
                redirect_stdout(output), self.assertRaisesRegex(self.wizard.MigrationError, "TON work data"):
            wizard.check_space(self.space_probe())
        self.assertIn(str(wizard.work_dir), output.getvalue())
        self.assertFalse(wizard.donor_stopped)

    def test_docker_storage_uses_actual_upper_layer_and_volume_directory(self):
        docker_root = self.root / "docker-root"
        volumes = docker_root / "volumes"
        volumes.mkdir(parents=True)
        upper = self.root / "independent-writable-layer"
        upper.mkdir()
        inspected = {"GraphDriver": {"Name": "overlay2", "Data": {"UpperDir": str(upper)}}}
        self.assertEqual(self.wizard.docker_storage_paths(inspected, docker_root), (volumes, upper))

    def test_docker_storage_rejects_missing_explicit_upper_layer(self):
        docker_root = self.root / "docker-root"
        (docker_root / "overlay2").mkdir(parents=True)
        inspected = {"GraphDriver": {"Name": "overlay2", "Data": {"UpperDir": str(self.root / "missing-layer")}}}
        with self.assertRaises(self.wizard.MigrationError):
            self.wizard.docker_storage_paths(inspected, docker_root)

    def test_docker_storage_refuses_unknown_store_instead_of_assuming_root_filesystem(self):
        docker_root = self.root / "docker-root"
        docker_root.mkdir()
        # Ignore any unrelated containerd store on the host running the tests.
        with mock.patch.object(Path, "is_dir", autospec=True, side_effect=lambda path: path == docker_root):
            with self.assertRaises(self.wizard.MigrationError):
                self.wizard.docker_storage_paths({}, docker_root)

    def test_container_log_measurement_streams_all_bytes_and_rejects_driver_failure(self):
        wizard = self.wizard.Wizard()
        wizard.old_id = "original-container"
        contents = b"rotated log line\n" * 100000 + b"last log line\n"
        process = mock.MagicMock()
        process.__enter__.return_value = process
        process.stdout = io.BytesIO(contents)
        process.wait.return_value = 0
        with mock.patch.object(self.wizard.subprocess, "Popen", return_value=process):
            self.assertEqual(wizard.measure_logs(), len(contents))
        process.stdout = io.BytesIO(b"logger driver error\n")
        process.wait.return_value = 1
        with mock.patch.object(self.wizard.subprocess, "Popen", return_value=process):
            with self.assertRaises(self.wizard.MigrationError):
                wizard.measure_logs()

    def environment_writer(self, name, consent):
        wizard = self.wizard.Wizard(tty=io.StringIO(consent))
        wizard.root = self.root / name
        (wizard.root / "deployment").mkdir(parents=True)
        wizard.root.chmod(0o750)
        (wizard.root / "deployment").chmod(0o755)
        wizard.project = "environment-consent-test"
        wizard.settings = {"MYTONCTRL_IMAGE": "selected:new", "TON_WORK_HOST_DIR": str(wizard.root / "ton-work")}
        original = b"SECRET=original-value\r\nLITERAL=$HOME\r\n"
        path = wizard.root / "deployment/.env"
        path.write_bytes(original)
        path.chmod(0o640)
        return wizard, path, original

    def test_existing_environment_requires_explicit_yes_including_default_and_eof(self):
        for index, answer in enumerate(("no\n", "\n", "")):
            with self.subTest(answer=repr(answer)):
                wizard, path, original = self.environment_writer(f"cancel-{index}", answer)
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaises(self.wizard.MigrationError):
                    wizard.write_deployment("MYTONCTRL_IMAGE=template:image\n", "services: {}\n")
                self.assertIn(str(path), output.getvalue())
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
                self.assertEqual(stat.S_IMODE(wizard.root.stat().st_mode), 0o750)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o755)
                self.assertEqual({child.name for child in path.parent.iterdir()}, {".env"})
                self.assertFalse((wizard.root / "migration.json").exists())

    def test_confirmed_environment_replacement_is_atomic_private_and_backed_up(self):
        wizard, path, original = self.environment_writer("accept", "yes\n")
        original_inode = path.stat().st_ino
        caller_env = self.root / ".env"
        caller_env.write_text("CALLER_CONFIGURATION=untouched\n")
        output = io.StringIO()
        with redirect_stdout(output):
            wizard.write_deployment("MYTONCTRL_IMAGE=template:image\n", "services: {}\n")
        self.assertIn(str(path), output.getvalue())
        self.assertEqual(self.wizard.parse_env(path.read_text())["MYTONCTRL_IMAGE"], "selected:new")
        self.assertNotEqual(path.stat().st_ino, original_inode)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(wizard.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        backup = path.with_name(".env.before-migration")
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(caller_env.read_text(), "CALLER_CONFIGURATION=untouched\n")
        self.assertFalse(any(child.name.startswith(".env.") and child.name != backup.name
                             for child in path.parent.iterdir()))

    def test_environment_backup_uses_unique_names_and_never_replaces_existing_backups(self):
        wizard, path, original = self.environment_writer("backup-collision", "yes\n")
        first = path.with_name(".env.before-migration")
        second = path.with_name(".env.before-migration.1")
        first.write_bytes(b"older backup zero")
        second.write_bytes(b"older backup one")
        with redirect_stdout(io.StringIO()):
            wizard.write_deployment("MYTONCTRL_IMAGE=template:image\n", "services: {}\n")
        self.assertEqual(first.read_bytes(), b"older backup zero")
        self.assertEqual(second.read_bytes(), b"older backup one")
        third = path.with_name(".env.before-migration.2")
        self.assertEqual(third.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(third.stat().st_mode), 0o600)

    def test_destination_accepts_an_empty_directory_or_only_deployment_and_regular_environment(self):
        for name, contents in (("empty", None), ("deployment-only", "deployment"), ("environment-only", ".env")):
            with self.subTest(contents=contents):
                destination = self.root / name
                destination.mkdir()
                if contents:
                    (destination / "deployment").mkdir()
                if contents == ".env":
                    (destination / "deployment/.env").write_text("EXISTING=configuration\n")
                before = file_digests(destination)
                self.assertEqual(self.wizard.ensure_destination_isolated(destination, [self.donor]), destination.resolve())
                self.assertEqual(file_digests(destination), before)

    def test_destination_refuses_node_data_prior_state_compose_and_linked_environments(self):
        invalid = ("ton-work/data", "legacy/data", "migration.json", "backup.tar.gz",
                   "deployment/compose.yml", "deployment/compose.yaml", "deployment/unexpected", ".env")
        for index, name in enumerate(invalid):
            with self.subTest(contents=name):
                destination = self.root / f"unexpected-{index}"
                path = destination / name
                path.parent.mkdir(parents=True)
                path.write_text("original contents\n")
                before = file_digests(destination)
                with self.assertRaises(self.wizard.MigrationError):
                    self.wizard.ensure_destination_isolated(destination, [self.donor])
                self.assertEqual(file_digests(destination), before)
        for index, kind in enumerate(("deployment symlink", "env symlink", "env hardlink")):
            with self.subTest(link=kind):
                destination = self.root / f"linked-{index}"
                destination.mkdir()
                target = self.root / f"link-target-{index}"
                if kind == "deployment symlink":
                    target.mkdir()
                    (destination / "deployment").symlink_to(target, target_is_directory=True)
                else:
                    (destination / "deployment").mkdir()
                    target.write_text("external configuration\n")
                    if kind == "env symlink":
                        (destination / "deployment/.env").symlink_to(target)
                    else:
                        os.link(target, destination / "deployment/.env")
                with self.assertRaises(self.wizard.MigrationError):
                    self.wizard.ensure_destination_isolated(destination, [self.donor])
                if target.is_file():
                    self.assertEqual(target.read_text(), "external configuration\n")

    def test_cancelled_environment_replacement_never_pulls_stops_or_creates_migration_state(self):
        original = b"EXISTING_DEPLOYMENT=preserved\n"
        wizard, calls, state = self.exercise_wizard(fail_at="env-cancel", existing_env=original, env_consent="no")
        self.assertEqual((wizard.root / "deployment/.env").read_bytes(), original)
        self.assertFalse((wizard.root / "migration.json").exists())
        self.assertFalse((wizard.root / "legacy").exists())
        self.assertFalse(wizard.donor_stopped)
        self.assertTrue(state["writer_running"])
        self.assertTrue(state["container_running"])
        self.assertFalse(state["pulled"])
        self.assertFalse(any(call[:2] == ["docker", "stop"] or call[:2] == ["docker", "update"]
                             or call[-2:-1] == ["stop"] for call in calls))

    def test_accepted_existing_environment_completes_migration_and_keeps_original_backup(self):
        original = b"PREVIOUS_DEPLOYMENT=preserved\r\n"
        wizard, _, state = self.exercise_wizard(existing_env=original, env_consent="yes")
        deployment = wizard.root / "deployment"
        self.assertEqual((deployment / ".env.before-migration").read_bytes(), original)
        self.assertEqual(stat.S_IMODE((deployment / ".env.before-migration").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(deployment.stat().st_mode), 0o700)
        self.assertEqual(self.wizard.parse_env((deployment / ".env").read_text())["NETWORK"], "mainnet")
        self.assertEqual(json.loads((wizard.root / "migration.json").read_text())["phase"], "verified")
        self.assertTrue(state["pulled"])
        self.assertFalse(state["container_running"])
        self.assertTrue((wizard.root / "ton-work/controller/initialized.json").is_file())


if __name__ == "__main__":
    unittest.main()
