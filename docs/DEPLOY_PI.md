# Running on the Pi

- Start with `python -m app`; host, port and threads come from `[server]` in `config.toml` (or `SOMAARI_PORT` in `.env`). LAN only; use ZeroTier for remote access.
- Changing the port: edit `config.toml`, then `systemctl --user restart somaari-plan`. Check it's free first: `ss -ltn | grep :<port>`.
- systemd unit `~/.config/systemd/user/somaari-plan.service` (user service, `Restart=on-failure`, `WorkingDirectory` = repo, `EnvironmentFile` = `.env`). Enable with `loginctl enable-linger`.
- `.env` holds `TYPESAFE_API_KEY` (plus any optional keys); mode 600.
- `gemini_cli` (if used) needs the CLI on the service's PATH and a login for the same user; set `Environment=PATH=...` in the unit.
- Backup: needs the CLI (`sudo apt install sqlite3`). Nightly cron `sqlite3 data/somaari.db ".backup data/backups/$(date +%F).db"`, then prune with `find data/backups -name '*.db' -mtime +14 -delete`.
- Logs: journald for the app; `data/ai.log` rotated at 1 MB, keep 3.
- Targets: idle RSS < 80 MB, Today page < 1 s on LAN, no swap use.
- VS Code Remote-SSH: exclude `.venv`, `data/` and `design/` from the file watcher.
