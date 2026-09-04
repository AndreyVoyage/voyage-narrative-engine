#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static frontend + launcher-argument checks (offline, no browser)."""

from __future__ import annotations

from pathlib import Path

import character_lab_server as server_mod
from services.character_lab import CharacterLabApp

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = _REPO_ROOT / "services" / "character_lab" / "web"


def _read(name):
    return (WEB_DIR / name).read_text(encoding="utf-8")


class TestAppModeArguments:
    def test_app_mode_url(self):
        assert server_mod.app_mode_url("127.0.0.1", 1234) == "http://127.0.0.1:1234"

    def test_app_mode_argument_uses_app_flag(self):
        assert server_mod.app_mode_argument("127.0.0.1", 1234) == ["--app=http://127.0.0.1:1234"]

    def test_launcher_script_uses_app_flag(self):
        ps1 = (_REPO_ROOT / "tools" / "start_character_lab.ps1").read_text(encoding="utf-8")
        assert "--app=" in ps1


class TestStaticFrontend:
    def test_three_column_layout(self):
        html = _read("index.html")
        assert "left-panel" in html
        assert "center-panel" in html
        assert "right-panel" in html

    def test_russian_labels_and_controls(self):
        html = _read("index.html")
        for token in (
            "Character Lab",
            "Персонажи",
            "Варианты",
            "Сессии",
            "Новая сессия",
            "Написать сообщение",
            "Загруженное состояние",
            "Отладка ходов",
        ):
            assert token in html, token

    def test_kira_and_variant_appear(self):
        html = _read("index.html")
        assert "KIRA" in html
        assert "Beta v1 — Current" in html

    def test_modes_character_and_turn_debugger(self):
        js = _read("app.js")
        assert "character" in js
        assert "turns" in js
        html = _read("index.html")
        assert "Персонаж" in html
        assert "Отладка ходов" in html

    def test_scene_and_memory_modes_now_functional(self):
        html = _read("index.html")
        # Slice 3: the two previously deferred modes are enabled (no "· Slice 3"
        # placeholder, buttons are not disabled).
        assert "Сцена · Slice 3" not in html
        assert "Память · Slice 3" not in html
        assert '<button class="mode" data-mode="memory">Память</button>' in html
        assert '<button class="mode" data-mode="scene">Сцена</button>' in html
        js = _read("app.js")
        assert "loadMemory" in js
        assert "loadScene" in js

    def test_workspace_controls_present(self):
        html = _read("index.html")
        for token in ("Рабочая область", "workspace-select", "new-clean-test", "Новый Clean Test"):
            assert token in html, token
        js = _read("app.js")
        assert "LONG-LIVED MEMORY" in js
        assert "CLEAN TEST" in js
        assert "/api/workspace/select" in js
        assert "/api/workspace/new-test" in js

    def test_memory_ui_has_no_fake_metrics(self):
        for name in ("index.html", "app.js", "app.css"):
            text = _read(name).lower()
            for forbidden in ("hallucination", "truth score", "confidence score", "risk:"):
                assert forbidden not in text, (name, forbidden)

    def test_no_external_assets(self):
        for name in ("index.html", "app.css", "app.js"):
            text = _read(name)
            for forbidden in ("cdn", "unpkg", "jsdelivr", "fonts.googleapis", "https://", "http://"):
                assert forbidden not in text, (name, forbidden)

    def test_frontend_has_no_provider_credential_logic(self):
        js = _read("app.js")
        for forbidden in ("api.deepseek.com", "DEEPSEEK_API_KEY", "Bearer", "Authorization", "api_key"):
            assert forbidden not in js, forbidden

    def test_catalog_provides_kira_and_variant(self, tmp_path):
        app = CharacterLabApp(
            acceptance_root=_REPO_ROOT / "accepted",
            data_root=tmp_path / "data",
            provider_availability="NOT CONFIGURED",
        )
        catalog = app.catalog()
        assert any(c["display_name"] == "KIRA" for c in catalog["characters"])
        assert any(v["display_name"] == "Beta v1 — Current" and v["implemented"] for v in catalog["variants"])
