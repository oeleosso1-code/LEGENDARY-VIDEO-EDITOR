# X14 Development — Resumable Long Video Render (verified local baseline)

Source: `source/legendary-video-studio/app/long_render.py`.

## Implemented
- Divides a requested render into integer-length chunks (minimum 5 s).
- Validates each finished chunk with ffprobe before reuse.
- Saves state atomically to a per-output `state.json` containing a fingerprint of the media and edit settings.
- Invalidates stale chunks if media file sizes/mtimes or relevant settings change.
- Optionally slices a user shotlist across chunk boundaries, with explicit rejection of tiny split shots (<0.15 s).
- Concatenates the video chunks and adds one continuous music track and optionally burn-in subtitles *after* concatenation.
- Local CLI: `python -m app.cli --clips clip.mp4 --music licensed.wav --seconds 60 --long --chunk-seconds 15 --out result.mp4`.

## Not implemented or verified
- No live Telegram job scheduling/hosting; user requested no release archive until completion.
- No cloud storage, no guaranteed crash-safe cross-process synchronization, no comprehensive content analysis, no artistically expert edits.
- Automatic per-chunk editing may differ from one holistic musical edit; transition continuity still needs improvement.
- Files can change while rendering; a single preflight fingerprint is not a full immutable media snapshot. For production use, introduce source pinning and job locking.
- ffmpeg intermediate storage can be large. Tested with small synthetic examples, not hours of real 4K media.

Do not publish this as a final production release.
