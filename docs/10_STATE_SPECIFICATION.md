Файл: 10_STATE_SPECIFICATION.md

```markdown
# 10_STATE_SPECIFICATION.md
# Спецификация runtime-состояния: state/STATE.json
# Версия: 1.0.1 (исправлено: унифицированы флаги)

## 1. Назначение
Файл `state/STATE.json` хранит **динамические данные** персонажа, которые обновляются после каждой сессии. Эти данные имеют **наивысший приоритет** при сборке (перезаписывают любые значения из модулей).

## 2. Полная структура

```json
{
  "session_id": "sess_2026-06-08_001",
  "timestamp": "2026-06-08T19:30:00Z",
  "scenario_id": "sauna_quartet",
  "scene_id": "P2_STEAM",
  "ag_level": 2,
  "characters": {
    "kira": {
      "module_id": "KIRA_MODULE_v14",
      "current_level": "U3-A",
      "previous_level": "U2-B",
      "internal_state": {
        "desire": 5,
        "anxiety": 4,
        "desire_tension": 3,
        "frustration": 0
      },
      "vscno": {
        "ВЛ": 2,
        "СТ": 3,
        "НЖ": 3,
        "ОГ": 2
      },
      "memory_snapshot": {
        "trust_levels": {
          "user": 75,
          "sergey": 40,
          "maksim": 80,
          "marina": 50
        },
        "attraction_levels": {
          "user": 85,
          "sergey": 90,
          "maksim": 70,
          "marina": 30
        },
        "emotional_anchors": ["first_meeting_sauna", "sergey_gaze_3sec"],
        "flags": {
          "first_meeting_complete": true,
          "first_kiss": false,
          "first_touch_erogenous": false,
          "first_orgasm_with_user": false,
          "sauna_confession_done": true,
          "shared_secret_desire": true,
          "regression_to_U7_A_occurred": false,
          "integration_U7_B_reached": false,
          "sergey_confrontation_complete": false,
          "maksim_comforted_after_shame": false
        }
      },
      "active": true,
      "in_scene": true
    }
  },
  "global": {
    "current_scenario": "sauna_quartet",
    "scene_id": "scene_03"
  }
}
```

3. Описание полей и типы

Поле Тип Обязательное Описание
session_id string ✅ Уникальный идентификатор сессии
timestamp string (ISO 8601) ✅ Время последнего обновления
scenario_id string ✅ Идентификатор сценария из scenarios/
scene_id string ❌ Конкретная фаза/сцена внутри сценария
ag_level integer (1-3) ✅ Глубина сборки (1=базовая, 2=продвинутая, 3=полная)
characters object ✅ Объект с данными всех персонажей
characters.{id}.module_id string ✅ Имя модуля персонажа (например, KIRA_MODULE_v14)
characters.{id}.current_level string ✅ Текущий эмоциональный уровень (U1-A … U7-B)
characters.{id}.previous_level string ❌ Предыдущий уровень (для отката)
characters.{id}.internal_state.desire integer (0-10) ✅ Уровень желания
characters.{id}.internal_state.anxiety integer (0-10) ✅ Уровень тревоги
characters.{id}.internal_state.desire_tension integer (0-10) ✅ Напряжение между желанием и стыдом
characters.{id}.internal_state.frustration integer (0-10) ✅ Фрустрация от нереализованного желания
characters.{id}.vscno object ✅ Четыре оси (сумма должна быть 10)
characters.{id}.vscno.ВЛ integer (0-4) ✅ Влечение
characters.{id}.vscno.СТ integer (0-4) ✅ Стыд
characters.{id}.vscno.НЖ integer (0-4) ✅ Напряжение
characters.{id}.vscno.ОГ integer (0-4) ✅ Оглядка/возбуждение
memory_snapshot.trust_levels object ✅ trust к другим персонажам (0-100)
memory_snapshot.attraction_levels object ✅ attraction (0-100)
memory_snapshot.emotional_anchors array ❌ НЛП-якоря (эмоциональные триггеры)
memory_snapshot.flags object ❌ Ключевые события (см. memory/FLAGS.json)
active boolean ✅ Активен ли персонаж в текущей сцене
in_scene boolean ✅ Находится ли в кадре
global object ✅ Глобальные параметры
global.current_scenario string ✅ Текущий сценарий
global.scene_id string ✅ Идентификатор сцены

4. Правила обновления

· После каждой сессии session_finalize.py обновляет:
  · current_level – на основе анализа ФМДР и триггеров.
  · internal_state и vscno – согласно state_triggers из модуля уровня.
  · memory_snapshot – на основе произошедших событий (увеличение trust/attraction, флаги).
· previous_level сохраняется перед изменением current_level.
· VSCNO: сумма всегда должна быть 10. При обновлении, если сумма нарушается, приоритет у ВЛ и ОГ, затем НЖ, затем СТ.
· ag_level может быть переопределён сценарием (если в сценарии указан recommended_ag_level).
· Приоритет триггеров при одновременном изменении internal_state: если несколько триггеров срабатывают одновременно, применяется наиболее сильное изменение (максимальный дельта). При конфликте (один триггер увеличивает desire, другой уменьшает) – побеждает изменение с большим абсолютным значением.

5. Пример изменения после эротической сцены

До сессии:

```json
"internal_state": { "desire": 3, "anxiety": 2, "desire_tension": 1, "frustration": 0 }
"vscno": { "ВЛ": 1, "СТ": 4, "НЖ": 3, "ОГ": 2 }
```

После сессии (повышение желания, снижение стыда):

```json
"internal_state": { "desire": 6, "anxiety": 3, "desire_tension": 4, "frustration": 1 }
"vscno": { "ВЛ": 3, "СТ": 2, "НЖ": 3, "ОГ": 2 }
```

6. Валидация

· Все обязательные поля должны присутствовать.
· current_level должен соответствовать одному из уровней, определённых в levels/ персонажа.
· previous_level (если указан) должен быть корректным уровнем (U1-A … U7-B).
· Сумма vscno = 10.
· ag_level ∈ {1,2,3}.
· trust и attraction ∈ [0,100].
· Имена флагов в flags должны соответствовать определённым в memory/FLAGS.json.

7. Связь с модулями

· current_level определяет, какой файл levels/{current_level}.json загружается.
· memory_snapshot перезаписывает значения trust/attraction из relationships/MATRIX.json.
· flags используются для проверки пороговых событий (например, если first_meeting_complete == true, то речевые паттерны могут меняться).
· ag_level влияет на набор загружаемых модулей (см. 03_ASSEMBLY_GUIDE.md, раздел 7).

---

Документ 10 из 12. Версия 1.0.1 (исправлена: унифицированы флаги с 11_MEMORY_SPECS.md)

```

Теперь файл полностью готов к сохранению. Хотите, продолжу с файлом 11, затем 12, затем шаблоны? Или уже достаточно?