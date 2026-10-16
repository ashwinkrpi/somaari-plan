# Testing

- `pytest` only. Tests use a temp SQLite file, `mock_jev` and `mock_llm` (`conftest.py` forces them). No network.
- `mock_jev` returns answers from `tests/fixtures/jev/<set>_<sha8>.json`; helper `fake_answers(t=..., p=..., conf=...)` builds them inline. A missing fixture fails loudly.
- Record a real Jev response once (`python -m app.ai.smoke jev --save`) to keep fixtures realistic.
- Port resolution test: CLI beats env beats config beats default; out-of-range and busy ports fail clearly.
- Test the pure parts hardest: `mdparse.py`, `dates.py`, `scheduler.py`, `quickparse.py`, threshold logic.
- `mdparse` golden test: `tests/fixtures/example-plan.md` must produce exactly `tests/fixtures/example-plan.expected.json` (21 candidates, 6 steps). If the rules in AI_PROMPTS.md change, regenerate the expected file and show Ashwin Koppam Raghavendra the diff.
- `quickparse` table test (no AI):
  | input (TODAY=2026-10-06) | date | time | type |
  |---|---|---|---|
  | Meeting tomorrow afternoon to review the site draft | 2026-10-07 | 15:00 | meeting |
  | Check Cloudflare Pages analytics on 3rd of next month | 2026-11-03 | – | task |
  | Call the bank at 4pm tomorrow | 2026-10-07 | 16:00 | task |
  | Dentist on 14 Nov at 10:30am | 2026-11-14 | 10:30 | task |
  | Plan next sprint next week | 2026-10-12 (week) | – | task |
- Real-provider smoke test, manual only: `python -m app.ai.smoke <jev|provider>`. Prints model, input tokens, latency.
- UI: manual checklist at 380px and 1440px, light and dark, keyboard only.
