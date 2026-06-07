#!/bin/bash
# =============================================================================
# deploy_from_archive.sh — Полное обновление Voyage Engine v3.0 (Quintet)
# Termux / Linux / macOS
# =============================================================================
# Что делает:
#   1. git pull origin main
#   2. Распаковка архива voyage_quintet_v3_update.zip
#   3. Распределение файлов по папкам
#   4. Обновление существующих файлов (README, QUICKSTART, build_prompt)
#   5. git add → commit → push
# =============================================================================
# Использование:
#   cd ~/voyage-narrative-engine
#   bash deploy_from_archive.sh [путь_к_архиву]
# =============================================================================

set -euo pipefail

# --- Configuration ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCHIVE_PATH="${1:-$REPO_DIR/voyage_quintet_v3_update.zip}"
BRANCH="main"
COMMIT_MSG="feat: v3.0 Quintet Update — Maxim, Sauna Quintet, NPC Autonomy"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Voyage Engine v3.0 — Deploy from Archive${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "Repo:    ${GREEN}$REPO_DIR${NC}"
    echo -e "Archive: ${GREEN}$ARCHIVE_PATH${NC}"
    echo ""
}

print_header

# --- Step 0: Check prerequisites ---
echo -e "${BLUE}[0/8] Checking prerequisites...${NC}"

if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Not a git repository: $REPO_DIR${NC}"
    exit 1
fi

if ! command -v unzip &> /dev/null; then
    echo -e "${YELLOW}Installing unzip...${NC}"
    pkg install unzip -y 2>/dev/null || apt-get install unzip -y 2>/dev/null || true
fi

if [ ! -f "$ARCHIVE_PATH" ]; then
    echo -e "${RED}[ERROR] Archive not found: $ARCHIVE_PATH${NC}"
    echo -e "${YELLOW}Download the archive first and place it in:${NC}"
    echo -e "  ${BLUE}$REPO_DIR/voyage_quintet_v3_update.zip${NC}"
    echo -e "${YELLOW}Or specify path:${NC}"
    echo -e "  ${BLUE}bash deploy_from_archive.sh /path/to/archive.zip${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All checks passed${NC}"

# --- Step 1: Git pull ---
echo ""
echo -e "${BLUE}[1/8] Git pull origin $BRANCH...${NC}"
git pull origin "$BRANCH" || {
    echo -e "${YELLOW}⚠ Pull failed or already up to date. Continuing...${NC}"
}

# --- Step 2: Backup existing files ---
echo ""
echo -e "${BLUE}[2/8] Creating backups...${NC}"
BACKUP_DIR="$REPO_DIR/.backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

for file in build_prompt.sh README.md QUICKSTART.md; do
    if [ -f "$REPO_DIR/$file" ]; then
        cp "$REPO_DIR/$file" "$BACKUP_DIR/"
        echo -e "  ${GREEN}✓${NC} Backed up: $file"
    fi
done

echo -e "  ${GREEN}✓${NC} Backups saved to: $BACKUP_DIR"

# --- Step 3: Unzip archive ---
echo ""
echo -e "${BLUE}[3/8] Unzipping archive...${NC}"
UNZIP_DIR="$REPO_DIR/.unzip_tmp_$$"
rm -rf "$UNZIP_DIR"
mkdir -p "$UNZIP_DIR"

unzip -o "$ARCHIVE_PATH" -d "$UNZIP_DIR"
echo -e "${GREEN}✓ Archive extracted to: $UNZIP_DIR${NC}"

# --- Step 4: Distribute files ---
echo ""
echo -e "${BLUE}[4/8] Distributing files to repository...${NC}"

# Create directories if missing
mkdir -p "$REPO_DIR/personas"
mkdir -p "$REPO_DIR/scenarios"
mkdir -p "$REPO_DIR/state"
mkdir -p "$REPO_DIR/governance"
mkdir -p "$REPO_DIR/docs"
mkdir -p "$REPO_DIR/living_world"

# Move new files
move_file() {
    local src="$1"
    local dst="$2"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        echo -e "  ${GREEN}✓${NC} $dst"
    else
        echo -e "  ${YELLOW}⚠ Missing in archive: $src${NC}"
    fi
}

move_file "$UNZIP_DIR/personas/MAXIM_MODULE_v1.json" "$REPO_DIR/personas/MAXIM_MODULE_v1.json"
move_file "$UNZIP_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json" "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json"
move_file "$UNZIP_DIR/state/STATE_TEMPLATE_QUINTET_v1.json" "$REPO_DIR/state/STATE_TEMPLATE_QUINTET_v1.json"
move_file "$UNZIP_DIR/governance/AUTONOMY_NPC_GUIDE_v3.md" "$REPO_DIR/governance/AUTONOMY_NPC_GUIDE_v3.md"
move_file "$UNZIP_DIR/build_prompt_v3.sh" "$REPO_DIR/build_prompt_v3.sh"
move_file "$UNZIP_DIR/docs/README_QUINTET_UPDATE.md" "$REPO_DIR/docs/README_QUINTET_UPDATE.md"

