# Быстрый старт Voyage Engine v2.0

## 1. Сборка PROMPT.txt

```bash
cd ~/voyage-narrative-engine
bash build_prompt.sh shy_to_bitch SC_000
```

Режимы:
- `default` — классическая Кира (стальная бабочка)
- `shy_to_bitch` — невинность → стерва (новый v2.0)

## 2. Загрузка в Kimi

1. Откройте Kimi (kimi.moonshot.cn)
2. Загрузите файл `PROMPT.txt`
3. Напишите: `Запускаем Voyage Engine v2.0`

## 3. Управление внутри сессии

| Команда | Эффект |
|---|---|
| `У1-А` … `У7-Б` | Переключить подуровень |
| `ТГ1` … `ТГ3` | Переключить грань |
| `АД [код]` | Активировать алгоритм |
| `М [параметры]` | Сгенерировать сценарий |
| `В` | Сгенерировать Qwen-промпт |
| `Г [0-4]` | Установить Autonomy Governor |
| `СТОП` | Emergency exit → У7-А |
| `режим default` | Переключить в legacy |
| `режим shy_to_bitch` | Переключить в совращение |
| `Сергей catalyst` | Роль Сергея: зеркало |
| `Сергей ally` | Роль Сергея: союзник |
| `Сергей rival` | Роль Сергея: соперник |

## 4. Обновление STATE после сессии

```bash
bash update_state.sh state/STATE_TEMPLATE_v2.json U2 B kira_first_blush kira_asked_why_you_look
```

## 5. Git commit

```bash
bash git_commit.sh "Session 2026-06-07: U2-B reached, SC_001-B completed"
```

## 6. Генерация картинок (Qwen Studio)

1. В конце каждого ответа Kimi генерирует `[AUTO_VISUAL]` блок.
2. Скопируйте Qwen-промпт (строка после `Qwen:`).
3. Вставьте в Qwen Studio (qwen.ai/studio).
4. Настройте: CFG из блока, Steps из блока, Seed = 54321 (для Киры) или 67890 (для Сергея).

## 7. Структура репозитория

```
voyage-narrative-engine/
├── README.md
├── QUICKSTART.md          ← вы здесь
├── build_prompt.sh        ← сборщик PROMPT.txt
├── update_state.sh        ← обновление STATE
├── git_commit.sh          ← git commit
├── PROMPT.txt             ← собранный промпт для Kimi
├── core/
│   └── VOYAGE_NARRATIVE_CORE_v2.md
├── personas/
│   ├── KIRA_MODULE_v12.json
│   └── SERGEY_MODULE_v3.json
├── state/
│   └── STATE_TEMPLATE_v2.json
├── scenarios/
│   └── SCENARIO_SHY_BLOOM.json
├── governance/
│   └── AUTONOMY_GOVERNOR_v2.md
├── visual/
│   └── QWEN_ADAPTER_v2.md
├── memory/
│   └── MEMORY_PROTOCOL_v2.md
└── legacy/v1.0/           ← старые файлы (backup)
```

## 8. Режимы Киры

### `default` (Стальная бабочка)
- У1: Стойкость → У7: Aftercare
- Классическая дуга спринтерши
- Используйте: `bash build_prompt.sh default`

### `shy_to_bitch` (Невинность → Стерва)
- У1-А: Невинность → У7-Б: Интеграция
- 14 подуровней (A/Б)
- Сергей — катализатор (зеркало)
- Используйте: `bash build_prompt.sh shy_to_bitch`

## 9. Треугольник отношений (Модель C)

- **Кира ↔ Я:** якорь, спасатель. Он ведёт её через невинность.
- **Сергей ↔ Я:** союзник по совращению. Уступает, если «я» сказал «стоп».
- **Кира ↔ Сергей:** зеркало. Он видит её микродвижения и отражает их.

## 10. Поддержка

- GitHub: https://github.com/AndreyVoyage/voyage-narrative-engine
- Issues: создавайте для багов и предложений
- Форки: приветствуются

---

> **Примечание:** Это prompt-native framework. Вся логика выполняется LLM на основе загруженного контекста. Для автоматизации парсинга STATE требуется runtime-скрипт (в разработке).
