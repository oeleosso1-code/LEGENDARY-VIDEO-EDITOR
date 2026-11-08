# LEGENDARY VIDEO EDITOR — latest source snapshot

**Status:** Development source, not a production-ready turnkey service.

Code snapshot includes X33 music/reference analysis, automatic shot planning, optional cloud vision, fixed timeline resumable rendering, Arabic title overlays, subtitles, and the subsequent dual OpenAI API key settings (`OPENAI_API_KEY` plus `OPENAI_API_KEY_SECONDARY`).

## What is verified
- Local test fixtures can render short MP4 videos via FFmpeg.
- Local Telegram handler logic is tested using simulated updates.
- OpenAI key failover tests use simulated responses.
- Live Telegram authorization, real API usage, Railway deployment, multi-hour rendering, external media rights checks, and artist-level editing quality are **not** verified.

## Deploy
Read `DEPLOY_RAILWAY.md`. Keep all three tokens (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `OPENAI_API_KEY_SECONDARY`) in Railway **Variables**, never in repository files or GitHub Actions logs. Set `ALLOWED_USER_IDS` and persistent storage before exposing the bot.

## Known limitations
- Large video jobs need a suitably provisioned compute instance and a persistent volume.
- Advanced motion tracking and music synchronization use heuristics and presets, not guaranteed human editor artistic decisions.
- User must have adequate rights to any music or footage they provide.
