#!/usr/bin/env bash
set -e

# Ensure we are in the script's directory
cd "$(dirname "$0")"

echo "=== Installing PyInstaller ==="
uv pip install pyinstaller

echo "=== Compiling Pushie to a single binary with icon ==="
uv run pyinstaller \
  --onefile \
  --windowed \
  --icon=logo.ico \
  --name pushie \
  --add-data "logo.ico:." \
  --add-data "logo.png:." \
  main.py

echo "=== Packaging Complete ==="
if [ -f "dist/pushie" ]; then
  chmod +x dist/pushie
  echo "Success! Standalone binary created at: $(pwd)/dist/pushie"
else
  echo "Error: Binary output was not found!"
  exit 1
fi
