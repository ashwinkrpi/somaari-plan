"""Write app/_build_info.py (git-ignored) with the commit and UTC build date. Run at release time:
    .venv/bin/python -m app.stamp
Running from source without it, About shows build_commit "dev" and build_date "unknown"."""
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "_build_info.py"


def main():
    commit = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True,
                            cwd=OUT.parent, check=True).stdout.strip()
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT.write_text(f'BUILD_COMMIT = "{commit}"\nBUILD_DATE = "{date}"\n', encoding="utf-8")
    print(f"stamped {commit} {date}")


if __name__ == "__main__":
    main()
