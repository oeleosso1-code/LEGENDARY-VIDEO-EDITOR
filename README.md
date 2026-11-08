# LEGENDARY VIDEO EDITOR X2 — Real-footage Telegram video editor

## Implemented
- Telegram: `/new`, `/make`, `/status`, `/cancel`, `/clear`; document/video/audio attachment handling, per-user persistent edit sessions, optional allowlist.
- Two OPTIONAL AI API slots: `OPENAI_API_KEY` and `GEMINI_API_KEY` (OpenAI is preferred when both are set). The selected service currently proposes English stock-footage search terms; **neither service yet watches the actual video or performs human-level subjective editing**.
- User footage and user-supplied music file (MP3/M4A/WAV etc.), or stock footage search via Pexels when no footage supplied.
- FFmpeg render: orientation 9:16 or 16:9, MP4 H.264, consistent 25 FPS, visual cut lengths guided by local soundtrack onset-energy peaks, soundtrack mixed with AAC and fade-out. Four editing pacing presets.
- Provenance info `sources.json`, editable shot decisions `edit_decisions.json` and a shot concat manifest saved under `jobs/users/<id>/renders/<jobid>`.
- Docker and unit tests; failed source downloads are skipped.

## Deployment
1. On a Linux server (or laptop with Python 3.12+ and FFmpeg), unzip the project.
2. Copy `.env.example` to `.env` and fill `TELEGRAM_BOT_TOKEN`. Keep it private. Fill **at least one** of `PEXELS_API_KEY` (for stock footage) OR send your own video clips.
3. Optionally fill `OPENAI_API_KEY`, `GEMINI_API_KEY`; do not put keys in the chat or public GitHub. If both are present, stock query generation uses OpenAI, and Gemini is a fallback only when OpenAI is missing (not automatic failover).
4. Set `ALLOWED_USER_IDS` to your numeric Telegram ID; blank permits anyone to access the bot.
5. Run `docker compose up --build -d` or install the requirements and run `python -m app.bot_pro`.
6. Example chat:
   - `/new Real football match edit | 45 | vertical | fast`
   - Send permitted football clips as Telegram video or MP4 documents.
   - Send licensed audio track as Telegram audio or MP3 document.
   - `/make`
   - `/status` or `/cancel`.

## Limits and honest caveats
- Video is **not AI-generated**; clips originate from user files or licensed Pexels stock. No unauthorised streaming-service song scraping. You must have permission to use a chosen commercial recording.
- The song upload is the actual audio. Merely typing a title does not download a copyrighted song.
- Does **not** implement face/emotion/action detection, intelligent shot ranking, 3D motion graphics, speed ramps, human-quality color grading, auto captions, voiceover, or an advanced timeline GUI. These remain future engineering modules.
- Regular cloud Telegram Bot API: download max around 20 MB, outgoing attachment up to 50 MB. Larger renders stay on the server and need a separately configured delivery system; the project does not claim to host a public file URL. Official local Bot API service supports larger attachments, but it is not configured here.
- Very long projects are technically accepted up to the configured 3600 seconds but **can require significant disk, CPU and hours of processing**. Render is sequential and CPU based. This is not yet a scalable long-form service.
- `/cancel` signals the Python task and does not reliably terminate already-running FFmpeg processes. Monitor host disk quotas and allowlist access.
- The beat alignment algorithm uses coarse audio energy transients, not an artistically curated edit nor reliable BPM/downbeat analysis on every genre.
- Always check Pexels license restrictions, third-party/trademark and depiction rights. Source credits in `sources.json`.

## Run tests
```
python -m pytest -q
python -m compileall -q app
```

## Architecture
`bot_pro.py`: Telegram controller and jobs; `editor_pro.py`: ffprobe/ffmpeg shot render; `audio.py`: peak grid; `director.py`: AI search-query adapter; `stock.py`: Pexels; `store.py`: isolated sessions; `config.py`: environment.

