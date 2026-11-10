import hashlib
import os
import tempfile
from pathlib import Path
from collections.abc import Sequence
from starlette.datastructures import UploadFile
from .container import ClientResources

MAX_UPLOAD = 50 * 1024 * 1024


async def save_upload(upload: UploadFile, directory: Path, suffix: str) -> Path:
    if Path(upload.filename or "").suffix.lower() != suffix:
        raise ValueError(f"Expected {suffix} file")
    directory.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise ValueError("Maximum upload size is 50 MB")
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        path = directory / (digest.hexdigest() + suffix)
        os.replace(temp, path)
        return path
    finally:
        Path(temp).unlink(missing_ok=True)


async def ingest_uploads(client: ClientResources, files: Sequence[UploadFile]) -> int:
    rows = 0
    for upload in files:
        path = await save_upload(upload, client.workspace / "focus_exports", ".csv")
        rows += client.engine.ingest_focus_csv(client.profile.client_id, path)
    return rows
