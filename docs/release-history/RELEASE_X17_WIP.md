# X17 — Music-offset-aware editing and timed Arabic titles (work in progress)

## Reliable starting point
Reconstructed source from X7 ZIP in `source/legendary-video-studio/`. Prior X8–X16 modules were not present as files; their release notes alone do not establish executable features. This branch implements a fresh, verifiable title module. It does not claim restoration of missing features.

## Implemented
- `app/audio.py`: `beat_grid` accepts `music_start` and decodes audio from that point, aligning detected peaks to the actual excerpt used in the output.
- `app/music_titles.py`: validates up to 20 JSON cues, draws Arabic/RTL title overlays with Pillow RAQM, supports four accent colors, glows and per-cue alpha fade in/out.
- `app/editor_pro.py`: optional `titles` overlay and `snap_titles` near existing onset boundaries; keeps source video in place and adds the music after video/title processing; records title cues in edit decisions.
- `app/cli.py`: `--titles titles.json` and `--snap-titles`.
- Container dependencies: Pillow, fontconfig, Noto fonts.

## Example
```
python -m app.cli --clips owned_clip.mp4 --music authorized_track.wav \
  --seconds 15 --titles titles.json --snap-titles --out final.mp4
```

Example `titles.json`:
```
[
  {"text":"لقطة أسطورية","start":0.6,"end":2.4,"accent":"gold"},
  {"text":"مونتاج احترافي","start":2.8,"end":4.6,"accent":"cyan"}
]
```

## Verification
- 41/41 available pytest tests passed (X7 recovered suite plus three new title validation tests).
- Actual FFmpeg render succeeded: 5.000-second MP4, two Arabic titles and an AAC music stream.
- Decoded frames at 1.1s and 2.55s show changed pixels consistent with title appearing then disappearing.

## Limitations
- Video-reference style imitation, semantic event detection and professional creative grading remain unimplemented here.
- Dynamic typography limited to alpha fades and fixed positions; no motion tracking or object-aware text placement.
- Title snapping uses short-duration cut points, not detailed beat/downbeat understanding.
- Did not connect to actual Telegram servers; titles are CLI-only at this stage.
- No files released to user per request.
