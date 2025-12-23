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
SUMMARY_GAPS="" # optional: which gaps to include in periodic summaries (--summary-gaps)

show_help() {
  cat <<EOF
Usage: $0 [-d] [-s SESSION] [-l LOGFILE] [-r RECENT_BARS] [-z DISPLAY_TZ] [-f FORMAT] [-g SUMMARY_GAPS]

Options:
  -d            Start tmux session detached (default: attached)
  -s SESSION    tmux session name (default: btc-trader)
  -l LOGFILE    When detached, redirect stdout/stderr to this file (default: ./trader_run.log)
  -r RECENT_BARS  Pass a --recent-bars value to the strategy (overrides default recent_bars)
  -z DISPLAY_TZ  Pass a --display-tz value to the strategy (e.g. 'Europe/Berlin' or 'UTC+1')
  -f FORMAT     Display tz format: 'full' (UTC + (local)) or 'local' (local-only)
  -g SUMMARY_GAPS  Which gap types to include in periodic summaries (both, up, down)
  -h            Show this help
EOF
}

# Pre-parse long-form options (support --summary-gaps and --summary-gaps=val)
TEMP_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --summary-gaps)
      SUMMARY_GAPS="$2"
      shift 2
      ;;
    --summary-gaps=*)
      SUMMARY_GAPS="${1#*=}"
      shift
      ;;
    *) TEMP_ARGS+=("$1")
      shift
      ;;
  esac
done
set -- "${TEMP_ARGS[@]}"

while getopts ":ds:l:r:z:f:g:h" opt; do
  case $opt in
    d) DETACHED=1 ;; 
    s) SESSION_NAME="$OPTARG" ;;
    l) LOGFILE="$OPTARG" ;;
    r) RECENT_BARS="$OPTARG" ;;
    z) DISPLAY_TZ="$OPTARG" ;;
    f) DISPLAY_TZ_FORMAT="$OPTARG" ;;
    g) SUMMARY_GAPS="$OPTARG" ;;
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
# Append summary gaps option if provided
if [ -n "$SUMMARY_GAPS" ]; then
  CMD="$CMD --summary-gaps $SUMMARY_GAPS"
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
