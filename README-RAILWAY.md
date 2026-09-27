# TeraBox Telegram Bot — Railway deployment

A simple Telegram bot that resolves authorized TeraBox shared links. It sends files that fit the configured Telegram upload limit and returns temporary direct links for larger files.

> Use only public/shared files or files you are authorized to access. This project does not bypass passwords, CAPTCHAs, private permissions, or other access controls.

## One-click deployment

After you upload this repository to GitHub, replace `YOUR_GITHUB_USER` and `YOUR_REPOSITORY` in the button URL below, then put the URL in your README:

```markdown
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.com/new/github?repo=https%3A%2F%2Fgithub.com%2FYOUR_GITHUB_USER%2FYOUR_REPOSITORY)
```

The repository's root README already contains a placeholder button. Update it after GitHub creates your final repository URL.

## Required Railway variables

Add these in Railway → service → **Variables**:

```text
BOT_TOKEN=your_telegram_botfather_token
COOKIE_JSON=your_terabox_ndus_cookie_value
```

`COOKIE_JSON` may be only the `ndus` value, as shown above. You may alternatively add the complete browser cookie header as `TERABOX_COOKIE`; if both are present, `TERABOX_COOKIE` is used.

Do not commit either value to GitHub or paste it into public issues. If you want to use a full cookie object:

```text
COOKIE_JSON={"ndus":"your_terabox_ndus_cookie_value","lang":"en"}
```

Optional settings:

```text
MAX_UPLOAD_MB=49
DOWNLOAD_TIMEOUT_SECONDS=1800
MAX_CONCURRENT_DOWNLOADS=1
HTTP_MAX_RETRIES=3
HTTP_INITIAL_DELAY=0.5
HTTP_BACKOFF_FACTOR=2.0
RATE_LIMIT=10
RATE_WINDOW=60
CACHE_TTL=60
CACHE_MAX_SIZE=100
```

## Deploy

1. Upload this repository to GitHub.
2. Open Railway and choose **New Project → Deploy from GitHub Repo**.
3. Select the repository. Railway detects the included `Dockerfile`.
4. Add `BOT_TOKEN` and `COOKIE_JSON` variables.
5. Deploy the service.
6. Generate a Railway domain under **Settings → Networking**.
7. Check `https://YOUR-DOMAIN/health`.
8. Open the bot in Telegram and send `/start`.

The bot uses long polling, so no Telegram webhook or public domain is required for bot operation. The Railway domain is useful for the resolver health/API endpoints.

The Telegram bot uses the bundled direct TeraBox session resolver. It does not depend on a separate hosted proxy service.

## Behavior

- `/start` shows usage instructions.
- A TeraBox URL is resolved through the local resolver API.
- Files under `MAX_UPLOAD_MB` are downloaded temporarily and uploaded to Telegram.
- Larger files receive the temporary TeraBox direct download link instead.
- Temporary files are deleted after upload or failure.
- One download runs at a time by default.

The normal Telegram Bot API upload ceiling is approximately 50 MB, so the default is 49 MB. To upload larger files directly, a separate local Telegram Bot API server is required; that is intentionally not included in this free one-service deployment.

## Test

```bash
curl https://YOUR-DOMAIN/health
curl --get 'https://YOUR-DOMAIN/api' \\
  --data-urlencode 'url=https://terabox.com/s/REPLACE_ME' \\
  --data-urlencode 'resolve=true'
```

Then send a public authorized TeraBox link to the bot.

## Cookie refresh

If logs or bot replies show verification/authentication errors, refresh the `ndus` cookie from your logged-in TeraBox browser session and update the Railway `COOKIE_JSON` variable. Do not repeatedly retry verification errors or attempt to bypass them.
