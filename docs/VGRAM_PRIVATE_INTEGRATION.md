# VGRAM Private integration plan

This branch is the VGRAM Private integration branch. Upstream OwpenGram behavior is retained unless a change is required for the VGRAM identity or authentication model.

## Confirmed in the current server source

- MTProto API layer 229 is the canonical profile; compatibility profiles cover older layers.
- PostgreSQL migrations include a local Stars balance/transaction ledger (`0009_stars_ledger`).
- Star Gifts have persistence and protocol paths (`0011_star_gifts` and later migrations).
- Collectible usernames have server-side support; this is not a general-purpose arbitrary NFT marketplace.
- Login supports development codes and external OTP delivery through a signed webhook or SMTP.
- Login code TTL and attempt limits are configurable.
- The Android client documents Android 5.0+ support and its own-server discovery endpoint.

## Required VGRAM behavior (not yet implemented)

1. **Issued virtual numbers only.** Add a durable number registry with unique canonical phone, owner Telegram bot ID, status, issue/activation timestamps, and one-time use policy. Reject unissued numbers before sending a login code and repeat the ownership/status check during sign-in to prevent race conditions.
2. **Bot-based code delivery.** Reuse the existing OTP webhook contract, but deliver only to the Telegram account that owns the issued virtual number. Verify HMAC signatures, timestamp skew, expiry, idempotency key and delivery receipt. Never log OTP values.
3. **Registration grant.** Credit the initial 1,000 VGRAM Stars exactly once after successful first registration using the existing Stars ledger transaction boundary; do not confuse this internal balance with Telegram platform XTR.
4. **VGRAM NFT shop.** Audit collectible username support separately from gifts. Add a catalog and ownership/transfer ledger only where missing; all purchases/transfers must be transactional and idempotent.
5. **Android identity.** Set the VGRAM app label, package ID, login copy, custom server defaults, and deep-link scheme without breaking MTProto transport or account isolation.
6. **Android 12 verification.** Build and test the APK on Android 12, including cold start, number entry, bot-delivered code, sign-in, app restart, and chat navigation.
7. **Security and operations.** Use private secrets, rotate any signing credentials that were previously committed, enable rate limits and audit events, and never expose admin or bot tokens in the APK.

## Explicitly out of scope until separately audited

- Telegram Bot API XTR payments are not the VGRAM internal Stars ledger.
- The presence of a Stars ledger migration does not prove every Stars RPC is implemented correctly.
- Star Gifts and collectible usernames do not by themselves constitute the requested NFT marketplace.
- Group-call signaling/SFU support does not prove stable one-to-one audio/video calling on every Android device.
- Layer 229 compatibility does not prove full Telegram feature parity.

## Implementation order

1. Virtual-number registry and bot ownership binding.
2. HMAC-protected bot OTP delivery adapter.
3. Auth whitelist enforcement and abuse/rate-limit tests.
4. One-time 1,000 Stars registration grant.
5. NFT marketplace gaps and transactional ownership.
6. Android branding, VGRAM server selection, and Android 12 regression tests.
7. CI build, integration tests, deployment hardening, and release APK.
