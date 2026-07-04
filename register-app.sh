#!/usr/bin/env bash
set -e

# Detect if the binary pushie is placed in a /bin directory
BINARY_PATH=""
for path in "/usr/local/bin/pushie" "/usr/bin/pushie" "/bin/pushie"; do
  if [ -f "$path" ]; then
    BINARY_PATH="$path"
    break
  fi
done

if [ -z "$BINARY_PATH" ]; then
  echo "Error: 'pushie' binary must be placed in a /bin directory (e.g., /usr/bin, /usr/local/bin, or /bin) before running this script."
  exit 1
fi

echo "Found pushie binary at: $BINARY_PATH"

# Setup the icon path
ICON_SRC="$(dirname "$0")/logo.png"
if [ ! -f "$ICON_SRC" ]; then
  ICON_SRC="/home/lebron/PyCharmProjects/pushie/logo.png"
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
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=Pushie
Comment=Push-to-Talk & Keyboard/Mouse Macro Tool
Exec=$BINARY_PATH
Icon=$ICON_DST
Terminal=false
Categories=Utility;
EOF

chmod +x "$DESKTOP_FILE"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Success! Registered Pushie as a desktop application."
echo "Entry file created at: $DESKTOP_FILE"
echo "Launch target: $BINARY_PATH"
