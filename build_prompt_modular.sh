#!/bin/bash
# =============================================================================
# Voyage Modular Prompt Builder v1.1
# Dedicated script for building prompts from modular personas + scenarios
# Usage: bash build_prompt_modular.sh [scenario_id] [variant] [ag_level] [--separate]
#
# MODES:
#   default       — Single file PROMPT_MODULAR.txt (all-in-one)
#   --separate    — Separate files: PROMPT_SCENARIO.txt + PROMPT_[CHAR].txt + TRIGGER_GUIDE.txt
#
# This script calls scripts/python/build_prompt_modular.py
# which loads:
#   - Modular scenario from scenarios/[scenario_id]/
#   - Modular personas from personas/[id]/ (via runtime_loader.py)
#   - Speech matrices, initiatives, activities, relationships
#
# EXAMPLES:
#   bash build_prompt_modular.sh sauna_extended standard AG3
#   bash build_prompt_modular.sh sauna_extended standard AG3 --separate
#   bash build_prompt_modular.sh sauna_extended compact AG1
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCENARIO_ID="${1:-sauna_extended}"
VARIANT="${2:-standard}"
AG_LEVEL="${3:-AG3}"
PYTHON_SCRIPT="$REPO_DIR/scripts/python/build_prompt_modular.py"
OUTPUT="$REPO_DIR/PROMPT_MODULAR.txt"

# Check for --separate flag anywhere in args
SEPARATE_MODE=false
for arg in "$@"; do
    if [ "$arg" = "--separate" ]; then
        SEPARATE_MODE=true
    fi
done

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Voyage Modular Prompt Builder v1.1${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "Scenario: ${GREEN}$SCENARIO_ID${NC}"
echo -e "Variant:  ${GREEN}$VARIANT${NC}"
echo -e "AG Level: ${GREEN}$AG_LEVEL${NC}"
if [ "$SEPARATE_MODE" = true ]; then
    echo -e "Mode:     ${GREEN}SEPARATE (per-persona files)${NC}"
else
    echo -e "Mode:     ${GREEN}SINGLE FILE${NC}"
fi
echo ""

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[ERROR] Python not found. Please install Python 3.${NC}"
    exit 1
fi

# Check script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}[ERROR] Builder script not found: $PYTHON_SCRIPT${NC}"
    exit 1
fi

# Run builder
if [ "$SEPARATE_MODE" = true ]; then
    echo -e "${BLUE}Building SEPARATE prompts...${NC}"
    $PYTHON_CMD "$PYTHON_SCRIPT" "$SCENARIO_ID" "$VARIANT" "$AG_LEVEL" --separate
else
    echo -e "${BLUE}Building single-file prompt...${NC}"
    $PYTHON_CMD "$PYTHON_SCRIPT" "$SCENARIO_ID" "$VARIANT" "$AG_LEVEL"
fi

# Show results
if [ "$SEPARATE_MODE" = true ]; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  SEPARATE PROMPTS built successfully!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "Files created:"
    for f in PROMPT_SCENARIO.txt PROMPT_KIRA.txt PROMPT_MARINA.txt PROMPT_SERGEY.txt PROMPT_MAKSIM.txt PROMPT_ANDREY_SENIOR.txt TRIGGER_GUIDE.txt; do
        if [ -f "$REPO_DIR/$f" ]; then
            SIZE=$(wc -c < "$REPO_DIR/$f" | awk '{print $1}')
            SIZE_KB=$(awk "BEGIN {printf \"%.1f\", $SIZE/1024}")
            echo -e "  ${GREEN}✓${NC} $f (${SIZE_KB} KB)"
        fi
    done
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "  1. Load ${BLUE}PROMPT_SCENARIO.txt${NC} FIRST into LLM chat"
    echo -e "  2. Load personas on demand via triggers (see ${BLUE}TRIGGER_GUIDE.txt${NC})"
    echo -e "  3. Or load all persona files if context allows"
else
    if [ -f "$OUTPUT" ]; then
        SIZE=$(wc -c < "$OUTPUT" | awk '{print $1}')
        LINES=$(wc -l < "$OUTPUT" | awk '{print $1}')
        SIZE_KB=$(awk "BEGIN {printf \"%.1f\", $SIZE/1024}")
        
        echo ""
        echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  PROMPT built successfully!${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
        echo -e "Output: ${BLUE}$OUTPUT${NC}"
        echo -e "Size:   ${BLUE}$SIZE bytes ($SIZE_KB KB)${NC}"
        echo -e "Lines:  ${BLUE}$LINES${NC}"
        echo ""
        
        # Quick content check
        echo -e "${YELLOW}Content checks:${NC}"
        grep -q "РЕЧЕВАЯ МАТРИЦА" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Speech matrices included" || echo -e "  ${RED}✗${NC} Speech matrices missing"
        grep -q "АВТОНОМНЫЕ ИНИЦИАТИВЫ" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Initiatives included" || echo -e "  ${RED}✗${NC} Initiatives missing"
        grep -q "P1_entrance" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Scenario phases included" || echo -e "  ${RED}✗${NC} Scenario phases missing"
        grep -q "ФМДР" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} FMDR instructions included" || echo -e "  ${RED}✗${NC} FMDR instructions missing"
        echo ""
    else
        echo -e "${RED}[ERROR] Output file not created.${NC}"
        exit 1
    fi
fi
