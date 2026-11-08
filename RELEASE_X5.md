# LEGENDARY VIDEO EDITOR X5 — Preview and soundtrack gain

## Implemented
- `/preview`: generates an **up to 12-second** lower-resolution draft from uploaded clips. This deliberately requires uploaded clips and does not trigger fresh Pexels downloads. It does not modify the stored full-length session.
- `/volume 0.75`: adjusts gain on uploaded soundtrack. Accepted values 0.0–1.5 (above 1 may clip on loud music). Defaults to 0.85.
- New FFmpeg encoder preview mode uses 360×640 portrait or 640×360 landscape and CRF 28.
- CLI flags `--preview` and `--music-volume`.
- All renders save `preview` and `music_volume` in `edit_decisions.json` for auditing.

## Telegram examples
```
/new nature documentary | 60 | horizontal | cinematic
# Send video MP4 and permitted audio MP3
/volume 0.65
/preview
/make
```

## Verify
Run `python -m pytest -q`. The included X5 integration test creates a real temporary source video and verifies export via FFmpeg. 24 tests passed in the build environment. No live Telegram/Pexels/AI connection was tested.

## Limitations
- `/preview` is an initial draft, **not** a frame-accurate segment of a previously produced long edit. The footage/order can differ from the final render.
- Preview still performs a render. It is not instant playback.
- The audio command changes user-provided music volume; it does not intelligently duck voiceover or normalize loudness.
- No automated copyright music downloader, professional-grade scene understanding, long-job resume or cloud delivery yet.
