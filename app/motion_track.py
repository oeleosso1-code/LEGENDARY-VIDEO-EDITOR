"""Heuristic motion-aware reframing for real footage (not person detection).

A moving camera/background can mislead the detector; use only if enabled in the
user's shotlist. Output normalized centers for a mild, bounded digital pan.
"""
from __future__ import annotations
import asyncio
import math
from pathlib import Path
import statistics

WIDTH,HEIGHT=64,36
FRAME=WIDTH*HEIGHT


def track_frames(data: bytes, fps: float=4.) -> dict:
    if fps <= 0 or not math.isfinite(fps):raise ValueError('Invalid fps')
    count=len(data)//FRAME
    if count < 3:
        return {'start_x':.5,'start_y':.5,'end_x':.5,'end_y':.5,'confidence':0.,'frames':count}
    centers=[]
    previous=data[:FRAME]
    for i in range(1,count):
        current=data[i*FRAME:(i+1)*FRAME]
        weighted_x=weighted_y=weight_sum=0.
        changed=0
        # Sparse-pixel temporal changes track dominant motion, not semantic objects.
        for y in range(2,HEIGHT-2,2):
            for x in range(2,WIDTH-2,2):
                index=y*WIDTH+x
                diff=abs(current[index]-previous[index])
                if diff < 25:continue
                weight=diff-24
                weighted_x+=x*weight
                weighted_y+=y*weight
                weight_sum+=weight
                changed+=1
        if weight_sum and 2<=changed<=WIDTH*HEIGHT//4:
            centers.append((weighted_x / weight_sum / (WIDTH-1),
                            weighted_y / weight_sum / (HEIGHT-1), changed))
        previous=current
    if not centers:
        return {'start_x':.5,'start_y':.5,'end_x':.5,'end_y':.5,'confidence':0.,'frames':count}
    length=max(1,len(centers)//3)
    # Mean of several frames suppresses jitter from transient motion.
    def mean(which,dim):return statistics.mean(v[dim] for v in which)
    start,end=centers[:length],centers[-length:]
    return {'start_x':round(max(.20,min(.80,mean(start,0))),3),
            'start_y':round(max(.2,min(.8,mean(start,1))),3),
            'end_x':round(max(.2,min(.8,mean(end,0))),3),
            'end_y':round(max(.2,min(.8,mean(end,1))),3),
            'confidence':round(min(1,len(centers)/max(1,count-1)),2),'frames':count}


async def estimate_motion(path: Path, *, start: float=0., duration: float=3.) -> dict:
    path=Path(path)
    if not path.is_file() or not math.isfinite(start) or start<0 or not math.isfinite(duration) or duration<=0:
        raise ValueError('Invalid motion analysis request')
    process=await asyncio.create_subprocess_exec('ffmpeg','-nostdin','-v','error',
        '-ss',f'{start:.3f}','-i',str(path),'-t',str(min(duration,20.)),
        '-vf',f'fps=4,scale={WIDTH}:{HEIGHT}',
        '-f','rawvideo','-pix_fmt','gray','pipe:1',
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:data,error=await asyncio.wait_for(process.communicate(),90)
    except asyncio.TimeoutError:
        process.kill();await process.communicate();raise RuntimeError('Motion analysis timed out')
    except asyncio.CancelledError:
        process.kill();await process.communicate();raise
    if process.returncode:raise RuntimeError(error.decode(errors='replace')[-240:])
    return track_frames(data)


def crop_filter(width:int, height:int, tracking:dict, source_seconds:float) -> str:
    """FFmpeg dynamic crop using bounded normalized center interpolation."""
    if not source_seconds > 0 or not math.isfinite(source_seconds):raise ValueError('Invalid shot duration')
    sx=tracking['start_x'];ex=tracking['end_x']
    sy=tracking['start_y'];ey=tracking['end_y']
    for v in (sx,ex,sy,ey):
        if not 0 <= v <= 1 or not math.isfinite(v):raise ValueError('Invalid tracking center')
    w=math.ceil(width*1.16/2)*2
    h=math.ceil(height*1.16/2)*2
    # Embedded formulas contain only computed, validated finite numbers.
    # Crop receives its own time value after setpts reset in the caller.
    x=f'max(0\\,min(in_w-out_w\\,in_w*({sx:.4f}+({ex-sx:.4f})*t/{source_seconds:.4f})-out_w/2))'
    y=f'max(0\\,min(in_h-out_h\\,in_h*({sy:.4f}+({ey-sy:.4f})*t/{source_seconds:.4f})-out_h/2))'
    return (f'setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=increase,'
            f'crop={width}:{height}:x={x}:y={y},setsar=1')
