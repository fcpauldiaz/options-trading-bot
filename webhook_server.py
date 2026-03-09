import hashlib
import json
import logging
import os
from typing import Any

import aiohttp.web

from config import WEBHOOK_APP_ID_ALLOWED, WEBHOOK_SUBTITLE_CHANNEL_2

logger = logging.getLogger(__name__)

CHANNEL_1 = 1
CHANNEL_2 = 2


def _synthetic_id(body: str, delivered_date: int | None, delivered_date_iso: str) -> int:
    raw = f"{body}|{delivered_date or ''}|{delivered_date_iso or ''}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    return int(h[:15], 16) & ((1 << 63) - 1)


class WebhookMessage:
    __slots__ = ("id", "content", "embeds", "timestamp", "is_webhook", "channel")

    def __init__(
        self,
        message_id: int,
        content: str,
        channel: int,
    ):
        self.id = message_id
        self.content = content
        self.embeds: list[dict[str, Any]] = []
        self.timestamp = None
        self.is_webhook = True
        self.channel = channel

    def is_spacemonkey(self) -> bool:
        return False

    def get_embed_titles(self) -> list[str]:
        return []


class WebhookProcessedTracker:
    def __init__(
        self,
        file_1: str = "processed_webhooks_1.txt",
        file_2: str = "processed_webhooks_2.txt",
    ):
        self._files = {CHANNEL_1: file_1, CHANNEL_2: file_2}
        self._processed: dict[int, set[int]] = {CHANNEL_1: set(), CHANNEL_2: set()}
        for ch in (CHANNEL_1, CHANNEL_2):
            self._load(ch)

    def _load(self, channel: int) -> None:
        path = self._files[channel]
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._processed[channel].add(int(line))
                        except ValueError:
                            continue
        except OSError as e:
            logger.error("Error loading webhook processed ids for channel %s: %s", channel, e)

    def _save(self, channel: int, message_id: int) -> None:
        try:
            with open(self._files[channel], "a") as f:
                f.write(f"{message_id}\n")
        except OSError as e:
            logger.error("Error saving webhook processed id %s: %s", message_id, e)

    def is_processed(self, message_id: int, channel: int) -> bool:
        return message_id in self._processed.get(channel, set())

    def mark_processed(self, message_id: int, channel: int) -> None:
        if channel not in self._processed:
            self._processed[channel] = set()
        if message_id not in self._processed[channel]:
            self._processed[channel].add(message_id)
            self._save(channel, message_id)


def _parse_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    app_id = data.get("app_id")
    title = data.get("title")
    subtitle = data.get("subtitle")
    body = data.get("body")
    delivered_date = data.get("delivered_date")
    delivered_date_iso = data.get("delivered_date_iso")

    if not isinstance(app_id, str) or not app_id.strip():
        return None
    if not isinstance(title, str):
        return None
    if not isinstance(subtitle, str):
        return None
    if not isinstance(body, str):
        return None
    if delivered_date is not None and not isinstance(delivered_date, (int, float)):
        return None
    if delivered_date_iso is not None and not isinstance(delivered_date_iso, str):
        return None

    ts = int(delivered_date) if delivered_date is not None else None
    iso = (delivered_date_iso or "").strip() if isinstance(delivered_date_iso, str) else ""

    return {
        "app_id": app_id.strip(),
        "title": title,
        "subtitle": subtitle,
        "body": body,
        "delivered_date": ts,
        "delivered_date_iso": iso,
    }


def _channel_for_subtitle(subtitle: str) -> int:
    allowed = WEBHOOK_SUBTITLE_CHANNEL_2 or ""
    parts = [p.strip() for p in allowed.split(",") if p.strip()]
    return CHANNEL_2 if subtitle.strip() in parts else CHANNEL_1


async def handle_discord_webhook(request: aiohttp.web.Request) -> aiohttp.web.Response:
    logger.info("Webhook POST /webhook/discord received")
    try:
        body = await request.read()
        data = json.loads(body) if body else {}
        logger.info("Webhook payload: %s", data)
    except (json.JSONDecodeError, ValueError) as e:
        raw = body.decode("utf-8", errors="replace")[:500] if body else ""
        logger.warning("Webhook 400 Invalid JSON: %s. Payload: %s", e, raw)
        return aiohttp.web.json_response(
            {"error": "Invalid JSON"},
            status=400,
        )

    parsed = _parse_payload(data)
    if not parsed:
        logger.warning("Webhook 400 Invalid payload: missing or invalid fields. Payload: %s", data)
        return aiohttp.web.json_response(
            {"error": "Invalid payload: missing or invalid fields"},
            status=400,
        )

    allowed_ids = [
        aid.strip().lower()
        for aid in (WEBHOOK_APP_ID_ALLOWED or "").split(",")
        if aid.strip()
    ]
    received = (parsed["app_id"] or "").strip().lower()
    if allowed_ids and received not in allowed_ids:
        logger.warning(
            "Webhook 400 app_id not allowed. Received: %r, expected: %r. Payload: %s",
            parsed["app_id"],
            WEBHOOK_APP_ID_ALLOWED,
            parsed,
        )
        return aiohttp.web.json_response(
            {"error": "app_id not allowed"},
            status=400,
        )

    bot: "TradingBot" = request.app["bot"]
    tracker: WebhookProcessedTracker = request.app["webhook_tracker"]

    synthetic_id = _synthetic_id(
        parsed["body"],
        parsed["delivered_date"],
        parsed["delivered_date_iso"],
    )
    channel = _channel_for_subtitle(parsed["subtitle"])
    logger.info("Webhook accepted: id=%s channel=%s body=%r", synthetic_id, channel, parsed["body"][:100])

    if tracker.is_processed(synthetic_id, channel):
        logger.info("Webhook duplicate skipped: id=%s channel=%s", synthetic_id, channel)
        return aiohttp.web.Response(status=200)

    msg = WebhookMessage(
        message_id=synthetic_id,
        content=parsed["body"],
        channel=channel,
    )

    if channel == CHANNEL_2 and getattr(bot, "scraper_2", None) is not None:
        logger.info("Webhook processing channel 2: id=%s", synthetic_id)
        await bot.process_message_2(msg)
    else:
        logger.info("Webhook processing channel 1: id=%s", synthetic_id)
        await bot.process_message(msg)

    tracker.mark_processed(synthetic_id, channel)
    logger.info("Webhook processed: id=%s channel=%s", synthetic_id, channel)
    return aiohttp.web.Response(status=200)


def create_app(bot: "TradingBot", webhook_tracker: WebhookProcessedTracker) -> aiohttp.web.Application:
    app = aiohttp.web.Application()
    app["bot"] = bot
    app["webhook_tracker"] = webhook_tracker
    app.router.add_post("/webhook/discord", handle_discord_webhook)
    return app