# --- Step 5: Update existing files ---
echo ""
echo -e "${BLUE}[5/8] Updating existing project files...${NC}"

# 5.1 Update build_prompt.sh — create symlink or replace
if [ -f "$REPO_DIR/build_prompt.sh" ]; then
    # Save old version
    mv "$REPO_DIR/build_prompt.sh" "$REPO_DIR/build_prompt_v2_legacy.sh"
    echo -e "  ${GREEN}✓${NC} Old build_prompt.sh → build_prompt_v2_legacy.sh"
fi

# Make v3 executable and link as default
chmod +x "$REPO_DIR/build_prompt_v3.sh"
ln -sf "$REPO_DIR/build_prompt_v3.sh" "$REPO_DIR/build_prompt.sh"
echo -e "  ${GREEN}✓${NC} build_prompt.sh → build_prompt_v3.sh (symlink)"

# 5.2 Update README.md — append quintet section
if [ -f "$REPO_DIR/README.md" ]; then
    # Check if already updated
    if ! grep -q "Quintet Update" "$REPO_DIR/README.md"; then
        cat >> "$REPO_DIR/README.md" << 'EOF'

---

## 🆕 Что нового в v3.0 (Quintet Update)

### Новые персонажи
- **Максим** — лояльный неуклюжий гигант, друг Сергея. 7 уровней дуги (MX1-MX7).

### Новые сценарии
- **Квинтет** — все 5 персонажей в сауне (SQ_000 — SQ_007). От входа до ухода.

### Автономность NPC
- При AG≥3 персонажи действуют без пользователя: отправляют сообщения, взаимодействуют друг с другом.
- При AG=4 полная автономия: AI пишет первым, NPC заводят отношения.

### Новые команды
- `bash build_prompt.sh quintet standard` — сборка для квинтета
- `bash build_prompt.sh quintet npc-autonomy` — с автономностью NPC
- `Г3` / `живой мир` — proactive events
- `Г4` / `автопилот` — полная автономия NPC

### Файлы
- `personas/MAXIM_MODULE_v1.json` — новый персонаж
- `scenarios/SCENARIO_SAUNA_QUINTET.json` — сценарий квинтета
- `state/STATE_TEMPLATE_QUINTET_v1.json` — state для 5 персонажей
- `governance/AUTONOMY_NPC_GUIDE_v3.md` — гайд автономности
- `build_prompt_v3.sh` — обновлённый скрипт сборки
EOF
        echo -e "  ${GREEN}✓${NC} README.md updated with Quintet section"
    else
        echo -e "  ${YELLOW}⚠ README.md already has Quintet section${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ README.md not found, skipping${NC}"
fi

# 5.3 Update QUICKSTART.md — append quintet section
if [ -f "$REPO_DIR/QUICKSTART.md" ]; then
    if ! grep -q "Квинтет" "$REPO_DIR/QUICKSTART.md"; then
        cat >> "$REPO_DIR/QUICKSTART.md" << 'EOF'

---

### Квинтет (5 персонажей в сауне)

```bash
# Сборка PROMPT.txt для квинтета
bash build_prompt.sh quintet standard

# С автономностью NPC (AG3)
bash build_prompt.sh quintet npc-autonomy

# Конкретная сцена
bash build_prompt.sh quintet standard SQ_001
```

Стартовая команда для квинтета:
```
Запускаем Voyage Engine v3.0.
Режим: kira_persona_mode = "shy_to_bitch"
Сергей: sergey_role = "catalyst"
Марина: marina_level = MA1
Максим: maksim_level = MX1
Текущий STATE: Квинтет, сауна, вечер.
Начни сцену SQ_000.
```

### Управление автономностью NPC

| Команда | Эффект |
|---------|--------|
| `Г3` или `живой мир` | AG=3. NPC отправляют сообщения, взаимодействуют друг с другом. |
| `Г4` или `автопилот` | AG=4. Полная автономия. AI пишет первым. |
| `что делали?` | NPC рассказывают о proactive events. |
| `Сергей, что видел?` | Сергей сообщает о микродвижениях Киры. |
| `Марина, где была?` | Марина рассказывает о своих действиях. |
EOF
        echo -e "  ${GREEN}✓${NC} QUICKSTART.md updated with Quintet section"
    else
        echo -e "  ${YELLOW}⚠ QUICKSTART.md already has Quintet section${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ QUICKSTART.md not found, skipping${NC}"
