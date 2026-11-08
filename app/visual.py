"""Lightweight objective shot analysis using FFmpeg grayscale samples.

No face recognition, copyrighted footage download, or third-party model required.
Scores are heuristics (brightness, contrast, motion, detail), NOT human taste.
"""
import asyncio
import json
import math
from pathlib import Path

SAMPLE_W, SAMPLE_H = 96, 54


def image_metrics(frame: bytes, previous: bytes | None = None) -> dict:
    """Compute robust metrics on a single 8-bit grayscale frame."""
    n = len(frame)
    if n != SAMPLE_W * SAMPLE_H:
        raise ValueError('Expected a 96x54 grayscale frame')
    avg = sum(frame) / n
    contrast = math.sqrt(sum((v - avg) ** 2 for v in frame) / n)
    # 1/8 pixel subsampling for inexpensive directional gradients.
    detail = sum(abs(frame[i] - frame[i-1]) for i in range(1, n, 4) if i % SAMPLE_W) / max(1, (n // 4))
    motion = sum(abs(a-b) for a,b in zip(frame[::4],previous[::4]))/(len(frame[::4])) if previous else 0.0
    return {'brightness':round(avg,2),'contrast':round(contrast,2),
            'detail':round(detail,2),'motion':round(motion,2)}


def quality_score(metrics: dict, style: str = 'cinematic') -> float:
    """Objective footage ranking only; avoid very dark/flat shots."""
    brightness = max(0.0, 1.0-abs(metrics['brightness']-118)/118)
    contrast = min(1.0, metrics['contrast']/54)
    detail = min(1.0, metrics['detail']/26)
    motion = min(1.0, metrics['motion']/24)
    weights={'fast':(.18,.18,.24,.40),'cinematic':(.26,.28,.30,.16),
             'smooth':(.28,.24,.34,.14),'documentary':(.26,.28,.34,.12)}
    wb,wc,wd,wm=weights.get(style, weights['cinematic'])
    return round(wb*brightness+wc*contrast+wd*detail+wm*motion,4)


async def inspect_clip(path: Path, duration: float, style='cinematic', timeout=90) -> dict:
    """Sample three short grayscale frames and return an editorial quality estimate."""
    result=[]; last=None
    # Each seek uses fast input-side -ss; caps work on long clips.
    for frac in (0.12,0.46,0.78):
        timestamp=max(0, min(max(duration-.15,0),duration*frac))
        p=await asyncio.create_subprocess_exec(
            'ffmpeg','-hide_banner','-loglevel','error','-ss',f'{timestamp:.3f}',
            '-i',str(path),'-frames:v','1','-vf',f'scale={SAMPLE_W}:{SAMPLE_H}',
            '-pix_fmt','gray','-f','rawvideo','pipe:1',
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try: output,err=await asyncio.wait_for(p.communicate(),timeout)
        except BaseException:
            p.kill();await p.communicate();raise
        if p.returncode or len(output)!=SAMPLE_W*SAMPLE_H:
            continue
        result.append(image_metrics(output,last));last=output
    if not result: return {'score':0,'samples':0,'style':style}
    summary={k:round(sum(m[k] for m in result)/len(result),2) for k in result[0]}
    return {**summary,'score':quality_score(summary,style),'samples':len(result),'style':style}


def balanced_clip_order(scores: list[float], segments: int) -> list[int]:
    """Quality-weighted rotation: cover every asset, then prefer higher scoring assets."""
    if not scores or segments<0: raise ValueError('Invalid clips or segment count')
    # Do not hide low-ranked clips entirely: source variety matters.
    ordering=sorted(range(len(scores)), key=lambda i:(-scores[i],i))
    result=[]
    for i in range(segments):
        cycle=i//len(ordering)
        j=i%len(ordering)
        # Rotate each cycle to reduce conspicuous exact repeats.
        result.append(ordering[(j+cycle)%len(ordering)])
    return result
