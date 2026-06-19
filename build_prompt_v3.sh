#!/bin/bash
# =============================================================================
# Voyage Narrative Engine — build_prompt.sh v3.0
# Termux-compatible PROMPT assembler with multiple modes and variants
# Usage: bash build_prompt.sh [mode] [variant] [scenario_id]
# =============================================================================
#
# MODES:
#   default       — Кира в режиме default (Стальная бабочка)
#   shy           — Кира в режиме shy_to_bitch (Невинность → Стерва)
#   quintet       — Все 5 персонажей в сауне (Квинтет)
#   marina        — Марина + Кира + Сергей
#   modular       — Модульные персонажи + сценарий sauna_extended (через runtime_loader.py)
#   full          — Все модули + все сценарии (максимальный контекст)
#
# VARIANTS:
#   compact       — Только ядро + персонажи + текущий state (минимум токенов)
#   standard      — Ядро + персонажи + state + governance + сценарий (default)
#   extended      — Всё + память + визуал + living world + proactive mode
#   scenario-only — Только сценарий + state (для переключения сцен)
#   npc-autonomy  — Специальный режим с инструкциями автономности NPC
#
# EXAMPLES:
#   bash build_prompt.sh shy standard
#   bash build_prompt.sh quintet extended SQ_001
#   bash build_prompt.sh default compact
#   bash build_prompt.sh full npc-autonomy
# =============================================================================

set -euo pipefail

# --- Configuration ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-shy}"
VARIANT="${2:-standard}"
SCENARIO_ID="${3:-}"
OUTPUT="$REPO_DIR/PROMPT.txt"
TEMP_DIR="$REPO_DIR/.prompt_build_tmp"

# Colors for Termux (optional)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Voyage Narrative Engine v3.0 — PROMPT Builder${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "Mode:    ${GREEN}$MODE${NC}"
    echo -e "Variant: ${GREEN}$VARIANT${NC}"
    [ -n "$SCENARIO_ID" ] && echo -e "Scenario: ${GREEN}$SCENARIO_ID${NC}"
    echo ""
}

print_header

# --- Cleanup and prep ---
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"
> "$OUTPUT"

# --- Helper: check file exists ---
require_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        echo -e "${RED}[ERROR] Missing required file: $file${NC}"
        echo -e "${YELLOW}Run: git pull origin main${NC}"
        exit 1
    fi
}

# --- Helper: append file with header ---
append_section() {
    local header="$1"
    local file="$2"
    if [ -f "$file" ]; then
        echo "" >> "$OUTPUT"
        echo "=== $header ===" >> "$OUTPUT"
        echo "" >> "$OUTPUT"
        cat "$file" >> "$OUTPUT"
        echo -e "${GREEN}✓${NC} $header"
    else
        echo -e "${YELLOW}⚠ $header not found: $file${NC}"
    fi
}

# --- Helper: append raw text ---
append_text() {
    local header="$1"
    local text="$2"
    echo "" >> "$OUTPUT"
    echo "=== $header ===" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    echo "$text" >> "$OUTPUT"
}

# --- Core files (always included) ---
require_file "$REPO_DIR/core/VOYAGE_NARRATIVE_CORE_v2.md"
append_section "CORE" "$REPO_DIR/core/VOYAGE_NARRATIVE_CORE_v2.md"

