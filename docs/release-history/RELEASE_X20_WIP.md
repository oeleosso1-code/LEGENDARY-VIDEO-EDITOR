# LEGENDARY VIDEO EDITOR — Scene Director (working milestone, not final)

## Source of truth
The executable code recovered in this workspace is X7, restored under `source/legendary-video-studio/`. Other X8–X19 notes exist, but their asserted implementation is not assumed to be present. This change adds `app/scene_director.py` and tests to the recovered codebase.

## Implemented
- Local frame sampling with FFmpeg (max 12 frame samples per planning request).
- Shot candidate objective metrics (brightness/contrast/motion/detail) and rough candidate rankings.
- Scene shotlist generated as valid JSON for existing `render_pro` / CLI `--shotlist`.
- **Optional** OpenAI or Gemini image description per frame; uploads happen ONLY if `--cloud-vision openai` or `--cloud-vision gemini` is explicitly set. Video files themselves are not uploaded by this feature. External model labels can be incorrect.
- Brief-to-label lexical matching for some English/Arabic words. No claim that this achieves professional scene comprehension.
- Default local mode does not understand actions, identities, goals, plot, or musical intent.

## Run
From `source/legendary-video-studio`:

```sh
python -m app.scene_director --clips clip1.mp4 clip2.mp4 --brief 'football goal' --seconds 10 --out plan.json
python -m app.cli --clips clip1.mp4 clip2.mp4 --shotlist plan.json --seconds 10 --out edit.mp4 --preview
```

Explicit cloud vision mode: add `--cloud-vision openai` or `--cloud-vision gemini` to first command and configure the appropriate secret through a private environment variable. It sends up to 12 sampled images to that service; permissions/privacy/possible API costs are the operator's responsibility. Not tested against live provider API.

## Verification
`python -m pytest -q` from project root: 43 passed, including a real FFmpeg MP4 export from a generated shotlist. Telegram connection and long-form video rendering remain untested in this working milestone.

## Still incomplete
Telegram integration for semantic planning; persistent job queue, retries and long-form engine; verified cloud image API calls; sophisticated music cuts, automatic content-specific event recognition, motion tracking, VFX and cinematic automatic review; licensing checks for stock footage/music; end-to-end real-bot testing.

No delivery archive prepared, per user preference.
