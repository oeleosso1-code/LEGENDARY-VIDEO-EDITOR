"""Objective MP4 delivery checks. Creative quality cannot be inferred reliably.

Black detection generates warnings, never censorship or automatic removal: a dark
shot may be intentional. Failures are limited to corrupted/missing streams,
invalid geometry, or material duration mismatch.
"""
from __future__ import annotations
import asyncio
import json
import math
from pathlib import Path
import re


async def delivery_check(path: Path, *, expected_seconds: float | None=None,
                         width: int | None=None,height: int | None=None,
                         require_audio: bool=False, sample_seconds: float=12.) -> dict:
    path=Path(path)
    if not path.is_file() or path.stat().st_size==0:
        raise ValueError('Output file missing')
    if expected_seconds is not None and (not math.isfinite(expected_seconds) or expected_seconds<=0):
        raise ValueError('Invalid expected duration')
    process=await asyncio.create_subprocess_exec(
      'ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path),
      stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:raw,error=await asyncio.wait_for(process.communicate(),30)
    except asyncio.TimeoutError:
        process.kill();await process.communicate();raise RuntimeError('Media probe timed out')
    if process.returncode:raise RuntimeError(error.decode(errors='replace')[-300:])
    info=json.loads(raw)
    streams=info.get('streams',[])
    video=next((x for x in streams if x.get('codec_type')=='video'),None)
    audio=any(x.get('codec_type')=='audio' for x in streams)
    seconds=float(info.get('format',{}).get('duration',0))
    issues=[]
    if not video:issues.append('Missing video stream')
    if require_audio and not audio:issues.append('Expected music but output has no audio stream')
    if expected_seconds is not None and abs(seconds-expected_seconds)>.18:
        issues.append('Output duration differs from approved edit timeline')
    dimensions=[int(video.get('width',0)),int(video.get('height',0))] if video else [0,0]
    if width is not None and dimensions[0]!=width:issues.append('Unexpected output width')
    if height is not None and dimensions[1]!=height:issues.append('Unexpected output height')
    warnings=[]
    black_intervals=[]
    if video and sample_seconds>0:
        span=min(seconds,max(0,sample_seconds))
        proc=await asyncio.create_subprocess_exec(
         'ffmpeg','-nostdin','-hide_banner','-v','info','-i',str(path),
         '-t',f'{span:.3f}','-vf','blackdetect=d=0.7:pix_th=0.06',
         '-an','-f','null','-',stdout=asyncio.subprocess.DEVNULL,
         stderr=asyncio.subprocess.PIPE)
        try:_,log=await asyncio.wait_for(proc.communicate(),45)
        except asyncio.TimeoutError:
            proc.kill();await proc.communicate()
            warnings.append('Black frame detector timed out')
        else:
            if proc.returncode==0:
                text=log.decode(errors='replace')
                for match in re.finditer(r'black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)',text):
                    black_intervals.append({'start':float(match.group(1)),
                                            'end':float(match.group(2)),
                                            'seconds':float(match.group(3))})
                if black_intervals:
                    warnings.append('Extended dark/black sequences detected; inspect manually before publishing')
            else:
                warnings.append('Black frame detector unavailable')
    return {'ok':not issues,'issues':issues,'warnings':warnings,'black_intervals':black_intervals,
            'duration':round(seconds,3),'dimensions':dimensions,'has_audio':audio,
            'file_bytes':path.stat().st_size,'verification':'objective technical checks only'}
