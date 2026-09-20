#!/usr/bin/env bash
# Full pipeline: download -> run -> figures -> summary -> report -> README -> notebook -> tests.
# Usage: scripts/run_all.sh [--skip-download] [--fast]
set -euo pipefail
cd "$(dirname "$0")/.."
[[ " $* " == *" --skip-download "* ]] || python tools/download.py
FAST=""; [[ " $* " == *" --fast "* ]] && FAST="--fast"
python -m d1basis run $FAST
python scripts/plots.py
python scripts/summarize.py
python scripts/report.py
python scripts/readme.py
python scripts/make_notebook.py
python -m pytest
echo done
