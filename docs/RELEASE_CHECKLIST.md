# Before making the repo public

- [x] License chosen and `LICENSE` added; README states it
- [x] Secret scan of the full git history (e.g. gitleaks); `.env`, `data/`, `config.toml` never committed
- [x] `config.example.toml` and `.env.example` complete, with no real values
- [x] README + docs/GUIDE.md: what it is, screenshots (light/dark), Pi install, AI setup (TypeSafe key; `mode=llm` for users without one; subscription-vs-API note)
- [x] Fonts licence (Bricolage Grotesque, OFL) included
- [x] Remove personal sample data from the seed and `tests/fixtures/`; keep a neutral example plan and regenerate its `.expected.json` (history: D-12)
- [ ] Fresh-clone install tested on the Pi from docs/GUIDE.md only
- [x] Issues/PR templates optional; CHANGELOG starts at v0.1.0
