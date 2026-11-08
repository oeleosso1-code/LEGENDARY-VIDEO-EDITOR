"""Validated user-authored timeline for deliberate, repeatable edits.

Example: {"shots":[{"clip":0,"start":1.2,"duration":2.5,"speed":1.0}, ...]}
All positions are in seconds; clip refers to the order supplied to the editor.
"""
import json
import math
from pathlib import Path


def parse_shotlist(path: Path, source_durations: list[float], total: float) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('shots'), list):
        raise ValueError('Shotlist must contain a shots array')
    shots = data['shots']
    if not shots or len(shots) > 2400:
        raise ValueError('Shotlist needs 1 to 2400 shots')
    result = []
    accumulated = 0.0
    for index, raw in enumerate(shots):
        if not isinstance(raw, dict):
            raise ValueError(f'Shot {index}: object required')
        clip = raw.get('clip')
        if type(clip) is not int or not 0 <= clip < len(source_durations):
            raise ValueError(f'Shot {index}: invalid clip index')
        try:
            start, duration, speed = (float(raw.get('start', 0)), float(raw['duration']), float(raw.get('speed', 1)))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f'Shot {index}: invalid numeric fields') from None
        if not all(map(math.isfinite, (start, duration, speed))):
            raise ValueError(f'Shot {index}: non-finite time')
        if not (start >= 0 and duration >= 0.15 and 0.25 <= speed <= 4.0):
            raise ValueError(f'Shot {index}: invalid start, duration or speed')
        ramp=raw.get('ramp')
        if ramp is not None:
            if (not isinstance(ramp,list) or len(ramp) not in (3,5) or
                any(type(x) not in (int,float) or not math.isfinite(x) or not .25 <= x <= 4 for x in ramp)):
                raise ValueError(f'Shot {index}: ramp must be 3 or 5 speeds between 0.25 and 4')
            if speed != 1.0:
                raise ValueError(f'Shot {index}: speed and ramp cannot be combined')
            frames=round(duration*25)
            if frames < len(ramp):raise ValueError(f'Shot {index}: too short for speed ramp')
            base,extra=divmod(frames,len(ramp))
            consumed=sum((base+(1 if n<extra else 0))/25*r for n,r in enumerate(ramp))
        else:
            consumed=duration*speed
        if start + consumed > source_durations[clip] + 0.05:
            raise ValueError(f'Shot {index}: source too short for requested speed and duration')
        follow=raw.get('follow_motion',False)
        if type(follow) is not bool:raise ValueError(f'Shot {index}: follow_motion must be boolean')
        accumulated += duration
        shot={'clip': clip, 'start': start, 'duration': duration, 'speed': speed}
        if ramp is not None:shot['ramp']=[float(v) for v in ramp]
        if follow:shot['follow_motion']=True
        result.append(shot)
    if abs(accumulated - total) > 0.05:
        raise ValueError(f'Shotlist duration {accumulated:.3f}s does not match output {total:.3f}s')
    return result


def trim_shotlist(shots: list[dict], seconds: float) -> list[dict]:
    """Keep the first `seconds` of an already validated shotlist."""
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Preview duration must be positive')
    result=[]
    left=float(seconds)
    for shot in shots:
        if left <= 0.00001:
            break
        duration=min(left,shot['duration'])
        if duration < 0.15:
            raise ValueError('Preview creates a shot shorter than 0.15s')
        result.append({**shot,'duration':duration})
        left-=duration
    if left > 0.05:
        raise ValueError('Not enough footage in shotlist')
    return result
