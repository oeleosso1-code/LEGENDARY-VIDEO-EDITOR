# X12 WIP — Telegram Long-form Job Controller

## Implemented
- `/longmake` runs X11's resumable, verified-chunk export from a Telegram session containing user-uploaded clips.
- `/longstatus` reads atomic per-user job metadata including chunk totals and current stage.
- `/longcancel` requests cancellation and retains completed valid segments for later reuse.
- `/longresume` explicitly reruns the long-form renderer on current session inputs and uses cached chunks if their signature and verification match.
- Only the final assembled picture gets the global music track and optional timed subtitles.
- The run state is saved as `longform_job.json` under that user's configured storage folder. Input folders are checked before rendering.
- A progress callback is available to longform renderer clients.

## Known boundaries
- `/longresume` uses the **current session** settings. For strict restoration of a prior project, session snapshots/versions still need to be implemented.
- Progress represents completed *video chunks*, not final audio/subtitle processing, and does not provide a percentage of total wall time.
- Each video chunk is rendered with the existing automatic editor. Since its content selection begins anew in each chunk, continuity across chunk boundaries is not yet guaranteed.
- No multi-process lock, cloud queue, persistent worker recovery, or HTTPS download links have been implemented. Run one bot worker at a time.
- Telegram interaction is unit tested using simulated interfaces; no live Telegram server/API key was used.
- This release does not add copyrighted song retrieval or bypass licensing controls.

## Verification
Run `python -m pytest -q` at the repository root. Existing FFmpeg integration tests cover actual video export, while Telegram controller tests use mocks.
