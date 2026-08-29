#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab local HTTP server (127.0.0.1 only).

Serves the lightweight Character Lab frontend and a small JSON API over the
existing Slice 1 runtime/capture foundation. No external interfaces, no secret
values returned, no package/acceptance mutation, no arbitrary filesystem or
command endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parent
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.character_lab import CharacterLabApp  # noqa: E402
from services.character_lab.app import resolve_data_root  # noqa: E402
from crp_provider_adapter import ProviderConfig, build_provider_callable  # noqa: E402
from crp_kira_r4_runner import (  # noqa: E402
    LIVE_BASE_URL,
    LIVE_CREDENTIAL_ENV,
    LIVE_MAX_TOKENS,
    LIVE_MODEL,
    LIVE_PROVIDER_ID,
    LIVE_TIMEOUT_S,
)

BIND_HOST = "127.0.0.1"
WEB_DIR = _REPO_ROOT / "services" / "character_lab" / "web"

_STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.css": "app.css",
    "/app.js": "app.js",
}


def app_mode_url(host: str, port: int) -> str:
    """The App Mode URL the launcher opens (no normal browser chrome)."""
    return f"http://{host}:{port}"


def app_mode_argument(host: str, port: int) -> list:
    """App Mode command argument for Edge/Chrome (--app=<url>)."""
    return [f"--app={app_mode_url(host, port)}"]


def provider_availability(credential_env: str = LIVE_CREDENTIAL_ENV) -> str:
    """Presence-only check of the credential env var NAME (never its value)."""
    return "CONFIGURED" if credential_env in os.environ else "NOT CONFIGURED"


def build_provider_info() -> dict:
    return {
        "provider_id": LIVE_PROVIDER_ID,
        "model": LIVE_MODEL,
        "base_url": LIVE_BASE_URL,
        "timeout_s": LIVE_TIMEOUT_S,
        "max_tokens": LIVE_MAX_TOKENS,
        "json_mode": False,
        "credential_env": LIVE_CREDENTIAL_ENV,
    }


def build_deepseek_provider_factory():
    config = ProviderConfig(
        provider_id=LIVE_PROVIDER_ID,
        model=LIVE_MODEL,
        base_url=LIVE_BASE_URL,
        credential_env=LIVE_CREDENTIAL_ENV,
        timeout_s=LIVE_TIMEOUT_S,
        max_tokens=LIVE_MAX_TOKENS,
    )

    def factory(recorder=None):
        return build_provider_callable(config, recorder=recorder)

    return factory


def build_app(
    *,
    provider_factory=None,
    provider_info=None,
    availability=None,
    data_root=None,
    acceptance_root=None,
) -> CharacterLabApp:
    availability = availability if availability is not None else provider_availability()
    return CharacterLabApp(
        acceptance_root=acceptance_root,
        data_root=data_root,
        provider_factory=provider_factory,
        provider_info=provider_info,
        provider_availability=availability,
    )


class CharacterLabServer:
    """Loopback-only HTTP server wrapping a CharacterLabApp."""

    def __init__(self, app: CharacterLabApp, bind: str = BIND_HOST, port: int = 0, web_dir=WEB_DIR) -> None:
        self._app = app
        self._web_dir = Path(web_dir)
        self._httpd = ThreadingHTTPServer((bind, port), self._make_handler())
        self._thread: Optional[threading.Thread] = None

    @property
    def host(self) -> str:
        return self._httpd.server_address[0]

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return app_mode_url(self.host, self.port)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        thread.start()
        self._thread = thread
        return thread

    def shutdown(self) -> None:
        try:
            self._httpd.shutdown()
        finally:
            self._httpd.server_close()

    # ---------------------------------------------------------------- handler
    def _make_handler(self):
        app = self._app
        web_dir = self._web_dir
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CharacterLab/0.1"

            def log_message(self, *args) -> None:
                pass

            def _json(self, status: int, obj) -> None:
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", 0) or 0)
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return {}
                return data if isinstance(data, dict) else {}

            def _serve_static(self, name: str) -> None:
                path = web_dir / name
                if not path.exists():
                    self.send_error(404)
                    return
                if name.endswith(".html"):
                    content_type = "text/html"
                elif name.endswith(".css"):
                    content_type = "text/css"
                else:
                    content_type = "application/javascript"
                body = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _route(self, method: str, path: str) -> None:
                if method == "GET":
                    if path in _STATIC_FILES:
                        self._serve_static(_STATIC_FILES[path])
                        return
                    if path == "/health":
                        self._json(200, app.health())
                        return
                    if path == "/api/catalog":
                        self._json(200, app.catalog())
                        return
                    if path == "/api/state":
                        self._json(200, app.loaded_state())
                        return
                    if path == "/api/sessions":
                        self._json(200, app.list_sessions())
                        return
                    if path == "/api/character":
                        self._json(200, app.character_inspector())
                        return
                    if path == "/api/turns":
                        self._json(200, app.list_turns())
                        return
                    if path.startswith("/api/turn/"):
                        turn_id = urllib.parse.unquote(path[len("/api/turn/"):])
                        try:
                            self._json(200, app.turn_detail(turn_id))
                        except KeyError:
                            self._json(404, {"error": "unknown_turn", "message": "Ход не найден."})
                        return
                elif method == "POST":
                    if path == "/api/session/new":
                        self._json(200, app.new_session())
                        return
                    if path == "/api/session/select":
                        sid = self._read_json().get("session_id")
                        try:
                            self._json(200, app.select_session(sid))
                        except KeyError:
                            self._json(404, {"error": "unknown_session", "message": "Сессия не найдена."})
                        return
                    if path == "/api/chat":
                        body = self._read_json()
                        result = app.chat(body.get("message", ""), body.get("session_id"))
                        self._json(200 if result.get("ok") else 409, result)
                        return
                    if path == "/shutdown":
                        self._json(200, {"status": "shutting_down"})
                        threading.Thread(target=server_ref.shutdown, daemon=True).start()
                        return
                self._json(404, {"error": "not_found", "message": "Not found."})

            def do_GET(self) -> None:
                self._route("GET", self.path.split("?", 1)[0])

            def do_POST(self) -> None:
                self._route("POST", self.path.split("?", 1)[0])

        return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Character Lab local server (127.0.0.1 only)")
    parser.add_argument("--host", default=BIND_HOST)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--port-file", default=None, help="write the bound port to this file")
    args = parser.parse_args(argv)

    availability = provider_availability()
    provider_factory = None
    if availability == "CONFIGURED":
        provider_factory = build_deepseek_provider_factory()

    app = build_app(
        provider_factory=provider_factory,
        provider_info=build_provider_info(),
        availability=availability,
    )
    server = CharacterLabServer(app, bind=args.host, port=args.port)
    if args.port_file:
        Path(args.port_file).write_text(str(server.port), encoding="utf-8")

    print(f"Character Lab server: {server.base_url}", flush=True)
    print(f"Provider availability: {availability}", flush=True)

    thread = server.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
