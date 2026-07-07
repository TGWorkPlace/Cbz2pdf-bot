# CBR/CBZ → PDF Bot

A Telegram bot (built on Pyrogram) that detects `.cbz` and `.cbr` comic
archives, converts them to PDF, and sends the PDF back — admins only.

## How it works

- Send the bot a `.cbz` or `.cbr` file.
- `.cbz` (ZIP) archives are extracted with Python's stdlib `zipfile`.
- `.cbr` (RAR) archives are extracted via the `unar` CLI tool (installed
  in the Docker image) — no proprietary `unrar` binary needed.
- Pages are naturally sorted (page2 before page10), normalized to RGB
  JPEG, and merged into a single PDF with `img2pdf`.
- Only one conversion runs at a time to keep memory usage predictable
  on memory-constrained hosts like Koyeb's free tier.

## Environment variables

| Variable       | Required | Description                                   |
|----------------|----------|------------------------------------------------|
| `API_ID`       | yes      | Telegram API ID                                |
| `API_HASH`     | yes      | Telegram API hash                              |
| `BOT_TOKEN`    | yes      | Bot token from @BotFather                      |
| `ADMIN_IDS`    | yes      | Comma-separated Telegram user IDs, e.g. `123,456` |
| `DOWNLOAD_DIR` | no       | Temp working directory (default `./downloads`) |
| `MAX_FILE_SIZE`| no       | Max accepted file size in bytes (default 500MB)|

## Deploy

```bash
docker build -t cbr-cbz-pdf-bot .
docker run -e API_ID=... -e API_HASH=... -e BOT_TOKEN=... -e ADMIN_IDS=123456789 cbr-cbz-pdf-bot
```

On Koyeb, set the same environment variables in your service config;
the Dockerfile already installs `unar` and exposes port 8080 for health
checks.
