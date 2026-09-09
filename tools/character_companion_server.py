#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Companion local server (loopback only, fake provider only).

Deliberately a SEPARATE, tiny process from the Character Lab React server
(``tools/character_lab_react_server.py``) -- Companion is a separate client and
must not share Lab's route table, debug surface, or data root. It is NOT a new
architecture: identical stdlib ``http.server`` framing, the same
transport-adapter dependency direction, the same deterministic network-free
FAKE provider. It exposes ONLY the five Companion endpoints.

    tools/character_companion_server.py   (HTTP framing)
            v
    CompanionTransport                    (JSON dict <-> service)
            v
    CompanionService                      (RuntimeService + Runtime Memory, unchanged)

Never binds anything but 127.0.0.1. Never performs a live provider call.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.character_companion import (  # noqa: E402
    CompanionService,
    CompanionTransport,
    LocalLLMConfig,
    RoleAssignment,
    ROLE_DIALOGUE,
    SettingsStore,
    build_default_credential_vault,
    resolve_companion_provider_factory,
)
from services.character_companion.image_jobs import (  # noqa: E402
    FakeImageGenerator,
    UnavailableImageGenerator,
)
from services.character_companion.local_provider import (  # noqa: E402
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_LOCAL_MODEL,
)
from services.character_companion.transport import CompanionTransportError  # noqa: E402

BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8788  # Lab React server uses 8787; keep distinct
FAKE_PROVIDER_ID = "fake"
FAKE_MODEL = "fake-companion-mvp-v1"
DEFAULT_FAKE_REPLY = "Это детерминированный тестовый ответ (fake provider)."


def build_fake_provider_factory(response: str = DEFAULT_FAKE_REPLY):
    def factory(recorder):
        def provider(messages):
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake-companion", "model": "fake",
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def build_transport(
    *,
    data_root,
    acceptance_root=None,
    response: str = DEFAULT_FAKE_REPLY,
    env: Optional[dict] = None,
    credential_vault=None,
    mode: str = "dev",
) -> CompanionTransport:
    """Compose the Companion service with secure provider configuration.

    The DIALOGUE provider is chosen from persisted settings (``companion_settings.json``,
    no secrets) + the credential vault. Legacy ``COMPANION_PROVIDER`` env
    (``fake`` default | ``local``) seeds the DIALOGUE role on first start so
    existing local integration keeps working. There is no cloud mode env and no
    automatic fallback."""
    repo_root = Path(__file__).resolve().parents[1]
    env = env if env is not None else dict(os.environ)
    data_root = Path(data_root)
    data_root.mkdir(parents=True, exist_ok=True)

    settings_store = SettingsStore(data_root)
    provider_env = (env.get("COMPANION_PROVIDER") or "").strip().lower()
    if provider_env == "local":
        # legacy env path: env is authoritative and re-applied every start.
        cfg = LocalLLMConfig.from_env(env)
        seeded = settings_store.load()
        seeded.roles[ROLE_DIALOGUE] = RoleAssignment("local", cfg.model)
        seeded.local_num_ctx = cfg.num_ctx
        if cfg.base_url:
            seeded.base_urls["local"] = cfg.base_url
        settings_store.save(seeded)
    elif not settings_store.path.exists():
        # default first start -> DIALOGUE = fake; thereafter persisted settings win.
        seeded = settings_store.load()
        seeded.roles[ROLE_DIALOGUE] = RoleAssignment("fake", "fake")
        settings_store.save(seeded)

    vault = credential_vault
    if vault is None:
        try:
            vault = build_default_credential_vault(data_root)
        except Exception:  # noqa: BLE001 -- platform without a secure store
            vault = None

    gen_mode = (env.get("COMPANION_IMAGE_GENERATOR") or "fake").strip().lower()
    image_generator = FakeImageGenerator() if gen_mode == "fake" else UnavailableImageGenerator()

    service = CompanionService(
        acceptance_root=acceptance_root or (repo_root / "accepted"),
        data_root=data_root,
        provider_factory=build_fake_provider_factory(response),
        provider_info={"provider_id": FAKE_PROVIDER_ID, "model": FAKE_MODEL},
        image_generator=image_generator,
        settings_store=settings_store,
        credential_vault=vault,
        mode=mode,
    )
    return CompanionTransport(service)


