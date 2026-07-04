# Pushie

Pushie is a modern PySide6-based macro builder. It couples push-to-talk microphone management with keyboard/mouse automation using the native **XDG Global Shortcuts portal** over DBus.

## Features

- **XDG Global Shortcuts Portal Integrations**: Works natively under Wayland/X11 without requiring root access or unsafe key logging. Compatible with sandboxed containers (Flatpak/Snap).
- **Macro Editor UI**: Create, reorder, edit, and delete lists of actions.
- **Action Categories**:
  - **Keyboard**: Press, release, and tap keys.
  - **Mouse**: Click (left/middle/right/wheel buttons) and coordinate-based movements.
  - **Delay**: Milli-second duration pauses.
  - **Mic Controls**: Custom mute toggles and specific process target volume profiles (e.g. `discord`, `vesktop`).
- **Daemon Mode**: Minimizes to the system tray, keeping hotkeys active in the background.
- **Auto-Cleanup**: On app termination or standard terminal `Ctrl+C` interrupt, running macros automatically run their release/unmute action lists before exiting.
- **Launch Configurations**: CLI parameter `--minimized` to boot straight to the system tray.

---

## Installation & Setup

Pushie requires PySide6, PyYAML, dbus-python, and PyGObject.

Ensure you have the required system and Python dependencies installed. We recommend using `uv` to manage environment requirements:

```bash
# Run via uv directly
uv run main.py
```

### Command Line parameters
Start minimized to tray directly:
```bash
uv run main.py --minimized
```

---

## Configuration directory

Macros are stored individually as YAML configurations:
- Primary: `$HOME/.config/pushie/<macro_id>.yaml`
- Fallback: `$HOME/.pushie/<macro_id>.yaml`

---

## Testing

```bash
uv run python3 -m unittest tests/test_storage.py tests/test_engine.py tests/test_xdg_shortcuts.py
```
