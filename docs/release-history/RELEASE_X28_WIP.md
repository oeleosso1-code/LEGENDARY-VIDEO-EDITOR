# LEGENDARY VIDEO EDITOR X28 — long-render Telegram commands (WIP)

## Verified source baseline

X7 executable project plus `app/resume_render.py` (X27) and its tests. X8–X26 are not presumed fully integrated.

## New code

- `app/long_jobs.py`: persistent, atomic immutable request snapshot for a long-render job under a user's separate directory; validates ownership of uploaded source clips/music, size of task, orientation, color, pacing, and audio settings. Rejects unsupported manual shotlists/subtitles explicitly rather than silently ignoring them.
- `app/bot_pro.py`: registered `/longmake`, `/longstatus`, and `/longresume` with existing authorization guard and per-user task guard. Uses existing checkpoint renderer, stable work directory, shared render semaphore, and Telegram final-video delivery when within Bot API send limits.
- Resumes use the saved request rather than the user's subsequently modified session. The renderer checks actual input hashes before reusing chunks.
- Interrupted/running checkpoint state left over from a previous process is shown as interrupted when no current in-memory worker exists.
- `tests/test_long_jobs_x28.py`: persistence, isolation, validation, deleted-media handling, checkpoint reports, and mocked bot handler flow.

## Results

`python -m pytest -q`: 52 passed. Some preexisting tests include real FFmpeg MP4 rendering/reuse. New Telegram handler tests use local mocks; **no live Telegram server, AI cloud API or full-length render was tested**.

## Known limitations

- Single-process in-memory per-user task lock; no multi-replica distributed locking, durable queue or webhook setup.
- Only uploaded clips/song work in long-render mode; not Pexels, subtitles or manual shotlists. Processing each chunk independently can repeat footage and cause continuity issues.
- Cancellation signals the Python task, but no comprehensive guarantee of terminating all already-started FFmpeg descendants.
- No secure remote storage / large output delivery yet. Larger final outputs remain on the server.
- No GPU inference, semantic event understanding, motion tracking, human-professional montage quality guarantee.

The user requested **no project download or ZIP until final completion**. No archive has been created in this turn.
