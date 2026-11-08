# LEGENDARY VIDEO EDITOR X30 — Telegram + fixed-timeline integration (WIP)

## Actual changes in executable source
- `app/long_jobs.py`: accept a valid owner-uploaded shotlist for long render, validate its structure, freeze a copy under a per-job private folder, record a SHA-256 digest, and reject altered snapshots during resume. Old long-render requests without a shotlist still use the previous automatic clip path.
- `app/bot_pro.py`: `/longmake` and `/longresume` now select `render_timeline` when the approved shotlist exists. Otherwise they select `render_resumable`. Timeline chunk progress is atomically saved in `timeline_status.json` for `/longstatus`.
- `app/timeline_render.py`: optional progress callback reports completed cache chunks and completion state; encoding and cached segment validation remain in the existing X29 renderer.
- `tests/test_x30_telegram_timeline.py`: tests snapshot immutability, ownership boundaries, timing validity, end-to-end video export through a simulated Telegram Bot, and cached repeat render.

## Verification
From `source/legendary-video-studio`, ran `python -m pytest -q`: **59 passed**. End-to-end test generates actual small MP4 sources through FFmpeg, invokes the same `process_long_job` function as Telegram, checks successful completion, then repeats the job and verifies its chunk is reused.

## Limitations
- Telegram SDK is mocked in tests. No live Bot API connectivity or deployment was verified.
- Fixed timeline path does not support titles/subtitles, multi-server locking, cloud object storage, real-time preview or semantic AI scene understanding.
- The fixed timeline renderer currently uses 360×640 or 640×360 output, 25 fps, hard cuts, selected speeds, six color presets, and one audio bed. Default chunk target is 20 seconds (short 5-second tests produce one cached chunk).
- Output sizing for large content requires secure external delivery; only files within the bot's message size limit are sent directly.
- User requested no ZIP/file delivery before end-to-end project completion. No package was produced in this update.
