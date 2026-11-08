# X10 work in progress — resumable long-form export

## Implemented

- `app/longform.py`: split requests into segments of at least five seconds and render each in an isolated temporary directory.
- Persist resumable `render_state.json` with an input/configuration signature; reuse a segment only after fresh ffprobe quality checks.
- Reassemble a final MP4 via FFmpeg concat demuxer and run overall duration, dimension and audio-stream validation.
- CLI `--longform --chunk-seconds N` enables the workflow. The existing default CLI renderer remains unchanged.
- Four X10 tests including a real two-part MP4 render and a second run that reuses both cached parts.

## Example

```bash
python -m app.cli --clips my_clip.mp4 --music licensed_song.mp3 --seconds 600 --longform --chunk-seconds 120 --out result.mp4
```

## Limitations

- **Not yet integrated into Telegram job scheduling.** Only the standalone CLI activates this feature.
- No shotlist or per-chunk subtitle timestamp rewriting. Both are explicitly rejected in the CLI.
- Per-segment editing can produce discontinuities in content at segment boundaries; it does not carry a continuous narrative plan across chunks.
- FFmpeg stream-copy concatenation presumes identically encoded segments. Audio boundary glitches and seamless music looping are not yet assured.
- This is not parallel / distributed processing and does not implement locking. A given output job must be handled by only one worker.
- Resume signatures use source file metadata (path/size/mtime), not full cryptographic content hashes.
- Human assessment of storytelling and music synchronization remains necessary.
