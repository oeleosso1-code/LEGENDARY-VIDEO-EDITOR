# X27 work in progress — real checkpointed video rendering

## Source baseline

Reconstructed from the verified X7 ZIP at `source/legendary-video-studio`. This does **not** establish that X8–X26 were merged; those are largely release notes in the available working directory.

## Implemented

- `app/resume_render.py`: asynchronous `render_resumable()` method for rendering multiple real-footage chunks. It writes an atomic `status.json` with a signature, a completion count and whether work was reused.
- Each checkpoint is saved after video probing. Restarting the same job reuses valid completed checkpoints. Missing and invalid chunks are rendered again.
- SHA-256 hash of input contents, audio contents and output parameters prevents accidental reuse when a media file or output settings change.
- A single soundtrack is mixed after silent chunk concatenation, so separate chunks do not restart the song.
- Final rendering uses a `.partial.mp4` file and atomic rename after duration/video validation, keeping an earlier output intact if rendering fails.
- Existing UI/editor features are preserved from the verified X7 baseline.

## Tests run

`cd source/legendary-video-studio && python -m pytest -q` -> **46 passed**. Includes tests that actually render a ten-second MP4 from two parts, check that it has an audio stream, reuse checkpoints in a second run, invalidate checkpoints when color changes, and simulate a worker interruption that resumes from the one completed chunk. FFmpeg and ffprobe were installed in this test environment.

## Still missing, and must not be claimed complete

- A Telegram command or worker-queue adapter for this new checkpoint renderer; it is currently a local Python API.
- Distinct user-specific job work directories and cross-process locking must be enforced by caller. Do not share a work directory between simultaneous jobs.
- Timeline continuity across chunk boundaries, including scene choices, overlays, subtitles and manual shotlists. This API currently re-plans each chunk independently and **does not support** custom shotlists or subtitles.
- Advanced semantic scene understanding, music-direction decisions, motion tracking and professional VFX.
- Large-scale/end-to-end performance testing, real Telegram account connection, third-party cloud AI verification.
- Caching efficiency optimization: music changes currently invalidate video chunks too.

No ZIP was built or shared, following the user's instruction to withhold the final archive until the overall project is complete.
