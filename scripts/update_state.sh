#!/bin/bash
# update_state.sh — Обновление STATE.json после сессии
# Использование: ./update_state.sh [session_notes_file]
# Пример: ./update_state.sh session_notes.txt

set -e

VOYAGE_HOME="${VOYAGE_HOME:-$HOME/voyage-narrative-engine}"
STATE_FILE="$VOYAGE_HOME/state/STATE_TEMPLATE_v2.json"
BACKUP_DIR="$VOYAGE_HOME/backups"
mkdir -p "$BACKUP_DIR"

NOTES_FILE="${1:-}"

echo "📝 Voyage State Updater v1.0"
echo "   State file: $STATE_FILE"
echo ""

# Бэкап текущего state
if [ -f "$STATE_FILE" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    cp "$STATE_FILE" "$BACKUP_DIR/STATE_${TIMESTAMP}.json"
    echo "✅ Backup created: STATE_${TIMESTAMP}.json"
fi

# Инструкция для пользователя
cat << 'EOF'

📋 Как обновить STATE после сессии:

1. Скопируйте ключевые события из чата в файл session_notes.txt:
   - Какие уровни достигли персонажи?
   - Какие флаги установлены (kissed, phone_exchanged)?
   - Как изменились trust/attraction?
   - Какие emotional anchors активированы?

2. Пример session_notes.txt:
   ---
   Session: sauna_2026_06_07
   Kira: U2-A → U3-A (after pool splash)
   Marina: U1-B → U2-A (after tea ritual)
   Sergey: S2 → S3 (ally mode)
   Flags: sauna_visited=true, kira_flirt_initiated=true, marina_first_smile=true
   Trust: Kira→User: 75→80, Marina→User: 40→55
   Attraction: Kira→User: 85→90, Marina→User: 35→50
   Key events: kira_accidental_touch, pool_splashed, deep_talk_unlocked
   ---

3. Запустите: ./update_state.sh session_notes.txt

EOF

if [ -n "$NOTES_FILE" ] && [ -f "$NOTES_FILE" ]; then
    echo "✅ Processing notes: $NOTES_FILE"
    # Здесь можно добавить парсинг, но пока — ручное обновление
    echo "⚠️  Автоматический парсинг пока не реализован."
    echo "   Пожалуйста, обновите STATE_TEMPLATE_v2.json вручную:"
    echo "   - Откройте $STATE_FILE"
    echo "   - Обновите current_level для каждого персонажа"
    echo "   - Обновите trust_levels, attraction_levels"
    echo "   - Обновите flags"
    echo "   - Добавьте записи в audit_log"
    echo ""
    echo "💡 Совет: Используйте JSON-Patch из отчёта Persona Analyst."
else
    echo "ℹ️  No notes file provided. Manual update required."
fi

echo ""
echo "✅ State update instructions printed."
echo "   Next: git add state/ && git commit -m 'update state after session'"
