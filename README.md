# reasoning-shim

A tiny proxy that makes reasoning models work with tools that only read the `content` field.

## The problem

Most tools built on the OpenAI chat API read the assistant's reply from `choices[].message.content` (or `delta.content` when streaming). Reasoning models put their actual answer in a separate `reasoning_content` field and leave `content` empty or nearly empty.

The result: the tool sees an empty reply. No plan, no tool calls, nothing. It looks like the model is broken when it is working fine, just answering in a field the tool never reads.

I hit this while driving [Strix](https://github.com/usestrix/strix), an autonomous pentest agent, with a free reasoning model. Strix heard silence on every turn. This shim fixed it.

## The fix

`reasoning-shim` sits between your tool and the upstream model as an OpenAI-compatible endpoint. It:

- copies `reasoning_content` into `content` when `content` is empty, for both streaming and non-streaming responses,
- passes `tool_calls` through untouched, so tool use still works,
- forces one upstream model id, so the tool can send whatever model name it likes.

Point your tool at the shim instead of at the upstream, and a reasoning model behaves like a normal one.

## Usage

Requires Python 3.10+ and `aiohttp`.

```bash
# with uv
SHIM_UPSTREAM="https://your-openai-compatible-endpoint/v1" \
SHIM_UPSTREAM_KEY="your-upstream-key" \
SHIM_MODEL="your-reasoning-model-id" \
uv run --with aiohttp python reasoning-shim.py

# or with pip
pip install aiohttp
SHIM_UPSTREAM="..." SHIM_UPSTREAM_KEY="..." SHIM_MODEL="..." python reasoning-shim.py
```

The shim listens on `127.0.0.1:4001` by default.

### Environment

| Var | Required | Default | What it does |
|-----|----------|---------|--------------|
| `SHIM_UPSTREAM_KEY` | yes | none | Bearer key for the upstream endpoint |
| `SHIM_UPSTREAM` | no | `https://api.tokenrouter.com/v1` | Upstream OpenAI-compatible base URL |
| `SHIM_MODEL` | no | `qwen/qwen3.8-max-free` | Model id forced on every upstream call |
| `SHIM_PORT` | no | `4001` | Local port to listen on |

### Pointing a tool at it

Anything that speaks the OpenAI API works. Set the base URL to the shim and use any model name:

```bash
export OPENAI_BASE_URL="http://127.0.0.1:4001/v1"
export OPENAI_API_KEY="anything"   # the shim authenticates upstream with SHIM_UPSTREAM_KEY
```

Example with Strix:

```bash
export STRIX_LLM="openai/your-model"
export LLM_API_BASE="http://127.0.0.1:4001/v1"
export LLM_API_KEY="anything"
strix --target ./my-app
```

## Notes

- Reasoning models spend tokens thinking before they answer. Give them a generous `max_tokens` or the visible reply can still come back empty.
- This is a local dev convenience, not a hardened production proxy. It has no auth of its own, so bind it to localhost.
- One upstream model per instance. Run more instances on different ports for more models.

## License

MIT
