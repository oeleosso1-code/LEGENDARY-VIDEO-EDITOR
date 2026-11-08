# LEGENDARY VIDEO EDITOR X7 — Telegram shotlist editor

## Implemented in X7
- `/shotadd CLIP START DURATION [SPEED]`: append a precise timeline shot; 1-based clip numbering. Output duration in seconds, speed 0.25–4×. The bot checks the referenced source duration.
- `/shots`: show up to 30 entries and the total timeline duration.
- `/shotclear`: delete the manual shotlist and resume auto-selected cuts.
- Upload a document named `shotlist.json`: validates the file against the uploaded videos and project length before saving it. Max 256 KiB.
- `/make`: validates a manual shotlist before starting, then passes it into the rendering engine.
- `/preview`: trims a validated manual timeline to the first 12 seconds, preserving shot sequence and speed.
- Isolated job snapshots and safer running-job cleanup.

## Example
Create a 5-second video with two shots:
```
/new Product montage | 5 | horizontal | cinematic
```
Upload the corresponding clips and audio, then:
```
/shotadd 1 0 2 1
/shotadd 2 1 3 0.75
/shots
/preview
/make
```
The shot durations must total the `/new` output length exactly (tolerance ±0.05 s). Source footage must be long enough for each requested shot, accounting for speed.

## Verification
`python -m pytest -q` => 38 passed in the supplied environment. FFmpeg smoke test renders a 6-second preview from a longer manually specified timeline.
Telegram unit commands were tested with stubbed Telegram SDK types because python-telegram-bot could not be installed in this sandbox. Real Telegram polling and cloud APIs remain untested.

## Known limitations
Not a human-equivalent autonomous editor. No licensed-song acquisition or unauthorized video extraction. Output is still 720p for full renders, 360p for previews. The Python rendering process is sequential and long jobs may take substantial resources. Telegram standard Bot API upload/download limits apply. External stock, OpenAI, and Gemini integrations require credentials and network availability. Setting `ALLOWED_USER_IDS` is recommended for a personal bot.
