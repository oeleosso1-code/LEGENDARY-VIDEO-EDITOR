"""Validated Arabic/Unicode title overlays for fixed-timeline rendering.

Text is read from UTF-8 files, never interpolated into filter arguments.
The caller is responsible for rights to fonts and video footage.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

PALETTE = {'white':'white','gold':'0xFFD966','yellow':'yellow',
           'cyan':'cyan','red':'red','green':'0x8EF8AD'}
MAX_TITLES = 50


def load_titles(path: Path, total: float) -> list[dict]:
    path = Path(path)
    if path.suffix.lower() != '.json' or not path.is_file() or path.stat().st_size > 64 * 1024:
        raise ValueError('Invalid titles JSON file')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or not isinstance(payload.get('titles'), list):
        raise ValueError('Titles JSON must contain titles array')
    rows = payload['titles']
    if len(rows) > MAX_TITLES:
        raise ValueError('Too many titles')
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f'Title {i}: object required')
        content = row.get('text')
        if not isinstance(content, str) or not content.strip() or len(content) > 140 or '\n' in content or '\r' in content or any(ord(c) < 32 for c in content):
            raise ValueError(f'Title {i}: invalid text')
        try:
            start, end = float(row['start']), float(row['end'])
        except (KeyError, ValueError, TypeError):
            raise ValueError(f'Title {i}: invalid timing') from None
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or end > total + .05:
            raise ValueError(f'Title {i}: timing outside video')
        color = row.get('color','white')
        if color not in PALETTE:
            raise ValueError(f'Title {i}: invalid color')
        position = row.get('position','center')
        if position not in ('top','center','bottom'):
            raise ValueError(f'Title {i}: invalid position')
        out.append({'text':content, 'start':start, 'end':end, 'color':color,'position':position})
    return out


def _escape_filter_path(path: Path) -> str:
    # Escape for the FFmpeg filtergraph parser, followed by the option parser.
    return str(path.resolve()).replace('\\','\\\\').replace(':','\\:').replace("'", "\\'").replace(',','\\,').replace('[','\\[').replace(']','\\]')


def title_filters(titles: list[dict], temp_dir: Path, font: Path) -> str:
    if not font.is_file():
        raise RuntimeError('An Arabic-capable .ttf font must be installed')
    fonts = _escape_filter_path(font)
    terms = []
    for i, title in enumerate(titles):
        textpath = temp_dir / f'title_{i:03d}.txt'
        textpath.write_text(title['text'],encoding='utf-8')
        safe = _escape_filter_path(textpath)
        vertical = {'top':'(h*0.15-text_h/2)','center':'(h-text_h)/2',
                    'bottom':'(h*0.84-text_h/2)'}[title['position']]
        # Avoid unsafe expression parsing from untrusted input: only validated numbers are used.
        # Double drawtext creates a restrained soft-ish outline, not a true blur/glow.
        base = (f'fontfile={fonts}:textfile={safe}:text_shaping=1:'
                f'fontsize=h*0.054:x=(w-text_w)/2:y={vertical}:'
                f'enable=between(t\\,{title["start"]:.3f}\\,{title["end"]:.3f})')
        terms.append(f'drawtext={base}:fontcolor=black@0.65:borderw=5:bordercolor=black@0.45')
        terms.append(f'drawtext={base}:fontcolor={PALETTE[title["color"]]}:borderw=1:bordercolor=black@0.8')
    return ','.join(terms)


def find_font() -> Path:
    import os
    override = os.environ.get('VIDEO_EDITOR_ARABIC_FONT')
    options = ([Path(override)] if override else []) + [
        Path('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'),
        Path('/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in options:
        if path.is_file():
            return path
    # Distros often install Noto with different filenames; respect fc-match.
    import subprocess
    try:
        result = subprocess.run(['fc-match','-f','%{file}','Noto Sans Arabic'],capture_output=True,text=True,timeout=3,check=True)
        p = Path(result.stdout.strip())
        if p.is_file():
            return p
    except (OSError, subprocess.SubprocessError):
        pass
    raise RuntimeError('No Arabic-capable font found')
