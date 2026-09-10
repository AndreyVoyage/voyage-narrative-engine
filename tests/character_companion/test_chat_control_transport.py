#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHAT CONTROL AND COMPOSER ASSISTANT V1 -- loopback HTTP.

Real Companion server on 127.0.0.1 through the fake provider. Proves the
writing-assistant rewrite endpoint, chat rename, and presentation hide/restore
for chats and messages survive a reload, create no conversation event, and
never leak a secret. No external network.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

KEY = "sk-chat-control-loopback-SECRET-777888"


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _http(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_loopback_chat_control_and_writing_assistant(tmp_path):
    from services.character_companion import InMemoryCredentialVault
    from tools.character_companion_server import CompanionServer, build_transport

    data_root = tmp_path / "cd"
    vault = InMemoryCredentialVault()

    def make_server():
        return CompanionServer(
            build_transport(data_root=data_root, env={"COMPANION_PROVIDER": "fake"}, credential_vault=vault),
            port=_free_port(),
        )

    server = make_server()
    server.start()
    try:
        b = server.base_url

        # WRITING_ASSISTANT is in the role catalog, not runtime-wired
        _, view = _http(b, "GET", "/api/companion/settings")
        wa = next(r for r in view["roleCatalog"] if r["role"] == "WRITING_ASSISTANT")
        assert wa["runtimeWired"] is False

        # V2A: the co-author executes on the DIALOGUE assignment. No separate
        # WRITING_ASSISTANT assignment is required, and there is no
        # assistant_not_configured gate based on its absence. Here DIALOGUE is
        # the default fake provider, so a non-empty draft rewrites straight away.
        st, res = _http(b, "POST", "/api/companion/writing-assistant/rewrite",
                        {"draft": "прив я сегодня устал давай просто поговорим"})
        assert st == 200 and isinstance(res["suggestion"], str) and res["suggestion"].strip()

        # storing a WRITING_ASSISTANT assignment neither is required nor changes
        # execution (no auto-fallback semantics introduced).
        _http(b, "POST", "/api/companion/settings/roles",
              {"role": "WRITING_ASSISTANT", "providerId": "fake", "modelId": "fake"})
        st, res = _http(b, "POST", "/api/companion/writing-assistant/rewrite",
                        {"draft": "ещё один черновик для доработки"})
        assert st == 200 and isinstance(res["suggestion"], str) and res["suggestion"].strip()

        # legacy /rewrite still rejects an empty draft; the new /suggest endpoint
        # accepts it and derives COMPOSE.
        st, err = _http(b, "POST", "/api/companion/writing-assistant/rewrite", {"draft": "   "})
        assert st == 400 and err["error"]["code"] == "invalid_draft"
        st, sug = _http(b, "POST", "/api/companion/writing-assistant/suggest", {"draft": ""})
        assert st == 200 and isinstance(sug["suggestion"], str) and sug["suggestion"].strip()

        # a session with real history
        _, session = _http(b, "POST", "/api/companion/sessions", {"characterId": "kira", "title": "RC"})
        sid = session["sessionId"]
        _http(b, "POST", "/api/companion/messages", {"sessionId": sid, "text": "первое"})
        _, before = _http(b, "GET", f"/api/companion/sessions/{sid}/messages")
        assert len(before["messages"]) == 2

        # rewrite again -> STILL no conversation event created
        _http(b, "POST", "/api/companion/writing-assistant/rewrite", {"draft": "ещё черновик"})
        _, after = _http(b, "GET", f"/api/companion/sessions/{sid}/messages")
        assert after["messages"] == before["messages"]

        # rename
        _, r = _http(b, "POST", "/api/companion/sessions/rename", {"sessionId": sid, "title": "Мой вечер"})
        assert r["titleOverride"] == "Мой вечер"

        # hide + restore a message
        seq = before["messages"][0]["seq"]
        _, h = _http(b, "POST", "/api/companion/messages/visibility",
                     {"sessionId": sid, "messageId": seq, "hidden": True})
        assert seq in h["hiddenMessageIds"]
        _, uh = _http(b, "POST", "/api/companion/messages/visibility",
                      {"sessionId": sid, "messageId": seq, "hidden": False})
        assert seq not in uh["hiddenMessageIds"]
        # hide it again so we can check persistence
        _http(b, "POST", "/api/companion/messages/visibility",
              {"sessionId": sid, "messageId": seq, "hidden": True})

        # hide the chat
        _, hc = _http(b, "POST", "/api/companion/sessions/visibility", {"sessionId": sid, "hidden": True})
        assert hc["hidden"] is True

        # no secret anywhere
        _http(b, "POST", "/api/companion/settings/credentials", {"providerId": "openai", "secret": KEY})
        _, v2 = _http(b, "GET", "/api/companion/settings")
        assert KEY not in json.dumps(v2)
    finally:
        server.shutdown()

    # ---- reload: presentation state persists, history intact ----
    server2 = make_server()
    server2.start()
    try:
        b = server2.base_url
        _, sessions = _http(b, "GET", "/api/companion/characters/kira/sessions")
        row = next(s for s in sessions["sessions"] if s["sessionId"] == sid)
        assert row["hidden"] is True
        assert row["titleOverride"] == "Мой вечер"
        assert seq in row["hiddenMessageIds"]
        _, msgs = _http(b, "GET", f"/api/companion/sessions/{sid}/messages")
        assert len(msgs["messages"]) == 2          # nothing was deleted

        # restore the chat
        _, rc = _http(b, "POST", "/api/companion/sessions/visibility", {"sessionId": sid, "hidden": False})
        assert rc["hidden"] is False
    finally:
        server2.shutdown()
