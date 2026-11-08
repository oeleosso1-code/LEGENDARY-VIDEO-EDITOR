# X26 (work in progress) — persistent Telegram render status

Base: restored X7 source at `source/legendary-video-studio`. The X8–X25 implementation is not assumed to be available or integrated.

## Implemented in this iteration
- New `app/job_registry.py`: atomic per-user job status (`queued`, `running`, `completed`, `failed`, `cancelled`, `interrupted`) and minimal phase updates.
- Integrates registry into `/make`, `/preview`, `/status` and the render controller.
- Marks pre-existing queued/running records as interrupted when the bot starts again.
- Handles tasks cancelled while waiting to acquire the global rendering semaphore.
- Stores no API keys, user text prompts or sensitive payloads in `job.json`.
- Four focused new tests for lifecycle, permissions by user directory, restart semantics and status metadata.

## Verification
- `python -m pytest -q`: 42 passed (38 restored baseline + 4 new tests).
- `python -m py_compile app/bot_pro.py app/job_registry.py`: passed.
- Telegram API / remote AI providers: NOT connected or end-to-end tested.
- Video editing and long-video resume functions described in older WIP notes are NOT claimed as restored.

## Limitations / unfinished
- The job registry is status/audit, **not** a persistent queue or video checkpoint/resume engine; interrupted tasks require explicit restart.
- `/cancel` requests task cancellation but external ffmpeg process may continue if subprocess cancellation is not handled by its wrapper.
- A Telegram-account integration test, worker shutdown handling, cleanup retention policy, multi-worker locking, delivery of very large videos and event-based progress percentages are still needed.
- The creative quality of montage cannot be inferred from these passing unit tests.
