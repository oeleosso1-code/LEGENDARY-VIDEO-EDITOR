# X8 development checkpoint (not a final release)

- Added deterministic scene-aware source-window selection; rotates through valid scenes and checks source duration.
- Corrected music onset extraction so `/musicstart` and `render_pro(music_start=...)` analyse the chosen section of the soundtrack instead of the beginning.
- Beat boundaries are recorded in `edit_decisions.json` for repeatable audits.
- Added X8 unit tests and a small real-FFmpeg export test.

Not implemented: semantic event recognition, licensed commercial music retrieval, human-level subjective edits, live Telegram production verification, scalable long-form processing. No secrets needed or stored. Do not distribute a final ZIP until the owner requests it.
