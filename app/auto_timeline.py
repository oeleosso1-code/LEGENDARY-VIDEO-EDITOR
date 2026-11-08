"""Deterministic cut planning over real uploaded clips and locally detected beats.

It does not invent frames, identify football events or imply artistic judgment.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from .music_director import analyze_music
from .editor_pro import probe
from .shotlist import parse_shotlist


STYLE_PACE={'fast':1.6,'cinematic':3.1,'smooth':4.4,'documentary':5.0}


def build_timeline(durations: list[float], seconds: float, *, style: str='cinematic',
                   onsets: list[float] | None = None, reference_pace: float | None = None,
                   priority: list[int] | None = None) -> dict:
    if style not in STYLE_PACE or not durations or not math.isfinite(seconds) or not 1 <= seconds <= 10800:
        raise ValueError('Invalid plan settings')
    if any(not math.isfinite(d) or d < .2 for d in durations):
        raise ValueError('Invalid video source durations')
    if priority is None:priority=list(range(len(durations)))
    if sorted(priority)!=list(range(len(durations))):raise ValueError('Invalid visual ranking')
    pace=STYLE_PACE[style]
    if reference_pace is not None:
        if not math.isfinite(reference_pace): raise ValueError('Invalid reference pace')
        pace=max(.65,min(6.0,reference_pace))
    pace=max(.24, min(pace, max(durations)-.05))
    fps=25
    total_frames=round(seconds*fps)
    marks=[0]
    max_source_frames=max(5, math.floor(max(durations)*fps)-1)
    onset_frames=sorted({round(x*fps) for x in (onsets or []) if math.isfinite(x) and 0 < x < seconds})
    while marks[-1] < total_frames:
        left=total_frames-marks[-1]
        if left <= max_source_frames and left <= max(5,round(pace*fps*1.5)):
            end=total_frames
        else:
            target=marks[-1]+min(round(pace*fps), max_source_frames)
            options=[v for v in onset_frames if abs(v-target)<=round(.32*fps) and v-marks[-1]>=5]
            end=min(options,key=lambda n:abs(n-target)) if options else target
            if total_frames-end < 5 and left <= max_source_frames:end=total_frames
        if end <= marks[-1]:raise RuntimeError('Non-progressing edit planner')
        marks.append(end)
        if len(marks)>2401:raise ValueError('Too many shots; choose a slower cut pace')
    shots=[]
    for i,(a,b) in enumerate(zip(marks,marks[1:])):
        # Rotation avoids using one clip for all shots.
        clip=priority[i % len(durations)]
        duration=(b-a)/fps
        source=durations[clip]
        # Advance through each video, then wrap; no use beyond the source range.
        available=max(0,source-duration)
        if source < duration:
            # Pick the shortest feasible source that can hold this shot.
            possibles=[(d,j) for j,d in enumerate(durations) if d>=duration]
            if not possibles:raise ValueError('All source clips are shorter than an edit segment')
            clip=min(possibles)[1]
            source=durations[clip]
            available=source-duration
        start=round(((i//len(durations))*pace*1.37)%max(available,.001),3) if available>.01 else 0.
        start=min(start,max(0,source-duration))
        shots.append({'clip':clip,'start':start,'duration':duration,'speed':1.0})
    return {'shots':shots,'planning':{'strategy':'deterministic_real_footage',
            'style':style,'fps':fps,'suggested_pace':pace,'music_onsets_used':len(onset_frames)}}


async def plan_uploaded_sources(paths: list[Path], seconds: int, *, style: str,
                                song: Path | None=None, music_start: float=0,
                                reference_profile: dict | None=None,
                                priority: list[int] | None=None) -> dict:
    durations=[]
    for path in paths:
        seconds_in_source,video=await probe(Path(path))
        if not video:raise ValueError('Uploaded file is not a valid video: '+Path(path).name)
        durations.append(seconds_in_source)
    profile=await analyze_music(song,music_start=music_start,duration=seconds) if song else None
    beats=[x['time'] for x in profile['onsets'] if x['strength']>=.25] if profile else []
    pace=reference_profile.get('average_shot_seconds') if reference_profile else None
    result=build_timeline(durations,seconds,style=style,onsets=beats,reference_pace=pace,priority=priority)
    if profile:
        result['music_analysis']={'tempo_estimate_bpm':profile['tempo_estimate_bpm'],
                                  'onsets_used':len(beats),'music_start':music_start,
                                  'truncated':profile['truncated']}
    return result


def write_edit_plan(path: Path, plan: dict, durations: list[float], seconds: float) -> Path:
    """Validate before atomically publishing a user-editable shotlist."""
    import os,uuid
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.plan-'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(json.dumps({'shots':plan['shots']},ensure_ascii=False,indent=2),encoding='utf8')
        parse_shotlist(tmp,durations,seconds)
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
    return path
