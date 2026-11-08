# X2.1: Open-source project integration bridges

**These are external dependencies, not vendored forks or code copies.** The base Docker image does not install these optional projects; default behavior remains unchanged. Users choose and install each tool deliberately.

## 1. PySceneDetect (BSD-3-Clause)
https://github.com/Breakthrough/PySceneDetect

- Install `pip install -r requirements-optional.txt` in the same Python environment as this project.
- Set `SCENE_DETECTION=1` in `.env`. The editor scans input videos for shot boundaries and prefers shot starts when cutting music-aligned clips. It is an input-analysis improvement, *not* action recognition.
- If absent, the editor automatically falls back to its existing source offset selection.

## 2. Auto-Editor (Unlicense)
https://github.com/WyattBlue/auto-editor

- Install the `auto-editor` CLI from the upstream project into the execution environment and confirm `auto-editor --help` works.
- Set `SILENCE_CLEANUP=1` in `.env`.
- Runs only for `/new ... | ... | ... | documentary`, trimming detected pauses from provided or stock clips before the ordinary editor. This is best for talking-head/interview footage, and inappropriate for uninterrupted music performance.
- When it is unavailable or an individual input fails, the original footage is used.

## 3. whisper.cpp (MIT)
https://github.com/ggml-org/whisper.cpp

- Install the upstream `whisper-cli` binary in PATH. Download an appropriate GGML model from an authorized model source yourself and store it locally.
- Configure `WHISPER_MODEL=/absolute/path/to/ggml-model.bin` in `.env`.
- After render, the bot creates an `.srt` transcript of the *finished* video's audio and sends the SRT file as a separate Telegram document. It does **not** burn subtitles into the picture, translate the text, or guarantee accuracy.
- If no audio is present, transcription is skipped with a logged diagnostic. If your edit has a copyrighted song rather than dialogue, speech recognition is not useful; leave the feature off.

## Licensing and rights
- PySceneDetect: BSD-3-Clause. auto-editor: Unlicense. whisper.cpp: MIT. FFmpeg: LGPL with possible GPL components depending on build. Review third-party licenses, their dependencies, and distribution terms before release.
- Use permitted user-supplied footage/audio or properly licensed stock. No music ripping or unauthorized downloads.

## Practical limits
- The scene detector adds CPU/disk read work on long videos; trim time may vary by version.
- Silence cleanup is opt-in because trimming a music video would ruin the requested synchronization.
- The base project is not a human-equivalent editor or fully unattended enterprise renderer.
