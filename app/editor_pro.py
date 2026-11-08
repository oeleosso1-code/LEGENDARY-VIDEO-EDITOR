"""Real footage editing engine. Beat-aware jump cuts, portrait/landscape, music mixing, output MP4."""
import asyncio
import json
import math
from pathlib import Path
from .audio import beat_grid,duration_segments
from . import config
from .integrations import scene_boundaries, IntegrationUnavailable
from .visual import inspect_clip, balanced_clip_order
from .shotlist import parse_shotlist

async def command(*args: str,timeout: int=7200):
    p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try: out,err=await asyncio.wait_for(p.communicate(),timeout)
    except asyncio.TimeoutError:
        p.kill();await p.communicate();raise RuntimeError('تجاوزت المعالجة المهلة المحددة')
    except asyncio.CancelledError:
        p.kill();await p.communicate();raise
    if p.returncode: raise RuntimeError(err.decode(errors='replace')[-1200:])
    return out

async def probe(path: Path):
    out=await command('ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path),timeout=30)
    data=json.loads(out)
    dur=float(data.get('format',{}).get('duration') or 0)
    video=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),None)
    return dur, bool(video)

COLOR_PRESETS = {
    'natural': '',
    'cinematic': 'eq=contrast=1.08:saturation=0.93:brightness=-0.015',
    'vivid': 'eq=contrast=1.10:saturation=1.22',
    'noir': 'hue=s=0,eq=contrast=1.13',
    'warm': 'colorbalance=rs=.045:gs=.015:bs=-.045',
    'cool': 'colorbalance=rs=-.035:gs=.01:bs=.045',
}

def subtitle_filter(path: Path) -> str:
    """Escape an absolute SRT path for FFmpeg libass filtergraph syntax."""
    safe = str(path.resolve()).replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'").replace(',', '\\,').replace('[', '\\[').replace(']', '\\]')
    return f"subtitles=filename='{safe}'"

