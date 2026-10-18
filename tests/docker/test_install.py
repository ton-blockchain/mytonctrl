"""Exercise the standalone deployment bootstrap without network or Docker."""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


INSTALL_SCRIPT = Path(__file__).resolve().parents[2] / "docker/install.sh"
EXISTING_NAMES = (".env", "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml",
                  "compose.override.yml", "compose.override.yaml", "docker-compose.override.yml",
                  "docker-compose.override.yaml")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.deployment = self.root / "deployment"
        self.deployment.mkdir()
        self.tools = self.root / "bin"
        self.tools.mkdir()
        # PATH contains no real downloader or Docker executable.
        for name in ("bash", "cat", "mktemp", "rm", "chmod", "ln", "jq"):
            self.assertIsNotNone(shutil.which(name), f"Missing test utility: {name}")
            (self.tools / name).symlink_to(shutil.which(name))
        self.download_log = self.root / "downloads.jsonl"
        self.docker_log = self.root / "docker-called"
        self.env_template = self.root / "env.example"
        self.env_contents = (
            "# Downloaded configuration stays literal.\n"
            "TON_IMAGE=ton-template:image\n"
            "MYTONCTRL_IMAGE=template:image\n"
            "PUBLIC_IP=\n"
            "MYTONCTRL_ARGS=-m validator -n mainnet -d\n"
            "SUBSTITUTION=$(touch unexpected)\n"
            "BACKTICKS=`touch unexpected-backtick`\n"
            "LITERAL=${HOME} # keep this text\n"
        )
        self.env_template.write_text(self.env_contents)
        self.compose_template = self.root / "compose-template.yml"
        self.compose_contents = "services:\n  mytonctrl:\n    image: ${MYTONCTRL_IMAGE}\n"
        self.compose_template.write_text(self.compose_contents)
        self.archive_template = self.root / "archive-template.yml"
        self.archive_contents = (
            "services:\n  ton-binaries:\n    volumes:\n"
            "      - ./tonutils-storage:/usr/local/bin/tonutils-storage:ro\n"
        )
        self.archive_template.write_text(self.archive_contents)
        self.storage_binary = self.root / "tonutils-storage-binary"
        self.storage_contents = b"\x7fELFmock archive storage executable\n"
        self.storage_binary.write_bytes(self.storage_contents)
        self.storage_version = "v9.8.7"
        self.storage_release = self.root / "storage-release.json"
        self.storage_release.write_text(json.dumps({"tag_name": self.storage_version}))
        self.environment = dict(os.environ)
        self.environment.update(
            PATH=str(self.tools),
            INSTALL_TEST_DOWNLOAD_LOG=str(self.download_log),
            INSTALL_TEST_DOCKER_LOG=str(self.docker_log),
            INSTALL_TEST_ENV_TEMPLATE=str(self.env_template),
            INSTALL_TEST_COMPOSE_TEMPLATE=str(self.compose_template),
            INSTALL_TEST_ARCHIVE_TEMPLATE=str(self.archive_template),
            INSTALL_TEST_STORAGE_BINARY=str(self.storage_binary),
            INSTALL_TEST_STORAGE_RELEASE=str(self.storage_release),
        )
        uname = self.tools / "uname"
        uname.write_text(
            f"#!{sys.executable}\n"
            "import os\nimport sys\n"
            "print(os.environ.get('INSTALL_TEST_ARCH', 'x86_64') if sys.argv[1] == '-m' "
            "else os.environ.get('INSTALL_TEST_OS', 'Linux'))\n"
        )
        uname.chmod(0o755)
        docker = self.tools / "docker"
        docker.write_text(
            f"#!{sys.executable}\n"
            "import os\nfrom pathlib import Path\n"
            "Path(os.environ['INSTALL_TEST_DOCKER_LOG']).write_text('unexpected Docker invocation')\n"
            "raise SystemExit(99)\n"
        )
        docker.chmod(0o755)

    def downloader(self, name):
        executable = self.tools / name
        executable.write_text(
            f"#!{sys.executable}\n"
            "import json\nimport os\nfrom pathlib import Path\nimport shutil\nimport sys\n"
            "args = sys.argv[1:]\n"
            "tool = Path(sys.argv[0]).name\n"
            "flag = '--output' if tool == 'curl' else '-O'\n"
            "destination = Path(args[args.index(flag) + 1])\n"
            "url = args[-1]\n"
            "log = Path(os.environ['INSTALL_TEST_DOWNLOAD_LOG'])\n"
            "count = len(log.read_text().splitlines()) if log.exists() else 0\n"
            "with log.open('a') as output:\n"
            "    output.write(json.dumps({'tool': tool, 'url': url, 'args': args}) + '\\n')\n"
            "if count + 1 == int(os.environ.get('INSTALL_TEST_FAIL_DOWNLOAD', '0')):\n"
            "    destination.write_text('partial download')\n"
            "    raise SystemExit(22)\n"
            "if url.endswith('/.env.example'):\n"
            "    source = os.environ['INSTALL_TEST_ENV_TEMPLATE']\n"
            "elif url.endswith('/docker/compose.yml'):\n"
            "    source = os.environ['INSTALL_TEST_COMPOSE_TEMPLATE']\n"
            "elif url.endswith('/docker/compose.archive.yml'):\n"
            "    source = os.environ['INSTALL_TEST_ARCHIVE_TEMPLATE']\n"
            "elif url == 'https://api.github.com/repos/xssnick/tonutils-storage/releases/latest':\n"
            "    source = os.environ['INSTALL_TEST_STORAGE_RELEASE']\n"
            "elif '/releases/download/' in url and '/tonutils-storage-linux-' in url:\n"
            "    source = os.environ['INSTALL_TEST_STORAGE_BINARY']\n"
            "else:\n"
            "    raise SystemExit('Unexpected asset URL: ' + url)\n"
            "shutil.copyfile(source, destination)\n"
        )
        executable.chmod(0o755)

    def run_install(self, args=(), stdin=False, directory=None, success=True):
        directory = directory or self.deployment
        if stdin:
            command = [str(self.tools / "bash"), "-s", "--", *args]
            payload = INSTALL_SCRIPT.read_text()
        else:
            command = [str(INSTALL_SCRIPT), *args]
            payload = None
        result = subprocess.run(command, input=payload, cwd=directory, env=self.environment,
                                capture_output=True, text=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.docker_log.exists(), "The bootstrap must not start Docker")
        self.assertFalse(list(directory.glob(".mytonctrl-install.*")), "Download staging files must be removed")
        return result

    def requests(self):
        if not self.download_log.exists():
            return []
        return [json.loads(line) for line in self.download_log.read_text().splitlines()]

    def assert_deployment(self, image, branch="master", tool="curl"):
        self.assertEqual((self.deployment / ".env").read_text(),
                         self.env_contents.replace("MYTONCTRL_IMAGE=template:image", "MYTONCTRL_IMAGE=" + image))
        self.assertEqual((self.deployment / "compose.yml").read_text(), self.compose_contents)
        self.assertEqual(stat.S_IMODE((self.deployment / ".env").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.deployment / "compose.yml").stat().st_mode), 0o644)
        self.assertEqual({path.name for path in self.deployment.iterdir()}, {".env", "compose.yml"})
        self.assertFalse((self.deployment / "unexpected").exists())
        self.assertFalse((self.deployment / "unexpected-backtick").exists())
        base = f"https://raw.githubusercontent.com/ton-blockchain/mytonctrl/{branch}"
        self.assertEqual([(request["tool"], request["url"]) for request in self.requests()],
                         [(tool, base + "/.env.example"), (tool, base + "/docker/compose.yml")])

    def assert_archive_deployment(self, arch="amd64", branch="master", tool="curl", image=None,
                                  ton_image=None, contents=None, directory=None):
        directory = directory or self.deployment
        image = image or f"ghcr.io/ton-blockchain/mytonctrl:{'latest' if branch == 'master' else 'dev'}"
        expected = (contents or self.env_contents).replace("MYTONCTRL_IMAGE=template:image",
                                                          "MYTONCTRL_IMAGE=" + image)
        expected = expected.replace("MYTONCTRL_ARGS=-m validator -n mainnet -d",
                                    "MYTONCTRL_ARGS=-m liteserver -n mainnet --archive")
        if ton_image:
            expected = expected.replace("TON_IMAGE=ton-template:image", "TON_IMAGE=" + ton_image)
        if "DUMP=true\n" in expected:
            expected = expected.replace("DUMP=true\n", "DUMP=false\n")
        else:
            expected += "DUMP=false\n"
        self.assertEqual((directory / ".env").read_text(), expected)
        self.assertEqual((directory / "compose.yml").read_text(), self.compose_contents)
        self.assertEqual((directory / "compose.override.yml").read_text(), self.archive_contents)
        self.assertEqual((directory / "tonutils-storage").read_bytes(), self.storage_contents)
        self.assertEqual({path.name for path in directory.iterdir()},
                         {".env", "compose.yml", "compose.override.yml", "tonutils-storage"})
        for name, mode in ((".env", 0o600), ("compose.yml", 0o644), ("compose.override.yml", 0o644),
                           ("tonutils-storage", 0o755)):
            self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode), mode)
        base = f"https://raw.githubusercontent.com/ton-blockchain/mytonctrl/{branch}"
        self.assertEqual([(request["tool"], request["url"]) for request in self.requests()], [
            (tool, base + "/.env.example"),
            (tool, base + "/docker/compose.yml"),
            (tool, base + "/docker/compose.archive.yml"),
            (tool, "https://api.github.com/repos/xssnick/tonutils-storage/releases/latest"),
            (tool, "https://github.com/xssnick/tonutils-storage/releases/download/"
                   f"{self.storage_version}/tonutils-storage-linux-{arch}"),
        ])

    def test_executable_bootstrap_fetches_only_two_assets_and_defaults_to_latest(self):
        self.downloader("curl")
        self.downloader("wget")
        self.run_install()
        self.assert_deployment("ghcr.io/ton-blockchain/mytonctrl:latest")

    def test_wget_stdin_bootstrap_selects_dev_assets_and_image(self):
        self.downloader("wget")
        self.run_install(["--branch", "dev"], stdin=True)
        self.assert_deployment("ghcr.io/ton-blockchain/mytonctrl:dev", branch="dev", tool="wget")

    def test_explicit_master_branch_selects_latest_image(self):
        self.downloader("curl")
        self.run_install(["--branch", "master"])
        self.assert_deployment("ghcr.io/ton-blockchain/mytonctrl:latest")

    def test_custom_image_changes_only_image_setting_and_keeps_asset_branch(self):
        self.downloader("wget")
        image = "registry.example.org/team/controller@sha256:" + "a" * 64
        self.run_install(["--branch", "dev", "--image", image], stdin=True)
        self.assert_deployment(image, branch="dev", tool="wget")

    def test_ton_image_override_preserves_ordinary_installation(self):
        self.downloader("curl")
        ton_image = "ghcr.io/ton-blockchain/ton:v2026.10"
        self.run_install(["--ton-image", ton_image])
        self.env_contents = self.env_contents.replace("TON_IMAGE=ton-template:image", "TON_IMAGE=" + ton_image)
        self.assert_deployment("ghcr.io/ton-blockchain/mytonctrl:latest")

    def test_archive_curl_downloads_amd64_binary_and_pins_both_images(self):
        self.downloader("curl")
        image = "ghcr.io/ton-blockchain/mytonctrl:v1.0.2"
        ton_image = "ghcr.io/ton-blockchain/ton:v2026.10"
        result = self.run_install(["--archive", "--image", image, "--ton-image", ton_image])
        self.assert_archive_deployment(image=image, ton_image=ton_image)
        self.assertIn("mainnet", (self.deployment / ".env").read_text())
        self.assertIn(f"compose.override.yml and tonutils-storage {self.storage_version}", result.stdout)
        self.assertFalse((self.deployment / "unexpected").exists())
        self.assertFalse((self.deployment / "unexpected-backtick").exists())

    def test_archive_wget_stdin_accepts_both_arm64_architecture_names(self):
        self.downloader("wget")
        for architecture in ("aarch64", "arm64"):
            with self.subTest(architecture=architecture):
                self.environment["INSTALL_TEST_ARCH"] = architecture
                directory = self.root / architecture
                directory.mkdir()
                self.download_log.unlink(missing_ok=True)
                self.run_install(["--archive", "--branch", "dev"], stdin=True, directory=directory)
                self.assert_archive_deployment(arch="arm64", branch="dev", tool="wget", directory=directory)

    def test_archive_replaces_existing_dump_setting_without_duplicating_it(self):
        self.downloader("curl")
        self.env_contents += "DUMP=true\n"
        self.env_template.write_text(self.env_contents)
        self.run_install(["--archive"])
        self.assert_archive_deployment()

    def test_archive_uses_the_new_release_tag_from_github(self):
        self.downloader("curl")
        self.storage_version = "v10.2.4"
        self.storage_release.write_text(json.dumps({"tag_name": self.storage_version}))
        result = self.run_install(["--archive"])
        self.assert_archive_deployment()
        self.assertIn(f"tonutils-storage {self.storage_version}", result.stdout)

    def test_archive_invalid_release_metadata_installs_nothing(self):
        self.downloader("wget")
        responses = ["not JSON", "{}", '{"tag_name": null}', '{"tag_name": 12}',
                     '{"tag_name": ""}', '{"tag_name": "../unsafe"}',
                     '{"tag_name": "$(touch unexpected)"}']
        for response in responses:
            with self.subTest(response=response):
                self.storage_release.write_text(response)
                self.download_log.unlink(missing_ok=True)
                result = self.run_install(["--archive"], success=False)
                self.assertIn("tonutils-storage release tag", result.stderr)
                self.assertEqual(len(self.requests()), 4)
                self.assertEqual(list(self.deployment.iterdir()), [])

    def test_archive_requires_jq_before_downloading(self):
        self.downloader("curl")
        (self.tools / "jq").unlink()
        result = self.run_install(["--archive"], success=False)
        self.assertIn("Install jq", result.stderr)
        self.assertEqual(self.requests(), [])
        self.assertEqual(list(self.deployment.iterdir()), [])

    def test_ordinary_installation_does_not_require_jq(self):
        self.downloader("wget")
        (self.tools / "jq").unlink()
        self.run_install()
        self.assert_deployment("ghcr.io/ton-blockchain/mytonctrl:latest", tool="wget")

    def test_archive_rejects_unsupported_architecture_or_os_before_download(self):
        self.downloader("curl")
        for os_name, architecture in (("Linux", "riscv64"), ("Darwin", "arm64")):
            with self.subTest(os_name=os_name, architecture=architecture):
                self.environment.update(INSTALL_TEST_OS=os_name, INSTALL_TEST_ARCH=architecture)
                self.run_install(["--archive"], success=False)
                self.assertEqual(list(self.deployment.iterdir()), [])
                self.assertEqual(self.requests(), [])

    def test_archive_failed_or_empty_download_leaves_no_output(self):
        self.downloader("wget")
        for download in (3, 4, 5):
            with self.subTest(download=download):
                self.download_log.unlink(missing_ok=True)
                self.environment["INSTALL_TEST_FAIL_DOWNLOAD"] = str(download)
                result = self.run_install(["--archive"], success=False)
                self.assertIn("Download failed", result.stderr)
                self.assertEqual(len(self.requests()), download)
                self.assertEqual(list(self.deployment.iterdir()), [])
        self.environment.pop("INSTALL_TEST_FAIL_DOWNLOAD")
        self.storage_binary.write_bytes(b"")
        result = self.run_install(["--archive"], success=False)
        self.assertIn("Downloaded file is empty", result.stderr)
        self.assertEqual(list(self.deployment.iterdir()), [])

    def test_archive_existing_binary_file_or_dangling_symlink_is_preserved(self):
        self.downloader("curl")
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                directory = self.root / f"archive-existing-{symlink}"
                directory.mkdir()
                binary = directory / "tonutils-storage"
                if symlink:
                    binary.symlink_to("missing-target")
                else:
                    binary.write_text("existing binary")
                self.run_install(["--archive"], directory=directory, success=False)
                self.assertEqual({path.name for path in directory.iterdir()}, {"tonutils-storage"})
                if symlink:
                    self.assertEqual(os.readlink(binary), "missing-target")
                else:
                    self.assertEqual(binary.read_text(), "existing binary")
        self.assertEqual(self.requests(), [])

    def test_ordinary_installation_preserves_unrelated_storage_binary(self):
        self.downloader("curl")
        binary = self.deployment / "tonutils-storage"
        binary.write_text("existing binary")
        self.run_install()
        self.assertEqual(binary.read_text(), "existing binary")
        self.assertEqual(len(self.requests()), 2)

    def test_publication_failure_rolls_back_own_outputs_and_preserves_racing_file(self):
        self.downloader("curl")
        real_ln = shutil.which("ln")
        (self.tools / "ln").unlink()
        wrapper = self.tools / "ln"
        wrapper.write_text(
            f"#!{sys.executable}\n"
            "import os\nfrom pathlib import Path\nimport sys\n"
            "if sys.argv[-1] == 'tonutils-storage':\n"
            "    replacement = Path('replacement.yml')\n"
            "    replacement.write_text('replacement by another process')\n"
            "    replacement.replace('compose.yml')\n"
            "    Path('tonutils-storage').mkdir()\n"
            "    Path('tonutils-storage/existing').write_text('preserved data')\n"
            f"os.execv({real_ln!r}, [{real_ln!r}, *sys.argv[1:]])\n"
        )
        wrapper.chmod(0o755)
        result = self.run_install(["--archive"], success=False)
        self.assertIn("Could not install tonutils-storage", result.stderr)
        self.assertEqual({path.name for path in self.deployment.iterdir()}, {"compose.yml", "tonutils-storage"})
        self.assertEqual((self.deployment / "compose.yml").read_text(), "replacement by another process")
        self.assertEqual((self.deployment / "tonutils-storage/existing").read_text(), "preserved data")

    def test_failed_second_download_installs_neither_file_and_removes_staging(self):
        self.downloader("curl")
        self.environment["INSTALL_TEST_FAIL_DOWNLOAD"] = "2"
        result = self.run_install(success=False)
        self.assertIn("Download failed", result.stderr)
        self.assertEqual(len(self.requests()), 2)
        self.assertEqual(list(self.deployment.iterdir()), [])

    def test_empty_second_download_installs_neither_file(self):
        self.downloader("wget")
        self.compose_template.write_text("")
        result = self.run_install(stdin=True, success=False)
        self.assertIn("Downloaded file is empty", result.stderr)
        self.assertEqual(list(self.deployment.iterdir()), [])

    def test_existing_environment_or_any_compose_filename_is_preserved(self):
        self.downloader("curl")
        for index, name in enumerate(EXISTING_NAMES):
            directory = self.root / f"existing-file-{index}"
            directory.mkdir()
            original = directory / name
            original.write_text("existing deployment must survive\n")
            with self.subTest(name=name):
                result = self.run_install(directory=directory, success=False)
                self.assertIn(name + " already exists", result.stderr)
                self.assertEqual(original.read_text(), "existing deployment must survive\n")
                self.assertEqual({path.name for path in directory.iterdir()}, {name})
        self.assertEqual(self.requests(), [])

    def test_existing_dangling_symlinks_are_preserved_before_download(self):
        self.downloader("wget")
        for index, name in enumerate(EXISTING_NAMES):
            directory = self.root / f"existing-link-{index}"
            directory.mkdir()
            original = directory / name
            original.symlink_to("missing-target")
            with self.subTest(name=name):
                result = self.run_install(stdin=True, directory=directory, success=False)
                self.assertIn(name + " already exists", result.stderr)
                self.assertTrue(original.is_symlink())
                self.assertEqual(os.readlink(original), "missing-target")
                self.assertEqual({path.name for path in directory.iterdir()}, {name})
        self.assertEqual(self.requests(), [])

    def test_existing_symlink_and_its_target_are_preserved(self):
        self.downloader("curl")
        target = self.root / "existing-config"
        target.write_text("external deployment configuration\n")
        original = self.deployment / "compose.yaml"
        original.symlink_to(target)
        self.run_install(success=False)
        self.assertTrue(original.is_symlink())
        self.assertEqual(target.read_text(), "external deployment configuration\n")
        self.assertEqual(self.requests(), [])

    def test_existing_compose_directory_is_preserved(self):
        self.downloader("curl")
        original = self.deployment / "compose.yml"
        original.mkdir()
        (original / "data").write_text("preserved")
        self.run_install(success=False)
        self.assertEqual((original / "data").read_text(), "preserved")
        self.assertEqual(self.requests(), [])

    def test_invalid_flags_and_images_fail_before_fetch_or_filesystem_changes(self):
        self.downloader("curl")
        invalid = (["--unknown"], ["--branch"], ["--image"], ["--ton-image"], ["--branch", "other"],
                   ["--image", "image with spaces"], ["--image", "$(touch unexpected)"],
                   ["--ton-image", "image with spaces"], ["--ton-image", "$(touch unexpected)"])
        for args in invalid:
            with self.subTest(args=args):
                self.run_install(args, success=False)
                self.assertEqual(list(self.deployment.iterdir()), [])
        self.assertEqual(self.requests(), [])

    def test_help_needs_no_downloader_or_docker(self):
        result = self.run_install(["--help"], stdin=True)
        self.assertIn("--branch master|dev", result.stdout)
        self.assertIn("--ton-image IMAGE", result.stdout)
        self.assertIn("--archive", result.stdout)
        self.assertIn("does not start containers", result.stdout)
        self.assertEqual(self.requests(), [])
        self.assertEqual(list(self.deployment.iterdir()), [])

    def test_missing_downloader_fails_without_creating_deployment_files(self):
        result = self.run_install(success=False)
        self.assertIn("Install wget or curl", result.stderr)
        self.assertEqual(list(self.deployment.iterdir()), [])

    def test_ambiguous_image_template_installs_neither_file(self):
        self.downloader("wget")
        self.env_template.write_text("MYTONCTRL_IMAGE=first\nMYTONCTRL_IMAGE=second\n")
        result = self.run_install(stdin=True, success=False)
        self.assertIn("must contain one MYTONCTRL_IMAGE", result.stderr)
        self.assertEqual(len(self.requests()), 2)
        self.assertEqual(list(self.deployment.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
