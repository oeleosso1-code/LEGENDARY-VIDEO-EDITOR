# X13 WIP — Project checkpoints (verified available source baseline: X7)

## Context and scope
The working directory contained narrative WIP documentation for X8–X12 but not their source modules. The most recent available complete source archive was X7. X13 source work has therefore been applied to an extracted X7 baseline under `source/legendary-video-studio/`, NOT claimed as a verified X12 integration.

## Implemented
- `app/snapshots.py`: checkpoints saved inside each user's storage folder as JSON manifests.
- `/checkpoint NAME` creates checkpoint with SHA-256 content hashes for all referenced clips, music, subtitles and shotlist.
- `/checkpoints` lists previously saved checkpoint names for that user.
- `/restore NAME` verifies referenced files are still in the same user's directory, unmodified and accessible, then restores session metadata atomically.
- Prevents unsafe checkpoint filenames and cross-user access; refuses checkpoint/restore while render task active.
- No API secrets, tokens or credentials are included in checkpoint manifests.

## Limitations
- Checkpoints do not duplicate media, so deleting or altering the original upload makes restoring that checkpoint fail.
- SHA-256 verification reads the entire file, so checkpoint/restore may take additional time for large uploads.
- The Telegram commands have not been exercised against live Telegram; functions are syntactically valid and importable in the available environment.
- Long-form job controller X12 source is unavailable in the mounted working files and thus is NOT integrated here. Avoid claiming a X12->X13 upgrade until source recovery/porting is done.

## Verification
- `python -m pytest -q`: 49 passed on extracted X7 + X13 source.
- `python -m compileall -q app` passed.
