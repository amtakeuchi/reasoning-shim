#!/usr/bin/env python3
"""Tiny OpenAI-compatible shim: rewrites reasoning_content -> content so tools like
Strix (which only read `content`) can use reasoning models. Forwards everything else
untouched, including native tool_calls. Streams and non-streams.

Env:
  SHIM_UPSTREAM      upstream base (default tokenrouter qwen-max)
  SHIM_UPSTREAM_KEY  bearer key for upstream (required)
  SHIM_MODEL         model id to force upstream (default qwen/qwen3.8-max-free)
  SHIM_PORT          listen port (default 4001)
"""
import os, json, aiohttp
from aiohttp import web

UPSTREAM = os.environ.get("SHIM_UPSTREAM", "https://api.tokenrouter.com/v1").rstrip("/")
KEY = os.environ["SHIM_UPSTREAM_KEY"]
MODEL = os.environ.get("SHIM_MODEL", "qwen/qwen3.8-max-free")
PORT = int(os.environ.get("SHIM_PORT", "4001"))


def _fix_delta(d):
    # move reasoning into content when content is absent, so a content-only reader sees text
    if d.get("reasoning_content") and not d.get("content"):
        d["content"] = d.pop("reasoning_content")
    return d


async def chat(request):
    body = await request.json()
    body["model"] = MODEL
    headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    streaming = bool(body.get("stream"))
    timeout = aiohttp.ClientTimeout(total=None, sock_read=300)
    async with aiohttp.ClientSession(timeout=timeout) as sess:
        async with sess.post(f"{UPSTREAM}/chat/completions", json=body, headers=headers) as up:
            if not streaming:
                data = await up.json()
                for ch in data.get("choices", []):
                    _fix_delta(ch.get("message", {}))
                return web.json_response(data, status=up.status)
            resp = web.StreamResponse(status=up.status, headers={"Content-Type": "text/event-stream"})
            await resp.prepare(request)
            async for raw in up.content:
                line = raw.decode("utf-8", "ignore")
                if line.startswith("data: "):
                    payload = line[6:].strip()
                    if payload and payload != "[DONE]":
                        try:
                            obj = json.loads(payload)
                            for ch in obj.get("choices", []):
                                _fix_delta(ch.get("delta", {}))
                            line = "data: " + json.dumps(obj) + "\n"
                        except Exception:
                            pass
                await resp.write(line.encode())
            await resp.write_eof()
            return resp


async def models(request):
    return web.json_response({"object": "list", "data": [{"id": MODEL, "object": "model"}]})


app = web.Application()
app.router.add_post("/v1/chat/completions", chat)
app.router.add_get("/v1/models", models)
if __name__ == "__main__":
    print(f"reasoning-shim: 127.0.0.1:{PORT} -> {UPSTREAM} ({MODEL})")
    web.run_app(app, host="127.0.0.1", port=PORT, print=None)
