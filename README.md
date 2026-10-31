# VGRAM Private Server

A self-hosted MTProto server based on the OwpenGram / gramsrv codebase, customized for the VGRAM Private messenger.

## Project repositories

- Android client: https://github.com/ramzilzokirov-lgtm/owpengram-android-client
- Server: https://github.com/ramzilzokirov-lgtm/owpengram-server

## Protocol and storage

- MTProto API layer 229, with upstream compatibility profiles.
- Go server.
- PostgreSQL for durable accounts, messages, settings, Stars ledger, gifts, and VGRAM virtual-number ownership.
- Redis for transient auth/session state.
- Docker Compose deployment.

## VGRAM Private additions

- Telegram bot issues one `+888` virtual number per Telegram account.
- Only numbers present in the VGRAM virtual-number registry can request login codes.
- The number becomes bound to the VGRAM account after successful first registration.
- Login codes are delivered to the same Telegram private chat that received the number.
- OTP webhook requests use HMAC-SHA256 signatures, short expiry, idempotency receipts and rate limits.
- The Stars status RPC reads the internal PostgreSQL ledger and grants 1,000 VGRAM Stars exactly once on first balance access.
- VGRAM internal Stars remain separate from Telegram platform XTR.
- Spending, transfers, top-ups and full transaction-history projection are still being implemented.

## Run

1. Copy `deploy/docker/.env.example` to `deploy/docker/.env`.
2. Set unique production secrets, including `POSTGRES_PASSWORD`, Redis password, admin tokens, `VGRAM_BOT_TOKEN`, and `TELESRV_OTP_WEBHOOK_SECRET`.
3. Set public IP/domain, production RSA identity, TURN/SFU settings and the PostgreSQL DSN.
4. Start the VGRAM profile:

```sh
docker compose --env-file deploy/docker/.env -f deploy/docker/compose.yaml --profile vgram up -d --build
```

5. Send `/start` to the Telegram bot, then use the issued number in the Android app.

The bot webhook listens on loopback only. Do not expose its HTTP port publicly.

## Current integration notes

See [VGRAM Private integration status](docs/VGRAM_PRIVATE_INTEGRATION.md) for implementation details and outstanding verification. The Android client currently contains a reserved placeholder host until the server has a real public endpoint.

## Upstream

This project is derived from the open-source OwpenGram / gramsrv implementation. Preserve upstream notices and comply with all applicable licenses. See [LICENSE](LICENSE).
