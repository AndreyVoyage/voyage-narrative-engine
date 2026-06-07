#!/bin/bash
# Update STATE from LLM response
# Usage: bash update_state.sh [state_file] [new_level] [new_sublevel] [flags...]

STATE_FILE="${1:-$HOME/voyage-narrative-engine/state/STATE_TEMPLATE_v2.json}"
NEW_LEVEL="$2"
NEW_SUBLEVEL="$3"
shift 3
NEW_FLAGS="$@"

if [ ! -f "$STATE_FILE" ]; then
    echo "[ERROR] State file not found: $STATE_FILE"
    exit 1
fi

if [ -z "$NEW_LEVEL" ] || [ -z "$NEW_SUBLEVEL" ]; then
    echo "Usage: bash update_state.sh [state_file] [U1-U7] [A|B] [flag1 flag2 ...]"
    exit 1
fi

# Update using python3 if available
if command -v python3 &> /dev/null; then
    python3 -c "
import json, sys, datetime
with open('$STATE_FILE', 'r') as f:
    state = json.load(f)

state['timestamp'] = datetime.datetime.now().isoformat() + 'Z'
state['characters']['kira']['level'] = '$NEW_LEVEL'
state['characters']['kira']['sublevel'] = '$NEW_SUBLEVEL'
state['characters']['kira']['full_level'] = '$NEW_LEVEL-$NEW_SUBLEVEL'

for flag in '$NEW_FLAGS'.split():
    if flag:
        state['flags'][flag] = True

with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f'[OK] State updated: {NEW_LEVEL}-{NEW_SUBLEVEL}')
print(f'[OK] Flags set: {NEW_FLAGS}')
"
else
    echo "[ERROR] python3 required for state updates"
    exit 1
fi
