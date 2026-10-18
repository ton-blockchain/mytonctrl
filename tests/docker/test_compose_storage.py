"""Check actual Compose interpolation without starting the node or using Docker's daemon."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = (ROOT / "compose.yaml", ROOT / "docker/compose.yml")
ARCHIVE_COMPOSE = ROOT / "docker/compose.archive.yml"


def compose_available():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(
            ["docker", "compose", "version"], capture_output=True, timeout=10
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(compose_available(), "Docker Compose is not installed")
class ComposeStorageTests(unittest.TestCase):
    def render(self, compose_file, host_dir, work_volume="mytonctrl-ton-work"):
        environment = {
            **os.environ,
            "MYTONCTRL_ENV_FILE": str(ROOT / ".env.example"),
            "TON_WORK_VOLUME": work_volume,
        }
        if host_dir is None:
            environment.pop("TON_WORK_HOST_DIR", None)
        else:
            environment["TON_WORK_HOST_DIR"] = host_dir
        return subprocess.run(
            ["docker", "compose", "--env-file", str(ROOT / ".env.example"),
             "-f", str(compose_file), "config", "--format", "json"],
            env=environment, capture_output=True, text=True, timeout=20,
        )

    def test_configured_directory_with_spaces_is_used_without_a_data_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            host_dir = Path(directory) / "external disk" / "ton-work"
            host_dir.mkdir(parents=True)
            for compose_file in COMPOSE_FILES:
                with self.subTest(compose_file=compose_file.name):
                    result = self.render(compose_file, str(host_dir))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    config = json.loads(result.stdout)
                    mounts = config["services"]["mytonctrl"]["volumes"]
                    work = next(mount for mount in mounts if mount["target"] == "/var/ton-work")
                    self.assertEqual(work["type"], "bind")
                    self.assertEqual(work["source"], str(host_dir))
                    self.assertNotIn("ton-work", config["volumes"])

    def test_blank_or_unset_storage_path_uses_the_original_named_volume(self):
        for compose_file in COMPOSE_FILES:
            for host_dir in ("", None):
                with self.subTest(compose_file=compose_file.name, host_dir=host_dir):
                    result = self.render(compose_file, host_dir)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    config = json.loads(result.stdout)
                    mounts = config["services"]["mytonctrl"]["volumes"]
                    work = next(mount for mount in mounts if mount["target"] == "/var/ton-work")
                    self.assertEqual(work["type"], "volume")
                    self.assertEqual(work["source"], "ton-work")
                    self.assertEqual(config["volumes"]["ton-work"]["name"], "mytonctrl-ton-work")

    def test_custom_named_volume_is_preserved_when_host_path_is_blank(self):
        for compose_file in COMPOSE_FILES:
            with self.subTest(compose_file=compose_file.name):
                result = self.render(compose_file, "", "existing-ton-work")
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(result.stdout)
                self.assertEqual(config["volumes"]["ton-work"]["name"], "existing-ton-work")


@unittest.skipUnless(compose_available(), "Docker Compose is not installed")
class ComposeArchiveTests(unittest.TestCase):
    def test_archive_override_preserves_exporter_mounts_with_each_base(self):
        environment = {
            **os.environ,
            "MYTONCTRL_ENV_FILE": str(ROOT / ".env.example"),
        }
        for compose_file in COMPOSE_FILES:
            with self.subTest(compose_file=str(compose_file.relative_to(ROOT))):
                result = subprocess.run(
                    ["docker", "compose", "--env-file", str(ROOT / ".env.example"),
                     "-f", str(compose_file), "-f", str(ARCHIVE_COMPOSE),
                     "config", "--format", "json"],
                    env=environment, capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(result.stdout)
                mounts = {
                    mount["target"]: mount
                    for mount in config["services"]["ton-binaries"]["volumes"]
                }
                self.assertEqual(mounts["/ton-artifacts"]["source"], "ton-artifacts")
                self.assertEqual(mounts["/scripts"]["source"], "ton-scripts")
                self.assertTrue(mounts["/scripts"]["read_only"])
                storage = mounts["/usr/local/bin/tonutils-storage"]
                self.assertEqual(storage["type"], "bind")
                self.assertEqual(storage["source"], str(compose_file.parent / "tonutils-storage"))
                self.assertTrue(storage["read_only"])
                self.assertFalse(storage["bind"]["create_host_path"])

    def test_deployment_autoloads_archive_override_without_creating_missing_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory)
            shutil.copyfile(ROOT / "docker/compose.yml", deployment / "compose.yml")
            shutil.copyfile(ARCHIVE_COMPOSE, deployment / "compose.override.yml")
            archive_env = (ROOT / ".env.example").read_text().replace(
                "MYTONCTRL_ARGS=-m validator -n mainnet -d",
                "MYTONCTRL_ARGS=-m liteserver -n mainnet --archive",
            )
            (deployment / ".env").write_text(archive_env + "\nDUMP=false\n")
            host_dir = deployment / "archive disk" / "ton-work"
            environment = dict(os.environ)
            environment.pop("COMPOSE_FILE", None)
            environment.update(
                MYTONCTRL_ENV_FILE=".env",
                TON_WORK_HOST_DIR=str(host_dir),
            )
            result = subprocess.run(
                ["docker", "compose", "--env-file", ".env", "config", "--format", "json"],
                cwd=deployment, env=environment, capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(result.stdout)
            storage = next(
                mount for mount in config["services"]["ton-binaries"]["volumes"]
                if mount["target"] == "/usr/local/bin/tonutils-storage"
            )
            self.assertEqual(storage["source"], str(deployment / "tonutils-storage"))
            self.assertFalse(storage["bind"]["create_host_path"])
            self.assertFalse((deployment / "tonutils-storage").exists())
            controller = config["services"]["mytonctrl"]
            self.assertEqual(controller["environment"]["MYTONCTRL_ARGS"],
                             "-m liteserver -n mainnet --archive")
            self.assertEqual(controller["environment"]["DUMP"], "false")
            work = next(mount for mount in controller["volumes"]
                        if mount["target"] == "/var/ton-work")
            self.assertEqual(work["source"], str(host_dir))
            self.assertNotIn("ton-work", config["volumes"])


if __name__ == "__main__":
    unittest.main()
