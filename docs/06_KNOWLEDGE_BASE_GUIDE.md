# 06_KNOWLEDGE_BASE_GUIDE.md
# Руководство по работе с базой знаний
# Версия: 2.0.0

---

## 1. Структура базы знаний

```
knowledge_base/
├── INDEX.md                          # Реестр всех источников с тегами
├── nagoski_emily/
│   ├── dual_control_model.md
│   ├── nonconcordance.md
│   └── spectating.md
├── lowen_alexander/
│   ├── mask_and_true_self.md
│   └── breathing_and_orgasm.md
├── masters_johnson/
├── basson/
│   └── 2000_female_response_model.md
├── evolution/
│   └── arousal_as_motivation.md
├── attachment/
│   └── behavioral_systems.md
├── sexual_scripts/
│   └── gagnon_simon_definition.md
├── trauma_ptsd/
│   └── three_levels_dissociation.md
└── supplementary/
    └── bioenergetics.md
```

---

## 2. Формат файла источника

Каждый файл начинается с YAML-подобного блока метаданных:

```markdown
---
author: "Нагоски Эмили"
title: "Как хочет женщина"
year: 2016
tags: ["dual_control", "nonconcordance", "spectating", "responsive_desire"]
type: "academic_popular"
chapter: 4
pages: "89-102"
---

# Модель двойного контроля

## Ключевая идея
У женщин есть две независимые системы: «педаль газа» и «педаль тормоза».

## Цитата
> «Не существует врожденных стимулов или угроз — системы дают реакции исходя из опыта и контекста».

## Применение в модулях
- `psychology/AROUSAL.json`: описание SE и SI.
- `psychology/SPECTATORING.json`: наблюдение за собой как тормоз.

## Выдержки (2-5 абзацев)
[Текст для использования LLM]
```

**Обязательные поля:** author, title, year, tags, type.
**Типы:** academic, academic_popular, practical, fiction, philosophy.

---

## 3. Как добавить новый источник

1. Определить категорию (папку) по тематике.
2. Создать файл с именем на английском (dual_control_model.md).
3. Заполнить метаданные и выдержку (не более 2-3 страниц).
4. Добавить раздел «Применение в модулях».
5. Обновить INDEX.md.

---

## 4. Категории источников

| Папка | Содержание |
|-------|-----------|
| `nagoski_emily/` | Работы Эмили Нагоски |
| `lowen_alexander/` | Александр Лоуэн и биоэнергетика |
| `masters_johnson/` | Мастерс и Джонсон |
| `basson/` | Работы Розмари Бассон |
| `evolution/` | Эволюционная психология |
| `attachment/` | Теория привязанности |
| `sexual_scripts/` | Gagnon & Simon |
| `trauma_ptsd/` | Травма, диссоциация |
| `supplementary/` | Философия телесности, эротическая поэтика |

---

## 5. Использование базы знаний

В промпте укажите:
> «Используй базу знаний: файл `nagoski_emily/dual_control_model.md` для обоснования модуля.»

Если у LLM нет доступа к файлам — скопируйте содержимое в контекст чата. Файлы должны быть короткими (не более 1500 токенов).

---

## 6. Пример INDEX.md

```markdown
# Реестр базы знаний

## Нагоски
- [nagoski_emily/dual_control_model.md](nagoski_emily/dual_control_model.md) (tags: dual_control, arousal, inhibition)
- [nagoski_emily/nonconcordance.md](nagoski_emily/nonconcordance.md) (tags: nonconcordance, arousal)
- [nagoski_emily/spectating.md](nagoski_emily/spectating.md) (tags: spectating, shame)

## Лоуэн
- [lowen_alexander/mask_and_true_self.md](lowen_alexander/mask_and_true_self.md) (tags: mask, defense_mechanisms)
- [lowen_alexander/breathing_and_orgasm.md](lowen_alexander/breathing_and_orgasm.md) (tags: breathing, orgasm)

## Эволюционная психология
- [evolution/arousal_as_motivation.md](evolution/arousal_as_motivation.md) (tags: motivation, risk_perception)

## Теория привязанности
- [attachment/behavioral_systems.md](attachment/behavioral_systems.md) (tags: attachment, caregiving, sexuality)

## Сексуальные сценарии
- [sexual_scripts/gagnon_simon_definition.md](sexual_scripts/gagnon_simon_definition.md) (tags: scripts, definition)

## Травма и ПТСР
- [trauma_ptsd/three_levels_dissociation.md](trauma_ptsd/three_levels_dissociation.md) (tags: dissociation, ptsd, trauma)

## Basson
- [basson/2000_female_response_model.md](basson/2000_female_response_model.md) (tags: responsive_desire, basson)

## Supplementary
- [supplementary/bioenergetics.md](supplementary/bioenergetics.md) (tags: bioenergetics)
```

---

## 7. Поддержка и обновление

- Проверяйте актуальность источников (особенно научных статей).
- Художественные источники — укажите `type: fiction`.
- Практические руководства — `type: practical` + предупреждение о субъективности.

---

*Документ 06 из 09*
