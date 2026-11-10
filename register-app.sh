#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILT_BINARY="$SCRIPT_DIR/dist/pushie"
INSTALL_PATH="/usr/bin/pushie"

# Ask a yes/no question, default yes. Usage: confirm "Question?"
confirm() {
  local reply
  read -r -p "$1 [Y/n] " reply || reply="n"
  case "$reply" in
    ""|[yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

# Run a command as root, using sudo only when needed
as_root() {
  if [ "$EUID" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

# Find an already installed binary
find_installed() {
  local path
  for path in "/usr/bin/pushie" "/usr/local/bin/pushie" "/bin/pushie"; do
    if [ -f "$path" ]; then
      echo "$path"
      return 0
    fi
  done
  return 1
}

# --- Step 1: install the binary ---
BINARY_PATH="$(find_installed || true)"

if [ -f "$BUILT_BINARY" ]; then
  if [ -z "$BINARY_PATH" ]; then
    QUESTION="Copy $BUILT_BINARY to $INSTALL_PATH?"
  elif cmp -s "$BUILT_BINARY" "$BINARY_PATH"; then
    QUESTION=""
    echo "Installed binary at $BINARY_PATH is already up to date."
  else
    INSTALL_PATH="$BINARY_PATH"
    QUESTION="Replace $BINARY_PATH with the build from $BUILT_BINARY?"
  fi

  if [ -n "$QUESTION" ] && confirm "$QUESTION"; then
    as_root install -m 755 "$BUILT_BINARY" "$INSTALL_PATH"
    BINARY_PATH="$INSTALL_PATH"
    echo "Installed pushie to: $BINARY_PATH"
  fi
elif [ -z "$BINARY_PATH" ]; then
  echo "Error: no built binary at $BUILT_BINARY and pushie is not installed."
  echo "Run ./build.sh first, then run this script again."
  exit 1
fi

if [ -z "$BINARY_PATH" ]; then
  echo "Error: pushie is not installed, so there is nothing to register."
  exit 1
fi

echo "Using pushie binary at: $BINARY_PATH"

# --- Step 2: register the desktop entry ---
if ! confirm "Register Pushie as a desktop application?"; then
  echo "Skipped desktop registration."
  exit 0
fi

ICON_SRC="$SCRIPT_DIR/logo.png"
if [ ! -f "$ICON_SRC" ]; then
  echo "Error: icon not found at $ICON_SRC"
  exit 1
fi

ICON_DST=""
if [ -w "/usr/share/pixmaps" ]; then
  ICON_DST="/usr/share/pixmaps/pushie.png"
  cp "$ICON_SRC" "$ICON_DST"
  echo "Installed system-wide icon to: $ICON_DST"
else
  mkdir -p "$HOME/.local/share/icons"
  ICON_DST="$HOME/.local/share/icons/pushie.png"
  cp "$ICON_SRC" "$ICON_DST"
  echo "Installed user-space icon to: $ICON_DST"
fi

# Define Desktop Entry target
DESKTOP_DIR="$HOME/.local/share/applications"
if [ "$EUID" -eq 0 ] && [ -w "/usr/share/applications" ]; then
  DESKTOP_DIR="/usr/share/applications"
fi

mkdir -p "$DESKTOP_DIR"
DESKTOP_FILE="$DESKTOP_DIR/pushie.desktop"

# Create Desktop entry file
cat <<DESKTOP > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=Pushie
Comment=Push-to-Talk & Keyboard/Mouse Macro Tool
Exec=$BINARY_PATH
Icon=$ICON_DST
Terminal=false
Categories=Utility;
DESKTOP

chmod +x "$DESKTOP_FILE"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Success! Registered Pushie as a desktop application."
echo "Entry file created at: $DESKTOP_FILE"
echo "Launch target: $BINARY_PATH"