Official docs: https://core.telegram.org/bots/api and https://www.pexels.com/api/documentation/

## Standalone CLI (no Telegram / no API keys)
Use your own local video and music files. No AI account is required:
```
python -m app.cli --clips input1.mp4 input2.mp4 --music song.mp3 --seconds 45 --orientation vertical --style fast --out finished.mp4
```
This mode also writes an `edit_decisions.json` file next to the output. For a first test, use a short 5–10 second project to estimate the machine's rendering speed.

## X2.1 Optional external open-source integrations
See [INTEGRATIONS.md](INTEGRATIONS.md). Three bridge modules are integrated into the processing flow: scene starts from PySceneDetect, opt-in silence cleanup via auto-editor CLI for documentary projects, and optional post-render SRT export via whisper.cpp. **The optional third-party executables/models are not bundled**; setup and actual service tests must be done on the deployment machine. The default Docker image does not install them.

## X3 — Tested footage analysis and quality-weighted assembly

**New module:** `app/visual.py` samples three low-resolution grayscale frames from each video through FFmpeg. It calculates brightness, contrast, rough detail, and frame-to-frame motion. These are objective **heuristics**, not professional visual understanding, face recognition, or a promise of cinematic quality.

**New behavior:** `render_pro()` ranks supplied clips by sampled technical quality while rotating through all available sources. Repeated appearances use different positions from the original video. An additional `clip_inspections` section and per-cut `source_quality_score` are recorded in `edit_decisions.json`. X2.1 optional scene detection is retained.

**Telegram:** send permitted video files, then `/inspect` to see approximate technical scores before `/make`. This does not cost AI API credits and works when FFmpeg is installed. The bot has not been tested against the live Telegram service; live credentials are never included in the archive.

**Verification performed locally:** 16 automated tests passed; Python modules compiled; a real 6-second horizontal MP4 render with user-supplied test WAV completed successfully and ffprobe verified `duration=6.000000`. No claim is made that this tests all source codecs, Telegram upload limits, long-form performance, AI keys, Pexels network search, or actual third-party integrations.

**Limitations:** ranking does not detect football actions, facial emotion, rhythm of choreography or narrative relevance. It can prefer technically brighter clips over artistically intentional dark footage. The editor is still mostly hard-cut based; automated expert-level decisions, proprietary effects, cloud hosting, large-project resumability, licensed music catalog integrations, and creator-reviewed approvals are not implemented. The tool never downloads arbitrary commercial recordings.

**Next implementation priorities:** timeline preview and user approval, per-shot subject/action classifiers (opt-in models), resumable segment rendering, reusable transition templates and color pipeline, cloud-backed large-file delivery, and end-to-end Telegram integration tests.

## X4 — Color grade presets and burned-in SRT subtitles
This iteration adds **real, tested** FFmpeg video treatments and caption support (see `RELEASE_X4.md`). The defaults remain unchanged unless you select a preset or upload a caption file.

Standalone command:
```
python -m app.cli --clips clip1.mp4 clip2.mp4 --music permitted-song.mp3 --seconds 45 --orientation vertical --style cinematic --color cinematic --subtitles captions.srt --out result.mp4
```

Telegram: `/grade warm` (also `natural`, `cinematic`, `vivid`, `noir`, `cool`) and send an SRT document alongside videos and an authorized audio file, then `/make`. To use captions on Docker, the installed FFmpeg must support `subtitles`/libass. Color tuning is a *preset*, not intelligent per-scene color matching. This does **not** implement downloading arbitrary copyrighted music.

## X5 — Draft preview & music level
Version X5 adds `/preview` for a short **low-resolution draft** (requires uploaded footage) and `/volume 0.75` for adjusting the volume of the uploaded music file. `/make` exports the full session. Session duration is not altered by preview. Local CLI also accepts `--preview --music-volume 0.75`. See [RELEASE_X5.md](RELEASE_X5.md).

