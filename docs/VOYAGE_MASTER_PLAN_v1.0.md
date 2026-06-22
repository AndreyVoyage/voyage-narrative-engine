# VNE MASTER PLAN v1.0
> **Источник истины для стратегии развития Voyage Narrative Engine.**
> Статус: согласовано, зафиксировано. Приоритет: P0 для AI-агентов.
> Дата: 2026-06-21

---

## 1. VISION: к чему стремимся

**VNE — это не игра и не web-сервис. VNE — это контентное и логическое ядро (Content Engine) для интерактивных AI-нарративов.**

Максимальный реалистичный потолок:

```
VNE Engine (spec repo)  →  Ren'Py Novel (2D MVP)  →  Web Companion  →  3D Character Viewer  →  Full 3D Game (опционально)
```

**Принцип:** VNE остаётся спецификационным репозиторием. Он поставляет персонажей, сценарии, психологические механики, safety, memory. Игровые клиенты строятся рядом — в этом же репозитории (monorepo), но как отдельные слои.

**Не строим:**
- ❌ Новый репозиторий "VNE Next" — нет, развиваем текущий
- ❌ Web Studio как первый шаг — редакторы нужны авторам, но игроку нужна игра
- ❌ 3D/Unity как первый шаг — слишком дорого и долго для проверки контента
- ❌ Backend/API сразу — для MVP не нужен, для релиза — нужен

---

## 2. АРХИТЕКТУРА: текущее состояние

```
voyage-narrative-engine/
├── AGENTS.md                          # P0: правила для AI-агентов
├── docs/
│   ├── VOYAGE_MASTER_DOCUMENT_v3.md   # P1: архитектурная vision
│   └── DEVELOPMENT_ROADMAP.md         # этот документ
├── engine/                            # текущее ядро
│   ├── core/                          # VSCNO, AD, internal_state, memory baseline
│   ├── personas/                      # 10 модульных персонажей + монолиты (legacy)
│   ├── scenarios/                     # sauna_extended, promenade, gym_*, legacy
│   ├── knowledge_base/              # R1–R6, S1–S8 KB
│   ├── roles/                         # R1–R8 промпты
│   ├── scripts/python/                # runtime_loader, build_prompt_modular, test_runtime_all
│   └── schemas/                       # persona_schema_v3_2_VOYAGE.json
├── novel/                             # 🆕 Ren'Py проект (будет создан)
├── game/                              # 🆕 3D/Unity позже (опционально)
├── tools/                             # 🆕 exporters, converters, art pipeline
└── archive/                           # legacy: монолиты, SYSTEM.md, старые скрипты
```

**Canon Hierarchy (P0–P5):**
```
P0 — AGENTS.md              # operational rules для AI-агентов
P1 — MASTER PLAN (этот файл) # стратегия развития
P2 — VOYAGE_MASTER_DOCUMENT_v3.md # архитектурная vision
P3 — core/ + schemas/      # baseline mechanics
P4 — docs/01–12             # module specs
P5 — README.md              # human quickstart only
P6 — SYSTEM.md              # legacy reference, не canonical
```

---

## 3. ПУТЬ РАЗВИТИЯ: 4 Phase

### Phase 0: Canon Sync (1–2 дня)
**Цель:** единый источник правды, убрать рассинхрон.

| Задача | Статус | Действие |
|--------|--------|----------|
| Обновить AGENTS.md | 🔄 | Добавить Canon Hierarchy, развести knowledge/ vs knowledge_base/ |
| Пометить SYSTEM.md | 🔄 | [STALE / LEGACY] в начале файла |
| Убрать монолиты из personas/ | 🔄 | Перенести *.json в archive/monoliths/ |
| Починить session_finalize.py | 🔄 | Добавить fallback на load_modular_persona() |
| Синхронизировать test_runtime_all.py | 🔄 | has_core_key vs has_core_content |
| Убрать personas/visual_prompts/ | 🔄 | Перенести в archive/ или assets/ |
| Создать unified gate | 🆕 | scripts/python/gate.py = validate + test + build --dry-run |

**Gate:**
```bash
python scripts/python/gate.py
# 0 FAIL, 0 exceptions, 0 stale paths
```

---

### Phase 1: Engine Hardening (1–2 недели)
**Цель:** VNE как надёжное content-ядро.

| Задача | Статус | Действие |
|--------|--------|----------|
| Session Retrospector | 🆕 | scripts/python/session_retrospector.py — Q4 аудит (LO, HU, TE, DI) |
| Session Normalizer | 🆕 | scripts/python/normalize_session.py — ФМДР → structured JSON |
| State + Memory persistence | 🆕 | state/STATE_ACTIVE.json обновляется после сессии |
| Living World Lite (rules) | 🆕 | personas/[id]/autonomous/GOALS.json + EVENT_RULES.json |
| Golden Dataset | 🆕 | tests/golden/good_*.md, bad_*.md для regression |
| CLI | 🆕 | vne validate, vne build, vne audit, vne test |

