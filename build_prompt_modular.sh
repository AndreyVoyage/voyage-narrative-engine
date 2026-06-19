#!/bin/bash
# =============================================================================
# Voyage Modular Prompt Builder v1.0
# Dedicated script for building prompts from modular personas + scenarios
# Usage: bash build_prompt_modular.sh [scenario_id] [variant] [ag_level]
#
# This script calls scripts/python/build_prompt_modular.py
# which loads:
#   - Modular scenario from scenarios/[scenario_id]/
#   - Modular personas from personas/[id]/ (via runtime_loader.py)
#   - Speech matrices, initiatives, activities, relationships
#
# EXAMPLES:
#   bash build_prompt_modular.sh sauna_extended standard AG3
#   bash build_prompt_modular.sh sauna_extended compact AG1
#   bash build_prompt_modular.sh sauna_extended extended AG4
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCENARIO_ID="${1:-sauna_extended}"
VARIANT="${2:-standard}"
AG_LEVEL="${3:-AG3}"
PYTHON_SCRIPT="$REPO_DIR/scripts/python/build_prompt_modular.py"
OUTPUT="$REPO_DIR/PROMPT_MODULAR.txt"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Voyage Modular Prompt Builder v1.0${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "Scenario: ${GREEN}$SCENARIO_ID${NC}"
echo -e "Variant:  ${GREEN}$VARIANT${NC}"
echo -e "AG Level: ${GREEN}$AG_LEVEL${NC}"
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
echo -e "${BLUE}Building prompt...${NC}"
$PYTHON_CMD "$PYTHON_SCRIPT" "$SCENARIO_ID" "$VARIANT" "$AG_LEVEL"

# Show results
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
    grep -q "silent_observation" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Sergey silent observation" || echo -e "  ${RED}✗${NC} Sergey silent observation missing"
    grep -q "preparing_tea" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Maksim tea activity" || echo -e "  ${RED}✗${NC} Maksim tea activity missing"
    grep -q "authority_gaze" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Andrey authority gaze" || echo -e "  ${RED}✗${NC} Andrey authority gaze missing"
    grep -q "P1_entrance" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} Scenario phases included" || echo -e "  ${RED}✗${NC} Scenario phases missing"
    grep -q "ФМДР" "$OUTPUT" && echo -e "  ${GREEN}✓${NC} FMDR instructions included" || echo -e "  ${RED}✗${NC} FMDR instructions missing"
    echo ""
    
    # Show first 200 chars of prompt
    echo -e "${YELLOW}Prompt preview (first 500 chars):${NC}"
    echo "---"
    head -c 500 "$OUTPUT"
    echo "..."
    echo "---"
else
    echo -e "${RED}[ERROR] Output file not created.${NC}"
    exit 1
fi
