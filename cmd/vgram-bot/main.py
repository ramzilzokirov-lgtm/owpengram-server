import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

BOT_TOKEN = os.environ.get("VGRAM_BOT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("VGRAM_DATABASE_URL", "").strip()
OTP_SECRET = os.environ.get("VGRAM_OTP_WEBHOOK_SECRET", "").encode()
HTTP_ADDR = os.environ.get("VGRAM_BOT_HTTP_ADDR", "127.0.0.1:2801")
NUMBER_PREFIX = "888"
CODE_TTL_MAX_SECONDS = 5 * 60
MAX_BODY_BYTES = 64 * 1024

pool: asyncpg.Pool | None = None
bot: Bot | None = None
delivery_locks: dict[str, asyncio.Lock] = {}


def response(accepted: bool, **fields: Any) -> web.Response:
    payload = {"accepted": accepted, **fields}
    return web.json_response(payload)


async def issue_number(telegram_user_id: int, chat_id: int) -> str:
    assert pool is not None
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            """
            SELECT phone FROM vgram_virtual_numbers
            WHERE telegram_user_id = $1 AND status IN ('issued', 'active')
            """,
            telegram_user_id,
        )
        if existing:
            await conn.execute(
                """
                UPDATE vgram_virtual_numbers
                SET telegram_chat_id = $2
                WHERE phone = $1 AND status IN ('issued', 'active')
                """,
                existing,
                chat_id,
            )
            return str(existing)

        for _ in range(20):
            phone = NUMBER_PREFIX + f"{secrets.randbelow(100_000_000):08d}"
            try:
                created = await conn.fetchval(
                    """
                    INSERT INTO vgram_virtual_numbers
                        (phone, telegram_user_id, telegram_chat_id, status)
                    VALUES ($1, $2, $3, 'issued')
                    ON CONFLICT (telegram_user_id) DO NOTHING
                    RETURNING phone
                    """,
                    phone,
                    telegram_user_id,
                    chat_id,
                )
                if created:
                    return str(created)
            except asyncpg.UniqueViolationError:
                continue

            existing = await conn.fetchval(
                """
                SELECT phone FROM vgram_virtual_numbers
                WHERE telegram_user_id = $1 AND status IN ('issued', 'active')
                """,
                telegram_user_id,
            )
            if existing:
                return str(existing)

        raise RuntimeError("could not allocate a unique VGRAM number")


