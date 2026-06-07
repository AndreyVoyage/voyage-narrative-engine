# Voyage Narrative Engine v3.0 — Quintet Update

## Новые файлы

### 1. personas/MAXIM_MODULE_v1.json
Персонаж Максим — друг Сергея, "лояльный неуклюжий гигант".
- 7 уровней эмоциональной дуги (MX1-MX7)
- Динамические визуалы для каждого уровня
- Отношения с Кирой, Мариной, Сергеем, Пользователем
- Интеграция с сауной

### 2. scenarios/SCENARIO_SAUNA_QUINTET.json
Сценарий "Квинтет" — все 5 персонажей в сауне.
- 8 сцен (SQ_000 — SQ_007)
- От входа до ухода
- Мультиперсонажные динамики
- NPC-to-NPC диалоги
- Autonomy Governor rules для квинтета

### 3. state/STATE_TEMPLATE_QUINTET_v1.json
State для квинтета с 5 персонажами + npc_relationships.

### 4. governance/AUTONOMY_NPC_GUIDE_v3.md
Полный гайд по автономным действиям NPC.
- AG0-AG4 уровни
- Примеры NPC-to-NPC диалогов
- Протокол USER_RETURNED
- Таблицы развития отношений
- Safety & Boundaries

### 5. build_prompt_v3.sh
Обновлённый скрипт сборки PROMPT.txt.
- Режимы: default, shy, quintet, marina, full
- Варианты: compact, standard, extended, scenario-only, npc-autonomy
- Поддержка Termux (цвета, termux-clipboard-set, termux-share)
- Автоматическая сборка из файлов репозитория

## Использование

```bash
# Стандартный квинтет
bash build_prompt_v3.sh quintet standard

# Квинтет с полной автономией
bash build_prompt_v3.sh quintet npc-autonomy

# Только сцена SQ_001
bash build_prompt_v3.sh quintet standard SQ_001

# Компактный режим (минимум токенов)
bash build_prompt_v3.sh shy compact

# Полный режим со всеми модулями
bash build_prompt_v3.sh full extended
```

## Автономность NPC

При AG≥3 персонажи могут:
- Отправлять сообщения пользователю при offline >30min
- Взаимодействовать друг с другом (NPC-to-NPC)
- Развивать отношения (Марина↔Максим, Кира↔Марина, Сергей↔Максим)
- Генерировать proactive events

При AG=4 полная автономия:
- AI пишет первым
- Персонажи уходят/приходят
- Заводят отношения без пользователя
- Пользователь возвращается и узнаёт о произошедшем
