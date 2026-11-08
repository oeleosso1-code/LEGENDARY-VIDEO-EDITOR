"""Local, consent-free music analysis of user-supplied audio; no song downloads.

Tempo is only an estimate, not a guarantee of musical beat tracking. Times are
relative to the requested music_start, so they directly map to the edit timeline.
"""
from __future__ import annotations
import asyncio
from array import array
import math
from pathlib import Path
import statistics


def _onsets(rms: list[float], hop: float) -> list[dict]:
    if len(rms) < 8:
        return []
    novelty = [0.] * len(rms)
    for i in range(2, len(rms)):
        before = (rms[i - 1] + rms[i - 2]) / 2
        novelty[i] = max(0., rms[i] - before)
    active = [v for v in novelty if v > 0]
    if len(active) < 3:
        return []
    threshold = max(180., sorted(active)[min(len(active)-1, int(len(active)*.79))])
    candidates = [(i * hop, novelty[i]) for i in range(2, len(novelty)-2)
                  if novelty[i] >= threshold and novelty[i] >= novelty[i-1]
                  and novelty[i] >= novelty[i+1]]
    # Non-max suppression in 220ms windows; prefer stronger transients.
    chosen: list[tuple[float, float]] = []
    for stamp, strength in sorted(candidates, key=lambda p: -p[1]):
        if all(abs(stamp - prior) >= .22 for prior, _ in chosen):
            chosen.append((stamp, strength))
    chosen.sort()
    ceiling = max(s for _, s in chosen) if chosen else 1.
    return [{'time':round(t,3), 'strength':round(s / ceiling,3)} for t,s in chosen]


def _tempo(events: list[dict]) -> float | None:
    intervals = [b['time'] - a['time'] for a,b in zip(events, events[1:])]
    intervals = [d for d in intervals if .27 <= d <= 1.12]
    if len(intervals) < 4:
        return None
    median = statistics.median(intervals)
    consistency = sum(abs(d-median) <= .12 for d in intervals) / len(intervals)
    if consistency < .54:
        return None
    return round(60. / median, 1)


def analyze_pcm(data: bytes, *, rate: int = 8000, hop_seconds: float = .05) -> dict:
    """Analyze 16-bit mono PCM and return track-relative highlights/onsets."""
    if rate <= 0 or hop_seconds <= 0:
        raise ValueError('Invalid audio rate or hop')
    if len(data) % 2:
        data = data[:-1]
    samples = array('h');samples.frombytes(data)
    block = max(1, round(rate * hop_seconds))
    rms = []
    for offset in range(0, len(samples) - block + 1, block):
        section = samples[offset:offset + block]
        rms.append(math.sqrt(sum(float(s)*s for s in section) / len(section)))
    beats = _onsets(rms, block / rate)
    if rms:
        # Compare broad windows for energetic passages; no claims about lyrics/genre.
        span = max(1, int(round(1.0 / (block/rate))))
        windows = [(i * block / rate, sum(rms[i:i+span])/len(rms[i:i+span]))
                   for i in range(0,len(rms),span)]
        baseline = statistics.median(v for _,v in windows)
        highlights = [{'start':round(t,2), 'energy':round(v,1)} for t,v in windows
                      if v >= max(500., baseline*1.3)]
    else:
        highlights=[]
    return {'duration_analyzed':round(len(samples)/rate,3),
            'tempo_estimate_bpm':_tempo(beats), 'onsets':beats,
            'high_energy_windows':highlights, 'method':'PCM RMS onset heuristic'}


async def analyze_music(audio: Path, *, music_start: float = 0., duration: float = 60.) -> dict:
    """Reads at most 600 seconds using ffmpeg; does not transmit audio to an API."""
    audio = Path(audio)
    if not audio.is_file() or not math.isfinite(music_start) or music_start < 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid audio file or time range')
    window = min(duration, 600.)
    process = await asyncio.create_subprocess_exec(
        'ffmpeg','-nostdin','-v','error','-ss',f'{music_start:.3f}',
        '-i',str(audio),'-t',f'{window:.3f}','-ac','1','-ar','8000',
        '-f','s16le','pipe:1',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        output,errors = await asyncio.wait_for(process.communicate(), timeout=180)
    except asyncio.TimeoutError:
        process.kill();await process.communicate();raise RuntimeError('Music decoding timed out')
    except asyncio.CancelledError:
        process.kill();await process.communicate();raise
    if process.returncode:
        raise RuntimeError('Audio decode failed: '+errors.decode(errors='replace')[-250:])
    profile=analyze_pcm(output)
    profile['music_start']=music_start
    profile['truncated']=duration > 600.
    return profile
