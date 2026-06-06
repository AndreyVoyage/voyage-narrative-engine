#!/bin/bash
# Собирает PROMPT.txt из модулей
# Использование: ./tools/assemble.sh [STATE_FILE] [сценарий]

STATE_FILE="${1:-state/TEMPLATE.json}"
SCENARIO="${2:-}"

# Определить имя сессии из STATE
SESSION=$(basename "$STATE_FILE" .json)

# Собрать PROMPT.txt
{
    echo "# VOYAGE NARRATIVE ENGINE"
    echo "# Session: ${SESSION}"
    echo "# Built: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo ""
    echo "[CORE]"
    cat core/VOYAGE_NARRATIVE_CORE.md
    echo ""
    echo "[PERSONAS]"
    echo "## KIRA"
    cat personas/KIRA_MODULE.json
    echo ""
    echo "## SERGEY"
    cat personas/SERGEY_MODULE.json
    echo ""
    echo "## USER (Я)"
    cat personas/USER_MODULE.json
    echo ""
    echo "[STATE]"
    cat "$STATE_FILE"
    echo ""
    echo "[SCENARIO]"
    if [ -n "$SCENARIO" ] && [ -f "$SCENARIO" ]; then
        cat "$SCENARIO"
    else
        echo "# Укажи сценарий: ./tools/assemble.sh state/POST_ACT1.json scenarios/acts/ACT_2_BAR.md"
    fi
} > PROMPT.txt

echo "PROMPT.txt собран ($(wc -c < PROMPT.txt) байт)"
