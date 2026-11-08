# X15 work-in-progress (not shipped)

## Built
- `app/reference_style.py`: reference video technical inspection and Arabic typographic overlay with Pillow RAQM.
- Optional CLI parameters `--reference`, `--title-text`, `--title-start`, `--title-end`, `--title-accent`.
- Optional Telegram commands `/referencelast`, `/refinspect`, `/title`, `/titleoff` (code connected, not tested against Telegram network).
- Reference separated from editable footage for Telegram requests. Checkpoint source verification includes the reference media.
- Docker dependencies updated to include Pillow, fontconfig, and Noto fonts.

## Verification
56 local tests passed, including a real 2-second video render with an Arabic PNG overlay and audio stream. Provided reference sample processed successfully (18.019 seconds, 576x1024, 30fps). No new file bundle, per user's request.

## Still required
- True semantic shot understanding (football event detection, motion tracking, subject focus).
- Reference timing and animated text tracking; technical analysis is not style imitation.
- Multi-user production queue, live Telegram auth/network testing, resilient cancellation.
- Validated long-form resumability combined with titles/overlays and external object storage.
- Music-aware creative decisions, licensed audio sourcing and rights handling.
- Support for advanced color grading, transitions, speed ramps and review feedback.
