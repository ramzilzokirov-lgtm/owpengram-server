# VGRAM Private integration status

This branch is the VGRAM Private integration branch. Upstream OwpenGram behavior is retained unless a change is required for the VGRAM identity or authentication model.

## Confirmed in the current server source

- MTProto API layer 229 is the canonical profile; compatibility profiles cover older layers.
- PostgreSQL migrations include a local Stars balance/transaction ledger (`0009_stars_ledger`).
- Star Gifts have persistence and protocol paths (`0011_star_gifts` and later migrations).
- Collectible usernames have server-side support; this is not a general-purpose arbitrary NFT marketplace.
- Login supports configurable external OTP delivery through a signed webhook or SMTP.
- Login code TTL and attempt limits are configurable.
- The Android client documents Android 5.0+ support.

## Added on the VGRAM Private branch

- Durable `vgram_virtual_numbers` registry with one Telegram owner per number.
- Auth send-code, sign-in verification, and registration checks against the issued-number registry.
- First successful registration binds the virtual number to the new VGRAM account; later sign-ins must match that account.
- VGRAM accounts require an external OTP sender; they do not fall back to the legacy 777000 in-app login code.
- The Stars status RPC reads the PostgreSQL ledger and grants 1,000 internal VGRAM Stars exactly once on first balance access; the grant is recorded in the transaction ledger.
- Telegram bot service in `cmd/vgram-bot`: `/start` issues a `+888` number, and the signed OTP webhook sends login codes to that Telegram chat.
- Durable OTP delivery receipts, request HMAC verification, idempotency checks, and a per-number resend interval.
- Optional Compose profile `vgram` for the bot service.
- Android app label and login copy branded as VGRAM Private; upstream public OwpenGram server removed from the built-in server list.

## Required setup before the first real login

1. Create a Telegram bot with BotFather and put its token in `VGRAM_BOT_TOKEN`.
2. Generate a long random `TELESRV_OTP_WEBHOOK_SECRET`; the bot adapter and server must share it.
3. Set `TELESRV_PHONE_CODE_DELIVERY_PROVIDER=webhook`, `TELESRV_PHONE_CODE_LENGTH=6`, and `TELESRV_OTP_WEBHOOK_URL=http://127.0.0.1:2801/v1/otp/deliveries`.
4. Set the real public address, Postgres DSN, Redis settings, and a production RSA identity.
5. Run the stack with `docker compose --profile vgram up -d` so the bot service starts alongside the server.
6. Open the bot and send `/start`; it issues a `+888` virtual number. Enter that number in the Android app and request a code.
7. Replace the Android placeholder host `vgram-private.invalid` with the deployed server host and build/test on Android 12.

The bot profile is optional in the generic Compose topology. VGRAM virtual-number registration will not work unless the profile is enabled and the bot token/webhook secret are configured.

## Still required / not yet verified

- End-to-end test of bot-issued numbers against a running PostgreSQL server and the Android client.
- Confirm the Android login screen accepts the `+888` prefix without a country-code workaround.
- Add a `VG...` alias format only after client/server normalization is implemented; the current registry and MTProto phone field use digits.
- Add transactional Stars spending, transfers, transaction-history projection, and admin adjustments; the current RPC exposes the balance but not yet the complete economy.
- Audit collectible username/NFT code and add a separate marketplace only where upstream behavior is missing.
- Verify one-to-one calls, secret-chat E2E behavior, and Android 12 cold-start/login regressions.
- Production deployment, secret rotation, and release APK signing.

## Explicitly out of scope until separately audited

- Telegram Bot API XTR payments are not the VGRAM internal Stars ledger.
- The presence of a Stars ledger migration does not prove every Stars RPC is implemented correctly.
- Star Gifts and collectible usernames do not by themselves constitute the requested NFT marketplace.
- Group-call signaling/SFU support does not prove stable one-to-one audio/video calling on every Android device.
- Layer 229 compatibility does not prove full Telegram feature parity.
