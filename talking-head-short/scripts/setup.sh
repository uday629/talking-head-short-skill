#!/usr/bin/env bash
# One-time setup (safe to re-run). Prints the python to use: PY=...
command -v ffmpeg >/dev/null || { echo "ffmpeg missing → mac: brew install ffmpeg | linux: apt-get install -y ffmpeg"; exit 1; }
ENV=${THS_ENV:-$HOME/.thsenv}
[ -x "$ENV/bin/python" ] || ${PYTHON:-python3} -m venv "$ENV" >/dev/null 2>&1 || ENV=""
PY="${ENV:+$ENV/bin/}python3"; [ -n "$ENV" ] || PY=python3
$PY -m pip install -q --disable-pip-version-check numpy scipy pillow "opencv-python-headless<5" >/dev/null 2>&1
$PY -m pip install -q --disable-pip-version-check faster-whisper >/dev/null 2>&1
$PY -c "import numpy,scipy,PIL,cv2" 2>/dev/null || echo "WARN core libs missing"
$PY -c "import faster_whisper" 2>/dev/null && echo "whisper ok" || echo "whisper unavailable → transcript fallback (align_text.py)"
echo "PY=$PY"
