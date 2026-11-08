"""Durable checkpointed rendering using real footage and a single final soundtrack.

This is a local API, not yet a Telegram queue.  All chunk output lives under work_dir.
"""
import hashlib
import json
import math
import os
from pathlib import Path

from .editor_pro import render_pro, probe, command


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as src:
        for piece in iter(lambda: src.read(1024 * 1024), b''):
            h.update(piece)
    return h.hexdigest()


def _atomic_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _chunks(seconds: int, length: int) -> list[int]:
    if not isinstance(seconds, int) or not isinstance(length, int) or seconds < 5 or length < 5:
        raise ValueError('seconds and chunk length must be integers >= 5')
    if length >= seconds:
        return [seconds]
    n = max(1, math.ceil(seconds / length))
    while n > 1 and seconds // n < 5:
        n -= 1
    return [seconds // n + (1 if i < seconds % n else 0) for i in range(n)]


async def render_resumable(
    inputs: list[Path], music: Path | None, target: Path, seconds: int,
    work_dir: Path, *, chunk_seconds: int = 10, orientation: str = 'vertical',
    style: str = 'cinematic', color: str = 'natural', music_start: float = 0.0,
    music_volume: float = 0.85, preview: bool = False,
) -> dict:
    """Return a manifest with reused/rendered chunk counts. Requires exclusive work_dir ownership.

    Chunk renders intentionally have no soundtrack; one continuous track is laid
    across the assembled picture. No support for manual shotlist or subtitles yet.
    """
    target, work_dir = Path(target).resolve(), Path(work_dir).resolve()
    inputs = [Path(p).resolve() for p in inputs]
    music = Path(music).resolve() if music is not None else None
    if not inputs or any(not p.is_file() for p in inputs):
        raise ValueError('Video inputs are required and must exist')
    if music is not None and not music.is_file():
        raise ValueError('Music file not found')
    if not math.isfinite(music_start) or music_start < 0:
        raise ValueError('Invalid music start')
    if not math.isfinite(music_volume) or not 0 <= music_volume <= 1.5:
        raise ValueError('Invalid music volume')
    if target.is_relative_to(work_dir) or work_dir.is_relative_to(target.parent / target.name):
        raise ValueError('Use a separate output file and work directory')
    parts = _chunks(seconds, chunk_seconds)
    options = {'sources': [(str(p), _digest(p)) for p in inputs],
               'music': (str(music), _digest(music)) if music else None,
               'seconds': seconds, 'parts': parts, 'orientation': orientation,
               'style': style, 'color': color, 'music_start': music_start,
               'music_volume': music_volume, 'preview': preview, 'engine': 'X27-1'}
    signature = hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()
    work_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Use signature-specific chunk directory, never assume another render is compatible.
    chunks_dir = work_dir / signature[:24]
    chunks_dir.mkdir(exist_ok=True)
    status_path = work_dir / 'status.json'
    status = {'signature': signature, 'total': len(parts), 'finished': 0,
              'state': 'running', 'reused': 0, 'rendered': 0}
    _atomic_json(status_path, status)
    staged = []
    try:
        for i, duration in enumerate(parts):
            part = chunks_dir / f'part_{i:05d}.mp4'
            valid = False
            if part.is_file():
                try:
                    d, video = await probe(part)
                    valid = video and abs(d - duration) <= 0.18 and part.stat().st_size > 1000
                except Exception:
                    pass
            if valid:
                status['reused'] += 1
            else:
                part.unlink(missing_ok=True)
                stage = chunks_dir / f'render_{i:05d}'
                stage.mkdir(exist_ok=True)
                pending = stage / 'picture.mp4'
                await render_pro(inputs, None, pending, duration, orientation=orientation,
                                 style=style, color=color, preview=preview)
                d, video = await probe(pending)
                if not video or abs(d - duration) > 0.18:
                    raise RuntimeError(f'Invalid rendered chunk {i}: {d}')
                os.replace(pending, part)
                status['rendered'] += 1
            staged.append(part)
            status['finished'] = i + 1
            _atomic_json(status_path, status)
        concat_file = chunks_dir / 'assemble.ffconcat'
        concat_file.write_text('ffconcat version 1.0\n' + ''.join(f'file {p.name}\n' for p in staged), encoding='utf-8')
        picture = chunks_dir / 'joined.mp4'
        await command('ffmpeg', '-hide_banner', '-v', 'error', '-y', '-safe', '1',
                      '-f', 'concat', '-i', str(concat_file), '-c:v', 'copy', '-an', str(picture))
        incoming = target.parent / (target.name + '.partial.mp4')
        incoming.unlink(missing_ok=True)
        if music:
            fade = max(0, seconds - 1.1)
            await command('ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', str(picture),
                          '-ss', f'{music_start:.3f}', '-stream_loop', '-1', '-i', str(music),
                          '-filter_complex', f'[1:a]volume={music_volume:.3f},afade=t=out:st={fade:.3f}:d=1.1[a]',
                          '-map', '0:v:0', '-map', '[a]', '-t', str(seconds),
                          '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', str(incoming))
        else:
            await command('ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', str(picture),
                          '-c', 'copy', '-movflags', '+faststart', str(incoming))
        actual, has_video = await probe(incoming)
        if not has_video or abs(actual - seconds) > 0.2:
            raise RuntimeError(f'Final output failed duration/video validation: {actual}')
        os.replace(incoming, target)
        status['state'] = 'completed'
        status['output'] = str(target)
        _atomic_json(status_path, status)
        return status
    except BaseException:
        status['state'] = 'interrupted'
        _atomic_json(status_path, status)
        raise