async def start_handler(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    try:
        phone = await issue_number(message.from_user.id, message.chat.id)
    except Exception:
        await message.answer("Не удалось выдать номер. Попробуйте позже.")
        return
    await message.answer(
        "Добро пожаловать в <b>VGRAM Private</b>!\n\n"
        "Ваш виртуальный номер:\n"
        f"<code>+{phone}</code>\n\n"
        "1. Откройте приложение VGRAM Private.\n"
        "2. Введите этот номер.\n"
        "3. Запросите код входа — я автоматически пришлю его сюда.\n\n"
        "<b>Никому не передавайте код входа.</b>"
    )


async def number_handler(message: Message) -> None:
    await start_handler(message)


async def code_handler(message: Message) -> None:
    await message.answer(
        "Чтобы получить код, введите свой виртуальный номер в приложении VGRAM Private "
        "и нажмите «Продолжить». Код автоматически придёт в этот чат."
    )


def verify_signature(headers: Mapping[str, str], body: bytes) -> bool:
    if not OTP_SECRET:
        return False
    raw_timestamp = headers.get("X-Telesrv-Timestamp", "")
    try:
        timestamp = int(raw_timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - timestamp) > 300:
        return False
    expected = "sha256=" + hmac.new(
        OTP_SECRET, raw_timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(headers.get("X-Telesrv-Signature", ""), expected)


async def otp_delivery(request: web.Request) -> web.Response:
    if request.content_type != "application/json":
        return response(False, error_code="CONTENT_TYPE_INVALID")
    try:
        body = await request.read()
    except Exception:
        return response(False, error_code="REQUEST_INVALID")
    if len(body) > MAX_BODY_BYTES or not verify_signature(request.headers, body):
        return response(False, error_code="SIGNATURE_INVALID")
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response(False, error_code="JSON_INVALID")
    if not isinstance(data, dict):
        return response(False, error_code="JSON_INVALID")

    delivery_id = str(data.get("delivery_id", ""))
    phone = str(data.get("recipient", ""))
    code = str(data.get("code", ""))
    try:
        expires_in = int(data.get("expires_in", 0) or 0)
        expires_at = datetime.fromisoformat(str(data.get("expires_at", "")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return response(False, error_code="REQUEST_INVALID")
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        data.get("version") != "1"
        or data.get("purpose") != "login_sms"
        or data.get("channel") != "sms"
        or not re.fullmatch(r"[0-9]{5,32}", phone)
        or not re.fullmatch(r"[0-9]{6}", code)
        or not delivery_id
        or delivery_id != request.headers.get("Idempotency-Key")
        or not 1 <= expires_in <= CODE_TTL_MAX_SECONDS
        or expires_at <= now
        or expires_at > now.replace(microsecond=0) + timedelta(seconds=CODE_TTL_MAX_SECONDS + 30)
    ):
        return response(False, error_code="REQUEST_INVALID")

    assert pool is not None and bot is not None
    fingerprint = hashlib.sha256(body).digest()
    lock = delivery_locks.setdefault(delivery_id, asyncio.Lock())
    async with lock:
        async with pool.acquire() as conn:
            async with conn.transaction():
                number = await conn.fetchrow(
                    """
                    SELECT telegram_chat_id FROM vgram_virtual_numbers
                    WHERE phone = $1 AND status IN ('issued', 'active')
                    FOR UPDATE
                    """,
                    phone,
                )
                if number is None:
                    return response(False, error_code="PHONE_NUMBER_UNAVAILABLE")

                inserted = await conn.fetchval(
                    """
                    INSERT INTO vgram_otp_deliveries
                        (delivery_id, phone, request_fingerprint, expires_at)
                    VALUES ($1, $2, $3, now() + ($4 * interval '1 second'))
                    ON CONFLICT (delivery_id) DO NOTHING
                    RETURNING delivery_id
                    """,
                    delivery_id,
                    phone,
                    fingerprint,
                    expires_in,
                )
                receipt = await conn.fetchrow(
                    """
                    SELECT phone, request_fingerprint, status, telegram_message_id
                    FROM vgram_otp_deliveries WHERE delivery_id = $1
                    FOR UPDATE
                    """,
                    delivery_id,
                )
                if receipt is None or receipt["phone"] != phone or not hmac.compare_digest(
                    bytes(receipt["request_fingerprint"]), fingerprint
                ):
                    return web.json_response(
                        {"accepted": False, "error_code": "IDEMPOTENCY_CONFLICT"},
                        status=409,
                    )
                if receipt["status"] == "sent":
                    return response(True, message_id=str(receipt["telegram_message_id"]))

                if inserted:
                    rate_row = await conn.fetchrow(
                        """
                        UPDATE vgram_virtual_numbers
                        SET last_code_sent_at = now()
                        WHERE phone = $1
                          AND (last_code_sent_at IS NULL OR
                               last_code_sent_at < now() - interval '15 seconds')
                        RETURNING telegram_chat_id
                        """,
                        phone,
                    )
                    if rate_row is None:
                        await conn.execute(
                            "DELETE FROM vgram_otp_deliveries WHERE delivery_id = $1",
                            delivery_id,
                        )
                        return web.json_response(
                            {"accepted": False, "error_code": "RATE_LIMITED", "retryable": True},
                            status=429,
                        )
                    chat_id = int(rate_row["telegram_chat_id"])
                else:
                    chat_id = int(number["telegram_chat_id"])

        try:
            sent = await bot.send_message(
                chat_id,
                "🔐 <b>VGRAM Private — код входа</b>\n\n"
                f"Ваш код: <code>{code}</code>\n\n"
                f"Действует примерно {expires_in // 60 or 1} мин. "
                "Никому не сообщайте этот код.",
                disable_web_page_preview=True,
            )
        except Exception:
            return web.json_response(
                {"accepted": False, "error_code": "BOT_DELIVERY_FAILED", "retryable": True},
                status=502,
            )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE vgram_otp_deliveries
                SET status = 'sent', telegram_message_id = $2, sent_at = now()
                WHERE delivery_id = $1 AND status = 'pending'
                """,
                delivery_id,
                sent.message_id,
            )
        return response(True, message_id=str(sent.message_id))


async def health(request: web.Request) -> web.Response:
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1 FROM vgram_virtual_numbers LIMIT 0")
        await conn.fetchval("SELECT 1 FROM vgram_otp_deliveries LIMIT 0")
    return web.json_response({"ok": True, "service": "vgram-bot"})


async def main() -> None:
    global pool, bot
    if not BOT_TOKEN or not DATABASE_URL or not OTP_SECRET:
        raise RuntimeError("VGRAM_BOT_TOKEN, VGRAM_DATABASE_URL and VGRAM_OTP_WEBHOOK_SECRET are required")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, command_timeout=10)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.get_me()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1 FROM vgram_virtual_numbers LIMIT 0")
        await conn.fetchval("SELECT 1 FROM vgram_otp_deliveries LIMIT 0")
    router = Router()
    router.message.register(start_handler, CommandStart())
    router.message.register(number_handler, Command("number"))
    router.message.register(code_handler, Command("code"))
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    app = web.Application(client_max_size=MAX_BODY_BYTES)
    app.router.add_get("/healthz", health)
    app.router.add_post("/v1/otp/deliveries", otp_delivery)
    host, port = HTTP_ADDR.rsplit(":", 1)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, int(port))
    await site.start()

    try:
        await dispatcher.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
