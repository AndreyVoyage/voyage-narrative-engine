# KB_S7_CORE.md
# Knowledge Base: Роль S7 — Scenario Refactor
# Назначение: Сжать сценарий для runtime (200K токенов)
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S7

**Роль:** Компрессор. Сжимает Scenario Module до 40–50% для runtime.

**Аналог:** R7 для персонажей (компрессия в 3 слоя: BASE + STATE + LIVE).

---

## 2. МЕТОДЫ КОМПРЕССИИ

### 2.1 Linear Table (для сцен)
```
Scene | Location | Level | VSCNO | Key Choice | Visual
------|----------|-------|-------|------------|--------
S001  | bar      | U1-A  | 3/3/1/3 | approach/look | dim, warm
S002  | bar      | U2-A  | 4/2/2/2 | flirt/withdraw | spotlight
S006  | bar      | U4-A  | 3/2/3/2 | kiss/pull_back | Rembrandt
```

### 2.2 Base + Delta (для сцен)
- **Base:** Сцена S001 (полная)
- **Delta S002:** Δlocation=0, Δlevel=+1, ΔВЛ=+1, ΔСТ=-1, Δvisual=spotlight
- **Delta S006:** Δlocation=0, Δlevel=+3, ΔВЛ=0, ΔСТ=-1, Δvisual=Rembrandt

### 2.3 Glossary (для терминов)
- «ФМДР» → «Ф» (в таблице)
- «aftercare» → «А» (в таблице)
- «safety checkpoint» → «С» (в таблице)

### 2.4 Scene Folding (для рантайма)
- **Full scene:** Сцена с ФМДР (500 слов) — только текущая сцена
- **Compact scene:** Header + choices + vscno (50 слов) — остальные сцены
- **Collapsed scene:** ID + level + vscno (10 слов) — далёкие сцены

---

## 3. РАНТАЙМ СТРУКТУРА

### 3.1 SCENARIO_RUNTIME.md (3 слоя)
```markdown
# SCENARIO_RUNTIME: bar_encounter_andrey

## LAYER 1: BASE (система)
- VSCNO правила, AD коды, ФМДР формат
- Safety protocols
- ~10 KB

## LAYER 2: STATE (текущий прогресс)
- Current scene: S002
- Current level: U2-A
- VSCNO: 4/2/2/2
- Memory: [trust=5, flags={S001_approached}]
- ~2 KB

## LAYER 3: LIVE (активная сцена)
- S002 Full (ФМДР, 500 слов)
- S003 Compact (header, 50 слов)
- S001 Collapsed (ID, 10 слов)
- ~20 KB

## Total: ~32 KB (well within 200K)
```

---

## 4. ЧЕК-ЛИСТ КОМПРЕССИИ

```
□ Размер сжат до 40–50% оригинала
□ BASE layer содержит системные правила
□ STATE layer содержит текущий прогресс
□ LIVE layer содержит текущую сцену (full) + ближайшие (compact)
□ Далёкие сцены collapsed (ID + level)
□ Все choices сохранены (текст + branch)
□ Safety checkpoints сохранены
□ Aftercare notes сохранены
□ VSCNO target для каждой сцены сохранён
```

---

## 5. ВЫХОД ДЛЯ S8

```json
{
  "compressed_scenario": {
    "original_size": "120 KB",
    "compressed_size": "55 KB",
    "compression_ratio": 0.46,
    "layers": ["BASE", "STATE", "LIVE"],
    "next_step": "S8 Auditor (validation)"
  }
}
```

---

*KB_S7_CORE.md | Voyage Narrative Engine | 2026-06-18*
