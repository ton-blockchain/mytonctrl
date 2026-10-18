"""Exercise artifact publication without downloading TON or starting a node."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


EXPORT_SCRIPT = Path(__file__).resolve().parents[2] / "docker" / "export-ton.sh"
BINARIES = (
    "validator-engine",
    "validator-engine-console",
    "lite-client",
    "generate-random-id",
    "fift",
    "func",
)


class ExportTonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.artifacts = self.root / "artifacts"
        self.environment = dict(os.environ)
        self.environment.update(
            TON_ARTIFACTS_DIR=str(self.artifacts),
            TON_EXPORT_BIN_DIR=str(self.source / "bin"),
            TON_EXPORT_FIFT_DIR=str(self.source / "fift"),
            TON_EXPORT_SMARTCONT_DIR=str(self.source / "smartcont"),
            TON_IMAGE_REF="ghcr.io/ton-blockchain/ton:test",
        )
        for directory in ("bin", "fift", "smartcont"):
            (self.source / directory).mkdir(parents=True)
        for binary in BINARIES:
            path = self.source / "bin" / binary
            path.write_text("#!/bin/sh\nprintf 'fake TON binary\\n'\n")
            path.chmod(0o755)
        for resource in ("Fift.fif", "TonUtil.fif", "Asm.fif"):
            (self.source / "fift" / resource).write_text("// Fift library\n")
        for resource in ("wallet-v3.fif", "validator-elect-signed.fif"):
            (self.source / "smartcont" / resource).write_text("// wallet contract\n")

    def export(self, success=True, environment=None):
        result = subprocess.run(
            ["/bin/sh", str(EXPORT_SCRIPT)],
            env=environment or self.environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def current_release(self):
        return (self.artifacts / "current").resolve(strict=True)

    def assert_no_staging_files(self):
        self.assertFalse(list(self.artifacts.glob("releases/.staging.*")))
        self.assertFalse(list(self.artifacts.glob(".publish.*")))

    def test_repeated_publication_reuses_release(self):
        self.export()
        release = self.current_release()
        binary = release / "bin" / "validator-engine"
        original_inode = binary.stat().st_ino
        self.environment["TON_IMAGE_REF"] = "different-tag-for-same-content"
        os.utime(self.source / "bin" / "validator-engine", (1, 1))
        self.export()
        self.assertEqual(self.current_release(), release)
        self.assertEqual(binary.stat().st_ino, original_inode)
        self.assertEqual((release / "image-ref").read_text(), "different-tag-for-same-content\n")
        self.assert_no_staging_files()

    def test_separately_supplied_archive_downloader_is_published_with_ton_binaries(self):
        downloader = self.source / "bin" / "tonutils-storage"
        downloader.write_text("#!/bin/sh\nprintf 'archive downloader\\n'\n")
        downloader.chmod(0o755)
        self.export()
        published = self.current_release() / "bin" / "tonutils-storage"
        self.assertEqual(published.read_bytes(), downloader.read_bytes())
        self.assertEqual(published.stat().st_mode & 0o777, 0o755)

    def test_export_without_identity_does_not_retain_a_previous_image_reference(self):
        self.export()
        release = self.current_release()
        self.environment.pop("TON_IMAGE_REF")
        self.export()
        self.assertEqual(self.current_release(), release)
        self.assertFalse((release / "image-ref").exists())

    def test_same_content_retag_preserves_identity_of_an_active_controller_snapshot(self):
        self.export()
        release = self.current_release()
        active = self.root / "active"
        subprocess.run(
            [sys.executable, "-c",
             "from pathlib import Path; import sys; from entrypoint import snapshot_artifacts; "
             "root = Path(sys.argv[1]); snapshot_artifacts(tuple(root / name for name in "
             "('bin', 'fift', 'smartcont')), Path(sys.argv[2]))",
             str(release), str(active)],
            cwd=EXPORT_SCRIPT.parent, check=True, timeout=15,
        )
        self.environment["TON_IMAGE_REF"] = "ghcr.io/ton-blockchain/ton:retagged"
        self.export()

        self.assertEqual(self.current_release(), release)
        self.assertEqual((release / "image-ref").read_text(), "ghcr.io/ton-blockchain/ton:retagged\n")
        self.assertEqual((active / "image-ref").read_text(), "ghcr.io/ton-blockchain/ton:test\n")
        self.assertEqual((active / "bin/validator-engine").read_bytes(),
                         (release / "bin/validator-engine").read_bytes())

    def test_new_content_publishes_release_and_preserves_old_binaries(self):
        self.export()
        old_release = self.current_release()
        old_bytes = (old_release / "bin" / "validator-engine").read_bytes()
        (self.source / "bin" / "validator-engine").write_text("#!/bin/sh\nprintf 'new version\\n'\n")
        self.export()
        self.assertNotEqual(self.current_release(), old_release)
        self.assertEqual((old_release / "bin" / "validator-engine").read_bytes(), old_bytes)
        self.assertEqual(len(list((self.artifacts / "releases").iterdir())), 2)
        self.assert_no_staging_files()

    def test_executable_permissions_are_part_of_release_identity(self):
        self.export()
        old_release = self.current_release()
        (self.source / "bin" / "validator-engine").chmod(0o750)
        self.export()
        self.assertNotEqual(self.current_release(), old_release)
        self.assertEqual((old_release / "bin" / "validator-engine").stat().st_mode & 0o777, 0o755)

    def test_invalid_source_does_not_change_current_release(self):
        self.export()
        old_release = self.current_release()
        (self.source / "fift" / "TonUtil.fif").unlink()
        result = self.export(success=False)
        self.assertIn("missing resource", result.stderr)
        self.assertEqual(self.current_release(), old_release)
        self.assert_no_staging_files()

    def test_corrupted_existing_release_is_rejected(self):
        self.export()
        old_release = self.current_release()
        (old_release / "bin" / "validator-engine").write_text("corrupted binary")
        result = self.export(success=False)
        self.assertIn("existing release has been modified", result.stderr)
        self.assertEqual(self.current_release(), old_release)
        self.assert_no_staging_files()

    def test_source_symlinks_become_self_contained_files(self):
        real_binary = self.root / "actual-validator"
        real_binary.write_text("#!/bin/sh\nprintf 'symlink target\\n'\n")
        real_binary.chmod(0o755)
        source_binary = self.source / "bin" / "validator-engine"
        source_binary.unlink()
        source_binary.symlink_to(real_binary)
        self.export()
        published_binary = self.current_release() / "bin" / "validator-engine"
        self.assertFalse(published_binary.is_symlink())
        self.assertEqual(published_binary.read_bytes(), real_binary.read_bytes())

    def test_concurrent_exports_publish_one_complete_release(self):
        processes = [
            subprocess.Popen(
                ["/bin/sh", str(EXPORT_SCRIPT)],
                env=self.environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr or stdout)
        release = self.current_release()
        self.assertTrue((release / "bin" / "validator-engine").is_file())
        self.assertEqual(len(list((self.artifacts / "releases").iterdir())), 1)
        self.assert_no_staging_files()


if __name__ == "__main__":
    unittest.main()
