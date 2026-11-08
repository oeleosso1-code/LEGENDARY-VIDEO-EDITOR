# X16 work-in-progress — timed Arabic motion titles

## Code basis
Recovered the full X7 source archive into `source/legendary-video-studio/` because the prior X8–X15 source files were not present in the current working directory (only notes). This branch does not claim those later features are restored.

## Implemented
- `app/motion_titles.py`: JSON cue validation, Arabic text shaping with Pillow/RAQM and Noto-compatible local font via fontconfig, luminous multi-pass title PNGs.
- FFmpeg alpha-faded overlays with small vertical movement, start/end times on the full timeline; 12 title cues max per render.
- Added `--titles path/to/titles.json` to `python -m app.cli` and `titles` parameter to `render_pro`.
- Preserves source soundtrack when drawing titles; metadata records cues in `edit_decisions.json`.
- Titles are user-authored; the engine does not yet automatically extract title timing from reference video or understand its semantics.

## CLI example
`python -m app.cli --clips clip.mp4 --music licensed.wav --seconds 5 --titles titles.json --preview --out sample.mp4`

Example titles JSON:
```json
[
  {"text": "لقطة أسطورية", "start": 0.5, "end": 2.8, "accent": "gold"},
  {"text": "مونتاج احترافي", "start": 3.0, "end": 4.5, "accent": "cyan"}
]
```

## Verification
- 42/42 tests passed (38 restored X7 tests + 4 new title tests).
- A true 5-second FFmpeg MP4 render with two timed Arabic titles and an AAC music track passed. A decoded PNG frame during the first cue contained visual detail beyond the flat test background.
- Did not perform live Telegram testing or import the X8–X15 features documented in notes.

## Dependencies
The title feature needs Pillow with libraqm, ffmpeg with libx264, and Arabic fonts accessible via fontconfig. `Pillow>=11,<13` was added to requirements, plus fonts in Dockerfile.
