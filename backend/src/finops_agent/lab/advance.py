import json
import threading
from pathlib import Path
from typing import Any
from ..sources.models import load_source
from ..sources.s3 import sync
from .storage import publish

LOCK = threading.Lock()


def advance(client: Any, root: Path, expected_days: int) -> dict[str, Any]:
    with LOCK:
        source,_ = load_source(client.workspace)
        publisher = json.loads((root/'publisher.json').read_text())
        if not source.synthetic or source.endpoint!=publisher['endpoint']:
            raise ValueError('Only the configured local laboratory can publish synthetic data')
        path = root/source.client_id/'published.json'
        state = json.loads(path.read_text())
        if state['days']!=expected_days:
            raise ValueError('El laboratorio ya avanzó. Actualiza la vista antes de continuar.')
        published = publish(root,source.client_id,expected_days+1)
        return dict(published=published,sync=sync(client))
