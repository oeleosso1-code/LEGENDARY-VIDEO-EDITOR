# Security policy

Never commit Telegram bot tokens, OpenAI API keys, private videos, or credentials.
If a token is exposed, revoke or rotate it immediately. Use private hosting environment variables for `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `OPENAI_API_KEY_SECONDARY` and a narrow `ALLOWED_USER_IDS` allowlist. Explicitly enable cloud vision only after consent to share selected image frames with the service provider.
