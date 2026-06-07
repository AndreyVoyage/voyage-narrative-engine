#!/bin/bash
# Voyage Update Deploy Script v2.0
# One-shot deployment: finds archive, unpacks, places files, commits.
# Usage: copy-paste entire script into Termux terminal

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Voyage Update Deploy Script v2.0 ===${NC}"

# Config
ARCHIVE_NAME="voyage_update_2026-06-08_v3.zip"
REPO_DIR="$HOME/voyage-narrative-engine"
TMP_DIR="$HOME/.voyage_deploy_tmp"

# Step 1: Find archive
echo -e "\n${BLUE}[1/7] Finding archive...${NC}"

ARCHIVE_PATH=""
for path in "$HOME/$ARCHIVE_NAME" "$HOME/storage/downloads/$ARCHIVE_NAME" "$REPO_DIR/$ARCHIVE_NAME" "$HOME/Downloads/$ARCHIVE_NAME" "$(pwd)/$ARCHIVE_NAME"; do
    if [ -f "$path" ]; then
        ARCHIVE_PATH="$path"
        echo -e "${GREEN}  Found: $path${NC}"
        break
    fi
done

if [ -z "$ARCHIVE_PATH" ]; then
    echo -e "${RED}  ERROR: Archive $ARCHIVE_NAME not found!${NC}"
    echo -e "${YELLOW}  Searched in:${NC}"
    echo -e "    - $HOME/$ARCHIVE_NAME"
    echo -e "    - $HOME/storage/downloads/$ARCHIVE_NAME"
    echo -e "    - $REPO_DIR/$ARCHIVE_NAME"
    echo -e "    - $HOME/Downloads/$ARCHIVE_NAME"
    echo -e "    - $(pwd)/$ARCHIVE_NAME"
    echo -e "\n${YELLOW}  Please download the archive and place it in ~/ or ~/storage/downloads/${NC}"
    exit 1
fi

# Step 2: Check repo
echo -e "\n${BLUE}[2/7] Checking repository...${NC}"
if [ ! -d "$REPO_DIR" ]; then
    echo -e "${YELLOW}  Repository not found. Cloning...${NC}"
    cd "$HOME"
    git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
    if [ ! -d "$REPO_DIR" ]; then
        echo -e "${RED}  ERROR: Failed to clone repository${NC}"
        exit 1
    fi
    echo -e "${GREEN}  Cloned successfully${NC}"
else
    echo -e "${GREEN}  Repository found: $REPO_DIR${NC}"
    cd "$REPO_DIR"
    echo -e "${YELLOW}  Current branch: $(git branch --show-current 2>/dev/null || echo 'unknown')${NC}"
fi

# Step 3: Create directories
echo -e "\n${BLUE}[3/7] Creating directory structure...${NC}"
mkdir -p "$REPO_DIR/sessions/raw"
mkdir -p "$REPO_DIR/sessions/state"
mkdir -p "$REPO_DIR/sessions/memory"
mkdir -p "$REPO_DIR/sessions/stories"
mkdir -p "$REPO_DIR/sessions/visuals"
mkdir -p "$REPO_DIR/roles"
mkdir -p "$REPO_DIR/docs"
mkdir -p "$REPO_DIR/schemas"
mkdir -p "$REPO_DIR/scripts/termux"
mkdir -p "$REPO_DIR/scripts/python"
mkdir -p "$REPO_DIR/assets/images/character_sessions/kira"
mkdir -p "$REPO_DIR/assets/images/character_sessions/sergey"
mkdir -p "$REPO_DIR/assets/images/character_sessions/marina"
mkdir -p "$REPO_DIR/assets/images/character_sessions/maksim"
echo -e "${GREEN}  Directories created${NC}"

# Step 4: Unpack archive
echo -e "\n${BLUE}[4/7] Unpacking archive...${NC}"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
cd "$TMP_DIR"

if ! unzip -o "$ARCHIVE_PATH" >/dev/null 2>&1; then
    echo -e "${RED}  ERROR: Failed to unzip archive${NC}"
    echo -e "${YELLOW}  Trying with pkg install unzip...${NC}"
    pkg install unzip -y
    unzip -o "$ARCHIVE_PATH" || exit 1
fi

echo -e "${GREEN}  Archive unpacked to $TMP_DIR${NC}"

# Step 5: Copy files with verification
echo -e "\n${BLUE}[5/7] Copying files...${NC}"

# Main script
if [ -f "$TMP_DIR/session_finalize.py" ]; then
    cp "$TMP_DIR/session_finalize.py" "$REPO_DIR/session_finalize.py"
    chmod +x "$REPO_DIR/session_finalize.py"
    echo -e "${GREEN}  ✓ session_finalize.py${NC}"
else
    echo -e "${YELLOW}  ⚠ session_finalize.py not found in archive${NC}"
fi

# README
if [ -f "$TMP_DIR/README.md" ]; then
    cp "$TMP_DIR/README.md" "$REPO_DIR/README.md"
    echo -e "${GREEN}  ✓ README.md${NC}"
fi

