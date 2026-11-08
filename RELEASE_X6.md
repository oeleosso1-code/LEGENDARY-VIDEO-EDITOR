# LEGENDARY VIDEO EDITOR X6 — Manual timeline and soundtrack offsets

## New working features

1. **Precisely controlled shotlists** for local CLI. Write a JSON file with a `shots` array. Each shot selects the clip by its zero-based index from `--clips`, the source `start`, its final screen `duration`, and `speed` (0.25–4.0). The engine validates time bounds and total duration, then creates a deterministic edit, rather than automatically selecting sources and cuts.
2. **Per-shot speed adjustment** using FFmpeg timestamps. This is basic slow/fast playback, not optical-flow frame interpolation or keyframed cinematic speed ramps.
3. **Song start selection** via `--music-start` (CLI) and `/musicstart N` (Telegram). This allows editors to use a specific authorized part of a user-supplied song.
4. **Detailed audit trail** in `edit_decisions.json` includes manual flags, speeds and music offset.

## Example: render deliberately chosen shots

```bash
python -m app.cli --clips clips/action.mp4 clips/closeup.mp4 \
  --shotlist example_shotlist.json --seconds 5 \
  --music permitted-song.mp3 --music-start 24 \
  --style cinematic --orientation horizontal --out edited.mp4
```

The sample file is `example_shotlist.json`. Its example source time windows require both original clips to be long enough. When using shotlists, the `--seconds` value **must** equal the sum of `duration` entries, within 0.05s.

## Telegram

Upload your permitted audio and videos. `/musicstart 24` chooses 24 seconds into the uploaded track and `/make` renders as before. **Telegram does not yet accept shotlist uploads**; authoring a manually controlled timeline is a CLI feature. The Telegram bot has not been validated against a live account.

## Test evidence

- 32 unit/integration tests passed, including two source MP4 fixtures and a real 5-second shotlist transcode. FFprobe confirmed duration within ±0.2s.
- Existing X5 functionality and the optional open-source integrations are retained.
- Not included: generative footage, arbitrary commercial-music downloads, optical flow, AI scene semantics, motion tracking, multi-tenant cloud processing or a graphical editor.
