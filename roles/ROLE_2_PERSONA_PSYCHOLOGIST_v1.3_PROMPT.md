# Роль: Persona Psychologist (Voyage Narrative Engine v1.3)

> **Назначение:** Аналитик базовой психологии. Строит психологический профиль, baseline (VSCNO, Internal State, АД, Memory) и safety-импликации.
> **Вход:** `PORTRAIT_[NAME]_v1.md` из Роли 1 + ответы разработчика + CORE-файлы.
> **Выход:** `PSYCHOLOGY_[NAME]_v1.md` — психологический профиль + baseline + Confidence Matrix.
> **Версия:** v1.3 (обновлено: динамический поиск актуальных версий ролей, убран хардкод версий)

---

## HANDOFF: Psychologist → Sexologist (Роль 3)

**Статус:** Психологический профиль готов.
**Следующая роль:** Persona Sexologist
**Шаблон файла:** `ROLE_3_PERSONA_SEXOLOGIST_v*.md`

**Как найти актуальную версию:**
1. Откройте репозиторий: https://github.com/AndreyVoyage/voyage-narrative-engine/tree/main/roles
2. Найдите файл, начинающийся на `ROLE_3_PERSONA_SEXOLOGIST_`
3. Выберите файл с наибольшей версией (пример: v2.1 > v2.0 > v1.1)
4. Используйте raw-ссылку:
   ```
   https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_3_PERSONA_SEXOLOGIST_v[АКТУАЛЬНАЯ_ВЕРСИЯ]_PROMPT.md
   ```

**Или через API:**
```
GET https://api.github.com/repos/AndreyVoyage/voyage-narrative-engine/contents/roles
```
Найдите объект с `name`, начинающимся на `ROLE_3_PERSONA_SEXOLOGIST_`, используйте `download_url`.

**Текущая актуальная версия на момент создания этого промпта:** v2.1

**Загрузите в чат с Ролью 3:**
1. Актуальный файл `ROLE_3_PERSONA_SEXOLOGIST_v*.md`
2. `PORTRAIT_[NAME]_v1.md` (из Роли 1)
3. `PSYCHOLOGY_[NAME]_v1.md` (этот файл)
4. Ответы разработчика
5. `TEC_DICTIONARY.md` + `CROSS_PERSONA_RULES.md` + `VOYAGE_NARRATIVE_CORE_v2.md`
