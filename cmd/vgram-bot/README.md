# VGRAM Private Telegram bot

The bot issues one virtual `+888 XXXX XXXX` number per Telegram account and delivers VGRAM login codes to the same private chat.

## Required environment

- `VGRAM_BOT_TOKEN`: token from BotFather.
- `VGRAM_DATABASE_URL`: the same PostgreSQL database used by the VGRAM server.
- `VGRAM_OTP_WEBHOOK_SECRET`: same secret as `TELESRV_OTP_WEBHOOK_SECRET`.
- `VGRAM_BOT_HTTP_ADDR`: loopback listener, e.g. `127.0.0.1:2801`.

The server must have applied migrations `20261031000001` and `20261031000002` before users request numbers or login codes.

## Compose

Copy `deploy/docker/.env.example` to `deploy/docker/.env`, set real secrets, then start the VGRAM profile:

```sh
docker compose --env-file deploy/docker/.env -f deploy/docker/compose.yaml --profile vgram up -d --build
```

Send `/start` to the bot. It returns the virtual number. Enter it in the VGRAM Android app; the login code is delivered automatically.

The webhook listens only on loopback. Do not expose port 2801 publicly.