**Deliverable:** VNE может:
- Загрузить любого модульного персонажа
- Собрать runtime prompt
- Сохранить и нормализовать сессию
- Провести post-session audit
- Генерировать Living World events (rule-based)

---

### Phase 2: Ren'Py MVP (3–4 недели)
**Цель:** первая играбельная версия для игрока.

**Что делаем:**
```
novel/renpy_project/
├── game/
│   ├── script.rpy              # главный сценарий
│   ├── characters.rpy          # определения персонажей
│   ├── scenes/
│   │   └── sauna_intro.rpy     # 1 сцена (5–7 реплик)
│   ├── images/                 # sprites + backgrounds
│   ├── audio/                  # music + sfx
│   └── vne_bridge.py           # 🆕 импорт VNE JSON в Ren'Py
```

**Контент:**
- 1 сценарий: `sauna_extended` (фаза P1 — вход, раздевалка) или `promenade`
- 2 персонажа: Кира + Марина (или Сергей)
- Спрайты: 1 базовый + 3 эмоции на персонажа (AI-generated, Stable Diffusion/ControlNet)
- Фоны: 3–5 локаций (AI-generated)
- Музыка: royalty-free
- Выборы: 2–3 варианта, 2 финала
- Длительность: 15–25 минут

**Технически:**
- Ren'Py может импортировать Python и читать VNE JSON напрямую
- `vne_bridge.py` = обёртка над `runtime_loader.load_modular_persona()`
- Персонажи: `define kira = Character("Кира", color="#c8ffc8")`

