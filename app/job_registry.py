"""Durable per-user render state, without secrets or raw request payloads.

A registry is an audit/status record, not a resumable render queue. In-flight
jobs marked running at restart become interrupted until explicitly restarted.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from . import store

STATES = frozenset({'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted'})
TERMINAL = frozenset({'completed', 'failed', 'cancelled', 'interrupted'})

def _now():
    return datetime.now(timezone.utc).isoformat()

def _safe_id(job_id: str):
    if not isinstance(job_id, str) or len(job_id) != 32 or any(x not in '0123456789abcdef' for x in job_id):
        raise ValueError('invalid job id')
    return job_id

def _path(uid: int, job_id: str) -> Path:
    return store.root(uid) / 'renders' / _safe_id(job_id) / 'job.json'

def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_name('.job-'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('w', encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)

def create(uid: int, preview: bool=False) -> dict:
    job_id=uuid.uuid4().hex
    now=_now()
    record={'id':job_id,'state':'queued','preview':bool(preview),'created_at':now,
            'updated_at':now,'phase':'waiting','error':None}
    _atomic_write(_path(uid,job_id),record)
    return record

def read(uid: int, job_id: str) -> dict:
    path=_path(uid,job_id)
    obj=json.loads(path.read_text('utf-8'))
    if obj.get('id')!=job_id or obj.get('state') not in STATES:
        raise ValueError('corrupt job state')
    return obj

def update(uid: int, job_id: str, *, state: str|None=None, phase: str|None=None, error: str|None=None) -> dict:
    record=read(uid,job_id)
    if state is not None:
        if state not in STATES:raise ValueError('unknown state')
        if record['state'] in TERMINAL:raise ValueError('terminal job cannot transition')
        if record['state']=='queued' and state not in ('running','cancelled','failed','interrupted'):
            raise ValueError('invalid transition')
        record['state']=state
    if phase is not None:record['phase']=str(phase)[:80]
    if error is not None:record['error']=str(error)[:200]
    record['updated_at']=_now()
    _atomic_write(_path(uid,job_id),record)
    return record

def latest(uid: int) -> dict|None:
    folder=store.root(uid)/'renders'
    if not folder.exists():return None
    records=[]
    for candidate in folder.glob('*/job.json'):
        try:
            record=read(uid,candidate.parent.name)
            records.append(record)
        except (ValueError,OSError,KeyError,json.JSONDecodeError):
            continue
    return max(records,key=lambda r:r['created_at']) if records else None

def mark_interrupted(uid: int) -> int:
    """Run once at startup for jobs that cannot still be running in this process."""
    folder=store.root(uid)/'renders'
    if not folder.exists():return 0
    changed=0
    for candidate in folder.glob('*/job.json'):
        try:
            record=read(uid,candidate.parent.name)
            if record['state'] in ('queued','running'):
                update(uid,record['id'],state='interrupted',phase='restart')
                changed+=1
        except (ValueError,OSError,KeyError,json.JSONDecodeError):pass
    return changed
