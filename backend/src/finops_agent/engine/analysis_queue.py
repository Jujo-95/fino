"""Single-backend durable coordination; separate from LangGraph checkpoint tables."""
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4
from .analysis_store import timestamp


class AnalysisQueue:
    def __init__(self, root: Path) -> None:
        self.lock = threading.RLock()
        self.db = sqlite3.connect(root/'analysis-jobs.sqlite',check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, client TEXT NOT NULL, '
            'key TEXT UNIQUE NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL, '
            'attempts INTEGER DEFAULT 0, checkpoint TEXT, heartbeat TEXT, next_attempt TEXT)')
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS active_analysis_client ON jobs(client) WHERE state IN ('queued','running')")
        self.db.execute("UPDATE jobs SET state='queued' WHERE state='running'")
        self.db.commit()

    def enqueue(self, body: dict[str,Any], key: str) -> tuple[str,bool]:
        with self.lock,self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute("SELECT id FROM jobs WHERE client=? AND state IN ('queued','running')",[body['client_id']]).fetchone()
            row = row or self.db.execute('SELECT id FROM jobs WHERE key=?',[key]).fetchone()
            if row:
                return str(row['id']),False
            identity = uuid4().hex
            self.db.execute('INSERT INTO jobs(id,client,key,state,body,created) VALUES (?,?,?,?,?,?)',
                [identity,body['client_id'],key,'queued',json.dumps(body),timestamp()])
            return identity,True

    def claim(self) -> dict[str,Any] | None:
        with self.lock,self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute("SELECT * FROM jobs WHERE state='queued' AND (next_attempt IS NULL OR next_attempt<=?) ORDER BY created LIMIT 1",[timestamp()]).fetchone()
            if not row:
                return None
            self.db.execute("UPDATE jobs SET state='running',attempts=attempts+1,heartbeat=? WHERE id=?",[timestamp(),row['id']])
            return dict(row,body=json.loads(row['body']))

    def update(self, identity: str, state: str, checkpoint: str = '') -> None:
        with self.lock,self.db:
            self.db.execute('UPDATE jobs SET state=?,checkpoint=?,heartbeat=? WHERE id=?',[state,checkpoint,timestamp(),identity])

    def get(self, identity: str) -> dict[str,Any] | None:
        with self.lock:
            row = self.db.execute('SELECT * FROM jobs WHERE id=?',[identity]).fetchone()
            return dict(row) if row else None

    def promote_report(self, identity: str) -> None:
        with self.lock, self.db:
            row = self.db.execute('SELECT body FROM jobs WHERE id=?', [identity]).fetchone()
            if not row:
                return
            body = json.loads(row['body'])
            body['_canonical_report'] = True
            self.db.execute('UPDATE jobs SET body=? WHERE id=?', [json.dumps(body), identity])

    def retry(self, identity: str, attempts: int) -> None:
        from datetime import datetime,timedelta,timezone
        due = (datetime.now(timezone.utc)+timedelta(seconds=15*2**attempts)).isoformat()
        with self.lock,self.db:
            self.db.execute("UPDATE jobs SET state='queued',next_attempt=?,checkpoint='retry-transient' WHERE id=? AND state='running'",[due,identity])

    def has_key(self, key: str) -> bool:
        with self.lock:
            return self.db.execute('SELECT 1 FROM jobs WHERE key=?',[key]).fetchone() is not None

    def close(self) -> None:
        self.db.close()
