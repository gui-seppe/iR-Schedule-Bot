"""Run oneshot against a fake Discord webhook endpoint."""
import asyncio
import json

from aiohttp import web

from bot import oneshot


def _serve(handler_state):
    async def get_msg(request):
        return web.json_response(handler_state["message"])

    async def patch_msg(request):
        handler_state["patches"].append(await request.json())
        return web.json_response({"id": "42"})

    async def post(request):
        handler_state["posts"].append(await request.json())
        return web.json_response({"id": "99"})

    app = web.Application()
    app.router.add_get("/api/webhooks/1/tok/messages/42", get_msg)
    app.router.add_patch("/api/webhooks/1/tok/messages/42", patch_msg)
    app.router.add_post("/api/webhooks/1/tok", post)
    return app


async def _run(state, msg_id, tmp_path, monkeypatch):
    runner = web.AppRunner(_serve(state))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        await oneshot.run(f"http://127.0.0.1:{port}/api/webhooks/1/tok", msg_id)
    finally:
        await runner.cleanup()


def test_edit_message_with_reactions_and_old_image(tmp_path, monkeypatch):
    state = {
        "message": {"id": "42", "embeds": [{"title": "old"}],
                    "attachments": [{"filename": "schedule.png"}],
                    "reactions": [{"emoji": {"name": "🔥"}, "count": 1}]},
        "patches": [], "posts": [],
    }
    asyncio.run(_run(state, "42", tmp_path, monkeypatch))
    assert len(state["patches"]) == 1 and not state["posts"]
    patch = state["patches"][0]
    assert patch["attachments"] == []  # old image removed
    assert patch["content"].startswith("## ") and len(patch["embeds"]) == 2


def test_unchanged_board_is_not_edited(tmp_path, monkeypatch):
    state = {"message": {}, "patches": [], "posts": []}
    asyncio.run(_run(state, None, tmp_path, monkeypatch))  # first run posts
    posted = state["posts"][0]
    state["message"] = {"id": "42", "content": posted["content"], "embeds": posted["embeds"], "attachments": [],
                        "reactions": [{"emoji": {"name": "👍"}, "count": 2}]}
    asyncio.run(_run(state, "42", tmp_path, monkeypatch))
    assert state["patches"] == []
