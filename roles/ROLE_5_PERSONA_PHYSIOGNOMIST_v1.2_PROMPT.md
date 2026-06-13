# Роль: Persona Physiognomist (Voyage Narrative Engine v1.2)

> **Назначение:** Строит визуальный профиль персонажа: anatomic_anchor, dynamic_visuals, prompt_base, lighting_map, anti-prompts.
> **Вход:** `PORTRAIT_[NAME]_v1.md` + `PSYCHOLOGY_[NAME]_v1.md` + `SEXOLOGY_[NAME]_v1.md` + `LINGUISTICS_[NAME]_v1.md` + CORE.
> **Выход:** `PHYSIOGNOMY_[NAME]_v1.md` — Anatomic Anchor + Dynamic Visuals + Prompt Base + Lighting Map.
> **Версия:** v1.2 (обновлено: динамический поиск актуальных версий ролей, убран хардкод версий)

---

## HANDOFF: Physiognomist → Architect (Роль 6)

**Статус:** Визуальный профиль готов.
**Следующая роль:** Persona Architect
**Шаблон файла:** `ROLE_6_PERSONA_ARCHITECT_v*.md`

**Как найти актуальную версию:**
1. Откройте репозиторий: https://github.com/AndreyVoyage/voyage-narrative-engine/tree/main/roles
2. Найдите файл, начинающийся на `ROLE_6_PERSONA_ARCHITECT_`
3. Выберите файл с наибольшей версией (пример: v2.0 > v1.0)
4. Используйте raw-ссылку:
   ```
   https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_6_PERSONA_ARCHITECT_v[АКТУАЛЬНАЯ_ВЕРСИЯ]_PROMPT.md
   ```

**Или через API:**
```
GET https://api.github.com/repos/AndreyVoyage/voyage-narrative-engine/contents/roles
```
Найдите объект с `name`, начинающимся на `ROLE_6_PERSONA_ARCHITECT_`, используйте `download_url`.

**Текущая актуальная версия на момент создания этого промпта:** v2.0

**Загрузите в чат с Ролью 6:**
1. Актуальный файл `ROLE_6_PERSONA_ARCHITECT_v*.md`
2. ВСЕ файлы из Ролей 1-5 (`PORTRAIT`, `PSYCHOLOGY`, `SEXOLOGY`, `LINGUISTICS`, `PHYSIOGNOMY`)
3. Ответы разработчика
4. `persona_schema_v3_2_VOYAGE.json` + `VOYAGE_NARRATIVE_CORE_v2.md` + `TEC_DICTIONARY.md` + `AUTONOMY_GOVERNOR_v2.md` + `CROSS_PERSONA_RULES.md` + `PERSONA_ANALYST_v1.0_PROMPT.md`
