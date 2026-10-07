"""Discord bot: keeps one message in a channel updated with the tracked series board.

Run: python -m bot.main   (needs DISCORD_TOKEN and CHANNEL_ID in .env)
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

from .message import describe
from .render import render_board
from .schedule import build_board, load_json, next_change

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
        rows = build_board(config, data, now)

        description = describe(rows)
        png = render_board(rows, config.get("title", "Tracked series"))
        # Countdowns tick client-side; only edit when the content actually changes.
        signature = hashlib.sha256(description.encode() + _static_part(rows)).hexdigest()
        if signature != self.last_signature:
            await self.publish(description, png, config)
            self.last_signature = signature

        wake = next_change(rows, now)
        delay = MAX_SLEEP if wake is None else (wake - now).total_seconds() + AFTER_START
        delay = max(MIN_SLEEP, min(MAX_SLEEP, delay))
        log.info("next refresh in %.0fs", delay)
        return delay

    async def publish(self, description: str, png: bytes, config: dict) -> None:
        channel = await self.fetch_channel(self.channel_id)
        embed = discord.Embed(title=config.get("title", "Tracked series"), description=description,
                              color=0xE03C31, timestamp=datetime.now(timezone.utc))
        embed.set_image(url="attachment://schedule.png")
        embed.set_footer(text="Times are in your local timezone · last change")
        file = discord.File(io.BytesIO(png), filename="schedule.png")

        msg_id = self.state.get("message_id") if self.state.get("channel_id") == self.channel_id else None
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, attachments=[file])
                log.info("edited message %s", msg_id)
                return
            except discord.NotFound:
                log.warning("message %s gone, posting a new one", msg_id)
        msg = await channel.send(embed=embed, file=file)
        self.state = {"channel_id": self.channel_id, "message_id": msg.id}
        _save_state(self.state)
        log.info("posted message %s", msg.id)


def _static_part(rows) -> bytes:
    # The image only shows week/track/weather, so hash those instead of the PNG (which has a timestamp).
    return json.dumps([[r.label, r.week, [s.week for s in r.sides]] for r in rows], default=str).encode()


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ["DISCORD_TOKEN"]
    channel_id = int(os.environ["CHANNEL_ID"])
    ScheduleBot(channel_id).run(token, log_handler=None)


if __name__ == "__main__":
    main()