**Verified:** 24 automated tests including actual FFmpeg smoke export. Live Telegram API interaction and long-form performance remain unverified. Music volume is not full AI voice/music mixing.

## X7 — Manual storyboard timeline and music-start control

See [RELEASE_X7.md](RELEASE_X7.md). This release adds a **local-CLI** JSON shotlist, allowing per-shot source selection, in/out selection and 0.25–4× playback speeds, plus a soundtrack starting offset (`--music-start`). The Telegram bot accepts `/musicstart 24` after music upload. A user's specified soundtrack still requires the permitted audio file; a title alone does not download it.

```bash
python -m app.cli --clips clip0.mp4 clip1.mp4 --shotlist example_shotlist.json --seconds 5 --music licensed.mp3 --music-start 24 --out result.mp4
```

**Verification:** 32 automated tests passed, including a true FFmpeg render from a 2-shot JSON timeline to an MP4 of approximately 5 seconds. Live Telegram, proprietary music catalog access and real-world long renders remain untested.

## X7 — Edit individual shots from Telegram
You can now control the timeline directly in Telegram, not only through a local JSON file:

```text
/new Travel edit | 5 | horizontal | cinematic
```
Upload 2 video clips and optional permitted soundtrack, then:
```text
/shotadd 1 0 2 1
/shotadd 2 1 3 0.75
/shots
/preview
/make
```
`/shotadd` parameters: **1-based clip index**, **source start time**, **output shot duration**, **playback speed** (optional, 1× by default). The sum of shot durations must match the requested video duration. The complete shotlist is validated again at export time. `/shotclear` removes the manual edits and restores automatic selection. Alternatively upload a UTF-8 JSON document named `shotlist.json` (see `example_shotlist.json`).

Use `/preview` to inspect the beginning of the manual timeline before final export. This is a working technical editor, not guaranteed human-level cinematic judgment. Check all copyrights and usage permissions for source footage and music.

See `RELEASE_X7.md` for precise changes and tested limitations.

## X33 development integration (not a final release)

This working tree contains executable X32 sources plus the following locally tested X33 modules. No final ZIP has been packaged, as requested.

- `app/music_director.py`: analyzes a user-supplied soundtrack *locally*, from the selected `music_start`, estimating onsets, broad energetic windows and tentative BPM. Music is not scraped or downloaded.
- `app/reference_style.py`: samples colors/brightness and coarse large frame changes in a **reference-only** video; it never inserts the reference into the output timeline.
- `app/auto_timeline.py`: produces validated, user-editable shotlists with an optional music-onset and reference-paced cut schedule. Does not identify goals or other high-level events by itself.
- `app/motion_track.py`: estimates centers of changing image regions and supports mild digital reframing for an explicitly requested `follow_motion: true` shot. It does **not** identify/track a specific person.
- `app/vision_director.py`: optional one-keyframe-per-source semantic *suggestions* through OpenAI/Gemini. Requires both operator `CLOUD_VISION_ENABLED=1` and user's explicit `/aiscan openai` or `/aiscan gemini` command. Provider API fees may apply; no external network test has been performed. Do not publish or send API keys in chat.
- `app/timeline_render.py`: supports three-/five-stage speed changes through `ramp`, optional motion-follow, and output quality `preview` (360×640), `hd` (720×1280), `fullhd` (1080×1920); horizontal dimensions are transposed. All modes use user-supplied real footage. The high-resolution mode increases CPU and storage requirements considerably; only HD was tested in a real video.
- `app/bot_pro.py`: new `/referencelast`, `/refinspect`, `/usegrade`, `/musicmap`, `/autoplan`, `/aiscan openai|gemini`, `/quality preview|hd|fullhd` commands. The Telegram handlers were tested by message simulation, **not** through live Telegram servers.

### Sample editable shot plan with stepped speed change and mild motion following