# Roles
if [ -d "$TMP_DIR/roles" ]; then
    for f in "$TMP_DIR/roles"/*.md; do
        [ -f "$f" ] && cp "$f" "$REPO_DIR/roles/" && echo -e "${GREEN}  ✓ roles/$(basename $f)${NC}"
    done
fi

# Docs
if [ -d "$TMP_DIR/docs" ]; then
    for f in "$TMP_DIR/docs"/*.md; do
        [ -f "$f" ] && cp "$f" "$REPO_DIR/docs/" && echo -e "${GREEN}  ✓ docs/$(basename $f)${NC}"
    done
fi

# Schemas
if [ -d "$TMP_DIR/schemas" ]; then
    for f in "$TMP_DIR/schemas"/*.json; do
        [ -f "$f" ] && cp "$f" "$REPO_DIR/schemas/" && echo -e "${GREEN}  ✓ schemas/$(basename $f)${NC}"
    done
fi

# Scripts
if [ -d "$TMP_DIR/scripts/termux" ]; then
    for f in "$TMP_DIR/scripts/termux"/*.sh; do
        [ -f "$f" ] && cp "$f" "$REPO_DIR/scripts/termux/" && chmod +x "$REPO_DIR/scripts/termux/$(basename $f)" && echo -e "${GREEN}  ✓ scripts/termux/$(basename $f)${NC}"
    done
fi

if [ -d "$TMP_DIR/scripts/python" ]; then
    for f in "$TMP_DIR/scripts/python"/*.py; do
        [ -f "$f" ] && cp "$f" "$REPO_DIR/scripts/python/" && echo -e "${GREEN}  ✓ scripts/python/$(basename $f)${NC}"
    done
fi

# Step 6: Verify
echo -e "\n${BLUE}[6/7] Verifying installation...${NC}"
cd "$REPO_DIR"

ERRORS=0

# Check main script
if [ ! -f "session_finalize.py" ]; then
    echo -e "${RED}  ✗ session_finalize.py missing${NC}"
    ERRORS=$((ERRORS+1))
else
    echo -e "${GREEN}  ✓ session_finalize.py present${NC}"
fi

# Check roles
ROLE_COUNT=$(ls roles/*.md 2>/dev/null | wc -l)
if [ "$ROLE_COUNT" -ge 3 ]; then
    echo -e "${GREEN}  ✓ roles/: $ROLE_COUNT files${NC}"
else
    echo -e "${YELLOW}  ⚠ roles/: only $ROLE_COUNT files (expected 4)${NC}"
fi

# Check sessions structure
for d in raw state memory stories visuals; do
    if [ -d "sessions/$d" ]; then
        echo -e "${GREEN}  ✓ sessions/$d/${NC}"
    else
        echo -e "${RED}  ✗ sessions/$d/ missing${NC}"
        ERRORS=$((ERRORS+1))
    fi
done

# Check Python
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 --version 2>&1)
    echo -e "${GREEN}  ✓ Python: $PY_VER${NC}"
else
    echo -e "${RED}  ✗ Python3 not found! Run: pkg install python3 -y${NC}"
    ERRORS=$((ERRORS+1))
fi

# Step 7: Git commit
echo -e "\n${BLUE}[7/7] Git commit...${NC}"
cd "$REPO_DIR"

# Configure git if needed
if [ -z "$(git config user.email 2>/dev/null)" ]; then
    git config user.email "voyage@local"
    git config user.name "Voyage Deploy"
    echo -e "${YELLOW}  Git user configured (temporary)${NC}"
fi

git add session_finalize.py README.md roles/ docs/ schemas/ scripts/ sessions/

if git diff --cached --quiet; then
    echo -e "${YELLOW}  Nothing new to commit (files already present?)${NC}"
else
    git commit -m "v2.1.0: add session_finalize.py, roles, docs, schemas, scripts

- session_finalize.py: one-file pipeline (State+Editor+Visual+Physiognomist)
- roles/: State Manager, Narrative Editor v1.1, Visual Extractor, Visual Physiognomist
- docs/: workflow analysis, session finalization guide, termux guide, deploy instructions
- schemas/: persona_schema_v3_2 with anatomic_anchor and generation_history
- scripts/: termux deploy, python consistency checker
- sessions/: folder structure for raw/state/memory/stories/visuals"
    echo -e "${GREEN}  ✓ Git commit created${NC}"
fi

# Cleanup
rm -rf "$TMP_DIR"
echo -e "${GREEN}  ✓ Temporary files cleaned${NC}"

# Summary
echo -e "\n${GREEN}=== DEPLOYMENT COMPLETE ===${NC}"
echo -e "${BLUE}Repository:${NC} $REPO_DIR"
echo -e "${BLUE}Files added:${NC}"
ls -1 "$REPO_DIR/session_finalize.py" "$REPO_DIR/roles"/*.md "$REPO_DIR/docs"/*.md 2>/dev/null | sed 's/^/  /'
echo -e "\n${BLUE}Next steps:${NC}"
echo -e "  1. Test: ${YELLOW}cd $REPO_DIR && python3 session_finalize.py --help${NC}"
echo -e "  2. Save a log: ${YELLOW}nano sessions/raw/session_2026-06-08.log${NC}"
echo -e "  3. Run: ${YELLOW}python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet${NC}"
echo -e "  4. Push: ${YELLOW}git push origin main${NC} (if needed)"
echo -e "\n${BLUE}Documentation:${NC}"
echo -e "  ${YELLOW}cat docs/RUNNING_IN_TERMUX.md${NC}"
echo -e "  ${YELLOW}cat README.md${NC}"
