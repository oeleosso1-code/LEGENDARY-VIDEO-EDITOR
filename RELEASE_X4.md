# X4 — Color grading and optional burned-in captions

## Added
- Presets for natural, cinematic, vivid, monochrome, warm, and cool footage color treatments using FFmpeg's `eq`, `hue`, and `colorbalance` filters.
- Optional SRT subtitle burn-in through FFmpeg's `subtitles` filter; requires FFmpeg built with libass.
- Local CLI accepts `--color` and `--subtitles`.
- Telegram bot accepts user-uploaded `.srt` documents and `/grade` color option; upload and bot routes **not live-tested**.
- Session settings and `edit_decisions.json` record the selected color and caption file.

## Local smoke test
An actual render was made from a local 6-second MP4 source, with an SRT subtitle file and the `warm` color setting. `ffprobe` confirmed a resulting MP4 of exactly 5.000 seconds. This validates a narrow representative case, not real-world caption readability across all phones/resolutions or human art direction.

## Unimplemented
Sophisticated speed ramps, motion tracked text, human-level editing decisions, real-time previews, licensed commercial audio discovery, and cloud render jobs remain unimplemented. User-supplied subtitles must be timed; whisper.cpp remains an optional post-render integration. All sample media belongs to the local test pipeline.
