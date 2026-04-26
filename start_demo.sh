#!/bin/bash
# Detection & Recovery — tmux launcher
# Usage: bash run.sh

PROJECT_DIR=~/Detection-Recovery-mini-proj
VENV=$PROJECT_DIR/venv/bin/activate

# ── Preflight: tmux ──────────────────────────────────────────────────────────

if ! command -v tmux &> /dev/null; then
  echo "[INFO] tmux not found — installing..."
  sudo apt install -y tmux 2>/dev/null || brew install tmux 2>/dev/null || {
    echo "[ERROR] Could not install tmux automatically. Run: sudo apt install tmux"
    exit 1
  }
fi

# ── Preflight: python3 ───────────────────────────────────────────────────────

if ! command -v python3 &> /dev/null; then
  echo "[ERROR] python3 is not installed."
  exit 1
fi

# ── Setup venv + dependencies ────────────────────────────────────────────────

if [ ! -f "$VENV" ]; then
  echo "[INFO] Creating virtual environment..."
  python3 -m venv $PROJECT_DIR/venv
fi

source $VENV

echo "[INFO] Installing dependencies..."
pip install -q -r $PROJECT_DIR/requirements.txt

# ── Kill any existing session ────────────────────────────────────────────────

tmux kill-session -t failover 2>/dev/null

# ── Create session: 3 panes ──────────────────────────────────────────────────
#
#  ┌─────────────────┬──────────────────┐
#  │  pane 0         │  pane 1          │
#  │  primary_server │  backup_server   │
#  ├─────────────────┴──────────────────┤
#  │  pane 2                            │
#  │  client_server                     │
#  └────────────────────────────────────┘

tmux new-session -d -s failover -x 220 -y 50

# Pane 0 — primary server (top left)
tmux send-keys -t failover:0.0 \
  "cd $PROJECT_DIR && source $VENV && python primary_server.py" Enter

# Pane 1 — backup server (top right)
tmux split-window -h -t failover:0.0
tmux send-keys -t failover:0.1 \
  "cd $PROJECT_DIR && source $VENV && python backup_server.py" Enter

# Pane 2 — client server (bottom, full width)
tmux split-window -v -t failover
tmux send-keys -t failover:0.2 \
  "cd $PROJECT_DIR && source $VENV && sleep 2 && python client_server.py" Enter

# ── Open dashboard in browser ────────────────────────────────────────────────

DASHBOARD="$PROJECT_DIR/dashboard.html"

sleep 1

if command -v xdg-open &> /dev/null; then
  xdg-open "$DASHBOARD" &
elif command -v open &> /dev/null; then
  open "$DASHBOARD" &
else
  echo "[INFO] Open dashboard manually: file://$DASHBOARD"
fi

# ── Attach ───────────────────────────────────────────────────────────────────

echo ""
echo "  ┌─ Detection & Recovery ─────────────────────────────┐"
echo "  │  Pane 0 (top-left)  : primary_server  :5000        │"
echo "  │  Pane 1 (top-right) : backup_server   :5001        │"
echo "  │  Pane 2 (bottom)    : client_server   :5002        │"
echo "  │                                                     │"
echo "  │  Dashboard → file://$DASHBOARD"
echo "  │                                                     │"
echo "  │  To simulate failover: use dashboard button        │"
echo "  │  To detach from tmux: Ctrl-B then D                │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""

tmux attach-session -t failover