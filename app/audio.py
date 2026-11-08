"""Music onset grid: local file only. No fetching copyrighted music."""
import asyncio
import math
import struct
from pathlib import Path

async def beat_grid(audio: Path | None, duration: float, spacing: float = 2.5) -> list[float]:
    """Find energy onset peaks with 16 kHz mono PCM; fallback to uniform grid."""
    fallback = [round(t * spacing, 3) for t in range(1, math.ceil(duration / spacing)) if t * spacing < duration - .4]
    if audio is None:
        return fallback
    proc = await asyncio.create_subprocess_exec('ffmpeg','-v','error','-i',str(audio),'-t',str(min(duration,180)), '-ac','1','-ar','16000','-f','s16le','pipe:1', stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        data, err = await asyncio.wait_for(proc.communicate(), 100)
    except asyncio.TimeoutError:
        proc.kill(); await proc.communicate(); return fallback
    if proc.returncode or len(data) < 64000:
        return fallback
    # 50ms RMS, rising-energy peaks, minimum distance 350ms.
    samples = memoryview(data).cast('h')
    block = 800
    energies = []
    for i in range(0,len(samples)-block,block):
        s = samples[i:i+block]
        energies.append(math.sqrt(sum(float(x)*x for x in s)/block))
    if len(energies) < 20: return fallback
    peaks=[]
    for i in range(2,len(energies)-2):
        delta = energies[i] - (energies[i-1]+energies[i-2])/2
        if delta > max(250, energies[i]*.19) and delta >= energies[i+1]-energies[i] and (not peaks or i*.05-peaks[-1] >= .35):
            peaks.append(round(i*.05,3))
    # Compose boundaries approximately every spacing seconds, snapping to nearby onsets.
    if len(peaks) < 3: return fallback
    points=[]
    t=spacing
    while t < duration-.4:
        choices=[p for p in peaks if abs(p-t) <= .38 and (not points or p-points[-1] >= 1.0)]
        v=min(choices,key=lambda p:abs(p-t)) if choices else round(t,3)
        if not points or v-points[-1] >= .6: points.append(v)
        t+=spacing
    return points


def duration_segments(duration: float, boundaries: list[float]) -> list[float]:
    marks=[0.0]+sorted(set(p for p in boundaries if .3 < p < duration-.3))+[float(duration)]
    return [round(b-a,3) for a,b in zip(marks,marks[1:])]
