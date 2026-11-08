# X22 — Editable persistent timeline (work in progress)

## Baseline and scope

Only the full X7 code archive was present in the active working environment. X8–X21 were primarily release notes; their functions must **not** be counted as implemented in this tree without code verification. This change applies to restored X7 code under `project/legendary-video-studio`.

## Implemented

- `app/project_timeline.py`: persistent JSON edit plan with clip metadata, source stat fingerprints, monotonic revision, atomic writes, insert/replace/delete/reorder operations, strict duration and shot validation using the existing `parse_shotlist` function, and export to the engine's original shotlist format.
- `app/project_cli.py`: local project creation, inspection, editing, validation and rendering to MP4. No key or Telegram token necessary.
- Regression and real-FFmpeg tests in `tests/test_project_timeline.py`.

## Example commands

From `project/legendary-video-studio` with FFmpeg available:

```bash
python -m app.project_cli create project.json --clips my_clip.mp4 --shot '[{"clip":0,"start":0,"duration":5,"speed":1}]'
python -m app.project_cli validate project.json
python -m app.project_cli show project.json
python -m app.project_cli move project.json --index 1 --destination 0 --expected-revision 0
python -m app.project_cli render project.json --out edit.mp4 --preview
```

`move` example assumes at least two shots. Shot positions use **zero-based** indexing. Use `--expected-revision` to reject stale edits.

## Limitations

- Media is referenced, not copied into the project. Source changes invalidate the saved plan. Stat-based fingerprints are lightweight (size/mtime), **not cryptographic verification**.
- This tool runs locally; its operations are not wired into the live Telegram bot yet.
- This is not a visual video editor, does not understand emotions or football goals, and is not human-quality autonomous editing.
- Underlying `render_pro` currently requires an approximately integer number of output seconds and a target duration between 5 seconds and configured maximum.
- Concurrency between distinct CLI processes remains subject to file locking not yet implemented; optimistic revisions detect but cannot prevent simultaneous read-modify-write races.
- Live Telegram, AI APIs, video longer than the sample test, and external sources were not tested.
