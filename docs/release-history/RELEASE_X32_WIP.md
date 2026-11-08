# LEGENDARY VIDEO EDITOR X32 — Arabic title overlays on long fixed-timeline renders

## Implemented and verified
- `app/titles.py`: strictly validated `titles.json` with up to 50 single-line Arabic/Unicode titles, timing, position and palette; no user text interpolated into FFmpeg filter expressions. Finds installed Arabic-capable font and uses FFmpeg `drawtext` with text shaping, outline and colour.
- `app/timeline_render.py`: titles are composited onto the full timeline after silent video chunks are concatenated, together with optional SRT captions. Music is added only once afterward. Visual chunk cache remains reusable when the titles change. CLI now accepts `--titles` and `--subtitles`.
- `app/long_jobs.py`: stores a job-scoped immutable `approved_titles.json`; SHA-256 checked on resume, prevents altered title content, and enforces an existing fixed shotlist.
- `app/store.py`, `app/bot_pro.py`: `titles.json` uploaded to Telegram is validated and kept in the user's session; forwarded into `/longmake` and `/longresume`; session `/clear` also removes it.
- `tests/test_x32_titles.py`: genuine two-clip FFmpeg MP4 output, two Arabic titles appearing at different times, music, SRT, cached chunk reuse, input validation and frozen snapshot tamper detection.

## Verification
Full regression suite: **65 passed**. `python -m compileall -q app` passed. Local FFmpeg video render tested. Telegram real network and deployment still untested.

## Titles JSON example
```json
{"titles":[
  {"text":"مونتاج أسطوري","start":0.3,"end":1.5,"color":"gold","position":"center"},
  {"text":"العراق","start":2.4,"end":3.4,"color":"cyan","position":"top"}
]}
```
Upload as `titles.json` alongside `shotlist.json` for `/longmake`. Valid colors: white, gold, yellow, cyan, red, green; positions: top, center, bottom. Requires ffmpeg with drawtext + Arabic-capable system font (Dockerfile now installs fontconfig and fonts-noto-core; actual container build remains unverified).

## Limitations
- Text is statically positioned with a bold border, not full per-letter keyframe animation, true optical glow or motion tracking.
- Automatic content understanding and human-quality artistic edit decisions remain unimplemented.
- Titles currently work only on fixed-shotlist long timeline; short `/make` and legacy auto long-render don't use this module.
- Docker build and live Telegram connectivity still require deployment validation.
- No ZIP or final deliverable generated at user request.
