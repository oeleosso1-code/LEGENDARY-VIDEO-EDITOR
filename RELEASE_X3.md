# X3 release notes

- Added `app/visual.py`: local FFmpeg grayscale-sample video analyzer with quality and motion heuristics.
- Quality-weighted, source-diverse shot ordering replaces pure round-robin in the render engine.
- Captures clip metrics and selected-shot scores in `edit_decisions.json`.
- Added `/inspect` Telegram command to review uploaded clip indicators before rendering.
- Added five unit tests and passed 16 tests total.
- Smoke-tested final MP4 (6.000000 seconds; H264/AAC) using actual local files.

No AI-generated imagery, no copyright bypass, no credential files, and no externally downloaded source code are bundled. Optional third-party bridges are described in `INTEGRATIONS.md`.
