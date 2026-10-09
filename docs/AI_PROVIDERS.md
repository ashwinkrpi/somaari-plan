# AI providers

Two kinds of AI call, kept separate in `app/ai/router.py`:

| Call | Used for | Default provider |
|---|---|---|
| `decide(state, questions)` | Is this line a task? Priority? Meeting? Date parts? | **Jev** (TypeSafe) |
| `generate(prompt)` | Rewriting loose prose into task titles; full extraction in LLM-only mode | `openrouter_free` |

Jev never generates text. Code splits plans into lines and owns titles and dates; Jev answers typed questions about each line. LLMs are a fallback, not the main path.

## Jev (TypeSafe)
- Endpoint: `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer $TYPESAFE_API_KEY`. Call it with stdlib `urllib`; no SDK.
- Body: `{"state": ..., "model": ..., "questions": {id: {type, instructions, criteria?}}}`.
- Question types: `noul` → `noul` 0–1 · `choice` → `choice`, `probabilities`, `confidence` · `score` → `score`, `probabilities`, `confidence`.
- Model: `jev-latest` while building. Pin a version (e.g. `jev-1.13.0`) once thresholds are tuned, because the alias moves.
- Limits: 64k tokens per request; 32k for state plus the longest question. Batch up to 40 lines per request.
- 429 → honour `retry-after`, max 3 tries.
- Billed per input token only. Log `usage.input_tokens` per call.
- Check the TypeSafe docs page "Jev jaggedness" for known weak spots before tuning thresholds.
- Building with Claude Code: install the TypeSafe skill once (`claude plugin marketplace add typesafe-ai/skills`, then `claude plugin install typesafe@typesafe-ai`). It loads only when needed.

## Generate providers (fallback)
| id | Auth | Notes |
|---|---|---|
| `openrouter_free` | `OPENROUTER_API_KEY` | `openrouter/free`; rate-limited; upstream may log prompts, so only the prose sentences are sent |
| `gemini_cli` | Gemini CLI login | `gemini -p` |
| `gemini_api` | `GEMINI_API_KEY` | free tier available |
| `ollama` | none | not built (left out in Stage 5; heavy on the Pi) |

No Claude models are used by the app (decision D-02). A Gemini app subscription includes no API access, so it works only through `gemini_cli`; verify flags with `gemini --help` first.

## Config — `config.toml` (committed as `config.example.toml`)
```toml
[ai]
mode = "jev"                       # jev | llm | off
jev_model = "jev-latest"
generate_chain = ["openrouter_free"]   # [] disables all LLM use
rewrite_prose = true               # send prose-heavy blocks to generate_chain
timeout_s = 60

[ai.thresholds]
task_accept = 0.70                 # noul at or above → task
task_review = 0.40                 # between review and accept → flagged in preview
confidence_review = 0.60           # choice confidence below → flagged
```
- `mode = "jev"`: Jev decides; LLM only rewrites prose (if `rewrite_prose`).
- `mode = "llm"`: for users without a TypeSafe key. `generate_chain` does full extraction with the JSON prompt in AI_PROMPTS.md.
- `mode = "off"`: code parsing only; every line becomes a draft task for manual review.
Keys live only in `.env` (`TYPESAFE_API_KEY`, optional others). The Settings page edits mode, model, chain and thresholds, never keys.

## Defaults by phase
- Tests: `decide` → `mock_jev`, `generate` → `mock_llm` (forced in `conftest.py`). No network.
- Development: `mode="jev"`, `generate_chain=["openrouter_free"]`.
- Other users without a TypeSafe key: `mode="llm"` with their own chain (e.g. `["gemini_api"]` or `["openrouter_free"]`).

## Router behaviour
1. Cache key = sha256(provider + model + question-set/prompt version + state). Hit → no call; pinning a new model misses the cache.
2. `decide`: one Jev request per batch. On failure → `mode` falls back to `llm` if `generate_chain` is set, else `off`. The UI says which.
3. `generate`: try the chain in order; validate JSON; one retry, then next provider.
4. Log provider, model, input tokens and latency to `data/ai.log`. Never log content or keys For generate providers, `model` is the model that actually answered (e.g. the one `openrouter/free` routed to); on failure, the requested model.