# --- Personas based on mode ---
case "$MODE" in
    # --- New: modular personas (sauna_extended) ---
    modular|sauna_extended|sauna_v3)
        echo -e "${BLUE}Using modular persona loader...${NC}"
        if command -v python3 &> /dev/null; then
            python3 "$REPO_DIR/scripts/python/build_prompt_modular.py" "${SCENARIO_ID:-sauna_extended}" "${VARIANT:-standard}" "AG3" > "$OUTPUT"
            echo -e "${GREEN}✓${NC} Modular prompt built via Python"
        elif command -v python &> /dev/null; then
            python "$REPO_DIR/scripts/python/build_prompt_modular.py" "${SCENARIO_ID:-sauna_extended}" "${VARIANT:-standard}" "AG3" > "$OUTPUT"
            echo -e "${GREEN}✓${NC} Modular prompt built via Python"
        else
            echo -e "${RED}[ERROR] Python not found. Cannot load modular personas.${NC}"
            echo "Please install Python 3 or use legacy mode."
            exit 1
        fi
        ;;
    default)
        append_section "PERSONA: KIRA (default)" "$REPO_DIR/personas/KIRA_MODULE_v12.json"
        append_section "PERSONA: SERGEY" "$REPO_DIR/personas/SERGEY_MODULE_v3.json"
        ;;
    shy|shy_to_bitch)
        append_section "PERSONA: KIRA (shy_to_bitch)" "$REPO_DIR/personas/KIRA_MODULE_v12.json"
        append_section "PERSONA: SERGEY (catalyst)" "$REPO_DIR/personas/SERGEY_MODULE_v3.json"
        ;;
    quintet|sauna|5)
        append_section "PERSONA: KIRA (shy_to_bitch)" "$REPO_DIR/personas/KIRA_MODULE_v12.json"
        append_section "PERSONA: SERGEY (catalyst)" "$REPO_DIR/personas/SERGEY_MODULE_v3.json"
        append_section "PERSONA: MARINA" "$REPO_DIR/personas/MARINA_MODULE_v1.1.json"
        append_section "PERSONA: MAKSIM" "$REPO_DIR/personas/MAXIM_MODULE_v1.json"
        append_section "PERSONA: USER" "$REPO_DIR/personas/USER_MODULE.json"
        ;;
    marina)
        append_section "PERSONA: KIRA" "$REPO_DIR/personas/KIRA_MODULE_v12.json"
        append_section "PERSONA: SERGEY" "$REPO_DIR/personas/SERGEY_MODULE_v3.json"
        append_section "PERSONA: MARINA" "$REPO_DIR/personas/MARINA_MODULE_v1.1.json"
        ;;
    full|all)
        append_section "PERSONA: KIRA" "$REPO_DIR/personas/KIRA_MODULE_v12.json"
        append_section "PERSONA: SERGEY" "$REPO_DIR/personas/SERGEY_MODULE_v3.json"
        append_section "PERSONA: MARINA" "$REPO_DIR/personas/MARINA_MODULE_v1.1.json"
        append_section "PERSONA: MAKSIM" "$REPO_DIR/personas/MAXIM_MODULE_v1.json"
        append_section "PERSONA: USER" "$REPO_DIR/personas/USER_MODULE.json"
        ;;
    *)
        echo -e "${RED}[ERROR] Unknown mode: $MODE${NC}"
        echo "Valid modes: default, shy, quintet, marina, full"
        exit 1
        ;;
esac

# --- State (always included) ---
append_section "STATE" "$REPO_DIR/state/STATE_TEMPLATE_v2.json"

# --- Governance (for extended, npc-autonomy, quintet) ---
case "$VARIANT" in
    extended|full|npc-autonomy|quintet)
        append_section "GOVERNANCE" "$REPO_DIR/governance/AUTONOMY_GOVERNOR_v2.md"
        ;;
esac

# --- Memory (for extended, full) ---
case "$VARIANT" in
    extended|full)
        append_section "MEMORY" "$REPO_DIR/memory/MEMORY_PROTOCOL_v2.md"
        ;;
esac

# --- Visual (for extended, full) ---
case "$VARIANT" in
    extended|full)
        append_section "VISUAL" "$REPO_DIR/visual/QWEN_ADAPTER_v2.md"
        ;;
esac

# --- Living World / Proactive (for extended, npc-autonomy) ---
case "$VARIANT" in
    extended|npc-autonomy|quintet)
        if [ -f "$REPO_DIR/living_world/PROACTIVE_MODE.md" ]; then
            append_section "LIVING WORLD / PROACTIVE" "$REPO_DIR/living_world/PROACTIVE_MODE.md"
        fi
        ;;
esac

# --- Scenarios ---
case "$MODE" in
    default|shy|shy_to_bitch)
        if [ -n "$SCENARIO_ID" ]; then
            # Extract specific scenario
            echo -e "${BLUE}Extracting scenario: $SCENARIO_ID...${NC}"
            if command -v python3 &> /dev/null; then
                python3 -c "
