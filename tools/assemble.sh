#!/bin/bash
# Собирает PROMPT.txt из модулей
# Использование: ./tools/assemble.sh [номер_сессии] [сценарий]

SESSION="${1:-SN_001}"
SCENARIO="${2:-}"

# Создать STATE если нет
if [ ! -f "state/sessions/${SESSION}.json" ]; then
    cp state/TEMPLATE.json "state/sessions/${SESSION}.json"
    echo "Создан state/sessions/${SESSION}.json"
fi

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
    echo "[STATE]"
    cat "state/sessions/${SESSION}.json"
    echo ""
    echo "[SCENARIO]"
    if [ -n "$SCENARIO" ] && [ -f "$SCENARIO" ]; then
        cat "$SCENARIO"
    else
        echo "# Укажи сценарий: ./tools/assemble.sh SN_001 scenarios/acts/ACT_2_BAR.md"
    fi
} > PROMPT.txt

echo "PROMPT.txt собран ($(wc -c < PROMPT.txt) байт)"
