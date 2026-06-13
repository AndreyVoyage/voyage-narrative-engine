# Роль: Persona Linguist (Voyage Narrative Engine v1.2)

> **Назначение:** Строит речевой профиль персонажа: лексика, темп, интонация, манера речи по всем 14 подуровням.
> **Вход:** `PORTRAIT_[NAME]_v1.md` + `PSYCHOLOGY_[NAME]_v1.md` + `SEXOLOGY_[NAME]_v1.md` + ответы + CORE.
> **Выход:** `LINGUISTICS_[NAME]_v1.md` — Speech Profile Matrix + примеры диалогов + код-переключение.
> **Версия:** v1.2 (обновлено: динамический поиск актуальных версий ролей, убран хардкод версий)

---

## HANDOFF: Linguist → Physiognomist (Роль 5)

**Статус:** Речевой профиль готов.
**Следующая роль:** Persona Physiognomist
**Шаблон файла:** `ROLE_5_PERSONA_PHYSIOGNOMIST_v*.md`

**Как найти актуальную версию:**
1. Откройте репозиторий: https://github.com/AndreyVoyage/voyage-narrative-engine/tree/main/roles
2. Найдите файл, начинающийся на `ROLE_5_PERSONA_PHYSIOGNOMIST_`
3. Выберите файл с наибольшей версией (пример: v1.1 > v1.0)
4. Используйте raw-ссылку:
   ```
   https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_5_PERSONA_PHYSIOGNOMIST_v[АКТУАЛЬНАЯ_ВЕРСИЯ]_PROMPT.md
   ```

**Или через API:**
```
GET https://api.github.com/repos/AndreyVoyage/voyage-narrative-engine/contents/roles
```
Найдите объект с `name`, начинающимся на `ROLE_5_PERSONA_PHYSIOGNOMIST_`, используйте `download_url`.

**Текущая актуальная версия на момент создания этого промпта:** v1.1

**Загрузите в чат с Ролью 5:**
1. Актуальный файл `ROLE_5_PERSONA_PHYSIOGNOMIST_v*.md`
2. `PORTRAIT_[NAME]_v1.md` (из Роли 1)
3. `PSYCHOLOGY_[NAME]_v1.md` (из Роли 2)
4. `SEXOLOGY_[NAME]_v1.md` (из Роли 3)
5. `LINGUISTICS_[NAME]_v1.md` (этот файл)
6. `VOYAGE_NARRATIVE_CORE_v2.md` + `QWEN_ADAPTER_v2.md` (если есть)
