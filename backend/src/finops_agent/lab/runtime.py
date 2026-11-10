import json
import logging
import signal
import threading
from datetime import date
from pathlib import Path
from typing import Any
import yaml
from ..config import atomic_write_text
from .generator import generate
from .scenarios import SCENARIOS, events
from .storage import bootstrap, publish


def prepare(root: Path, workspaces: Path, start: date, days: int, seed: int) -> None:
    for scenario in SCENARIOS.values():
        directory = root/scenario.client_id
        manifest = directory/'manifest.json'
        if manifest.exists():
            old = json.loads(manifest.read_text())
            if (old['start'],old['days'],old['seed'])!=(start.isoformat(),days,seed):
                raise ValueError('Existing lab uses different parameters; use a separate --root and --workspaces')
        generate(scenario,root,start,days,seed)
        workspace = workspaces/scenario.client_id
        profile = workspace/'client_profile.yaml'
        if profile.exists() and 'SINTÉTICO' not in profile.read_text():
            raise ValueError('Refusing to overwrite a non-laboratory client')
        if not profile.exists():
            atomic_write_text(profile,yaml.safe_dump(scenario.profile().model_dump(mode='json'),allow_unicode=True))
        notes = 'Datos sintéticos de laboratorio. Eventos de negocio conocidos:\n\n'+json.dumps(events(start),ensure_ascii=False)
        atomic_write_text(workspace/'context_notes/known-events.md',notes)


def serve(root: Path, workspaces: Path, start: date, days: int, seed: int, port: int, initial: int) -> None:
    from moto.server import ThreadedMotoServer
    if not 1<=initial<=days:
        raise ValueError('initial must be between 1 and days')
    prepare(root,workspaces,start,days,seed)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    server = ThreadedMotoServer(ip_address='127.0.0.1',port=port,verbose=False)
    server.start()
    try:
        bootstrap(root,workspaces,f'http://127.0.0.1:{port}')
        for client_id in SCENARIOS:
            state = root/client_id/'published.json'
            count = json.loads(state.read_text())['days'] if state.exists() else initial
            publish(root,client_id,count,restore=True)
        print(f'Laboratorio S3 listo en 127.0.0.1:{port}; autenticación IAM activa.',flush=True)
        stop = threading.Event()
        def shutdown(*_: Any) -> None:
            stop.set()
        signal.signal(signal.SIGTERM,shutdown)
        signal.signal(signal.SIGINT,shutdown)
        stop.wait()
    finally:
        server.stop()