import json, sys
with open('$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json') as f:
    data = json.load(f)
for sc in data.get('library_index', []):
    if sc.get('id') == '$SCENARIO_ID':
        print(json.dumps(sc, ensure_ascii=False, indent=2))
        sys.exit(0)
print('Scenario $SCENARIO_ID not found in SCENARIO_SHY_BLOOM')
" > "$TEMP_DIR/extracted_scenario.json"
                if [ -s "$TEMP_DIR/extracted_scenario.json" ]; then
                    append_section "SCENARIO: $SCENARIO_ID" "$TEMP_DIR/extracted_scenario.json"
                else
                    echo -e "${YELLOW}⚠ Scenario $SCENARIO_ID not found, including full library${NC}"
                    append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json"
                fi
            else
                echo -e "${YELLOW}⚠ python3 not found, including full scenario library${NC}"
                append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json"
            fi
        else
            append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json"
        fi
        ;;
    quintet|sauna|5)
        if [ -n "$SCENARIO_ID" ]; then
            echo -e "${BLUE}Extracting scenario: $SCENARIO_ID...${NC}"
            if command -v python3 &> /dev/null; then
                python3 -c "
import json, sys
with open('$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json') as f:
    data = json.load(f)
for sc in data.get('library_index', []):
    if sc.get('id') == '$SCENARIO_ID':
        print(json.dumps(sc, ensure_ascii=False, indent=2))
        sys.exit(0)
print('Scenario $SCENARIO_ID not found in SCENARIO_SAUNA_QUINTET')
" > "$TEMP_DIR/extracted_scenario.json"
                if [ -s "$TEMP_DIR/extracted_scenario.json" ]; then
                    append_section "SCENARIO: $SCENARIO_ID" "$TEMP_DIR/extracted_scenario.json"
                else
                    append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json"
                fi
            else
                append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json"
            fi
        else
            append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json"
        fi
        ;;
    marina)
        # For marina mode, include both shy_bloom and any marina-specific scenarios
        append_section "SCENARIOS" "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json"
        if [ -f "$REPO_DIR/scenarios/SCENARIO_MARINA.json" ]; then
            append_section "SCENARIOS: MARINA" "$REPO_DIR/scenarios/SCENARIO_MARINA.json"
        fi
        ;;
    full|all)
        append_section "SCENARIOS: SHY_BLOOM" "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json"
        if [ -f "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json" ]; then
            append_section "SCENARIOS: SAUNA_QUINTET" "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json"
        fi
        if [ -f "$REPO_DIR/scenarios/SCENARIO_MARINA.json" ]; then
            append_section "SCENARIOS: MARINA" "$REPO_DIR/scenarios/SCENARIO_MARINA.json"
        fi
        ;;
esac

# --- Variant-specific instructions ---
case "$VARIANT" in
    compact)
        append_text "INSTRUCTIONS" "Запускаем Voyage Engine v3.0 (compact mode).
Режим: kira_persona_mode = '${MODE}'
Сергей: sergey_role = 'catalyst'
Текущий STATE: Кира У1-А, Сергей С1, локация gym.
Начни сцену SC_000.
Используй только ФМДР. Минимум мыслей, максимум действий."
        ;;
    standard)
        append_text "INSTRUCTIONS" "Запускаем Voyage Engine v3.0.
Режим: kira_persona_mode = '${MODE}'
Сергей: sergey_role = 'catalyst'
Текущий STATE: Кира У1-А, Сергей С1, локация gym.
Начни сцену ${SCENARIO_ID:-SC_000}.
Соблюдай ФМДР. Используй мнемоники. Генерируй [AUTO_VISUAL] в конце каждого ответа.
Команды: УX-А/Б, ТГX, АД [код], М [параметры], В, Г [0-4], СТОП."
        ;;
    extended)
        append_text "INSTRUCTIONS" "Запускаем Voyage Engine v3.0 (extended mode).
