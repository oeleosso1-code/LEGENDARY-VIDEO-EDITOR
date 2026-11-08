# X11 development — continuous long-form audio and globally timed subtitles

## Implemented and tested

- Long-form chunk renderer now creates **video-only chunks**, preventing independent AAC encoders from inserting gaps at each segment join.
- After the chunks are combined, the full user-supplied soundtrack is applied **once**, from the requested music offset, with a fade near the end.
- Optional SRT subtitles are burned into the **assembled video timeline** rather than locally relative to individual chunks. The SRT therefore keeps its original global timestamps.
- CLI supports `--longform --subtitles captions.srt --music licensed_audio.wav`.
- Checkpoint signatures include an explicit pipeline version to avoid reusing incompatible chunks from X10.
- `tests/test_x11.py`: input validation and real FFmpeg integration test using two five-second chunks, audio plus an SRT caption after the chunk boundary, and a resumed second render.

## Verified

- 56/56 tests pass on the local runtime. An end-to-end 10s test produced an MP4 containing video and audio, and both video-only chunks were successfully reused on repeat.

## Important limits

- Timing and audio streams were verified automatically; subjective smoothness or subtitle accuracy is not validated by human viewing.
- The long-form CLI still does not support manual shotlists; full scene-to-scene continuity planning remains incomplete.
- This is not distributed processing; do not run multiple workers on the same output directory.
- Telegram long-form orchestration, automatic licensing verification, professional AI scene understanding and complex VFX remain unfinished.
- Requires FFmpeg built with libass for burned-in subtitles and user-provided music that is licensed or otherwise permitted.
