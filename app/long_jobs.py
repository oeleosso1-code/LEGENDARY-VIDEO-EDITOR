"""Persistent Telegram long-render request snapshots (never contains API credentials).

Only explicitly uploaded user-owned clip/music paths may be used. A snapshot is
immutable across resume requests. The checkpoint renderer rehashes file contents.
"""
from __future__ import annotations
import json
import hashlib
import math
import os
import uuid
from pathlib import Path
from . import store


def _owned(uid: int, path: str | None) -> Path | None:
    if not path:
        return None
    owner = store.root(uid).resolve()
    item = Path(path).resolve()
    if item.parent != owner or not item.is_file():
        raise ValueError('Input must be an existing upload in the user directory')
    return item


def _validate(uid: int, request: dict) -> dict:
    sources = [_owned(uid, p) for p in request.get('clips', [])]
    if not sources:
        raise ValueError('At least one uploaded video is required')
    if len(sources) > 20:
        raise ValueError('Too many source clips')
    seconds = request.get('seconds')
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 5 <= seconds <= 10800:
        raise ValueError('Duration outside allowed range')
    orientation = request.get('orientation', 'vertical')
    style = request.get('style', 'cinematic')
    color = request.get('color', 'natural')
    quality = request.get('quality', 'preview')
    if quality not in ('preview','hd','fullhd'):
        raise ValueError('Invalid quality mode')
    if quality!='preview' and not request.get('shotlist'):
        raise ValueError('High-resolution long render requires a fixed shotlist')
    if orientation not in ('vertical', 'horizontal') or style not in store.ALLOWED_STYLES:
        raise ValueError('Invalid orientation or style')
    from .editor_pro import COLOR_PRESETS
    if color not in COLOR_PRESETS:
        raise ValueError('Invalid color')
    start = float(request.get('music_start', 0))
    volume = float(request.get('music_volume', .85))
    if not math.isfinite(start) or start < 0 or not math.isfinite(volume) or not 0 <= volume <= 1.5:
        raise ValueError('Invalid music settings')
    subtitles = _owned(uid, request.get('subtitles'))
    if subtitles is not None and (subtitles.suffix.lower() != '.srt' or subtitles.stat().st_size > 2 * 1024 * 1024):
        raise ValueError('Invalid SRT file or size')
    if subtitles is not None and not request.get('shotlist'):
        raise ValueError('Long SRT requires a fixed shotlist')
    titles = _owned(uid, request.get('titles'))
    if titles is not None:
        if not request.get('shotlist'):
            raise ValueError('Long title overlays require a fixed shotlist')
        from .titles import load_titles
        load_titles(titles, seconds)
    shotlist = _owned(uid, request.get('shotlist'))
    if shotlist is not None:
        if shotlist.suffix.lower() != '.json' or shotlist.stat().st_size > 256 * 1024:
            raise ValueError('Invalid shotlist format or size')
        from .shotlist import parse_shotlist
        # This validates structural and timing constraints; the renderer checks actual source durations.
        parse_shotlist(shotlist, [float('inf')] * len(sources), seconds)
    music = _owned(uid, request.get('music'))
    return {'clips': [str(p) for p in sources], 'music': str(music) if music else None,
            'seconds': seconds, 'orientation': orientation, 'style': style,
            'color': color, 'quality':quality, 'music_start': start, 'music_volume': volume,
            'shotlist': str(shotlist) if shotlist else None,
            'subtitles': str(subtitles) if subtitles else None,
            'titles': str(titles) if titles else None}


def job_home(uid: int) -> Path:
    return store.root(uid) / 'long_render'


def request_path(uid: int) -> Path:
    return job_home(uid) / 'request.json'