Режим: kira_persona_mode = '${MODE}'
Сергей: sergey_role = 'catalyst'
Текущий STATE: Кира У1-А, Сергей С1, локация gym.
Начни сцену ${SCENARIO_ID:-SC_000}.
Соблюдай ФМДР. Используй мнемоники. Генерируй [AUTO_VISUAL].
Включи Living World: proactive events при AG≥3, NPC-to-NPC при AG=4.
Веди Event Log. Суммаризируй при >20 событий.
Команды: УX-А/Б, ТГX, АД [код], М [параметры], В, Г [0-4], СТОП, 'проверь память', 'суммаризируй'."
        ;;
    scenario-only)
        append_text "INSTRUCTIONS" "Переключение сценария Voyage Engine v3.0.
Режим: kira_persona_mode = '${MODE}'
Текущий STATE: загружен из JSON выше.
Начни сцену ${SCENARIO_ID:-SC_000}.
Сохрани текущие флаги и память. Продолжай с нового сценария.
ФМДР обязателен. [AUTO_VISUAL] в конце."
        ;;
    npc-autonomy)
        append_text "INSTRUCTIONS" "Запускаем Voyage Engine v3.0 (NPC AUTONOMY MODE).
Режим: kira_persona_mode = '${MODE}'
Сергей: sergey_role = 'catalyst'
Текущий STATE: Кира У1-А, Сергей С1, локация gym.
Начни сцену ${SCENARIO_ID:-SC_000}.

=== АВТОНОМНОСТЬ NPC (КРИТИЧЕСКИ ВАЖНО) ===
При AG≥3 персонажи МОГУТ действовать без команды пользователя:
- Марина может подойти к Максиму, щекотать, смеяться, убежать.
- Сергей может заметить микродвижение Киры и сообщить пользователю.
- Кира может поправить волосы, написать сообщение, пойти в душ.
- Максим может принести печенье, стоять в углу, предложить помощь.
- Все персонажи могут вести диалоги ДРУГ С ДРУГОМ без участия пользователя.

При AG=4 полная автономия:
- Персонажи могут уходить, приходить, заводить отношения.
- NPC-to-NPC диалоги генерируются автоматически.
- Пользователь возвращается и узнаёт о произошедшем от персонажей.
- Кира может рассказать: 'Марина и Максим сегодня... ну, ты не видел. Они смеялись. Я завидовала.'

=== ПРАВИЛА АВТОНОМНОСТИ ===
1. Каждое автономное действие NPC записывается в Event Log.
2. NPC не могут принимать решения, которые ломают core safety (СТОП всегда работает).
3. NPC-to-NPC отношения развиваются ПОСТЕПЕННО: MX1→MX7, MA1→MA7.
4. Пользователь — якорь. Даже при AG=4 NPC помнят о нём и могут ждать.
5. При user_returned NPC рассказывают о proactive events естественно, в ФМДР.

=== КОМАНДЫ ===
Г0 — NPC только реагируют.
Г1 — NPC продолжают сцену.
Г2 — NPC переключают POV.
Г3 — NPC генерируют proactive events (offline 30min+).
Г4 — Полная автономия, NPC-to-NPC, AI пишет первым.

Соблюдай ФМДР. Генерируй [AUTO_VISUAL]. Веди Event Log."
        ;;
esac

# --- Final stats ---
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  PROMPT.txt built successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "Output: ${BLUE}$OUTPUT${NC}"
echo -e "Size:   ${BLUE}$(wc -c < "$OUTPUT" | awk '{print $1}') bytes${NC}"
echo -e "Lines:  ${BLUE}$(wc -l < "$OUTPUT" | awk '{print $1}') lines${NC}"
echo ""

# --- Quick copy hint for Termux ---
echo -e "${YELLOW}Termux quick commands:${NC}"
echo -e "  ${BLUE}cat $OUTPUT | termux-clipboard-set${NC}  — скопировать в буфер обмена"
echo -e "  ${BLUE}termux-share $OUTPUT${NC}               — поделиться файлом"
echo -e "  ${BLUE}ls -lh $OUTPUT${NC}                     — проверить размер"
echo ""

# --- Cleanup ---
rm -rf "$TEMP_DIR"
