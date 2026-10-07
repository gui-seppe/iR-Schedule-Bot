"""Discord bot: keeps one message in a channel updated with the tracked series board.

Run: python -m bot.main   (needs DISCORD_TOKEN and CHANNEL_ID in .env)
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

from .message import board_embeds, content_key, heading
from .render import render_board
from .schedule import build_sections, load_json, next_change

log = logging.getLogger("schedule-bot")

CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "config.json"))
STATE_PATH = Path(os.getenv("STATE_PATH", "state.json"))
MIN_SLEEP, MAX_SLEEP = 30, 15 * 60  # seconds; MAX is a safety net in case something drifts
AFTER_START = 20  # refresh this many seconds after a race starts


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state))


class ScheduleBot(discord.Client):
    def __init__(self, channel_id: int):
        super().__init__(intents=discord.Intents(guilds=True))
        self.channel_id = channel_id
        self.state = _load_state()
        self.last_signature: str | None = None

    async def setup_hook(self) -> None:
        self.loop.create_task(self.run_board())

    async def run_board(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            delay = MAX_SLEEP
            try:
                delay = await self.refresh()
            except Exception:
                log.exception("refresh failed, retrying later")
                delay = 60
            await asyncio.sleep(delay)

    async def refresh(self) -> float:
        config = load_json(CONFIG_PATH)
        data = load_json(config.get("schedule_file", "data/schedule.json"))
        now = datetime.now(timezone.utc)
        sections = build_sections(config, data, now)
        rows = [r for sec in sections for r in sec.rows]

        title = config.get("title", "Tracked series")
        use_image = bool(config.get("image"))
        embeds = board_embeds(sections, "schedule.png" if use_image else None)
        content = heading(config)
        # Countdowns tick client-side; only edit when the content actually changes.
        signature = content_key(content, embeds)
        if signature != self.last_signature:
            png = render_board(rows, title) if use_image else None
            await self.publish(content, [discord.Embed.from_dict(e) for e in embeds], png)
            self.last_signature = signature

        wake = next_change(rows, now)
        delay = MAX_SLEEP if wake is None else (wake - now).total_seconds() + AFTER_START
        delay = max(MIN_SLEEP, min(MAX_SLEEP, delay))
        log.info("next refresh in %.0fs", delay)
        return delay

    async def publish(self, content: str, embeds: list[discord.Embed], png: bytes | None) -> None:
        channel = await self.fetch_channel(self.channel_id)
        files = [discord.File(io.BytesIO(png), filename="schedule.png")] if png else []

        msg_id = self.state.get("message_id") if self.state.get("channel_id") == self.channel_id else None
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(content=content, embeds=embeds, attachments=files)
                log.info("edited message %s", msg_id)
                return
            except discord.NotFound:
                log.warning("message %s gone, posting a new one", msg_id)
        msg = await channel.send(content=content, embeds=embeds, files=files)
        self.state = {"channel_id": self.channel_id, "message_id": msg.id}
        _save_state(self.state)
        log.info("posted message %s", msg.id)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ["DISCORD_TOKEN"]
    channel_id = int(os.environ["CHANNEL_ID"])
    ScheduleBot(channel_id).run(token, log_handler=None)


if __name__ == "__main__":
    main()
