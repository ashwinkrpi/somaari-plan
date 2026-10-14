# Running on the Pi

User-facing setup lives in [GUIDE.md](GUIDE.md): [install](GUIDE.md#install-on-a-raspberry-pi), [who can reach it](GUIDE.md#who-can-reach-it), [systemd service](GUIDE.md#run-as-a-service) (incl. `gemini_cli` PATH), [port changes](GUIDE.md#server), [backups](GUIDE.md#backups), [logs](GUIDE.md#logs). Keep this file to notes the guide doesn't need.

- Targets: idle RSS < 80 MB, Today page < 1 s on LAN, no swap use.
- VS Code Remote-SSH: exclude `.venv`, `data/` and `design/` from the file watcher.
