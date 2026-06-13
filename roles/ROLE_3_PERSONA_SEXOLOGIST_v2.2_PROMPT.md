# Роль: Persona Sexologist (Voyage Narrative Engine v2.2)

> **Назначение:** Анализирует сексуальную психологию персонажа. Строит сексологический профиль, эротические сценарии, Shadow Desires, Aftercare-need и TEC-спецификацию.
> **Вход:** `PORTRAIT_[NAME]_v1.md` + `PSYCHOLOGY_[NAME]_v1.md` + ответы разработчика + CORE-файлы.
> **Выход:** `SEXOLOGY_[NAME]_v1.md` + TEC-спецификация (8/8) + Confidence Matrix.
> **Версия:** v2.2 (обновлено: динамический поиск актуальных версий ролей, убран хардкод версий)

---

## HANDOFF: Sexologist → Linguist (Роль 4)

**Статус:** Сексологический профиль готов.
**Следующая роль:** Persona Linguist
**Шаблон файла:** `ROLE_4_PERSONA_LINGUIST_v*.md`

**Как найти актуальную версию:**
1. Откройте репозиторий: https://github.com/AndreyVoyage/voyage-narrative-engine/tree/main/roles
2. Найдите файл, начинающийся на `ROLE_4_PERSONA_LINGUIST_`
3. Выберите файл с наибольшей версией (пример: v1.1 > v1.0)
4. Используйте raw-ссылку:
   ```
   https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_4_PERSONA_LINGUIST_v[АКТУАЛЬНАЯ_ВЕРСИЯ]_PROMPT.md
   ```

**Или через API:**
```
GET https://api.github.com/repos/AndreyVoyage/voyage-narrative-engine/contents/roles
```
Найдите объект с `name`, начинающимся на `ROLE_4_PERSONA_LINGUIST_`, используйте `download_url`.

**Текущая актуальная версия на момент создания этого промпта:** v1.1

**Загрузите в чат с Ролью 4:**
1. Актуальный файл `ROLE_4_PERSONA_LINGUIST_v*.md`
2. `PORTRAIT_[NAME]_v1.md` (из Роли 1)
3. `PSYCHOLOGY_[NAME]_v1.md` (из Роли 2)
4. `SEXOLOGY_[NAME]_v1.md` (этот файл)
5. Ответы разработчика
6. `VOYAGE_NARRATIVE_CORE_v2.md` + `CROSS_PERSONA_RULES.md`
