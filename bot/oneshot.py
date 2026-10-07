"""Update the board once via a channel webhook, then exit. Meant to run on a schedule (GitHub Actions).

Env: WEBHOOK_URL (required), MESSAGE_ID (optional: the message to keep editing).
Without MESSAGE_ID a new message is posted and its ID printed; save it as the MESSAGE_ID variable.

Uses Discord's webhook HTTP API directly (plain JSON). discord.py's webhook client crashes when parsing
messages that have reactions, and we don't need its models anyway.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import aiohttp

from .message import board_embed, content_key, static_signature
from .render import render_board
from .schedule import build_board, load_json


class DiscordError(Exception):
    pass


async def _call(session: aiohttp.ClientSession, method: str, url: str, payload: dict | None = None,
                image: tuple[str, bytes] | None = None) -> dict:
    kwargs = {}
    if payload is not None and image:
        name, png = image
        payload = {**payload, "attachments": [{"id": 0, "filename": name}]}
        form = aiohttp.FormData()
        form.add_field("payload_json", json.dumps(payload), content_type="application/json")
        form.add_field("files[0]", png, filename=name, content_type="image/png")
        kwargs["data"] = form
    elif payload is not None:
        kwargs["json"] = payload
    async with session.request(method, url, **kwargs) as resp:
        if resp.status == 404:
            return {}
        if resp.status >= 400:
            raise DiscordError(f"{method} failed: {resp.status} {await resp.text()}")
        return await resp.json()


async def run(webhook_url: str, msg_id: str | None) -> None:
    config = load_json(os.getenv("CONFIG_PATH", "config.json"))
    data = load_json(config.get("schedule_file", "data/schedule.json"))
    rows = build_board(config, data, datetime.now(timezone.utc))
    title = config.get("title", "Tracked series")
    # Optional table image. Its file name carries a hash of its content, so the next run can tell whether
    # it is still current without keeping any state of its own.
    image_name = f"schedule-{static_signature(rows)}.png" if config.get("image") else None
    embed = board_embed(rows, title, image_name)

    def image() -> tuple[str, bytes] | None:
        return (image_name, render_board(rows, title)) if image_name else None

    async with aiohttp.ClientSession() as session:
        if msg_id:
            msg_url = f"{webhook_url}/messages/{msg_id}"
            msg = await _call(session, "GET", msg_url)
            if not msg:
                print(f"Message {msg_id} not found, posting a new one")
            else:
                current = (msg.get("embeds") or [{}])[0]
                have = [a["filename"] for a in msg.get("attachments", [])]
                same_image = have == ([image_name] if image_name else [])
                if same_image and content_key(current) == content_key(embed):
                    print("Board unchanged, nothing to do")
                    return
                if same_image:
                    await _call(session, "PATCH", msg_url, {"embeds": [embed]})
                else:
                    # Replacing the attachment list also drops an old image when the image is turned off.
                    await _call(session, "PATCH", msg_url, {"embeds": [embed], "attachments": []}, image())
                print(f"Updated message {msg_id}")
                return

        msg = await _call(session, "POST", f"{webhook_url}?wait=true", {"embeds": [embed]}, image())
        note = f"Posted new message {msg['id']}. Save it as the MESSAGE_ID repository variable."
        print(f"::notice::{note}" if os.getenv("GITHUB_ACTIONS") else note)
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary, "a") as f:
                f.write(f"{note}\n")


def main() -> None:
    url = (os.getenv("WEBHOOK_URL") or "").strip().rstrip("/")
    if not url:
        sys.exit("WEBHOOK_URL is not set (add it under Settings > Secrets and variables > Actions > Secrets)")
    if not url.startswith("https://") or "/api/webhooks/" not in url:
        sys.exit("WEBHOOK_URL doesn't look like a Discord webhook URL (https://discord.com/api/webhooks/...)")
    msg_id = (os.getenv("MESSAGE_ID") or "").strip()
    if msg_id and not msg_id.isdigit():
        sys.exit(f"MESSAGE_ID must be just the number, got {msg_id!r}")
    try:
        asyncio.run(run(url, msg_id or None))
    except DiscordError as e:
        sys.exit(f"Discord rejected the request: {e}")


if __name__ == "__main__":
    main()
