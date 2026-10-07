"""Update the board once via a channel webhook, then exit. Meant to run on a schedule (GitHub Actions).

Env: WEBHOOK_URL (required), MESSAGE_ID (optional: the message to keep editing).
Without MESSAGE_ID a new message is posted and its ID printed; save it as the MESSAGE_ID variable.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
from datetime import datetime, timezone

import aiohttp
import discord

from .message import board_embed, content_key, static_signature
from .render import render_board
from .schedule import build_board, load_json


async def run() -> None:
    config = load_json(os.getenv("CONFIG_PATH", "config.json"))
    data = load_json(config.get("schedule_file", "data/schedule.json"))
    rows = build_board(config, data, datetime.now(timezone.utc))
    title = config.get("title", "Tracked series")
    # Optional table image. Its file name carries a hash of its content, so the next run can tell whether
    # it is still current without keeping any state of its own.
    image_name = f"schedule-{static_signature(rows)}.png" if config.get("image") else None
    embed_dict = board_embed(rows, title, image_name)
    embed = discord.Embed.from_dict(embed_dict)

    def files() -> list[discord.File]:
        if not image_name:
            return []
        return [discord.File(io.BytesIO(render_board(rows, title)), filename=image_name)]

    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(os.environ["WEBHOOK_URL"], session=session)
        msg_id = int(os.getenv("MESSAGE_ID") or 0)

        if msg_id:
            try:
                msg = await webhook.fetch_message(msg_id)
            except discord.NotFound:
                print(f"Message {msg_id} not found, posting a new one")
            else:
                current = msg.embeds[0].to_dict() if msg.embeds else {}
                have = [a.filename for a in msg.attachments]
                same_image = have == ([image_name] if image_name else [])
                if same_image and content_key(current) == content_key(embed_dict):
                    print("Board unchanged, nothing to do")
                    return
                if same_image:
                    await webhook.edit_message(msg_id, embed=embed)
                else:
                    await webhook.edit_message(msg_id, embed=embed, attachments=files())
                print(f"Updated message {msg_id}")
                return

        msg = await webhook.send(embed=embed, files=files(), wait=True)
        note = f"Posted new message {msg.id}. Save it as the MESSAGE_ID repository variable."
        print(f"::notice::{note}" if os.getenv("GITHUB_ACTIONS") else note)
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary, "a") as f:
                f.write(f"{note}\n")


def main() -> None:
    if not os.getenv("WEBHOOK_URL"):
        sys.exit("WEBHOOK_URL is not set")
    asyncio.run(run())


if __name__ == "__main__":
    main()
