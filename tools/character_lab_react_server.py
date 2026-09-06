#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""React Character Lab desktop integration v1 -- local loopback HTTP server.

Serves a small JSON API (see ``services.character_lab.react_transport``) over
``CharacterLabServiceAdapter`` for the React Character Lab client
(``apps/character_lab_react``). This is a NEW module, separate from
``tools/character_lab_server.py`` (the existing vanilla Character Lab
server) -- the vanilla app and its server are untouched and remain fully
operational.

Binds ONLY to 127.0.0.1 (loopback). Never 0.0.0.0, never a LAN interface. No
authentication -- this is a local development integration slice, not a
production security boundary.

NO LIVE PROVIDER CALL IS AUTHORIZED for this integration slice: this server
always constructs its ``CharacterLabApp`` with a deterministic, network-free
FAKE provider (see ``build_fake_provider_factory``), never the real DeepSeek
adapter the vanilla server can use. Real live chat is a separate, later owner
decision.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.character_lab import CharacterLabApp  # noqa: E402
from services.character_lab.react_transport import (  # noqa: E402
    ReactTransport,
    ReactTransportError,
)
from services.character_lab.service_adapter import CharacterLabServiceAdapter  # noqa: E402

BIND_HOST = "127.0.0.1"
#: Fixed conventional local dev port so `vite.config.ts`'s proxy target can be
#: a static value -- a port number, not a machine-specific path. Overridable
#: via --port (e.g. --port 0 lets the OS pick, used by tests/smokes).
DEFAULT_PORT = 8787

FAKE_PROVIDER_ID = "fake"
FAKE_MODEL = "fake-react-desktop-integration-v1"
DEFAULT_FAKE_REPLY = "[KIRA] (фейковый провайдер, React Desktop Integration v1) Привет!"


def build_fake_provider_factory(response: str = DEFAULT_FAKE_REPLY):
    """A deterministic, network-free provider factory.

    Matches the same fake/recording provider shape used throughout the
    existing Character Lab test suite -- no live provider call, no
    credential read, ever, from this server.
    """

    def factory(recorder):
        def provider(messages):
            body = json.dumps(
                {"model": FAKE_MODEL, "messages": messages}, ensure_ascii=False
            ).encode("utf-8")
            if recorder:
                recorder({
                    "event": "request",
                    "payload": {"model": FAKE_MODEL, "messages": messages},
                    "body": body,
                })
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake-react",
                    "model": FAKE_MODEL,
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                }})
            return response

        return provider

    return factory


def build_app(
    *,
    data_root=None,
    acceptance_root=None,
    response: str = DEFAULT_FAKE_REPLY,
) -> CharacterLabApp:
    return CharacterLabApp(
        acceptance_root=acceptance_root,
        data_root=data_root,
        provider_factory=build_fake_provider_factory(response),
        provider_info={"provider_id": FAKE_PROVIDER_ID, "model": FAKE_MODEL},
        provider_availability="CONFIGURED",
    )


def build_transport(**app_kwargs) -> ReactTransport:
    app = build_app(**app_kwargs)
    adapter = CharacterLabServiceAdapter(app)
    return ReactTransport(adapter)


