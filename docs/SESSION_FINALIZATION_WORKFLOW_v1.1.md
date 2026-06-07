# SESSION FINALIZATION WORKFLOW v1.1
## Voyage Narrative Engine — Порядок действий после сессии

---

## Цель

Превратить сырой лог чата в три артефакта:
1. **STATE_UPDATE.json** — обновление состояния для следующей сессии
2. **STORY_YYYY-MM-DD.md** — литературный рассказ
3. **VISUAL_PROMPTS_YYYY-MM-DD.md** — промпты для иллюстраций

---

## Структура папок (создать в репозитории)

```
voyage-narrative-engine/
├── sessions/
│   ├── raw/                    # Сырые логи (copy-paste из чата)
│   │   └── session_2026-06-08_23-49.log
│   ├── state/                  # Обновления STATE
│   │   └── STATE_UPDATE_2026-06-08_23-49.json
│   ├── memory/                 # Обновления memory модулей
│   │   └── MEMORY_UPDATE_2026-06-08_23-49.json
│   ├── stories/                # Литературные рассказы
│   │   └── STORY_2026-06-08.md
│   └── visuals/                # Промпты для картинок
│       └── VISUAL_PROMPTS_2026-06-08.md
├── personas/                   # Модули персонажей (обновляются из memory/)
│   ├── KIRA_MODULE_v14.json
│   ├── SERGEY_MODULE_v4.json
│   ├── MARINA_MODULE_v2.json
│   └── MAKSIM_MODULE_v2.json
├── state/
│   └── STATE_TEMPLATE_v2.json  # Текущий активный STATE
└── roles/                      # Промпты для ролей
    ├── ROLE_STATE_MANAGER_v1.0_PROMPT.md
    ├── ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md
    └── ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md
```

---

## Шаг 0. Подготовка лога (вручную, сразу после сессии)

1. Откройте чат с сессией.
2. Выделите весь текст (Ctrl+A / Cmd+A).
3. Скопируйте в текстовый файл: `sessions/raw/session_YYYY-MM-DD_HH-MM.log`
4. Сделайте `git add` и `git commit` (сырой лог — ценный артефакт).

---

## Шаг 1. State Manager (техническая роль)

**Где выполнять:** Новый чат с любой LLM (Kimi, Claude, GPT-4 — не важно, нужна точность, не креативность).

**Что загрузить:**
1. `ROLE_STATE_MANAGER_v1.0_PROMPT.md` — как системное сообщение или первым сообщением.
2. `sessions/raw/session_YYYY-MM-DD_HH-MM.log` — приложить файлом.
3. (Опционально) `state/STATE_TEMPLATE_v2.json` — приложить файлом.

**Что получить:**
- `STATE_UPDATE_YYYY-MM-DD.json`
- `MEMORY_UPDATE_YYYY-MM-DD.json`

**Что сделать с результатом:**
- Сохранить в `sessions/state/` и `sessions/memory/`
- Вручную применить `MEMORY_UPDATE` к модулям персонажей (пока нет скрипта):
  - Открыть `personas/KIRA_MODULE_v14.json`
  - Найти блок `memory`
  - Обновить `trust_levels`, `attraction_levels`, `history`, `flags` по данным из MEMORY_UPDATE
  - Сохранить, сделать `git commit`

---

## Шаг 2. Narrative Editor v1.1 (творческая роль)

**Где выполнять:** Новый чат с Kimi / Claude / GPT-4 (нужен длинный контекст и стилистика).

**Что загрузить:**
1. `ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md` — как системное сообщение.
2. `sessions/raw/session_YYYY-MM-DD_HH-MM.log` — приложить файлом.
3. (Опционально) Модули персонажей — для точности голоса и визуальных деталей.

**Что получить:**
- `STORY_YYYY-MM-DD.md` — литературный рассказ.

**Что сделать с результатом:**
- Сохранить в `sessions/stories/`
- Прочитать, при необходимости отредактировать вручную (добавить/убрать детали)
- `git commit`

**Важно:** Если лог >50 реплик — попросите обработать по частям. После первой части напишите «продолжи».

---

## Шаг 3. Visual Extractor (визуальная роль)

**Где выполнять:** Новый чат с Kimi / Qwen (нужно понимание визуальных деталей).

**Что загрузить:**
1. `ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md` — как системное сообщение.
2. `sessions/raw/session_YYYY-MM-DD_HH-MM.log` — приложить файлом.
3. **Обязательно** модули персонажей (для `anatomic_anchor` и `visual_data`).

**Что получить:**
- `VISUAL_PROMPTS_YYYY-MM-DD.md` — 5-10 моментов с 3 вариантами промптов каждый.

**Что сделать с результатом:**
- Сохранить в `sessions/visuals/`
- Выбрать 2-3 момента для генерации (не все — дорого/долго)
- Скопировать промпт в Qwen / Midjourney / Stable Diffusion
- Полученные картинки сохранить в `assets/images/session_YYYY-MM-DD/`
- `git commit`

---

## Шаг 4. Git-фиксация (ручная)

```bash
cd voyage-narrative-engine
git add sessions/
git add personas/  # если обновляли memory
git add assets/images/  # если добавляли картинки
git commit -m "session: 2026-06-08 sauna_quartet, Kira U1-A→U3-A, Marina U1-A→U2-A"
git push origin main
```

---

## Почему 3 отдельных чата, а не 1

| Роль | Требования к LLM | Почему отдельно |
|------|------------------|-----------------|
| **State Manager** | Точность, математика, JSON | Творческий LLM может "приукрасить" цифры или забыть обновить флаг |
| **Narrative Editor** | Длинный контекст, стилистика, литературность | Технический LLM выдаст сухой отчёт вместо рассказа |
| **Visual Extractor** | Визуальное мышление, знание anatomic anchors | Перегрузка контекста, если совмещать с Narrative Editor |

**Если совместить в 1 чат:**
- Контекст переполнится (лог + модули + правила редактуры + правила визуала)
- LLM начнёт путаться: забудет обновить `desire`, или наоборот — сделает сухой отчёт вместо прозы

---

## Быстрый старт (минимальный набор)

Если у вас нет времени на все 3 шага — сделайте **только State Manager** (Шаг 1). Без него следующая сессия начнётся с нуля, и персонажи "забудут" всё.

Narrative Editor и Visual Extractor можно отложить на выходные — они не блокируют игру.

---

## Следующий этап автоматизации

Когда этот workflow будет работать ручной 3-5 раз — можно написать Python-скрипт `session_finalize.py`, который:
1. Прочитает лог
2. Отправит его в 3 API-вызова (State Manager, Narrative Editor, Visual Extractor)
3. Соберёт результаты в правильные папки
4. Обновит JSON-модули автоматически
5. Сделает `git commit`

Но сейчас — **ручной pipeline работает и даёт полный контроль**.
