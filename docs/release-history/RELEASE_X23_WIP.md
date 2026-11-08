# X23 — Safe project revisions (work in progress)

Based on the runnable X7 source plus the persistent project editing feature added to the working tree. This does not establish that intervening X8–X21 releases are integrated.

## Implemented

- POSIX `fcntl.flock` edit serialization on `<project>.lock` for local concurrent processes.
- Optimistic `expected_revision` checks inside the lock, preventing stale edits from silently overwriting another edit.
- Pre-edit metadata snapshots stored atomically in `<project>.history/rev_NNNNNNNN.json`.
- `restore_revision` creates a new revision rather than overwriting history.
- New local CLI commands: `history` and `restore --revision N --expected-revision CURRENT`.
- `tests/test_x23_history.py`: revision histories, restoration, invalid revision handling, cross-process stale edit conflict.

## Verification

`python -m pytest -q` — **47 passed**, two Python 3.13 multiprocessing fork deprecation warnings. No Telegram production connection tested.

## Examples

```bash
python -m app.project_cli history edit.json
python -m app.project_cli restore edit.json --revision 0 --expected-revision 2
python -m app.project_cli validate edit.json
```

## Limitations

- Linux/macOS flock on local filesystem. Windows requires another locking backend; remote network filesystems may vary.
- Project histories contain metadata and media paths, not media files; source video and music must remain available.
- Concurrent project creation is not serialized in the CLI. Snapshot writes and file updates are individually atomic, not one multi-file transaction across power failure.
- Restoring preserves references but requires subsequent `validate` and export; no live Telegram integration of revision history exists.
- This is a reliability improvement, not semantic film editing or automated recreation of a reference video.
