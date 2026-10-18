"""Image identities for the Docker status display."""

from __future__ import annotations

import os
from pathlib import Path

import mytonctrl


def _reference(value: str) -> str:
    value = value.strip()
    return value if value and not any(char.isspace() for char in value) else ""


def get_controller_image_ref() -> str:
    """Prefer identity baked into the running image over deployment settings."""
    reference = _reference(mytonctrl.__image_ref__)
    if reference:
        return reference
    version = _reference(mytonctrl.__version__)
    if version and version != "unknown":
        return version
    return _reference(os.getenv("MYTONCTRL_IMAGE", "")) or "unknown (controller image)"


def get_ton_image_ref(active: Path = Path("/run/ton-active")) -> str:
    """Read the identity pinned beside the binaries this container executes."""
    try:
        reference = _reference((active / "image-ref").read_text())
    except (OSError, UnicodeError):
        reference = ""
    return reference or "unknown (mounted TON binaries)"
