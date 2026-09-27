# TeraBox Telegram Bot

A Railway-ready Telegram bot for resolving authorized TeraBox shared links.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.com/new/github?repo=https%3A%2F%2Fgithub.com%2Ftanzid6gi%2Fterabox-telegram-bot)

## Quick start

1. Deploy this repository to Railway.
2. Add `BOT_TOKEN` from BotFather.
3. Add `COOKIE_JSON` with your TeraBox `ndus` cookie.
4. Start the bot and send `/start`.
5. Send a TeraBox share URL.

Small files are uploaded temporarily to Telegram and deleted. Larger files receive a temporary direct download link. Configure `MAX_UPLOAD_MB` if needed, but the normal Telegram Bot API limit is approximately 50 MB.

Read **[README-RAILWAY.md](README-RAILWAY.md)** for the complete deployment guide.

Never commit or share `BOT_TOKEN` or TeraBox cookies. Use only public/shared files or files you are authorized to access.
