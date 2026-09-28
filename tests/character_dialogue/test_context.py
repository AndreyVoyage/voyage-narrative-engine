"""Offline tests for the persona-context renderer."""

from __future__ import annotations

from services.character_dialogue.context import display_name, persona_context

from tests.character_dialogue._helpers import make_semantic


def test_identity_included():
    context = persona_context(make_semantic())
    assert "Имя: Марина" in context
    assert "Сдержанная и наблюдательная." in context
    assert "Врач тридцати лет из приморского города." in context


def test_biography_included_verbatim():
    context = persona_context(make_semantic())
    assert "Выросла у моря, давно работает врачом." in context


def test_psychology_included():
    context = persona_context(make_semantic())
    assert "сдержанная, наблюдательная" in context
    assert "методичная" in context


def test_speech_included():
    context = persona_context(make_semantic())
    assert "кратко и по делу" in context
    assert "нейтральный" in context


def test_relationships_included():
    context = persona_context(make_semantic())
    assert "кооперативная" in context
    assert "надежная" in context


def test_boundaries_included():
    context = persona_context(make_semantic())
    assert "не любит фамильярность" in context


def test_appearance_included_as_text():
    context = persona_context(make_semantic())
    assert "тёмные волосы" in context


def test_sexology_included_when_present():
    semantic = make_semantic(
        sexology={
            "intimacy_attitudes": ["нежная"],
            "preferences": ["медленно"],
            "emotional_dynamics": ["доверие"],
            "communication": ["словами"],
            "vulnerabilities": ["отвержение"],
            "intimacy_boundaries": ["без принуждения"],
        }
    )
    context = persona_context(semantic)
    assert "нежная" in context
    assert "без принуждения" in context
    assert "базовые авторские установки" in context


def test_absent_sexology_works():
    context = persona_context(make_semantic())
    assert "Сексология" not in context


def test_visual_identity_never_rendered():
    context = persona_context(make_semantic(visual_identity={"photo": "/tmp/x.png"}))
    assert "visual_identity" not in context
    assert "/tmp/x.png" not in context
    assert "photo" not in context


def test_display_name_fallback():
    assert display_name(make_semantic()) == "Марина"
    semantic = make_semantic()
    semantic["identity"]["display_name"] = ""
    assert display_name(semantic) == "Персонаж"