class ReactCharacterLabServer:
    """Loopback-only HTTP server wrapping a :class:`ReactTransport`."""

    def __init__(self, transport: ReactTransport, bind: str = BIND_HOST, port: int = DEFAULT_PORT) -> None:
        if bind != "127.0.0.1":
            raise ValueError("ReactCharacterLabServer must bind to 127.0.0.1 only")
        self._transport = transport
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
        return f"http://{self.host}:{self.port}"

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

    # ---------------------------------------------------------------- routes
    def _make_handler(self):
        transport = self._transport
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CharacterLabReact/0.1"

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

            def _call(self, fn) -> None:
                try:
                    self._json(200, fn())
                except ReactTransportError as exc:
                    self._json(exc.status, exc.to_json())

            def _route(self, method: str, path: str, body: dict) -> None:
                parts = [p for p in path.split("/") if p]

                if method == "GET" and parts == ["health"]:
                    self._json(200, {"status": "ready", "provider": "fake"})
                    return

                if method == "GET" and parts[:2] == ["api", "characters"]:
                    if len(parts) == 2:
                        return self._call(transport.list_characters)
                    character_id = urllib.parse.unquote(parts[2])
                    if len(parts) == 3:
                        return self._call(lambda: transport.get_character(character_id))
                    if len(parts) == 4 and parts[3] == "variants":
                        return self._call(lambda: transport.list_variants(character_id))
                    if len(parts) == 4 and parts[3] == "capabilities":
                        return self._call(lambda: transport.capabilities(character_id))

                elif method == "GET" and parts[:2] == ["api", "workspaces"]:
                    if len(parts) == 2:
                        return self._call(transport.list_workspaces)
                    workspace_id = urllib.parse.unquote(parts[2])
                    if len(parts) == 3:
                        return self._call(lambda: transport.get_workspace(workspace_id))
                    if len(parts) == 4 and parts[3] == "memory":
                        return self._call(lambda: transport.get_memory(workspace_id))
                    if len(parts) == 5 and parts[3] == "memory" and parts[4] == "events":
                        return self._call(lambda: transport.list_memory_events(workspace_id))
                    if len(parts) == 5 and parts[3] == "memory" and parts[4] == "candidates":
                        return self._call(lambda: transport.list_memory_promotion_candidates(workspace_id))
                    if len(parts) == 5 and parts[3] == "memory" and parts[4] == "consolidated":
                        return self._call(lambda: transport.list_consolidated_memory(workspace_id))
                    if len(parts) == 4 and parts[3] == "runtime-state":
                        return self._call(lambda: transport.get_runtime_state(workspace_id))

                elif method == "GET" and parts[:2] == ["api", "sessions"] and len(parts) == 3:
                    session_id = urllib.parse.unquote(parts[2])
                    return self._call(lambda: transport.get_session(session_id))

                elif method == "POST" and parts == ["api", "workspaces"]:
                    return self._call(transport.create_test_workspace)

                elif method == "POST" and parts == ["api", "sessions"]:
                    return self._call(lambda: transport.create_session(body))

                elif method == "POST" and parts == ["api", "chat"]:
                    return self._call(lambda: transport.send_message(body))

                elif method == "POST" and parts == ["api", "memory", "candidates"]:
                    return self._call(lambda: transport.propose_memory_promotion(body))

                elif method == "POST" and parts == ["api", "memory", "candidates", "decision"]:
                    return self._call(lambda: transport.decide_memory_promotion(body))

                elif method == "POST" and parts == ["api", "memory", "relations"]:
                    return self._call(lambda: transport.create_consolidated_memory_relation(body))

                elif method == "POST" and parts == ["api", "runtime-state", "set"]:
                    return self._call(lambda: transport.set_runtime_state(body))

                elif method == "POST" and parts == ["api", "runtime-state", "adjust"]:
                    return self._call(lambda: transport.adjust_runtime_state(body))

                elif method == "POST" and parts == ["api", "runtime-state", "remove"]:
                    return self._call(lambda: transport.remove_runtime_state(body))

                elif method == "POST" and parts == ["shutdown"]:
                    self._json(200, {"status": "shutting_down"})
                    threading.Thread(target=server_ref.shutdown, daemon=True).start()
                    return

                self._json(404, {"error": {"code": "not_found", "message": "Not found."}})

            def do_GET(self) -> None:
                raw = self.path.split("?", 1)
                self._route("GET", raw[0], {})

            def do_POST(self) -> None:
                path = self.path.split("?", 1)[0]
                body = self._read_json()
                self._route("POST", path, body)

        return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="React Character Lab desktop integration v1 server (127.0.0.1 only, fake provider only)"
    )
    parser.add_argument("--host", default=BIND_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--port-file", default=None, help="write the bound port to this file")
    args = parser.parse_args(argv)

    if args.host != "127.0.0.1":
        parser.error("--host must be 127.0.0.1 (loopback only)")

    transport = build_transport()
    server = ReactCharacterLabServer(transport, bind=args.host, port=args.port)
    if args.port_file:
        Path(args.port_file).write_text(str(server.port), encoding="utf-8")

    print(f"React Character Lab desktop integration v1 server: {server.base_url}", flush=True)
    print("Provider: FAKE ONLY -- no live provider call is authorized in this slice.", flush=True)

    thread = server.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
