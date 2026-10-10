#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -d .build-venv ]]; then
  "$PYTHON_BIN" -m venv .build-venv
fi
if [[ -f requirements-lock.txt ]]; then
  .build-venv/bin/python -m pip install -r requirements-lock.txt
else
  .build-venv/bin/python -m pip install -r requirements.txt 'pyinstaller==6.22.3'
fi
.build-venv/bin/python -m pip freeze > requirements-lock.txt
.build-venv/bin/python scripts/prepare_build.py
OUTPUT_DIR="${LOCAL_DESK_DIST:-$HOME/Library/Caches/LocalDeskBuild/dist}"
.build-venv/bin/python -m PyInstaller --noconfirm --distpath "$OUTPUT_DIR" LocalDesk.spec
.build-venv/bin/python scripts/sign_bundle.py "$OUTPUT_DIR/Local Desk.app"
/usr/bin/codesign --verify --deep --strict "$OUTPUT_DIR/Local Desk.app"
if [[ "${LOCAL_DESK_CPU_TEST:-0}" == 1 ]]; then
  "$OUTPUT_DIR/Local Desk.app/Contents/MacOS/LocalDesk" --self-test --cpu-only
else
  "$OUTPUT_DIR/Local Desk.app/Contents/MacOS/LocalDesk" --self-test
fi
