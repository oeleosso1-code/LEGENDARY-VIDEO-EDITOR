"""Deterministic, resumable rendering of an already approved edit decision list.

Frames are quantized to 25 fps. Chunk boundaries only occur between shots.
The music track is attached once after concatenation, not per chunk.
This module doesn't pick shots or access network services.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from .editor_pro import command, probe, COLOR_PRESETS, subtitle_filter
from .shotlist import parse_shotlist
from .titles import load_titles, title_filters, find_font
from .motion_track import estimate_motion, crop_filter
from .quality_check import delivery_check

FPS = 25
RENDER_FORMAT = 'timeline-v3-motion-ramp-quality-25fps'
OUTPUT_SIZES={'preview':{'vertical':(360,640),'horizontal':(640,360)},
              'hd':{'vertical':(720,1280),'horizontal':(1280,720)},
              'fullhd':{'vertical':(1080,1920),'horizontal':(1920,1080)}}


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _quantize(shots):
    out = []
    for i, shot in enumerate(shots):
        frames = round(shot['duration'] * FPS)
        if frames < 4:
            raise ValueError(f'Shot {i} has fewer than four output frames')
        out.append({**shot, 'frames': frames, 'duration': frames / FPS})
    return out


def partition_shots(shots: list[dict], desired_chunk_seconds: float = 20) -> list[list[dict]]:
    """Groups whole shots; does not silently split a shot at a chunk boundary."""
    if not math.isfinite(desired_chunk_seconds) or desired_chunk_seconds < 0.16:
        raise ValueError('Chunk length must be finite and >= 0.16 seconds')
    groups, current, length = [], [], 0.0
    for shot in shots:
        duration = float(shot['duration'])
        if current and length + duration > desired_chunk_seconds:
            groups.append(current)
            current, length = [], 0.0
        current.append(shot)
        length += duration
    if current:
        groups.append(current)
    return groups


async def _make_chunk(group: list[dict], sources: list[Path], path: Path, width: int, height: int, color: str, preset: str):
    """Render and verify whole shots; optionally use staged speed ramps and motion-follow crop."""
    with tempfile.TemporaryDirectory(prefix='shot-work-', dir=path.parent) as td:
        temp = Path(td)
        pieces = []
        for i, shot in enumerate(group):
            src = sources[shot['clip']]
            dst = temp / f'part_{i:04d}.mp4'
            frame_count=shot['frames']
            ramp=shot.get('ramp') or [shot['speed']]
            base,extra=divmod(frame_count,len(ramp))
            counts=[base+(1 if j<extra else 0) for j in range(len(ramp))]
            consumed=sum((frames/FPS)*speed for frames,speed in zip(counts,ramp))
            tracking=None
            if shot.get('follow_motion'):
                tracking=await estimate_motion(src,start=shot['start'],duration=consumed)
            position=shot['start']
            stages=[]
            completed=0
            for j,(frames,speed) in enumerate(zip(counts,ramp)):
                stage=temp / f'shot_{i:04d}_stage_{j:02d}.mp4'
                segment_length=frames/FPS*speed
                if tracking:
                    frac1=completed/frame_count
                    frac2=(completed+frames)/frame_count
                    motion={
                        'start_x':tracking['start_x']+(tracking['end_x']-tracking['start_x'])*frac1,
                        'end_x':tracking['start_x']+(tracking['end_x']-tracking['start_x'])*frac2,
                        'start_y':tracking['start_y']+(tracking['end_y']-tracking['start_y'])*frac1,
                        'end_y':tracking['start_y']+(tracking['end_y']-tracking['start_y'])*frac2}
                    vf=crop_filter(width,height,motion,segment_length)
                else:
                    vf=(f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                        f'crop={width}:{height},setsar=1')
                vf+=f',fps={FPS},setpts=(PTS-STARTPTS)/{speed:.6f},format=yuv420p'
                if COLOR_PRESETS[color]:vf+=','+COLOR_PRESETS[color]
                # Input-scoped -t ensures slow-motion output is not cut short.
                await command('ffmpeg','-nostdin','-hide_banner','-v','error','-y',
                              '-ss',f'{position:.6f}','-t',f'{segment_length+0.05:.6f}',
                              '-i',str(src),'-vf',vf,'-frames:v',str(frames),'-an',
                              '-c:v','libx264','-preset',preset,'-crf','24','-pix_fmt','yuv420p',str(stage))
                actual,video=await probe(stage)
                if not video or abs(actual - frames/FPS) > .12:
                    raise RuntimeError(f'Speed stage verification failed: shot {i}, phase {j}')
                stages.append(stage)
                position+=segment_length
                completed+=frames
            if len(stages)==1:
                stages[0].replace(dst)
            else:
                stages_manifest=temp/f'phase_{i:04d}.ffconcat'
                stages_manifest.write_text('ffconcat version 1.0\n'+''.join(f'file {p.name}\n' for p in stages),encoding='utf8')
                await command('ffmpeg','-nostdin','-hide_banner','-v','error','-y','-safe','1',
                              '-f','concat','-i',str(stages_manifest),'-c:v','copy',str(dst))
            pieces.append(dst)
        manifest = temp / 'shots.ffconcat'
        manifest.write_text('ffconcat version 1.0\n'+''.join(f'file {p.name}\n' for p in pieces))
        temp_output = temp / 'chunk.mp4'
        await command('ffmpeg','-nostdin','-hide_banner','-v','error','-y','-safe','1','-f','concat',
                      '-i',str(manifest),'-c:v','copy','-movflags','+faststart',str(temp_output))
        duration, has_video = await probe(temp_output)
        expected = sum(s['frames'] for s in group) / FPS
        if not has_video or abs(duration - expected) > 0.15:
            raise RuntimeError(f'Chunk verification failed: expected {expected:.3f}, got {duration:.3f}')
        os.replace(temp_output, path)


async def render_timeline(inputs: list[Path], shotlist: Path, output: Path, *,
                          music: Path | None = None, music_start: float = 0.,
                          music_volume: float = .85, orientation: str = 'vertical',
                          color: str = 'natural', chunk_seconds: float = 20.,
                          preset: str = 'ultrafast', progress_callback=None,
                          subtitles: Path | None = None, titles: Path | None = None,
                          quality: str = 'preview') -> dict:
    """Render an immutable shot plan. Safe reruns reuse hash-validated chunks.

    Output must be outside the chunk cache. No network calls are made.
    """
    if not inputs or any(not Path(x).is_file() for x in inputs):
        raise ValueError('Missing input video')
    if quality not in OUTPUT_SIZES:
        raise ValueError('Unsupported output quality')
    if orientation not in ('vertical', 'horizontal') or color not in COLOR_PRESETS:
        raise ValueError('Unsupported orientation or color')
    if preset not in ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium'):
        raise ValueError('Unsupported encoder preset')
    if not (math.isfinite(music_start) and music_start >= 0 and
            math.isfinite(music_volume) and 0 <= music_volume <= 1.5):
        raise ValueError('Invalid audio parameters')
    if music is not None and not music.is_file():
        raise ValueError('Missing music file')
    if subtitles is not None:
        subtitles = Path(subtitles).resolve()
        if not subtitles.is_file() or subtitles.suffix.lower() != '.srt' or subtitles.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Invalid subtitle file')
    sources = [Path(x).resolve() for x in inputs]
    source_lengths = []
    for src in sources:
        duration, video = await probe(src)
        if not video or duration <= 0:
            raise ValueError(f'Invalid video input: {src.name}')
        source_lengths.append(duration)
    raw = json.loads(shotlist.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('shots'), list):
        raise ValueError('Missing shots array')
    total = sum(float(s['duration']) for s in raw['shots'])
    shots = _quantize(parse_shotlist(shotlist, source_lengths, total))
    groups = partition_shots(shots, chunk_seconds)
    title_rows = load_titles(titles, sum(s['frames'] for s in shots) / FPS) if titles is not None else []
    inputs_hash = [_digest(p) for p in sources]
    width, height = OUTPUT_SIZES[quality][orientation]
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = output.parent / (output.stem + '_chunks')
    cache.mkdir(parents=True, exist_ok=True)
    if cache.resolve() == output.resolve():
        raise ValueError('Invalid output')
    chunk_paths = []
    reused = 0
    cursor = 0
    for i, group in enumerate(groups):
        key = hashlib.sha256(_canonical({'format': RENDER_FORMAT, 'shots':group,
                        'sources': {str(s['clip']): inputs_hash[s['clip']] for s in group}, 'orientation':orientation,
                        'color':color,'preset':preset,'quality':quality}).encode('utf-8')).hexdigest()
        path = cache / f'chunk_{i:05d}_{key[:20]}.mp4'
        meta = path.with_suffix('.json')
        expected = sum(s['frames'] for s in group) / FPS
        use_cache = False
        if path.is_file() and meta.is_file():
            try:
                record = json.loads(meta.read_text(encoding='utf-8'))
                duration, has_video = await probe(path)
                use_cache = (record.get('key') == key and record.get('hash') == _digest(path)
                             and has_video and abs(duration - expected) <= .15)
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
                use_cache = False
        if not use_cache:
            await _make_chunk(group, sources, path, width, height, color, preset)
            record = {'key': key, 'hash': _digest(path), 'frames': sum(x['frames'] for x in group)}
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=cache, delete=False) as fp:
                json.dump(record, fp)
                meta_tmp = fp.name
            os.replace(meta_tmp, meta)
        else:
            reused += 1
        chunk_paths.append(path)
        cursor += sum(s['frames'] for s in group)
        if progress_callback is not None:
            progress_callback({'state':'running', 'finished':i+1, 'total':len(groups)})

    # Construct a combined picture once; soundtrack can start at any supplied offset.
    with tempfile.TemporaryDirectory(prefix='final-work-', dir=output.parent) as td:
        td = Path(td)
        manifest = td / 'chunks.ffconcat'
        # concat manifest accepts absolute names when -safe 0; cache paths are internally controlled.
        manifest.write_text('ffconcat version 1.0\n'+''.join(
            "file '" + str(p).replace("'", "'\\''") + "'\n" for p in chunk_paths), encoding='utf8')
        silent = td / 'picture.mp4'
        await command('ffmpeg','-hide_banner','-v','error','-y','-safe','0','-f','concat',
                      '-i',str(manifest),'-c:v','copy',str(silent))
        expected = cursor / FPS
        if subtitles is not None or title_rows:
            subtitled = td / 'subtitled.mp4'
            visual_filters = []
            if subtitles is not None:
                visual_filters.append(subtitle_filter(subtitles))
            if title_rows:
                visual_filters.append(title_filters(title_rows, td, find_font()))
            await command('ffmpeg','-hide_banner','-v','error','-y',
                          '-i',str(silent),'-vf',','.join(visual_filters),
                          '-c:v','libx264','-preset',preset,'-crf','23',
                          '-pix_fmt','yuv420p','-an',str(subtitled))
            silent = subtitled
        candidate = td / 'result.mp4'
        if music is None:
            os.replace(silent, candidate)
        else:
            fade = max(0., expected - 1.0)
            await command('ffmpeg','-hide_banner','-v','error','-y','-i',str(silent),
                          '-stream_loop','-1','-ss',f'{music_start:.3f}','-i',str(music),
                          '-filter_complex',f'[1:a]volume={music_volume:.3f},afade=t=out:st={fade:.3f}:d=1[a]',
                          '-map','0:v:0','-map','[a]','-t',f'{expected:.3f}',
                          '-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart',str(candidate))
        actual, has_video = await probe(candidate)
        if not has_video or abs(actual - expected) > .16:
            raise RuntimeError(f'Final output invalid: expected {expected:.3f}, got {actual:.3f}')
        qc=await delivery_check(candidate,expected_seconds=expected,width=width,
                                height=height,require_audio=music is not None,
                                sample_seconds=min(10.,expected))
        if not qc['ok']:
            raise RuntimeError('Final delivery check failed: '+', '.join(qc['issues']))
        os.replace(candidate, output)
    (output.parent / (output.stem + '_quality_report.json')).write_text(
        json.dumps(qc,ensure_ascii=False,indent=2),encoding='utf8')
    if progress_callback is not None:
        progress_callback({'state':'completed', 'finished':len(groups), 'total':len(groups)})
    result = {'output':str(output), 'seconds':expected,'chunks':len(groups),
              'reused_chunks':reused,'shots':len(shots),'fps':FPS,
              'music':music is not None, 'subtitles':subtitles is not None, 'titles':len(title_rows),
              'quality':quality, 'width':width, 'height':height,
              'quality_ok':qc['ok'], 'quality_warnings':len(qc['warnings']), 'format':RENDER_FORMAT}
    (output.parent / (output.stem + '_render_report.json')).write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result


def main():
    """Command line entry point for a fixed, resumable edit timeline."""
    import argparse
    parser = argparse.ArgumentParser(description='Render a saved timeline using real footage')
    parser.add_argument('--input', nargs='+', type=Path, required=True, help='Ordered source video files')
    parser.add_argument('--shotlist', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--music', type=Path)
    parser.add_argument('--titles', type=Path)
    parser.add_argument('--subtitles', type=Path)
    parser.add_argument('--music-start', type=float, default=0.)
    parser.add_argument('--music-volume', type=float, default=.85)
    parser.add_argument('--orientation', choices=['vertical', 'horizontal'], default='vertical')
    parser.add_argument('--color', choices=sorted(COLOR_PRESETS), default='natural')
    parser.add_argument('--chunk-seconds', type=float, default=20.)
    parser.add_argument('--preset', default='veryfast')
    parser.add_argument('--quality', choices=sorted(OUTPUT_SIZES), default='preview')
    args = parser.parse_args()
    result = asyncio.run(render_timeline(args.input, args.shotlist, args.output,
        music=args.music, music_start=args.music_start, music_volume=args.music_volume,
        orientation=args.orientation, color=args.color,
        chunk_seconds=args.chunk_seconds, preset=args.preset,
        titles=args.titles, subtitles=args.subtitles, quality=args.quality))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
