import argparse
import os
import socket
import sys

from . import create_app
from .config import ConfigError, load_dotenv, resolve_server


def port_is_free(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def main(argv=None):
    p = argparse.ArgumentParser(prog="somaari-plan")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--dev", action="store_true", help="Flask debug server")
    args = p.parse_args(argv)
    load_dotenv()
    try:
        host, port, threads = resolve_server(args.host, args.port)
    except ConfigError as e:
        sys.exit(f"somaari-plan: {e}")
    # The Flask reloader's child re-runs main() while the parent holds the port.
    reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not reloader_child and not port_is_free(host, port):
        sys.exit(
            f"somaari-plan: port {port} is already in use. Pick another with "
            f"--port, SOMAARI_PORT or [server] port in config.toml."
        )
    app = create_app()
    print(f"somaari-plan on http://{host}:{port}", flush=True)
    if args.dev:
        app.run(host=host, port=port, debug=True, load_dotenv=False)  # .env already loaded above
    else:
        from waitress import serve
        serve(app, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
