"""Manual real-provider check: python -m app.ai.smoke <jev|openrouter_free|gemini_api|openai_compat>.
Prints provider, model, latency. Uses real tokens; never run from tests."""
import sys

from .. import config
from . import router


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit("usage: python -m app.ai.smoke <jev|openrouter_free|gemini_api|openai_compat>")
    config.load_dotenv()
    r = router.test_provider(argv[0])
    print(r)
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
