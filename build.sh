#!/usr/bin/env bash
set -e

# Ensure we are in the script's directory
cd "$(dirname "$0")"

echo "=== Checking GObject introspection data ==="
# PyInstaller only bundles the GLib typelibs if it can query them at build time.
# Without them the build "succeeds" but the binary crashes on start with
# "cannot import name GLib, introspection typelib not found".
if ! uv run python - <<'PY'
import gi
try:
    gi.require_version("GIRepository", "3.0")
except ValueError:
    gi.require_version("GIRepository", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import GIRepository, GLib
PY
then
  echo
  echo "Error: GLib / GIRepository introspection typelibs are missing."
  echo "Install them and run this script again:"
  echo "  Debian/Ubuntu: sudo apt install gir1.2-glib-2.0 gir1.2-girepository-3.0"
  echo "  Fedora:        sudo dnf install glib2 gobject-introspection"
  echo "  Arch:          sudo pacman -S glib2 gobject-introspection"
  exit 1
fi

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
