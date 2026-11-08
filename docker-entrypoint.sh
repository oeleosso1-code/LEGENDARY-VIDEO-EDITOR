#!/bin/sh
set -eu

# Railway mounts volumes at runtime, frequently owned by root.
# Fix access, then drop privileges for the Telegram bot.
OUTPUT_DIR="${OUTPUT_DIR:-/studio/jobs}"
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo 'ERROR: TELEGRAM_BOT_TOKEN is missing. Configure it in Railway Variables.' >&2
  exit 78
fi

mkdir -p "$OUTPUT_DIR"
if [ "$(id -u)" -eq 0 ]; then
  chown studio:studio "$OUTPUT_DIR"
  if [ ! -w "$OUTPUT_DIR" ]; then
    echo 'ERROR: Job volume is not writable.' >&2
    exit 73
  fi
  exec gosu studio "$@"
fi

if [ ! -w "$OUTPUT_DIR" ]; then
  echo 'ERROR: Job volume is not writable by the service account.' >&2
  exit 73
fi
exec "$@"
