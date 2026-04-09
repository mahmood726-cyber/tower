#!/usr/bin/env bash
#
# Tower tmux session starter
# Starts the Tower tmux session with 12 windows (4 streams x 3 windows each)
#
# Usage: ./tmux_start.sh
#
# If tmuxp is available, uses the tmuxp configuration.
# Otherwise, creates the session manually with tmux commands.
#

set -e

SESSION_NAME="tower"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"
TMUXP_CONFIG="$HOME/.tmuxp/tower.yaml"

# Window names (12 total)
WINDOWS=(
    "apps_dev1"
    "apps_dev2"
    "apps_check"
    "methods_dev1"
    "methods_dev2"
    "methods_check"
    "hta_dev1"
    "hta_dev2"
    "hta_check"
    "live_dev1"
    "live_dev2"
    "live_check"
)

echo "============================================================"
echo "Tower tmux Session Starter"
echo "Session name: $SESSION_NAME"
echo "============================================================"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "ERROR: tmux is not installed."
    echo "Install with: sudo apt install tmux"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists."
    echo "Attaching to existing session..."
    exec tmux attach-session -t "$SESSION_NAME"
fi

# Try tmuxp first if available
if command -v tmuxp &> /dev/null && [ -f "$TMUXP_CONFIG" ]; then
    echo "Using tmuxp to create session..."
    tmuxp load -d "$TMUXP_CONFIG"
    echo "Session created. Attaching..."
    exec tmux attach-session -t "$SESSION_NAME"
fi

# Fallback: Create session manually
echo "Creating session manually (tmuxp not available or config missing)..."

# Create session with first window
tmux new-session -d -s "$SESSION_NAME" -n "${WINDOWS[0]}"
tmux send-keys -t "$SESSION_NAME:${WINDOWS[0]}" "echo 'TOWER window: ${WINDOWS[0]}'" Enter

# Create remaining windows
for ((i=1; i<${#WINDOWS[@]}; i++)); do
    window="${WINDOWS[$i]}"
    tmux new-window -t "$SESSION_NAME" -n "$window"
    tmux send-keys -t "$SESSION_NAME:$window" "echo 'TOWER window: $window'" Enter
done

# Go back to first window
tmux select-window -t "$SESSION_NAME:${WINDOWS[0]}"

echo "Session '$SESSION_NAME' created with ${#WINDOWS[@]} windows."
echo "Attaching..."
exec tmux attach-session -t "$SESSION_NAME"
