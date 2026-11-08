"""Objective local style sampling from a user-provided reference video.

Never treats the reference as usable source footage and does not claim to
reproduce copyright-protected expressive details, text or precise effects.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
import math
import statistics
from .editor_pro import probe

SIZE=64
FRAME_BYTES=SIZE*SIZE*3


def analyze_rgb_frames(data: bytes, *, fps: float = 2.) -> dict:
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError('Bad fps')
    count=len(data)//FRAME_BYTES
    if count==0:raise ValueError('Reference contains no decoded frames')
    frames=[]
    for i in range(count):
        frame=memoryview(data)[i*FRAME_BYTES:(i+1)*FRAME_BYTES]
        # sparse samples reduce CPU and weight each scene equally
        rr=frame[0::12];gg=frame[1::12];bb=frame[2::12]
        r=sum(rr)/len(rr);g=sum(gg)/len(gg);b=sum(bb)/len(bb)
        frames.append((r,g,b,(r+g+b)/3))
    cuts=[]
    for i in range(1,len(frames)):
        difference=sum(abs(a-b) for a,b in zip(frames[i][:3],frames[i-1][:3]))/3
        if difference >= 30:
            cuts.append(round(i/fps,2))
    means=[statistics.mean(f[j] for f in frames) for j in range(3)]
    brightness=round(statistics.mean(f[3] for f in frames),1)
    saturation=round(statistics.mean(max(f[:3])-min(f[:3]) for f in frames),1)
    # Recommendation is a controllable tonal starting point, not a style clone.
    if saturation < 12: grade='noir'
    elif brightness < 74: grade='cinematic'
    elif means[0]>means[2]+15: grade='warm'
    elif means[2]>means[0]+15: grade='cool'
    elif saturation > 80: grade='vivid'
    else: grade='natural'
    return {'sampled_frames':count, 'sampled_seconds':round(count/fps,2),
            'brightness':brightness,'saturation':saturation,
            'mean_rgb':[round(x,1) for x in means],
            'coarse_cut_times':cuts[:80],
            'average_shot_seconds':round((count/fps)/(len(cuts)+1),2),
            'suggested_grade':grade,
            'method':'mean RGB sampling, rough major-cut detection',
            'limitations':'Does not recognize precise motion graphics, text, events or transitions.'}


async def inspect_reference(path: Path, *, sample_seconds: float = 45.) -> dict:
    path=Path(path)
    if not path.is_file() or not math.isfinite(sample_seconds) or sample_seconds <= 0:
        raise ValueError('Invalid reference or duration')
    video_duration,has_video=await probe(path)
    if not has_video:raise ValueError('Reference has no video')
    seconds=min(video_duration,sample_seconds,90.)
    process=await asyncio.create_subprocess_exec(
        'ffmpeg','-nostdin','-v','error','-i',str(path),'-t',str(seconds),
        '-vf',f'fps=2,scale={SIZE}:{SIZE}',
        '-f','rawvideo','-pix_fmt','rgb24','pipe:1',
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:output,err=await asyncio.wait_for(process.communicate(),timeout=90)
    except asyncio.TimeoutError:
        process.kill();await process.communicate();raise RuntimeError('Reference decode timed out')
    except asyncio.CancelledError:
        process.kill();await process.communicate();raise
    if process.returncode:raise RuntimeError(err.decode(errors='replace')[-250:])
    result=analyze_rgb_frames(output)
    result['source_duration']=round(video_duration,3)
    result['is_reference_only']=True
    return result
