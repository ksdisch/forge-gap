# forge-gap

The GLM-via-OpenRouter connection you'll build AI harnesses around. OpenRouter
exposes an **OpenAI-compatible** API, so this is a thin client over GLM-4.6 plus
a smoke test that proves both **chat** and **tool-calling** work.

```
forge-gap/
├─ glm.py          # the reusable client: chat(), MODEL  ← import this in harness code
├─ agent.py        # the reason→act→observe loop + deterministic grading
├─ scenario.py     # the S2 lookup-then-compute task (2 tools + ground truth)
├─ oracle.py       # the deterministic grader (never an LLM judge)
├─ verify.py       # smoke test: plain chat + one tool-calling round-trip
├─ test_oracle.py  # offline unit tests (oracle + scenario + dispatch)
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
   `forge-gap` → copy it (starts with `sk-or-v1-...`).

## 2. Drop the key in

Open `.env` and paste the key after `OPENROUTER_API_KEY=`, then save. That's it —
`.env` is gitignored, so the key never leaves your machine or gets committed.

## 3. Verify

```bash
cd ~/Desktop/forge-gap
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

## 5. Run the agent (S2 — scenario + oracle)

`agent.py` runs the bare **reason → act → observe** loop on a multi-step tool task and grades
the result against known ground truth — *deterministically*, never with an LLM judge.

```bash
uv run agent.py
```

The default task (`scenario.py`) is a **lookup-then-compute** scenario: GLM looks up an order,
looks up the shipping rate for that order's zone (a *chained* lookup), adds them, and calls
`submit_answer` with the total. The oracle (`oracle.py`) compares GLM's submitted number to the
known answer (140 + 18 = **158**) and prints **PASS**/**FAIL**. Every step is appended to
`trajectory.jsonl` (gitignored) for hand-reading.

Offline, before spending API calls, run the unit tests:

```bash
uv run test_oracle.py
```

One run is a single sample — a PASS/FAIL *rate* over many runs (with confidence intervals) is
what later sessions measure.

## Reference
- OpenRouter quickstart: https://openrouter.ai/docs/quickstart
- OpenRouter tool-calling: https://openrouter.ai/docs/guides/features/tool-calling
- GLM-4.6 model page: https://openrouter.ai/z-ai/glm-4.6
