#!/bin/bash
# Build PROMPT.txt for LLM session
# Usage: bash build_prompt.sh [mode] [scenario_id]
# mode: default | shy_to_bitch
# scenario_id: optional, e.g. SC_001-A

REPO_DIR="$(dirname "$0")"
MODE="${1:-shy_to_bitch}"
SCENARIO_ID="${2:-}"
OUTPUT="$REPO_DIR/PROMPT.txt"

echo "Building PROMPT.txt for mode: $MODE"

# Core
cat "$REPO_DIR/core/VOYAGE_NARRATIVE_CORE_v2.md" > "$OUTPUT"
echo "" >> "$OUTPUT"
echo "=== PERSONA: KIRA ===" >> "$OUTPUT"
cat "$REPO_DIR/personas/KIRA_MODULE_v12.json" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "=== PERSONA: SERGEY ===" >> "$OUTPUT"
cat "$REPO_DIR/personas/SERGEY_MODULE_v3.json" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "=== STATE ===" >> "$OUTPUT"
cat "$REPO_DIR/state/STATE_TEMPLATE_v2.json" >> "$OUTPUT"

# Scenario if specified
if [ -n "$SCENARIO_ID" ]; then
    echo "" >> "$OUTPUT"
    echo "=== SCENARIO: $SCENARIO_ID ===" >> "$OUTPUT"
    # Extract scenario from SCENARIO_SHY_BLOOM.json (requires python or jq)
    if command -v python3 &> /dev/null; then
        python3 -c "
import json, sys
with open('$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json') as f:
    data = json.load(f)
    for sc in data.get('library_index', []):
        if sc.get('id') == '$SCENARIO_ID':
            print(json.dumps(sc, ensure_ascii=False, indent=2))
            sys.exit(0)
    print('Scenario not found')
" >> "$OUTPUT"
    else
        echo "[WARNING] python3 not found. Cannot extract specific scenario. Full scenario file included." >> "$OUTPUT"
        cat "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json" >> "$OUTPUT"
    fi
else
    echo "" >> "$OUTPUT"
    echo "=== SCENARIOS ===" >> "$OUTPUT"
    cat "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json" >> "$OUTPUT"
fi

echo ""
echo "=== INSTRUCTIONS ===" >> "$OUTPUT"
echo "Запускаем Voyage Engine v2.0." >> "$OUTPUT"
echo "Режим: kira_persona_mode = '$MODE'" >> "$OUTPUT"
echo "Сергей: sergey_role = 'catalyst'" >> "$OUTPUT"
echo "Текущий STATE: Кира У1-А, Сергей С1, локация gym." >> "$OUTPUT"
if [ -n "$SCENARIO_ID" ]; then
    echo "Начни сцену $SCENARIO_ID." >> "$OUTPUT"
else
    echo "Начни сцену SC_000." >> "$OUTPUT"
fi

echo ""
echo "PROMPT.txt built successfully: $OUTPUT"
echo "Size: $(wc -c < $OUTPUT) bytes"