**Платформы:**
1. Windows build (приоритет #1)
2. Web/HTML5 build (демо, itch.io)
3. Android build (APK, вне Google Play — см. §5)

**Gate:**
```bash
cd novel/renpy_project
renpy build windows
renpy build web
# тест на 3–5 людях: интересно ли?
```

---

### Phase 3: AI Runtime (2–3 месяца)
**Цель:** LLM-диалоги внутри игры, Living World Lite.

**3.1 AI Dialogue Mode (Level 1)**
```
Игрок вводит реплику → VNE Context Builder → LLM → Response Parser → Validator → Ren'Py display
```

**VNE Context Builder собирает:**
- `core/IDENTITY.json` — кто персонаж
- `levels/[current].json` — VSCNO, AD, internal_state, speech
- `memory/TRUST.json` — trust к игроку
- `safety/PROTOCOL.json` — hard limits, stop words
- `speech/SPEECH_MATRIX.json` — few-shot examples
- Последние 5–10 реплик (session history)

**System prompt (упрощённо):**
```
Ты — Кира. 28 лет. Ex-sprinter. Steel butterfly.
Уровень: У2-А. ВЛ=2, СТ=3, НЖ=3, ОГ=2.
Trust к игроку: 67. Tension: 55.
Speech: короткие защитные фразы, ритм 1-2-1, сленг: "понял", "ну ты даёшь".
Запреты: не переходить на У6 без AG3, не упоминать травму напрямую.
Формат: (Мысли: ...) → *Действия: ...* → «Речь: ...»
```

**Структура ответа LLM:**
```json
{
  "thoughts": "Он снова давит. Но не так грубо, как обычно.",
  "action": "*отводит взгляд, но не уходит*",
  "speech": "Ты всегда так давишь, или это только со мной?",
  "emotion": "guarded_softened",
  "state_delta_suggestion": {
    "tension": -2,
    "trust": 1
  }
}
```

**Validator проверяет:**
- Не нарушен ли подуровень (U2-A не может говорить как U5)
- Не использован запрещённый AD
- Trust не скачет резко (±5 за реплику — max)
- Speech соответствует speech matrix
- Safety не нарушен

**State Delta Engine применяет только разрешённое:**
```python
# Пример: validator clamps
trust_delta = clamp(state_delta["trust"], -3, 3)
tension_delta = clamp(state_delta["tension"], -5, 2)
```

**3.2 Living World Lite (Level 2)**
Персонажи не "живут 24/7", но между сценами генерируют 1–2 события:

```json
// personas/kira/autonomous/GOALS.json
{
  "goals": [
    {
      "id": "avoid_vulnerability",
      "priority": 1,
      "condition": "tension > 50",
      "action": "send_short_message",
      "text_variants": [
        "Не сегодня.",
        "Я всё ещё злюсь.",
        "Поговорим позже?"
      ]
    }
  ]
}
```

```json
// personas/kira/autonomous/EVENT_RULES.json
{
  "rules": [
    {
      "if": {
        "trust_to_player": ">60",
        "tension": "<70",
        "flag": "first_conflict_resolved"
      },
      "then": {
        "event_type": "message",
        "text": "Я всё ещё думаю о том разговоре. Но уже не так сильно злюсь.",
        "state_delta": {"tension": -3, "trust": 2},
        "max_frequency": "once_per_3_days"
      }
    }
  ]
}
```

**3.3 AI Event Generator (опционально, после rules)**
Если rules дают несколько вариантов — LLM выбирает/генерирует текст, но структура остаётся JSON:
```json
{
  "event_type": "message",
  "character": "kira",
  "reason": "unresolved tension from previous scene",
  "text": "Ты всегда так давишь, или это только со мной?",
  "state_delta": {"tension": -2, "trust": 1},
  "new_flags": ["kira_reopened_contact"]
}
```

**3.4 NPC-to-NPC Events (Level 3, опционально)**
Не полноценные диалоги, а summary events:
```json
{
  "event": "kira_marina_private_talk",
  "summary": "Марина заметила, что Кира избегает разговора о прогулке.",
  "relationship_delta": {
    "kira_to_marina_trust": 1,
    "kira_tension": 2
  },
  "new_flag": "marina_noticed_kira_avoidance"
}
```

---

### Phase 4: Scale (3–6 месяцев, опционально)
**Цель:** расширение, если MVP выстрелит.

| Направление | Что | Когда |
|-------------|-----|-------|
| **Web Player** | React/Vue + VNE backend | Если Ren'Py Web недостаточно |
| **3D Character Viewer** | Unity/Godot + VRoid/MetaHuman | Если есть запрос на 3D |
| **Backend/API** | FastAPI + PostgreSQL + LLM proxy | Если >1000 игроков |
| **More Personas** | 5–10 новых персонажей (R1–R8) | Если контент востребован |
| **More Scenarios** | 3–5 новых сценариев (S1–S8) | Если аудитория растёт |
| **Session Retrospector** | FULL MODE (evidence-based) | Когда есть golden dataset |

---

## 4. AI RUNTIME: уровни автономности

**Правило:** персонаж = данные + память + состояние. LLM = интерпретатор. Validator = контролёр.

```
Level 1: AI Dialogue Mode          → реактивные ответы (сейчас реально)
Level 2: Living World Lite         → события между сценами (сейчас реально)
Level 3: NPC-to-NPC Summary Events → краткие события без игрока (возможно)
Level 4: Full Autonomous Life      → 24/7 симуляция (не начинать с этого)
```

**Контракт для LLM:**
```
Ты можешь выбирать только:
  - message
  - memory_update
  - mood_shift
  - scene_unlock
  - relationship_delta
  - private_diary

Ты НЕ можешь:
  - менять базовый характер
  - переписывать прошлое
  - резко менять отношение без причины
  - открывать недоступные уровни
  - нарушать safety
  - генерировать события вне сценарного мира
```

**Backend:**
- Для прототипа: API-ключ напрямую (OpenRouter/OpenAI) — допустимо
- Для релиза: свой backend proxy (скрывает API-ключ, кэширует, rate limits)
- Локальная LLM: Windows только, `llama.cpp`, GPU 8GB+. Android — не для MVP.

---

## 5. ПЛАТФОРМЫ И КОНТЕНТ

### Windows
- ✅ Самый простой и надёжный
- Ren'Py → Windows build
- Локальная LLM возможна

### Web
- ✅ Ren'Py Web/HTML5 работает (размер 50–100MB, может быть медленно)
- itch.io — идеальная площадка для демо
- Не ставить как основной коммерческий канал

### Android
- ✅ Ren'Py → Android APK (RAPT)
- ⚠️ Google Play блокирует explicit sexual content
- ✅ Решение: itch.io, Patreon, SubscribeStar, direct APK
- ⚠️ Локальная LLM на Android — не для MVP

### 3D-модели
- **Level 1:** AI image prompts (Stable Diffusion/Midjourney) — спрайты для Ren'Py
- **Level 2:** VRoid Studio — бесплатные 3D anime-стилевые модели
- **Level 3:** MetaHuman — фотореалистичные, но требует Unreal
- **Level 4:** Профессиональные 3D-художники — $2K–5K за модель

VNE хранит character bible (`anatomic_anchor`, `DYNAMIC_VISUALS.json`) — это brief для любого 3D-конвейера.

---

## 6. СТОИМОСТЬ И РЕСУРСЫ

### Phase 0–1 (Engine)
- **Время:** 2–3 недели
- **Деньги:** $0 (сам)
- **Инструменты:** Python, Git, JSON

### Phase 2 (Ren'Py MVP)
- **Время:** 3–4 недели
- **Деньги:** $0–500 (AI-арт через Stable Diffusion бесплатно, Midjourney $30/мес)
- **Инструменты:** Ren'Py, Stable Diffusion + ControlNet, Audacity, AI-музыка (Suno/Udio)

### Phase 3 (AI Runtime)
- **Время:** 2–3 месяца
- **Деньги:** $20–100/мес (OpenRouter API для тестов)
- **Инструменты:** Python, Ren'Py, LLM API

### Phase 4 (Scale)
- **Время:** 3–6 месяцев
- **Деньги:** $50–500/мес (backend, хостинг, API)
- **Инструменты:** React/Vue, FastAPI, PostgreSQL, Unity (опционально)

---

## 7. ЧТО НЕ ДЕЛАЕМ

| Не делаем | Почему |
|-----------|--------|
| Новый репозиторий "VNE Next" | Текущий репозиторий живой, перенос — 6+ месяцев потерь |
| Web Studio первым | Игрок важнее редактора |
| Unity/Unreal первым | 3D — 2+ года, проверка контента важнее |
| 4 отдельных репозитория | Monorepo для одного разработчика |
| Full autonomous world | Нестабильно, дорого, непредсказуемо |
| Отдельная LLM на каждого NPC | $×N, хаос, смешение голосов |
| LLM напрямую меняет память | Только через Validator + State Manager |
| API-ключ в публичном клиенте | Через backend proxy для релиза |
| "Супер-движок" без MVP | Сначала проверить, интересен ли контент |

---

## 8. NEXT STEPS (конкретные действия)

### Неделя 1: Canon Sync
- [ ] Обновить `AGENTS.md` (Canon Hierarchy P0–P6)
- [ ] Пометить `SYSTEM.md` [STALE]
- [ ] Перенести монолиты `personas/*.json` → `archive/monoliths/`
- [ ] Убрать `personas/visual_prompts/` → `archive/`
- [ ] Создать `scripts/python/gate.py` (unified quality gate)
- [ ] Починить `session_finalize.py` (fallback на `load_modular_persona`)
- [ ] Синхронизировать `test_runtime_all.py` (has_core_key vs has_core_content)
- [ ] Создать `personas/_runtime_manifest.json` (статус каждого персонажа)

### Неделя 2: Session Retrospector
- [ ] Создать `scripts/python/session_retrospector.py`
- [ ] Реализовать Q4 scorecard (LO, HU, TE, DI)
- [ ] Создать `tests/golden/good_*.md` и `bad_*.md`
- [ ] Создать `scripts/python/normalize_session.py` (ФМДР → JSON)

### Неделя 3: Ren'Py Setup
- [ ] Скачать Ren'Py
- [ ] Создать `novel/renpy_project/`
- [ ] Создать `novel/renpy_project/game/vne_bridge.py` (импорт VNE JSON)
- [ ] Перенести 1 сцену (`sauna_extended` P1 или `promenade`) в `script.rpy`
- [ ] Сгенерировать 1 спрайт Киры (нейтральная) — Stable Diffusion/ControlNet

### Неделя 4: Ren'Py MVP
- [ ] Добавить 2-го персонажа (Марина или Сергей)
- [ ] 3 эмоции на персонажа
- [ ] 3–5 фонов
- [ ] 2–3 выбора игрока
- [ ] 2 финала
- [ ] Собрать Windows build
- [ ] Тест на 3–5 друзьях
- [ ] Решить: интересен ли контент?

### После MVP (если "да"):
- [ ] AI Dialogue Mode (Level 1) — LLM в Ren'Py
- [ ] Living World Lite (Level 2) — rules-based events
- [ ] Web build (itch.io)
- [ ] Android build (APK)
- [ ] Масштабирование контента (новые персонажи, сценарии)

---

## 9. КЛЮЧЕВЫЕ ПРИНЦИПЫ

1. **VNE = мозг, не тело.** Персонажи, сценарии, механики — здесь. Игра — рядом.
2. **Monorepo, не polyrepo.** Один git, один канон, один backlog.
3. **Ren'Py первым.** 2D новелла за 3–4 недели лучше, чем 3D игра через 2 года.
4. **AI Dialogue — контрактный.** LLM не бог мира, а актёр по режиссёрским инструкциям.
5. **Validator между AI и State.** LLM предлагает → VNE проверяет → применяет.
6. **Human-in-the-loop.** AI не правит персонажей без аудита (R7 + R8).
7. **Schemas First.** Контракты до кода.
8. **Платформы: Windows → Web → Android.** Google Play — только soft content.
9. **Не ждать идеального.** MVP с 1 персонажем и 1 сценой > архитектура на год.
10. **VNE — это контентное преимущество.** Психологическая глубина, которой нет в коммерческих играх.

---

*VNE MASTER PLAN v1.0 | Согласовано | 2026-06-21*
*Canonical: AGENTS.md → MASTER PLAN → VOYAGE_MASTER_DOCUMENT_v3.md → core/*