def create(uid: int, session: dict) -> dict:
    """Create a new long render request. Caller must reject when a task is active."""
    validated = _validate(uid, session)
    home = job_home(uid)
    home.mkdir(parents=True, exist_ok=True)
    # New id prevents old checkpoints from accidentally satisfying a different request.
    request = {'job_id': uuid.uuid4().hex, **validated}
    if validated['shotlist'] or validated['subtitles'] or validated['titles']:
        frozen_dir = home / request['job_id']
        frozen_dir.mkdir(parents=True, exist_ok=True)
    if validated['shotlist']:
        # Freeze the approved timeline into a private job folder. Do not read the editable
        # session shotlist again when a task is resumed.
        frozen_dir = home / request['job_id']
        frozen_dir.mkdir(parents=True, exist_ok=True)
        frozen = frozen_dir / 'approved_shotlist.json'
        content = Path(validated['shotlist']).read_bytes()
        temp_shots = frozen_dir / ('shotlist-' + uuid.uuid4().hex + '.tmp')
        temp_shots.write_bytes(content)
        os.replace(temp_shots, frozen)
        request['shotlist'] = str(frozen)
        request['shotlist_sha256'] = hashlib.sha256(content).hexdigest()
    if validated['subtitles']:
        frozen_srt = frozen_dir / 'approved_subtitles.srt'
        content = Path(validated['subtitles']).read_bytes()
        tmp_srt = frozen_dir / ('subtitles-' + uuid.uuid4().hex + '.tmp')
        tmp_srt.write_bytes(content)
        os.replace(tmp_srt, frozen_srt)
        request['subtitles'] = str(frozen_srt)
        request['subtitles_sha256'] = hashlib.sha256(content).hexdigest()
    if validated['titles']:
        frozen_titles = frozen_dir / 'approved_titles.json'
        content = Path(validated['titles']).read_bytes()
        tmp = frozen_dir / ('titles-' + uuid.uuid4().hex + '.tmp')
        tmp.write_bytes(content)
        os.replace(tmp, frozen_titles)
        request['titles'] = str(frozen_titles)
        request['titles_sha256'] = hashlib.sha256(content).hexdigest()
    path = request_path(uid)
    temp = path.with_name('.request-' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as f:
            json.dump(request, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return request


def load(uid: int) -> dict:
    path = request_path(uid)
    if not path.is_file():
        raise ValueError('No prior long-render request to resume')
    request = json.loads(path.read_text(encoding='utf-8'))
    job_id = request.get('job_id', '')
    if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
        raise ValueError('Invalid saved request id')
    # Frozen shotlists must be checked in the trusted job-specific directory, not in
    # a path supplied by an edited request.json.
    result = dict(request)
    frozen_titles = request.get('titles')
    if frozen_titles:
        expected_titles = job_home(uid) / job_id / 'approved_titles.json'
        if Path(frozen_titles) != expected_titles or not expected_titles.is_file() or expected_titles.is_symlink():
            raise ValueError('Frozen titles unavailable or invalid')
        if hashlib.sha256(expected_titles.read_bytes()).hexdigest() != request.get('titles_sha256'):
            raise ValueError('Frozen titles integrity check failed')
        result['titles'] = None
    frozen_srt = request.get('subtitles')
    if frozen_srt:
        expected_srt = job_home(uid) / job_id / 'approved_subtitles.srt'
        if Path(frozen_srt) != expected_srt or not expected_srt.is_file() or expected_srt.is_symlink():
            raise ValueError('Frozen subtitles unavailable or invalid')
        if hashlib.sha256(expected_srt.read_bytes()).hexdigest() != request.get('subtitles_sha256'):
            raise ValueError('Frozen subtitles integrity check failed')
        result['subtitles'] = None
    frozen = request.get('shotlist')
    if frozen:
        expected = job_home(uid) / job_id / 'approved_shotlist.json'
        if Path(frozen) != expected or not expected.is_file() or expected.is_symlink():
            raise ValueError('Frozen shotlist is unavailable or invalid')
        if hashlib.sha256(expected.read_bytes()).hexdigest() != request.get('shotlist_sha256'):
            raise ValueError('Frozen shotlist integrity check failed')
        # Validation accepts an owned input in the user directory, so validate base
        # request without the frozen shotlist and independently validate its contents.
        result['shotlist'] = None
    saved_quality=request.get('quality','preview')
    if saved_quality not in ('preview','hd','fullhd'):
        raise ValueError('Invalid quality mode in saved request')
    # _validate accepts only user-root uploads. The frozen shotlist was separately
    # verified by its canonical job path and digest; temporarily validate the
    # other editable inputs with preview quality, then restore the saved setting.
    if frozen:
        result['quality']='preview'
    validated = _validate(uid, result)
    if frozen:
        validated['quality']=saved_quality

        from .shotlist import parse_shotlist
        parse_shotlist(expected, [float('inf')] * len(validated['clips']), validated['seconds'])
        validated['shotlist'] = str(expected)
        validated['shotlist_sha256'] = request['shotlist_sha256']
    if frozen_titles:
        from .titles import load_titles
        load_titles(expected_titles, validated['seconds'])
        validated['titles'] = str(expected_titles)
        validated['titles_sha256'] = request['titles_sha256']
    if frozen_srt:
        validated['subtitles'] = str(expected_srt)
        validated['subtitles_sha256'] = request['subtitles_sha256']
    return {'job_id': job_id, **validated}


def paths(uid: int, request: dict) -> tuple[Path, Path]:
    base = job_home(uid) / request['job_id']
    return base / 'final.mp4', base / 'checkpoints'


def status(uid: int) -> dict:
    req = load(uid)
    output, work = paths(uid, req)
    file = work / 'timeline_status.json' if req.get('shotlist') else work / 'status.json'
    if not file.is_file():
        return {'state': 'not_started', 'finished': 0, 'total': 0, 'output_exists': output.is_file()}
    data = json.loads(file.read_text('utf-8'))
    return {'state': str(data.get('state', 'unknown')), 'finished': int(data.get('finished', 0)),
            'total': int(data.get('total', 0)), 'output_exists': output.is_file()}