```json
{
  "shots": [
    {"clip": 0, "start": 0, "duration": 3, "speed": 1, "ramp": [0.5, 1, 1.5], "follow_motion": true},
    {"clip": 1, "start": 1, "duration": 2, "speed": 1}
  ]
}
```

`ramp` splits a shot into 3 or 5 constant-speed phases. It is **not** yet smooth optical-flow time interpolation. Tracking follows motion heuristics, not a guaranteed detected subject. Ensure the source is long enough for the sum of phase durations multiplied by phase speeds; shot validation enforces this.

### Using X33 commands after deployment

1. Upload original source clips and a legally usable song, then set `/new ...` and optionally `/musicstart 8`.
2. To use a video as inspiration, upload it as the last clip and send `/referencelast`. It will be excluded from the source timeline. Send `/refinspect` then optionally `/usegrade`.
3. Run `/musicmap` for a local sound-energy analysis. `/autoplan` creates a shotlist that can be revised with `/shots` and the shotlist upload commands.
4. To opt in to paid cloud frame analysis **only when the operator has enabled it**, send `/aiscan openai` or `/aiscan gemini`, followed by `/autoplan`.
5. Set `/quality hd` (or `fullhd`) for a fixed-shotlist `/longmake`, then use `/longstatus` and `/longresume` as needed.

### Explicit limitations

- APIs have not been verified against the owner's actual credentials; no real Telegram, OpenAI or Gemini calls were made in this work session.
- Image understanding is based on a *single thumbnail per video*, so important dynamic events can be missed. It is a ranking hint and not a substitute for professional event detection.
- Music onset tracking and estimated BPM are approximate; they are not semantic music understanding.
- Reference analysis estimates broad visual characteristics, not the complete motion graphics, title timings or transition effects of another editor.
- Digital subject following depends on frame differences and may mistake camera movement for subject movement.
- Long renders are cached by content hashes and output settings; full-hour and multi-user load tests, remote storage/large-file delivery and actual Docker container builds are still outstanding.
- Only use footage and music under licenses that permit the intended use. User must verify source and music rights before publishing.

### X33 delivery verification

- `app/quality_check.py` inspects streams, duration, dimensions and optional audio before an output file is atomically published. It logs warnings for extended dark frames but never automatically removes intentional darkness.
- Fixed-timeline renders now write `<output_stem>_quality_report.json`, separately from `<output_stem>_render_report.json`. A failed technical verification leaves any previously approved output intact.
- This does not measure pacing, storytelling, music rights or whether an artist's creative direction has been faithfully achieved.

## X34: Two **OpenAI** keys + Telegram configuration (no Gemini required)

Both user's keys are OpenAI Platform API keys. The Telegram bot token is separate.
On the **private host only** copy `.env.example` to `.env` and set:

```dotenv
TELEGRAM_BOT_TOKEN=<your own bot token (do not paste into chat)>
OPENAI_API_KEY=<your primary OpenAI Platform API key>
OPENAI_API_KEY_SECONDARY=<your second OpenAI Platform API key>
GEMINI_API_KEY=
ALLOWED_USER_IDS=<your numeric Telegram user ID>
CLOUD_VISION_ENABLED=0
```

Keep `.env` outside source control and restrict local permissions (`chmod 600 .env`).
Run `docker compose up --build -d`, then send `/connections` to the bot to check
only whether settings were loaded. `/connections` **does not validate credentials**.
Use `/aiscan openai` only after setting `CLOUD_VISION_ENABLED=1` and explicitly
consenting to sending extracted video frames to OpenAI. API usage may be billed.

The primary key is used first. The secondary key is tried only if the primary
returns an authentication / permission / rate-limit / server error or times out /
fails to connect. Non-retryable failures do not switch keys; neither key is
automatically used in parallel. Two keys under the same project may share
quotas and billing and do not guarantee extra capacity. OpenAI ChatGPT Plus
subscription is **not** an OpenAI API billing plan. Real credential validation
and live Telegram interaction have not yet been performed.

