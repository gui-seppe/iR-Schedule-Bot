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

from .message import describe, make_embed, static_signature
from .render import render_board
from .schedule import build_board, load_json


async def run() -> None:
    config = load_json(os.getenv("CONFIG_PATH", "config.json"))
    data = load_json(config.get("schedule_file", "data/schedule.json"))
    rows = build_board(config, data, datetime.now(timezone.utc))
    title = config.get("title", "Tracked series")
    description = describe(rows)
    # The signature goes in the file name, so the next run can tell whether the image is still current
    # without keeping any state of its own.
    image_name = f"schedule-{static_signature(rows)}.png"

    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(os.environ["WEBHOOK_URL"], session=session)
        msg_id = int(os.getenv("MESSAGE_ID") or 0)

        if msg_id:
            try:
                msg = await webhook.fetch_message(msg_id)
            except discord.NotFound:
                print(f"Message {msg_id} not found, posting a new one")
            else:
                same_image = any(a.filename == image_name for a in msg.attachments)
                same_text = bool(msg.embeds) and msg.embeds[0].description == description
                if same_image and same_text:
                    print("Board unchanged, nothing to do")
                    return
                embed = make_embed(title, description, image_name)
                if same_image:
                    await webhook.edit_message(msg_id, embed=embed)
                else:
                    png = render_board(rows, title)
                    file = discord.File(io.BytesIO(png), filename=image_name)
                    await webhook.edit_message(msg_id, embed=embed, attachments=[file])
                print(f"Updated message {msg_id} (image {'kept' if same_image else 'replaced'})")
                return

        png = render_board(rows, title)
        file = discord.File(io.BytesIO(png), filename=image_name)
        msg = await webhook.send(embed=make_embed(title, description, image_name), file=file, wait=True)
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
