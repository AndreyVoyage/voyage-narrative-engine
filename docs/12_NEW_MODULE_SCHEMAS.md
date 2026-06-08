Файл: 12_NEW_MODULE_SCHEMAS.md

```markdown
# 12_NEW_MODULE_SCHEMAS.md
# Компактные JSON Schema для новых модулей (physiology, sexology, meta, environment, dynamics)
# Версия: 1.0.0

> **Примечание:** Эти схемы являются **минимальными** и охватывают все обязательные поля. При наполнении модуля можно добавлять дополнительные поля, не нарушая данных требований. Полные примеры см. в `02_MODULE_SPECS.md` и `07_PERSONA_MODULAR_ARCHITECTURE.md`.

---

## 1. `physiology/AROUSAL_SIGNATURES.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["scale"],
  "properties": {
    "scale": {
      "type": "object",
      "patternProperties": {
        "^(0|[1-9]-[1-9]|10)$": {
          "type": "object",
          "required": ["pulse", "breathing", "skin", "narrative"],
          "properties": {
            "pulse": { "type": "string" },
            "breathing": { "type": "string" },
            "skin": { "type": "string" },
            "narrative": { "type": "string" }
          }
        }
      }
    }
  }
}
```

2. physiology/MICROEXPRESSIONS.json

```json
{
  "type": "object",
  "required": ["emotions", "level_mapping"],
  "properties": {
    "emotions": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["markers", "narrative"],
        "properties": {
          "markers": { "type": "array", "items": { "type": "string" } },
          "narrative": { "type": "string" }
        }
      }
    },
    "level_mapping": { "type": "object" }
  }
}
```

3. physiology/EROGENOUS_MAP.json

```json
{
  "type": "object",
  "required": ["zones", "progression_rules"],
  "properties": {
    "zones": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["sensitivity", "triggers"],
        "properties": {
          "sensitivity": { "type": "integer", "minimum": 1, "maximum": 10 },
          "triggers": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "progression_rules": { "type": "object" }
  }
}
```

4. sexology/RESPONSE_CYCLE.json

```json
{
  "type": "object",
  "required": ["model", "phases", "kira_specific"],
  "properties": {
    "model": { "type": "string", "enum": ["Basson_responsive_desire", "Masters_Johnson"] },
    "phases": {
      "type": "object",
      "patternProperties": {
        "^(neutral|receptivity|subjective_arousal|plateau|orgasm|resolution)$": {
          "type": "object",
          "required": ["desire_range", "kira_state"],
          "properties": {
            "desire_range": { "type": "string" },
            "kira_state": { "type": "string" },
            "narrative": { "type": "string" }
          }
        }
      }
    },
    "kira_specific": { "type": "object" }
  }
}
```

5. sexology/EROTIC_SCRIPTS.json

```json
{
  "type": "object",
  "required": ["scripts"],
  "properties": {
    "scripts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "actors", "actions", "settings", "triggers"],
        "properties": {
          "name": { "type": "string" },
          "actors": { "type": "array", "items": { "type": "string" } },
          "actions": { "type": "array", "items": { "type": "string" } },
          "settings": { "type": "array", "items": { "type": "string" } },
          "triggers": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}
```

6. meta/UNRELIABLE_NARRATOR.json

```json
{
  "type": "object",
  "required": ["lie_types", "lie_thresholds"],
  "properties": {
    "lie_types": {
      "type": "object",
      "patternProperties": {
        "^(denial|rationalization|projection|selective_amnesia)$": {
          "type": "object",
          "required": ["description", "examples", "detection", "frequency"],
          "properties": {
            "description": { "type": "string" },
            "examples": { "type": "array", "items": { "type": "string" } },
            "detection": { "type": "string" },
            "frequency": { "type": "string" }
          }
        }
      }
    },
    "lie_thresholds": { "type": "object" }
  }
}
```

7. environment/SENSORY_PROCESSING.json

```json
{
  "type": "object",
  "required": ["dominant_modality", "processing", "state_dependent_sensitivity"],
  "properties": {
    "dominant_modality": { "type": "string", "enum": ["visual", "auditory", "kinesthetic", "olfactory", "gustatory"] },
    "processing": {
      "type": "object",
      "patternProperties": {
        "^(visual|auditory|kinesthetic|olfactory|gustatory)$": {
          "type": "object",
          "required": ["acuity", "predicates", "triggers"],
          "properties": {
            "acuity": { "type": "string" },
            "predicates": { "type": "array", "items": { "type": "string" } },
            "triggers": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "state_dependent_sensitivity": { "type": "object" }
  }
}
```

8. psychology/IFS_PARTS.json

```json
{
  "type": "object",
  "required": ["parts", "part_transitions"],
  "properties": {
    "parts": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["role", "name", "active_levels", "speech", "body_language", "fears"],
        "properties": {
          "role": { "type": "string", "enum": ["manager", "exile", "firefighter", "self"] },
          "name": { "type": "string" },
          "active_levels": { "type": "array", "items": { "type": "string" } },
          "speech": { "type": "string" },
          "body_language": { "type": "string" },
          "fears": { "type": "string" }
        }
      }
    },
    "part_transitions": { "type": "object" }
  }
}
```

9. psychology/COGNITIVE_DISTORTIONS.json

```json
{
  "type": "object",
  "required": ["distortions", "distortion_level_map"],
  "properties": {
    "distortions": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["description", "examples", "active_levels", "trigger", "narrative_marker"],
        "properties": {
          "description": { "type": "string" },
          "examples": { "type": "array", "items": { "type": "string" } },
          "active_levels": { "type": "array", "items": { "type": "string" } },
          "trigger": { "type": "string" },
          "narrative_marker": { "type": "string" }
        }
      }
    },
    "distortion_level_map": { "type": "object" }
  }
}
```

10. dynamics/RIVALRY_TRIANGLE.json

```json
{
  "type": "object",
  "required": ["actors", "rules", "thresholds"],
  "properties": {
    "actors": { "type": "array", "items": { "type": "string" } },
    "rules": { "type": "object" },
    "thresholds": { "type": "object" }
  }
}
```

11. dynamics/CHARACTER_GROWTH_PATH.json

```json
{
  "type": "object",
  "required": ["arcs", "turning_points"],
  "properties": {
    "arcs": {
      "type": "array",
      "items": { "type": "object", "required": ["name", "progression"] }
    },
    "turning_points": {
      "type": "array",
      "items": { "type": "object", "required": ["level_from", "level_to", "trigger"] }
    }
  }
}
```

12. evolution/AROUSAL_AS_MOTIVATION.json

```json
{
  "type": "object",
  "required": ["theory", "effect_on_decision_making", "risk_perception_shift"],
  "properties": {
    "theory": { "type": "string" },
    "effect_on_decision_making": { "type": "string" },
    "risk_perception_shift": { "type": "string" }
  }
}
```

13. attachment/BEHAVIORAL_SYSTEMS.json

```json
{
  "type": "object",
  "required": ["attachment", "caregiving", "sexuality"],
  "properties": {
    "attachment": { "type": "object" },
    "caregiving": { "type": "object" },
    "sexuality": { "type": "object" }
  }
}
```

14. trauma_ptsd/THREE_LEVELS.json

```json
{
  "type": "object",
  "required": ["cognitive", "emotional", "bodily"],
  "properties": {
    "cognitive": { "type": "object" },
    "emotional": { "type": "object" },
    "bodily": { "type": "object" }
  }
}
```

15. psychology/VALUE_SYSTEM.json

```json
{
  "type": "object",
  "required": ["core_values", "value_conflicts", "value_shift_triggers"],
  "properties": {
    "core_values": { "type": "object" },
    "value_conflicts": { "type": "object" },
    "value_shift_triggers": { "type": "object" }
  }
}
```

16. psychology/DEFENSE_MECHANISMS.json

```json
{
  "type": "object",
  "required": ["levels", "triggers", "narrative_markers"],
  "properties": {
    "levels": {
      "type": "object",
      "properties": {
        "mature": { "type": "object" },
        "neurotic": { "type": "object" },
        "immature": { "type": "object" }
      }
    },
    "triggers": { "type": "object" },
    "narrative_markers": { "type": "object" }
  }
}
```

---

Документ 12 из 12. Версия 1.0.0

```

Файл 12 готов. Осталось создать шаблон `_TEMPLATE/INDEX.json` и исправленную версию `08_INDEX.json` с `default_ag_level`. Хотите, продолжу?