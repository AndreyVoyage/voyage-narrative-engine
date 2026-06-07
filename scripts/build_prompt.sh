#!/bin/bash
# build_prompt.sh — Автоматическая сборка PROMPT.txt для Voyage Narrative Engine
# Использование: ./build_prompt.sh [scenario_id] [participants...]
# Пример: ./build_prompt.sh sauna_quartet kira sergey marina

set -e

VOYAGE_HOME="${VOYAGE_HOME:-$HOME/voyage-narrative-engine}"
SCENARIO_ID="${1:-sauna_quartet}"
shift || true
PARTICIPANTS="${@:-kira sergey marina}"

OUTPUT_FILE="$VOYAGE_HOME/PROMPT.txt"
TEMP_DIR="$VOYAGE_HOME/.tmp"
mkdir -p "$TEMP_DIR"

echo "🔧 Voyage Prompt Builder v1.0"
echo "   Scenario: $SCENARIO_ID"
echo "   Participants: $PARTICIPANTS"
echo "   Output: $OUTPUT_FILE"
echo ""

# Проверка наличия файлов
check_file() {
    if [ ! -f "$1" ]; then
        echo "❌ ERROR: File not found: $1"
        exit 1
    fi
}

# 1. Системный промпт (CORE)
CORE_FILE="$VOYAGE_HOME/core/VOYAGE_NARRATIVE_CORE_v2.md"
if [ -f "$CORE_FILE" ]; then
    echo "✅ CORE loaded"
    cat "$CORE_FILE" > "$OUTPUT_FILE"
else
    echo "⚠️  CORE not found, using minimal system prompt"
    cat > "$OUTPUT_FILE" << 'EOF'
# SYSTEM PROMPT — Voyage Narrative Engine
Ты — Narrative Engine для интерактивной психологической сцены.
Формат: ФМДР (Мысли в скобках, Действия в звёздочках, Речь в кавычках).
Safety: СТОП/ХВАТИТ = emergency exit.
EOF
fi

echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# 2. Модули персонажей
for persona in $PARTICIPANTS; do
    MODULE_FILE="$VOYAGE_HOME/personas/${persona^^}_MODULE_*.json"
    # Находим последнюю версию
    LATEST=$(ls -t $VOYAGE_HOME/personas/${persona^^}_MODULE_*.json 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        echo "✅ Module loaded: $(basename $LATEST)"
        echo "# PERSONA: ${persona^^}" >> "$OUTPUT_FILE"
        cat "$LATEST" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "---" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    else
        echo "❌ Module not found for: $persona"
        exit 1
    fi
done

# 3. Сценарий
SCENARIO_FILE="$VOYAGE_HOME/scenarios/SCENARIO_${SCENARIO_ID^^}.json"
if [ -f "$SCENARIO_FILE" ]; then
    echo "✅ Scenario loaded: $(basename $SCENARIO_FILE)"
    echo "# SCENARIO: $SCENARIO_ID" >> "$OUTPUT_FILE"
    cat "$SCENARIO_FILE" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
else
    echo "⚠️  Scenario not found: $SCENARIO_FILE"
fi

# 4. State
STATE_FILE="$VOYAGE_HOME/state/STATE_TEMPLATE_v2.json"
if [ -f "$STATE_FILE" ]; then
    echo "✅ State loaded"
    echo "# STATE" >> "$OUTPUT_FILE"
    cat "$STATE_FILE" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
else
    echo "⚠️  State not found"
fi

# 5. Команда начать
cat >> "$OUTPUT_FILE" << 'EOF'
# COMMAND
НАЧНИ СЦЕНУ.
Опиши момент входа. Пользователь только что переступил порог.
Используй ФМДР для всех персонажей. Покажи их первые реакции, мысли, действия.
Пользователь — центр, но пока он только вошёл.
EOF

# Статистика
SIZE=$(wc -c < "$OUTPUT_FILE")
TOKENS=$((SIZE / 4))
echo ""
echo "✅ PROMPT.txt собран!"
echo "   Размер: $SIZE bytes (~$TOKENS tokens)"
echo "   Локация: $OUTPUT_FILE"
echo ""
echo "📋 Следующий шаг:"
echo "   1. Скопируйте PROMPT.txt в чат Kimi/DeepSeek"
echo "   2. Отправьте и начните сцену"
echo "   3. После сессии: ./update_state.sh"
