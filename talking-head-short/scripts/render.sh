#!/usr/bin/env bash
# Parallel render: bash render.sh PY WORKDIR [N]   (N parts in parallel, default = CPU cores up to 6)
PY=$1; WD=$2; N=${3:-$( (sysctl -n hw.ncpu 2>/dev/null || nproc) | awk '{print ($1>6)?6:$1}')}
D=$(cd "$(dirname "$0")" && pwd)
for i in $(seq 0 $((N-1))); do "$PY" "$D/engine.py" "$WD" --render --part $i/$N > "$WD/part$i.log" 2>&1 & done
wait
"$PY" "$D/engine.py" "$WD" --concat $N && rm -f "$WD"/video.part*.mp4 "$WD"/part*.log "$WD/parts.txt"
