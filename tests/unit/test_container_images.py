from pathlib import Path

import pytest

import mytonctrl
from mytonctrl import images


@pytest.mark.parametrize("tag", ["latest", "dev", "v1.2.3", "custom-tag"])
def test_controller_image_prefers_baked_reference_over_stale_environment(monkeypatch, tag):
    reference = f"ghcr.io/ton-blockchain/mytonctrl:{tag}"
    monkeypatch.setattr(mytonctrl, "__image_ref__", reference)
    monkeypatch.setattr(mytonctrl, "__version__", tag)
    monkeypatch.setenv("MYTONCTRL_IMAGE", "other/image:stale")

    assert images.get_controller_image_ref() == reference


def test_older_controller_image_uses_baked_tag_instead_of_stale_environment(monkeypatch):
    monkeypatch.setattr(mytonctrl, "__image_ref__", "")
    monkeypatch.setattr(mytonctrl, "__version__", "dev")
    monkeypatch.setenv("MYTONCTRL_IMAGE", "other/image:latest")

    assert images.get_controller_image_ref() == "dev"


def test_controller_without_build_identity_can_use_runtime_image_reference(monkeypatch):
    monkeypatch.setattr(mytonctrl, "__image_ref__", "")
    monkeypatch.setattr(mytonctrl, "__version__", "unknown")
    monkeypatch.setenv("MYTONCTRL_IMAGE", "mytonctrl:local")

    assert images.get_controller_image_ref() == "mytonctrl:local"


def test_controller_without_any_identity_reports_unknown(monkeypatch):
    monkeypatch.setattr(mytonctrl, "__image_ref__", "")
    monkeypatch.setattr(mytonctrl, "__version__", "unknown")
    monkeypatch.delenv("MYTONCTRL_IMAGE", raising=False)

    assert images.get_controller_image_ref() == "unknown (controller image)"


@pytest.mark.parametrize("reference", ["ghcr.io/ton-blockchain/ton:v2026.10", "ton@sha256:abcdef"])
def test_ton_image_uses_active_snapshot_instead_of_updated_provider_or_environment(
    tmp_path, monkeypatch, reference,
):
    active = tmp_path / "active"
    active.mkdir()
    (active / "image-ref").write_text(reference + "\n")
    provider = tmp_path / "provider"
    provider.mkdir()
    (provider / "image-ref").write_text("new-ton-image:latest\n")
    monkeypatch.setenv("TON_IMAGE", "configured-ton-image:new")
    monkeypatch.setenv("TON_ARTIFACTS_DIR", str(provider))

    assert images.get_ton_image_ref(active) == reference


@pytest.mark.parametrize("metadata", [None, "", "   \n", "one-image\nanother-image\n"])
def test_ton_mounts_without_valid_metadata_report_unknown(tmp_path, monkeypatch, metadata):
    if metadata is not None:
        (tmp_path / "image-ref").write_text(metadata)
    monkeypatch.setenv("TON_IMAGE", "configured-image:latest")

    assert images.get_ton_image_ref(tmp_path) == "unknown (mounted TON binaries)"


def test_unreadable_ton_metadata_does_not_break_status(monkeypatch):
    def unreadable(self):
        raise PermissionError("metadata unavailable")

    monkeypatch.setattr(Path, "read_text", unreadable)

    assert images.get_ton_image_ref() == "unknown (mounted TON binaries)"