fi

# 5.4 Update AGENTS.md if exists — add Maxim reference
if [ -f "$REPO_DIR/AGENTS.md" ]; then
    if ! grep -q "MAXIM_MODULE" "$REPO_DIR/AGENTS.md"; then
        cat >> "$REPO_DIR/AGENTS.md" << 'EOF'

---

## v3.0 Agents Reference

### Maxim (Максим)
- File: `personas/MAXIM_MODULE_v1.json`
- Role: loyal_clumsy_giant, friend of Sergey
- Levels: MX1 (cautious) → MX7 (integrated)
- Key trait: physically strong, emotionally careful, fears hurting others
- Sauna role: grounds the group, comic relief, unexpected depth

### Quintet Scenario
- File: `scenarios/SCENARIO_SAUNA_QUINTET.json`
- 8 scenes: SQ_000 (entrance) → SQ_007 (departure)
- Multi-character dynamics: Kira↔Marina (sisters), Sergey↔Maxim (brothers), Marina↔Maxim (sunshine & giant)

### NPC Autonomy
- File: `governance/AUTONOMY_NPC_GUIDE_v3.md`
- AG3: proactive events, NPC-to-NPC observations
- AG4: full autonomy, AI writes first, NPC relationships develop without user
EOF
        echo -e "  ${GREEN}✓${NC} AGENTS.md updated with v3.0 reference"
    else
        echo -e "  ${YELLOW}⚠ AGENTS.md already has v3.0 reference${NC}"
    fi
fi

# 5.5 Update .gitignore if needed
if [ -f "$REPO_DIR/.gitignore" ]; then
    if ! grep -q "backup" "$REPO_DIR/.gitignore"; then
        echo -e "\n# Deployment backups\n.backup_*\n.unzip_tmp_*" >> "$REPO_DIR/.gitignore"
        echo -e "  ${GREEN}✓${NC} .gitignore updated with backup exclusions"
    fi
fi

# --- Step 6: Verify file structure ---
echo ""
echo -e "${BLUE}[6/8] Verifying file structure...${NC}"

verify_file() {
    local file="$1"
    if [ -f "$file" ]; then
        local size=$(wc -c < "$file" | awk '{print $1}')
        echo -e "  ${GREEN}✓${NC} $(basename "$file") (${size} bytes)"
    else
        echo -e "  ${RED}✗${NC} MISSING: $file"
    fi
}

verify_file "$REPO_DIR/personas/MAXIM_MODULE_v1.json"
verify_file "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json"
verify_file "$REPO_DIR/state/STATE_TEMPLATE_QUINTET_v1.json"
verify_file "$REPO_DIR/governance/AUTONOMY_NPC_GUIDE_v3.md"
verify_file "$REPO_DIR/build_prompt_v3.sh"
verify_file "$REPO_DIR/build_prompt.sh"
verify_file "$REPO_DIR/docs/README_QUINTET_UPDATE.md"

# --- Step 7: Git commit ---
echo ""
echo -e "${BLUE}[7/8] Git commit...${NC}"

git add -A
git status --short

echo ""
read -p "Press ENTER to commit and push, or Ctrl+C to cancel..."

git commit -m "$COMMIT_MSG" || {
    echo -e "${YELLOW}⚠ Nothing to commit (already up to date)${NC}"
}

# --- Step 8: Git push ---
echo ""
echo -e "${BLUE}[8/8] Git push...${NC}"
git push origin "$BRANCH"

# --- Cleanup ---
rm -rf "$UNZIP_DIR"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Deploy complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Updated files:${NC}"
ls -lh "$REPO_DIR/personas/MAXIM_MODULE_v1.json" 2>/dev/null
ls -lh "$REPO_DIR/scenarios/SCENARIO_SAUNA_QUINTET.json" 2>/dev/null
ls -lh "$REPO_DIR/state/STATE_TEMPLATE_QUINTET_v1.json" 2>/dev/null
ls -lh "$REPO_DIR/governance/AUTONOMY_NPC_GUIDE_v3.md" 2>/dev/null
ls -lh "$REPO_DIR/build_prompt_v3.sh" 2>/dev/null
ls -lh "$REPO_DIR/build_prompt.sh" 2>/dev/null
echo ""
echo -e "${BLUE}Quick test:${NC}"
echo -e "  ${GREEN}bash $REPO_DIR/build_prompt.sh quintet standard${NC}"
echo -e "  ${GREEN}bash $REPO_DIR/build_prompt.sh quintet npc-autonomy SQ_000${NC}"
echo ""
echo -e "${YELLOW}Backups saved to:${NC} ${BLUE}$BACKUP_DIR${NC}"