class CompanionServer:
    """Loopback-only HTTP server wrapping a :class:`CompanionTransport`."""

    def __init__(self, transport: CompanionTransport, bind: str = BIND_HOST,
                 port: int = DEFAULT_PORT, web_root: Optional[Path] = None) -> None:
        if bind != "127.0.0.1":
            raise ValueError("CompanionServer must bind to 127.0.0.1 only")
        self._transport = transport
        self._web_root = Path(web_root).resolve() if web_root else None
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
        thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
        )
        thread.start()
        self._thread = thread
        return thread

    def shutdown(self) -> None:
        try:
            self._httpd.shutdown()
        finally:
            self._httpd.server_close()

    def _make_handler(self):
        transport = self._transport
        service = transport._service  # noqa: SLF001 -- same-process loopback image serving
        web_root = self._web_root

        class Handler(BaseHTTPRequestHandler):
            server_version = "CharacterCompanion/0.1"

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
                except CompanionTransportError as exc:
                    self._json(exc.status, exc.to_json())

            def _route(self, method: str, path: str, body: dict) -> None:
                parts = [p for p in path.split("/") if p]

                if method == "GET" and parts == ["health"]:
                    self._json(200, {"status": "ready", "client": "companion",
                                     "mode": getattr(service, "mode", "dev")})
                    return
                if method == "GET" and parts == ["api", "companion", "release"]:
                    return self._call(transport.get_release_info)
                if method == "GET" and parts == ["api", "companion", "characters"]:
                    return self._call(transport.list_characters)
                if method == "GET" and parts[:3] == ["api", "companion", "characters"] and len(parts) == 5 \
                        and parts[4] == "sessions":
                    character_id = urllib.parse.unquote(parts[3])
                    return self._call(lambda: transport.list_sessions(character_id))
                if method == "POST" and parts == ["api", "companion", "sessions"]:
                    return self._call(lambda: transport.create_session(body))
                if method == "GET" and parts[:3] == ["api", "companion", "sessions"] and len(parts) == 4:
                    return self._call(lambda: transport.get_session(urllib.parse.unquote(parts[3])))
                if method == "GET" and parts[:3] == ["api", "companion", "sessions"] and len(parts) == 5 \
                        and parts[4] == "messages":
                    session_id = urllib.parse.unquote(parts[3])
                    return self._call(lambda: transport.get_messages(session_id))
                if method == "GET" and parts[:3] == ["api", "companion", "sessions"] and len(parts) == 5 \
                        and parts[4] == "images":
                    session_id = urllib.parse.unquote(parts[3])
                    return self._call(lambda: transport.list_image_jobs(session_id))
                if method == "POST" and parts == ["api", "companion", "messages"]:
                    return self._call(lambda: transport.send_message(body))
                if method == "POST" and parts == ["api", "companion", "scenario"]:
                    return self._call(lambda: transport.random_scenario(body))
                if method == "POST" and parts == ["api", "companion", "sessions", "cover"]:
                    return self._call(lambda: transport.set_scene_cover(body))
                if method == "POST" and parts == ["api", "companion", "images"]:
                    return self._call(lambda: transport.create_image_job(body))
                if method == "POST" and parts == ["api", "companion", "images", "delete"]:
                    return self._call(lambda: transport.delete_image_job(body))
                if method == "GET" and parts[:3] == ["api", "companion", "images"] and len(parts) == 4:
                    return self._call(lambda: transport.get_image_job(urllib.parse.unquote(parts[3])))
                if method == "GET" and parts[:3] == ["api", "companion", "image-file"] and len(parts) >= 4:
                    return self._serve_image(urllib.parse.unquote("/".join(parts[3:])))

                # ---- provider settings (no raw-secret GET anywhere) ----
                if method == "GET" and parts == ["api", "companion", "settings"]:
                    return self._call(transport.get_settings)
                if method == "POST" and parts == ["api", "companion", "settings", "roles"]:
                    return self._call(lambda: transport.set_role(body))
                if method == "POST" and parts == ["api", "companion", "settings", "local"]:
                    return self._call(lambda: transport.set_local_settings(body))
                if method == "POST" and parts == ["api", "companion", "settings", "credentials"]:
                    return self._call(lambda: transport.store_credential(body))
                if method == "DELETE" and parts[:4] == ["api", "companion", "settings", "credentials"] and len(parts) == 5:
                    return self._call(lambda: transport.delete_credential(urllib.parse.unquote(parts[4])))
                if method == "POST" and parts == ["api", "companion", "settings", "test"]:
                    return self._call(lambda: transport.test_provider(body))
                if method == "GET" and parts[:4] == ["api", "companion", "settings", "resolve"] and len(parts) == 5:
                    return self._call(lambda: transport.resolve_role(urllib.parse.unquote(parts[4])))

                # static SPA (release mode): anything not an /api or /health route
                if method == "GET" and web_root is not None and (not parts or parts[0] not in ("api",)):
                    return self._serve_static("/".join(parts))

                self._json(404, {"error": {"code": "not_found", "message": "unknown route"}})

            def _serve_static(self, rel: str) -> None:
                rel = rel.strip("/")
                candidate = (web_root / rel).resolve() if rel else (web_root / "index.html")
                # path-traversal guard + SPA fallback to index.html
                if web_root not in candidate.parents and candidate != web_root / "index.html" \
                        and not str(candidate).startswith(str(web_root)):
                    candidate = web_root / "index.html"
                if candidate.is_dir():
                    candidate = candidate / "index.html"
                if not candidate.is_file():
                    candidate = web_root / "index.html"
                if not candidate.is_file():
                    self._json(404, {"error": {"code": "not_built", "message": "frontend build not found"}})
                    return
                ctype = {
                    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
                    ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2",
                    ".ico": "image/x-icon", ".map": "application/json",
                }.get(candidate.suffix, "application/octet-stream")
                raw = candidate.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _serve_image(self, result_ref: str) -> None:
                # loopback-only, generated-image serving. Fail closed on any ref
                # that is not exactly a file under <data_root>/images/.
                if not result_ref.startswith("images/") or ".." in result_ref or "\\" in result_ref:
                    self._json(400, {"error": {"code": "invalid_request", "message": "bad ref"}})
                    return
                images_root = (service._data_root / "images").resolve()  # noqa: SLF001
                path = (service._data_root / result_ref).resolve()       # noqa: SLF001
                if images_root not in path.parents or not path.is_file():
                    self._json(404, {"error": {"code": "not_found", "message": "image not found"}})
                    return
                raw = path.read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "image/svg+xml" if path.suffix == ".svg" else "application/octet-stream",
                )
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                self._route("GET", self.path.split("?", 1)[0], {})

            def do_POST(self) -> None:
                self._route("POST", self.path.split("?", 1)[0], self._read_json())

            def do_DELETE(self) -> None:
                self._route("DELETE", self.path.split("?", 1)[0], {})

        return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Character Companion local server (127.0.0.1 only)"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="0 = ephemeral")
    parser.add_argument("--port-file", default=None, help="write the bound port here")
    parser.add_argument("--data-root", required=True, help="durable Companion data root")
    parser.add_argument("--web-root", default=None, help="serve the built Companion SPA from here")
    parser.add_argument("--mode", default="dev", choices=["dev", "release"])
    parser.add_argument("--reply", default=DEFAULT_FAKE_REPLY)
    args = parser.parse_args(argv)

    web_root = Path(args.web_root) if args.web_root else None
    if web_root is not None and not (web_root / "index.html").is_file():
        print(f"[character_companion_server] ERROR: no built frontend at {web_root} "
              f"(run tools/build_character_companion_release.ps1)")
        return 2

    transport = build_transport(data_root=Path(args.data_root), response=args.reply, mode=args.mode)
    server = CompanionServer(transport, port=args.port, web_root=web_root)
    if args.port_file:
        Path(args.port_file).write_text(str(server.port), encoding="utf-8")
    served = "SPA + /api" if web_root else "/api only"
    print(f"[character_companion_server] listening on {server.base_url} (mode={args.mode}, {served})")
    server.start()
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
