#!/bin/bash
set -euo pipefail

cd ~/voyage-narrative-engine

# Проверка jq
if ! command -v jq &> /dev/null; then
    pkg install -y jq
fi

echo "🎨 Меняем цвет волос Киры..."

# 1. KIRA_MODULE.json — hair_color + signature_features
jq '.variables.hair_color = "dark_blonde" | .visual.signature_features |= map(gsub("light_blonde"; "dark_blonde"))' personas/KIRA_MODULE.json > personas/KIRA_MODULE.json.tmp
mv personas/KIRA_MODULE.json.tmp personas/KIRA_MODULE.json

# 2. STATE_TEMPLATE.json — новый seed для нового цвета
jq '.visual.kira_seed = 54321 | .characters.kira.visual_seed = 54321' state/STATE_TEMPLATE.json > state/STATE_TEMPLATE.json.tmp
mv state/STATE_TEMPLATE.json.tmp state/STATE_TEMPLATE.json

# 3. Визуальные сцены (если есть light_blonde)
for f in visual/VISUAL_SCENE_*.json; do
    [[ -e "$f" ]] || continue
    sed -i 's/light_blonde/dark_blonde/g' "$f" 2>/dev/null || true
done

# 4. Git push
git add -A
git commit -m "feat: Kira hair light_blonde → dark_blonde"
git pull --rebase && git push

echo "✅ Готово! Кира теперь dark_blonde."
