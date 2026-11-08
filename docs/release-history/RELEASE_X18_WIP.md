# X18 — Telegram-controlled Arabic animated titles (WIP)

## Verified codebase
Built on recovered X7 source plus executable X17 music_titles/editor_pro/audio improvements. Previous release notes alone do not establish restored functionality for all intermediate releases.

## Changes
- `app/title_controls.py`: validates timed Arabic title cues, prevents non-finite timestamps, enforces a 20-cue limit, validates supported accent colors, removes titles, writes a job-local JSON cue file.
- `app/bot_pro.py`: `/titleadd start end accent text`, `/titles`, `/titledel index`, `/titleclear` Telegram commands; title cues are saved in per-user session state.
- Telegram `/preview` clips titles to its shorter preview duration without changing the original session.
- Telegram render path creates cue JSON within isolated render directory and passes it to the existing `render_pro(..., titles=...)` pipeline.
- `app/store.py`: new sessions include `title_cues: []`. Schema version left at 7 to preserve compatibility with preexisting X7 tests; a future migration/versioning system is still needed.
- `tests/test_x18.py`: six unit/controller tests covering validation, limits, preview clipping, file format, simulated Telegram commands, and invalid inputs.

## Evidence
- `python -m pytest -q`: **48 passed**.
- `python -m compileall -q app`: passed.
- Actual FFmpeg render created `x18-check/result.mp4` (5.0 seconds, MP4 with visible timed Arabic titles); decoded frame comparison shows changed pixels during first cue.

## Limitations
- Real Telegram API connection was NOT tested (python-telegram-bot not installed in local test environment); controller tested with stubs.
- Color and fade overlay are basic, not professional motion tracking or semantic video understanding.
- Video render smoke test is silent; previously tested music workflows remain separate.
- The project is still WIP; no final ZIP should be delivered until user explicitly changes request.
