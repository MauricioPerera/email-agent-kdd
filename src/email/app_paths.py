"""Platform-neutral application paths for the non-technical user flow."""

import os
import sys
from pathlib import Path


def default_data_root() -> Path:
    """Return a stable per-user data directory without creating it."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) / "EmailAgent" if base else Path.home() / "EmailAgent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "EmailAgent"
    base = os.environ.get("XDG_DATA_HOME")
    return Path(base) / "email-agent" if base else Path.home() / ".local" / "share" / "email-agent"


def resolve_data_root(value=None) -> Path:
    """Resolve an optional user root and reject control-character paths."""
    raw = str(default_data_root()) if value is None else str(value)
    if not raw.strip() or any(character in raw for character in ("\x00", "\n", "\r", "\t")):
        raise ValueError("invalid data root")
    return Path(raw).expanduser().resolve()
