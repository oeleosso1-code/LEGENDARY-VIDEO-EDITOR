"""Atomic per-user session manifests. Inputs in user-specific folders."""
import json
import os
import uuid
from pathlib import Path
from . import config

ALLOWED_STYLES={'cinematic','fast','smooth','documentary'}

def root(uid: int) -> Path:
    p=config.OUTPUT_DIR/'users'/str(int(uid));p.mkdir(parents=True,exist_ok=True);return p

def blank():
    return {'prompt':'','seconds':30,'orientation':'vertical','style':'cinematic','clips':[],'music':None,'subtitles':None,'color':'natural','music_volume':0.85,'music_start':0.0,'shotlist':None,'titles':None,'reference':None,'reference_profile':None,'ai_analysis':None,'quality':'preview','version':7}

def load(uid: int):
    p=root(uid)/'session.json'
    if not p.exists(): return blank()
    try:
        d=json.loads(p.read_text('utf-8'))
        return d if isinstance(d,dict) and isinstance(d.get('clips'),list) else blank()
    except (ValueError,OSError): return blank()

def save(uid: int, data):
    p=root(uid)/'session.json'; tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)

def unique_file(uid: int,ext: str):
    return root(uid)/(uuid.uuid4().hex+ext)

def job_dir(uid: int):
    p=root(uid)/'renders'/uuid.uuid4().hex;p.mkdir(parents=True,exist_ok=True);return p