async def render_pro(inputs: list[Path],music: Path | None,target: Path,seconds: int,orientation='vertical',style='cinematic',color='natural',subtitles: Path | None=None,music_volume: float=0.85, preview: bool=False, shotlist: Path | None=None, music_start: float=0.0):
    if not math.isfinite(music_start) or music_start < 0: raise ValueError('Music start must be non-negative')
    if not inputs: raise ValueError('أضف فيديوهات أو اسم موضوع للبحث عن لقطات')
    if color not in COLOR_PRESETS: raise ValueError('Unknown color grade')
    if not 0 <= music_volume <= 1.5: raise ValueError('Music volume must be between 0 and 1.5')
    if subtitles is not None and (not subtitles.is_file() or subtitles.suffix.lower() != '.srt'): raise ValueError('Subtitles must be an existing SRT file')
    if not 5 <= seconds <= config.MAX_DURATION:raise ValueError('مدة الفيديو خارج الحدود المسموحة')
    target.parent.mkdir(parents=True,exist_ok=True)
    size=((360,640) if orientation=='vertical' else (640,360)) if preview else ((720,1280) if orientation=='vertical' else (1280,720))
    width,height=size
    step={'fast':1.6,'cinematic':3.2,'smooth':4.5,'documentary':5.5}.get(style,3.2)
    boundaries=await beat_grid(music,seconds,spacing=step) if shotlist is None else []
    durations=duration_segments(seconds,boundaries) if shotlist is None else []
    metadata=[]; valid=[]; inspections=[]
    scene_map = {}
    for clip in inputs:
        dur,hasvideo=await probe(clip)
        if hasvideo and dur>.15:
            valid.append((clip,dur))
            try:
                inspections.append(await inspect_clip(clip,dur,style))
            except Exception:
                inspections.append({"score":0,"samples":0,"style":style})
            if config.SCENE_DETECTION:
                try: scene_map[clip] = scene_boundaries(clip)
                except IntegrationUnavailable: pass
                except Exception: pass  # Scene detection is an optional enhancement.

    if not valid: raise RuntimeError('الملفات لا تحتوي على فيديو صالح')
    manual=parse_shotlist(shotlist,[v[1] for v in valid],seconds) if shotlist else None
    if manual is not None: durations=[s['duration'] for s in manual]
    # Prevent a pathological huge number of segments.
    if len(durations)>2400:raise ValueError('عدد القصات كبير جداً')
    staged=[]
    order=balanced_clip_order([s["score"] for s in inspections],len(durations)) if manual is None else [s['clip'] for s in manual]
    usage=[0]*len(valid)
    for i,d in enumerate(durations):
        choice=order[i]
        source,src_dur=valid[choice]
        repetition=usage[choice]
        usage[choice]+=1
        speed=manual[i]['speed'] if manual is not None else 1.0
        # Choose alternate regions within long sources instead of looping from beginning.
        usable=max(0.0,src_dur-d)
        offset=min(usable, repetition*max(1.1,step)*1.31 % max(usable,.001)) if usable else 0.
        # Scene-aware sourcing: prefer actual scene start boundaries over arbitrary mid-shot cuts.
        if manual is not None: offset=manual[i]['start']
        elif scene_map.get(source):
            options=[(start,end) for start,end in scene_map[source] if end-start >= min(d,src_dur)]
            if options:
                offset=options[repetition % len(options)][0]
        dst=target.parent/f'shot_{i:05}.mp4' 
        vf=f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=25,format=yuv420p'
        if COLOR_PRESETS[color]: vf+=','+COLOR_PRESETS[color]
        if style=='smooth' and d>=2: vf+=f',fade=t=in:st=0:d=0.15,fade=t=out:st={max(0,d-0.15):.3f}:d=0.15'
        if manual is not None:
            vf+=f',setpts=(PTS-STARTPTS)/{speed:.6f}'
        cmd=['ffmpeg','-hide_banner','-v','error','-y','-ss',f'{offset:.3f}','-stream_loop','-1','-i',str(source),'-t',f'{d * speed:.3f}' if manual is not None else f'{d:.3f}','-vf',vf,'-an','-c:v','libx264','-preset',config.VIDEO_PRESET,'-crf',('28' if preview else '25'),'-pix_fmt','yuv420p',str(dst)]
        await command(*cmd)
        staged.append(dst)
        metadata.append({'source':source.name,'offset':round(offset,3),'seconds':d,'speed':speed,'manual':manual is not None,'source_quality_score':inspections[choice]['score']})
    # Concat demuxer reads file names relative to its manifest, quote escaping disabled by UUID names.
    manifest=target.parent/'timeline.ffconcat'
    manifest.write_text('ffconcat version 1.0\n'+''.join(f'file {p.name}\n' for p in staged),encoding='utf-8')
    silent=target.parent/'picture.mp4'
    await command('ffmpeg','-hide_banner','-v','error','-y','-safe','1','-f','concat','-i',str(manifest),'-t',str(seconds),'-c:v','copy','-movflags','+faststart',str(silent))
    if subtitles:
        # Burn user-supplied SRT using FFmpeg's subtitles filter (requires libass).
        subtitled=target.parent/'captioned.mp4'
        await command('ffmpeg','-hide_banner','-v','error','-y','-i',str(silent),'-vf',subtitle_filter(subtitles),'-c:v','libx264','-preset',config.VIDEO_PRESET,'-crf','23','-an','-movflags','+faststart',str(subtitled))
        silent=subtitled
    if music:
        # Mild fade on soundtrack ending. Never attempt to rip streaming-service songs.
        fade=max(0,seconds-1.1)
        await command('ffmpeg','-hide_banner','-v','error','-y','-i',str(silent),'-ss',f'{music_start:.3f}','-stream_loop','-1','-i',str(music),'-filter_complex',f'[1:a]volume={music_volume:.3f},afade=t=out:st={fade:.2f}:d=1.1[a]','-map','0:v:0','-map','[a]','-t',str(seconds),'-c:v','copy','-c:a','aac','-b:a','160k','-movflags','+faststart',str(target))
    else: silent.replace(target)
    info={'orientation':orientation,'style':style,'color':color,'subtitles':subtitles.name if subtitles else None,'music':music.name if music else None,'seconds':seconds,'preview':preview,'music_volume':music_volume,'music_start':music_start,'shotlist':shotlist.name if shotlist else None,'timeline':metadata,'clip_inspections':[{'source':v[0].name,**inspections[i]} for i,v in enumerate(valid)],'note':'Hard cuts are optionally aligned to soundtrack energy peaks. No claim of subjective quality or scene understanding.'}
    (target.parent/'edit_decisions.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    # Staged intermediates can grow large. Keep sources + manifest + edit decision list, remove transcodes.
    for p in staged: p.unlink(missing_ok=True)
    return info
