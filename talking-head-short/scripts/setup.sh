#!/usr/bin/env bash
# One-time setup (safe to re-run). Works on a laptop and inside Claude's code sandbox.
# Prints the python to use: PY=...
ENV=${THS_ENV:-$HOME/.thsenv}
PY=python3
if [ -x "$ENV/bin/python3" ] || python3 -m venv "$ENV" >/dev/null 2>&1; then PY="$ENV/bin/python3"; fi
PIPX="$PY -m pip install -q --disable-pip-version-check"
$PIPX numpy scipy pillow "opencv-python-headless<5" >/dev/null 2>&1 || $PIPX --break-system-packages numpy scipy pillow "opencv-python-headless<5" >/dev/null 2>&1
command -v ffmpeg >/dev/null || { $PIPX imageio-ffmpeg >/dev/null 2>&1 || $PIPX --break-system-packages imageio-ffmpeg >/dev/null 2>&1; }
$PIPX faster-whisper >/dev/null 2>&1 || $PIPX --break-system-packages faster-whisper >/dev/null 2>&1
$PY -c "import numpy,scipy,PIL,cv2" 2>/dev/null && echo "core ok" || echo "WARN: core libs missing"
$PY -c "import sys;sys.path.insert(0,'$(dirname "$0")');import ff;print('ffmpeg ok', ff.FFMPEG)" 2>/dev/null || echo "WARN: no ffmpeg"
$PY -c "import faster_whisper" 2>/dev/null && echo "whisper ok (model auto-downloads: HuggingFace → GitHub mirror)" || echo "whisper lib missing → transcript fallback (align_text.py)"
echo "PY=$PY"
