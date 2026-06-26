# harness-lab

The GLM-via-OpenRouter connection you'll build AI harnesses around. OpenRouter
exposes an **OpenAI-compatible** API, so this is a thin client over GLM-4.6 plus
a smoke test that proves both **chat** and **tool-calling** work.

```
harness-lab/
├─ glm.py          # the reusable client: chat(), MODEL  ← import this in harness code
├─ verify.py       # smoke test: plain chat + one tool-calling round-trip
├─ .env            # your key lives here (gitignored)
├─ .env.example    # template
└─ pyproject.toml  # uv project (Python 3.11+, openai + python-dotenv)
```

## 1. Get your key

1. Sign in at **https://openrouter.ai** (Google / GitHub / email).
2. Add credits at **https://openrouter.ai/credits** — GLM-4.6 is a *paid* model, but
   cheap (~$0.40 / 1M input tokens). $5–$10 covers a huge amount of dev. *(Skip if you
   already have a balance.)*
3. Create a key at **https://openrouter.ai/keys** → **Create Key** → name it
   `harness-lab` → copy it (starts with `sk-or-v1-...`).

## 2. Drop the key in

Open `.env` and paste the key after `OPENROUTER_API_KEY=`, then save. That's it —
`.env` is gitignored, so the key never leaves your machine or gets committed.

## 3. Verify

```bash
cd ~/Desktop/john_SE_work/harness-lab
uv run verify.py
```

`uv` builds the venv and installs deps on first run. Expected tail:

```
All checks passed - GLM-4.6 chat + tool-calling work. Ready to build.
```

## 4. Use it

```python
from glm import chat, MODEL

resp = chat([{"role": "user", "content": "Explain a retry nudge in one line."}])
print(resp.choices[0].message.content)
```

`chat(...)` forwards `tools=`, `tool_choice=`, `temperature=`, `max_tokens=`, etc.
straight to the API — that's the surface your harness logic (retry nudges, error
recovery, step enforcement) will wrap.

## Reference
- OpenRouter quickstart: https://openrouter.ai/docs/quickstart
- OpenRouter tool-calling: https://openrouter.ai/docs/guides/features/tool-calling
- GLM-4.6 model page: https://openrouter.ai/z-ai/glm-4.6
