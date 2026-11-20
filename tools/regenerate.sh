#!/bin/bash
# Regenerate the reader. Everything project-specific comes from config.json.
#   ./regenerate.sh            -> chapters 1-10 (default)
#   ./regenerate.sh 1-30       -> a range
#   ./regenerate.sh all        -> every chapter
#   CONFIG=other.json ./regenerate.sh all
set -e
cd "$(dirname "$0")"
CFG="${CONFIG:-config.json}"
OUT="${OUTDIR:-..}"
if [ "${1:-1-10}" = "all" ]; then FLAG="--all"; else FLAG="--chapters ${1:-1-10}"; fi

python3 generate.py     "$OUT"            --config "$CFG" $FLAG
python3 build_draft.py  "$OUT/draft.html" --config "$CFG" $FLAG
python3 build_sync.py   "$OUT/sync.html"  --config "$CFG" $FLAG
python3 build_corpus.py "$OUT/corpus.js"  --config "$CFG"
echo "done -> $(cd "$OUT" && pwd)"
