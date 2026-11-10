import hashlib
import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKSPACES = Path(os.getenv("FINOPS_WORKSPACES_DIR", str(ROOT / "workspaces")))
KB_DIR = Path(os.getenv("FINOPS_KB_DIR", str(ROOT / "finops_capabilities_md/capabilities")))


def make_fingerprint(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


def validate_client(client_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", client_id):
        raise ValueError("client_id must contain lowercase letters, numbers and hyphens (max 64).")
    return client_id


def atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)
