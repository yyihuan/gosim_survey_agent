#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec /usr/bin/python3 -B scripts/run_current.py --run-id "local-L1-$(date +%Y%m%d-%H%M%S)-$$" --card L1 --exclusive
