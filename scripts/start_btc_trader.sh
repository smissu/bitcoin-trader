#!/usr/bin/env bash
# start_btc_trader.sh — start the gap monitor under tmux
# Usage:
#   ./start_btc_trader.sh            # attached session (interactive)
#   ./start_btc_trader.sh -d         # detached session (default log file: trader_run.log)
#   ./start_btc_trader.sh -d -l /path/to/logfile -s my-session

set -euo pipefail

SESSION_NAME="btc-trader"
LOGFILE="$(pwd)/trader_run.log"
DETACHED=0
RECENT_BARS=""  # optional: pass through to bitcoin-trader via --recent-bars
DISPLAY_TZ=""   # optional: pass through to bitcoin-trader via --display-tz

show_help() {
  cat <<EOF
Usage: $0 [-d] [-s SESSION] [-l LOGFILE] [-r RECENT_BARS] [-z DISPLAY_TZ] [-f FORMAT]

Options:
  -d            Start tmux session detached (default: attached)
  -s SESSION    tmux session name (default: btc-trader)
  -l LOGFILE    When detached, redirect stdout/stderr to this file (default: ./trader_run.log)
  -r RECENT_BARS  Pass a --recent-bars value to the strategy (overrides default recent_bars)
  -z DISPLAY_TZ  Pass a --display-tz value to the strategy (e.g. 'Europe/Berlin' or 'UTC+1')
  -f FORMAT     Display tz format: 'full' (UTC + (local)) or 'local' (local-only)
  -h            Show this help
EOF
}

while getopts ":ds:l:r:z:f:h" opt; do
  case $opt in
    d) DETACHED=1 ;; 
    s) SESSION_NAME="$OPTARG" ;;
    l) LOGFILE="$OPTARG" ;;
    r) RECENT_BARS="$OPTARG" ;;
    z) DISPLAY_TZ="$OPTARG" ;;
    f) DISPLAY_TZ_FORMAT="$OPTARG" ;;
    h) show_help; exit 0 ;;
    *) show_help; exit 2 ;;
  esac
done

CMD="conda run -n bitcoin-trader --no-capture-output python /Users/ericsmith/Documents/bitcoin-trader/bitcoin-trader.py"
# Append recent-bars flag if provided
if [ -n "$RECENT_BARS" ]; then
  CMD="$CMD --recent-bars $RECENT_BARS"
fi
# Append display timezone if provided
if [ -n "$DISPLAY_TZ" ]; then
  CMD="$CMD --display-tz \"$DISPLAY_TZ\""
fi
# Append display tz format if provided
if [ -n "$DISPLAY_TZ_FORMAT" ]; then
  CMD="$CMD --display-tz-format $DISPLAY_TZ_FORMAT"
fi

if [ "$DETACHED" -eq 1 ]; then
  echo "Starting tmux session '$SESSION_NAME' detached; logging to $LOGFILE"
  mkdir -p "$(dirname "$LOGFILE")"
  tmux new -d -s "$SESSION_NAME" bash -lc "$CMD >> \"$LOGFILE\" 2>&1"
  echo "$SESSION_NAME started (detached). PID saved to tmux session state — use 'tmux attach -t $SESSION_NAME' to attach."
else
  echo "Starting tmux session '$SESSION_NAME' attached."
  exec tmux new -s "$SESSION_NAME" bash -lc "$CMD"
fi
