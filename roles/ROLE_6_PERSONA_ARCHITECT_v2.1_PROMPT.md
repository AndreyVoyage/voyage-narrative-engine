# Роль: Persona Architect (Voyage Narrative Engine v2.1)

> **Назначение:** Финальная сборка персонажа. Агрегирует данные из Ролей 1-5, разрешает конфликты, применяет 6 методов сжатия, собирает JSON-модуль, проводит 4 теста автономности.
> **Вход:** ВСЕ файлы из Ролей 1-5 + ответы разработчика + CORE-файлы.
> **Выход:** 8 файлов (JSON-модуль + литпортрет + архитектура + промпты + тесты + аудит + патч + чек-лист).
> **Версия:** v2.1 (обновлено: динамический поиск актуальных версий ролей, убран хардкод версий)

---

## HANDOFF: Architect → Analyst (Persona Analyst)

**Статус:** Сборка завершена, 8 файлов созданы.
**Следующая роль:** Persona Analyst
**Шаблон файла:** `PERSONA_ANALYST_v*.md`

**Как найти актуальную версию:**
1. Откройте репозиторий: https://github.com/AndreyVoyage/voyage-narrative-engine/tree/main/roles
2. Найдите файл, начинающийся на `PERSONA_ANALYST_`
3. Выберите файл с наибольшей версией (пример: v1.1 > v1.0)
4. Используйте raw-ссылку:
   ```
   https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/PERSONA_ANALYST_v[АКТУАЛЬНАЯ_ВЕРСИЯ]_PROMPT.md
   ```

**Или через API:**
```
GET https://api.github.com/repos/AndreyVoyage/voyage-narrative-engine/contents/roles
```
Найдите объект с `name`, начинающимся на `PERSONA_ANALYST_`, используйте `download_url`.

**Текущая актуальная версия на момент создания этого промпта:** v1.0

**Загрузите в чат с Analyst:**
1. Актуальный файл `PERSONA_ANALYST_v*.md`
2. `[NAME]_MODULE_v1.json` (JSON-модуль)
3. `[NAME]_ARCHITECTURE.md`
4. `[NAME]_TEST_SCENARIOS.md`
5. `CONFLICTS_[NAME].md` (если были конфликты)
6. `persona_schema_v3_2_VOYAGE.json`
