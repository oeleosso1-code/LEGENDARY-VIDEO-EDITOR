"""Optional adapters to third-party open source tools.

No third-party source code is copied; adapters invoke installed tools/libraries.
These are opt-in features: ordinary rendering works without their installation.
"""
import asyncio
import shutil
from pathlib import Path


class IntegrationUnavailable(RuntimeError):
    pass


def scene_boundaries(path: Path, threshold: float = 27.0) -> list[tuple[float, float]]:
    """PySceneDetect BSD-3-Clause; returns time spans, or a clear installation error."""
    try:
        from scenedetect import detect, ContentDetector
    except ImportError as exc:
        raise IntegrationUnavailable('Install the optional scenedetect-headless package') from exc
    scenes = detect(str(path), ContentDetector(threshold=threshold), show_progress=False)
    return [(s.get_seconds(), e.get_seconds()) for s, e in scenes if e.get_seconds() > s.get_seconds()]


async def clean_silence(source: Path, output: Path) -> Path:
    """Run WyattBlue/auto-editor (Unlicense), when installed, on dialogue content."""
    if not shutil.which('auto-editor'):
        raise IntegrationUnavailable('Install the optional auto-editor executable')
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['auto-editor', str(source), '--output', str(output), '--no-open']
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(p.communicate(), timeout=3600)
    except BaseException:
        p.kill()
        await p.communicate()
        raise
    if p.returncode or not output.is_file():
        raise RuntimeError('Auto-Editor failed: ' + err.decode(errors='replace')[-700:])
    return output


async def transcribe_srt(source: Path, output_prefix: Path, model: Path) -> Path:
    """Run whisper.cpp (MIT); requires installed whisper-cli and a locally installed model."""
    if not shutil.which('whisper-cli'):
        raise IntegrationUnavailable('Install whisper.cpp whisper-cli')
    if not model.is_file():
        raise IntegrationUnavailable('Provide an existing whisper.cpp GGML model file')
    if not shutil.which('ffmpeg'):
        raise IntegrationUnavailable('FFmpeg is required to prepare 16 kHz audio')
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    wav = output_prefix.with_suffix('.wav')
    p = await asyncio.create_subprocess_exec('ffmpeg','-hide_banner','-v','error','-y','-i',str(source),'-ar','16000','-ac','1','-c:a','pcm_s16le',str(wav), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await p.communicate()
    if p.returncode:
        raise RuntimeError('Audio conversion failed: ' + err.decode(errors='replace')[-400:])
    try:
        p = await asyncio.create_subprocess_exec('whisper-cli','-m',str(model),'-f',str(wav),'-osrt','-of',str(output_prefix),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(p.communicate(), timeout=7200)
        except BaseException:
            p.kill()
            await p.communicate()
            raise
        srt = Path(str(output_prefix) + '.srt')
        if p.returncode or not srt.is_file():
            raise RuntimeError('whisper.cpp failed: ' + err.decode(errors='replace')[-700:])
        return srt
    finally:
        wav.unlink(missing_ok=True)
