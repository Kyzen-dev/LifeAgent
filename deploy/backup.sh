#!/usr/bin/env bash
# Consistent backup of LifeAgent data, safe while the bot is running.
#   bash deploy/backup.sh                 # writes ~/lifeagent-backups/lifeagent-YYYY-MM-DD_HHMM.tgz
# Daily at 04:00 with 14 days kept (add with `crontab -e`):
#   0 4 * * * mkdir -p ~/lifeagent-backups && cd ~/lifeagent && bash deploy/backup.sh >> ~/lifeagent-backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

DEST="${BACKUP_DIR:-$HOME/lifeagent-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$DEST"
stamp=$(date +%F_%H%M)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# SQLite online backup (a plain copy of a live WAL database can be inconsistent).
python3 - "$PWD/data/lifeagent.sqlite3" "$tmp/lifeagent.sqlite3" <<'PY'
import sqlite3, sys, os
src, dst = sys.argv[1], sys.argv[2]
if os.path.exists(src):
    with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
        s.backup(d)
PY

# Archive only what exists (a fresh install has no sessions yet); real tar errors still fail.
paths=()
for p in .env workspace/memory workspace/notes data/home/.claude; do
  [ -e "$p" ] && paths+=("$p")
done
db=()
[ -f "$tmp/lifeagent.sqlite3" ] && db=(-C "$tmp" lifeagent.sqlite3)
tar czf "$DEST/lifeagent-$stamp.tgz" "${db[@]}" -C "$PWD" "${paths[@]}"

find "$DEST" -name 'lifeagent-*.tgz' -mtime +"$KEEP_DAYS" -delete
echo "$(date '+%F %T') backup written: $DEST/lifeagent-$stamp.tgz ($(du -h "$DEST/lifeagent-$stamp.tgz" | cut -f1))"
