import asyncio
import math
from pathlib import Path
from .planner import VideoRequest

async def run_ffmpeg(*args: str) -> None:
    process = await asyncio.create_subprocess_exec('ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode('utf-8', errors='replace')[-1200:])

async def render(inputs: list[Path], target: Path, request: VideoRequest) -> None:
    if not inputs:
        raise ValueError('لا توجد لقطات للفيديو')
    width, height = (720, 1280) if request.vertical else (1280, 720)
    duration = math.ceil(request.duration / len(inputs))
    prepared = []
    for index, original in enumerate(inputs):
        segment = target.parent / f'segment_{index:03}.mp4'
        filters = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=25,format=yuv420p'
        await run_ffmpeg('-stream_loop', '-1', '-i', str(original), '-t', str(duration), '-vf', filters, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-movflags', '+faststart', str(segment))
        prepared.append(segment)
    # Each segment uses identical format, encoder, framerate and stream structure.
    manifest = target.parent / 'concat.txt'
    manifest.write_text(''.join(f"file '{p.name}'\n" for p in prepared), encoding='utf-8')
    await run_ffmpeg('-f', 'concat', '-safe', '1', '-i', str(manifest), '-t', str(request.duration), '-c', 'copy', '-movflags', '+faststart', str(target))
