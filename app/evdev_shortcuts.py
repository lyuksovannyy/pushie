import os
import threading
import logging
import re
from typing import Any, Optional, Union
from collections.abc import Sequence
from PySide6.QtCore import QObject, Signal, QFileSystemWatcher
from app.storage import Macro

try:
    import evdev
    from evdev import InputDevice, UInput, UInput as UInputClass # Wait, earlier we used UInput
except ImportError:
    evdev = None
    InputDevice = None
    UInput = None

# Let's import UInput correctly from evdev (it's UInput class)
if evdev is not None:
    try:
        from evdev import UInput
    except ImportError:
        try:
            from evdev import Uinput as UInput
        except ImportError:
            UInput = None

logger = logging.getLogger("pushie.evdev_shortcuts")


def parse_evdev_hotkey(hotkey_str: str) -> set[str]:
    """Parse hotkey string into normalized parts, e.g. 'Ctrl+X' -> {'ctrl', 'x'}."""
    if not hotkey_str:
        return set()
    parts = re.split(r'[\s\+\-]+', hotkey_str.lower())
    return {p.replace("key_", "").strip() for p in parts if p.strip()}


def evdev_key_matches(evdev_key: str, hotkey_set: set[str]) -> bool:
    """Check if evdev key name matches any entry in normalized hotkey set."""
    aliases = {
        "ctrl": {"leftctrl", "rightctrl"},
        "control": {"leftctrl", "rightctrl"},
        "shift": {"leftshift", "rightshift"},
        "alt": {"leftalt", "rightalt"},
        "meta": {"leftmeta", "rightmeta"},
        "super": {"leftmeta", "rightmeta"},
        "win": {"leftmeta", "rightmeta"},
    }
    for k in hotkey_set:
        if k == evdev_key:
            return True
        if k in aliases and evdev_key in aliases[k]:
            return True
    return False


class EvdevShortcutsClient(QObject):
    shortcut_activated = Signal(str)
    shortcut_deactivated = Signal(str)
    raw_key_pressed = Signal(str)
    status_changed = Signal(str) # "scanning", "ready", "unavailable"

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.macros: list[Macro] = []
        self.devices: dict[str, Any] = {}          # path -> InputDevice
        self.uinputs: dict[str, Any] = {}          # path -> UInput
        self.threads: dict[str, threading.Thread] = {}
        self.stop_events: dict[str, threading.Event] = {}
        self.pressed_keys: set[str] = set()
        self.lock = threading.Lock()

        if evdev is None:
            logger.warning("evdev package is not installed. Evdev shortcuts disabled.")
            return

        self.watcher = QFileSystemWatcher(self)
        if os.path.exists("/dev/input"):
            self.watcher.addPath("/dev/input")
            self.watcher.directoryChanged.connect(self.scan_devices)

    def scan_devices(self) -> None:
        try:
            self.status_changed.emit("scanning")
        except RuntimeError:
            pass
        t = threading.Thread(target=self._scan_devices_background, daemon=True)
        t.start()

    def _scan_devices_background(self) -> None:
        if evdev is None or InputDevice is None:
            try:
                self.status_changed.emit("unavailable")
            except RuntimeError:
                pass
            return

        try:
            current_paths = set(evdev.list_devices())
        except Exception as e:
            logger.error(f"Failed to list evdev devices: {e}")
            try:
                self.status_changed.emit("unavailable")
            except RuntimeError:
                pass
            return

        # Remove disconnected devices
        with self.lock:
            active_paths = list(self.devices.keys())
        for path in active_paths:
            if path not in current_paths:
                logger.info(f"Evdev device disconnected: {path}")
                self.stop_device_reader(path)

        # Add connected devices
        for path in current_paths:
            with self.lock:
                already_connected = path in self.devices
            if not already_connected:
                if "uinput" in path.lower():
                    continue
                try:
                    dev = InputDevice(path)
                    if "uinput" in dev.name.lower() or "uinput" in path.lower():
                        dev.close()
                        continue
                    cap = dev.capabilities()
                    if evdev.ecodes.EV_KEY in cap:
                        logger.info(f"Evdev device connected: {dev.name} ({path})")
                        self.start_device_reader(path, dev)
                    else:
                        dev.close()
                except Exception as e:
                    logger.debug(f"Could not open evdev device {path}: {e}")

        # Check if we successfully opened at least one key-capable device
        with self.lock:
            any_device = len(self.devices) > 0
        if any_device:
            try:
                self.status_changed.emit("ready")
            except RuntimeError:
                pass
        else:
            try:
                self.status_changed.emit("unavailable")
            except RuntimeError:
                pass

    def start_device_reader(self, path: str, dev: Any) -> None:
        if evdev is None or InputDevice is None or UInput is None:
            return

        # Perform the slower grabbing operations outside of self.lock
        grabbed = False
        ui = None
        try:
            dev.grab()
            ui = UInput.from_device(dev)
            grabbed = True
        except Exception as e:
            logger.warning(f"Could not grab evdev device {dev.name} or create uinput: {e}")

        if not grabbed:
            return

        with self.lock:
            self.devices[path] = dev
            if ui:
                self.uinputs[path] = ui

        logger.info(f"Grabbed evdev device: {dev.name}")

        stop_event = threading.Event()
        with self.lock:
            self.stop_events[path] = stop_event

        t = threading.Thread(
            target=self._device_reader_loop,
            args=(path, dev, stop_event),
            daemon=True
        )
        with self.lock:
            self.threads[path] = t
        t.start()

    def stop_device_reader(self, path: str) -> None:
        if path in self.stop_events:
            self.stop_events[path].set()
            del self.stop_events[path]
        if path in self.devices:
            dev = self.devices[path]
            try:
                dev.ungrab()
            except Exception:
                pass
            del self.devices[path]
        if path in self.uinputs:
            ui = self.uinputs[path]
            try:
                ui.close()
            except Exception:
                pass
            del self.uinputs[path]
        if path in self.threads:
            del self.threads[path]

    def update_macros(self, macros_list: list[Macro]) -> None:
        if evdev is None:
            return

        with self.lock:
            self.macros = macros_list

    def _device_reader_loop(self, path: str, dev: Any, stop_event: threading.Event) -> None:
        if evdev is None:
            return

        import select

        try:
            while not stop_event.is_set():
                r, w, x = select.select([dev.fd], [], [], 0.1)
                if not r:
                    continue

                for key_event in dev.read():
                    if key_event.type != evdev.ecodes.EV_KEY or key_event.value == 2:
                        # Forward non-key events directly
                        if path in self.uinputs:
                            try:
                                self.uinputs[path].write(key_event.type, key_event.code, key_event.value)
                                self.uinputs[path].syn()
                            except Exception:
                                pass
                        continue

                    keycode = key_event.code
                    keyname = evdev.ecodes.KEY.get(keycode)
                    if not keyname:
                        if path in self.uinputs:
                            try:
                                self.uinputs[path].write(key_event.type, key_event.code, key_event.value)
                                self.uinputs[path].syn()
                            except Exception:
                                pass
                        continue

                    key = str(keyname).removeprefix("KEY_").lower()
                    pressed = bool(key_event.value)

                    if pressed:
                        try:
                            self.raw_key_pressed.emit(key)
                        except RuntimeError:
                            pass

                    is_macro_key = False
                    matching_macros = []

                    with self.lock:
                        if pressed:
                            self.pressed_keys.add(key)
                        else:
                            self.pressed_keys.discard(key)

                        for m in self.macros:
                            if m.active and getattr(m, "bind_method", "xdg") == "evdev":
                                chord = parse_evdev_hotkey(m.hotkey)
                                if chord:
                                    if any(evdev_key_matches(key, {k}) for k in chord):
                                        is_macro_key = True
                                        matching_macros.append((m, chord))

                    swallow = False
                    if is_macro_key:
                        for m, _ in matching_macros:
                            if not getattr(m, "evdev_pass_through", False):
                                swallow = True
                                break

                    if not swallow:
                        if path in self.uinputs:
                            try:
                                self.uinputs[path].write(key_event.type, key_event.code, key_event.value)
                                self.uinputs[path].syn()
                            except Exception:
                                pass

                    if is_macro_key:
                        for m, chord in matching_macros:
                            chord_satisfied = all(
                                any(evdev_key_matches(pk, {k}) for pk in self.pressed_keys)
                                for k in chord
                            )
                            if pressed:
                                if chord_satisfied:
                                    self._trigger_activate(m)
                            else:
                                if not chord_satisfied:
                                    self._trigger_deactivate(m)
        except Exception as e:
            logger.debug(f"Error in evdev reader loop for {dev.name}: {e}")

    def _trigger_activate(self, m: Macro) -> None:
        try:
            self.shortcut_activated.emit(m.id)
        except RuntimeError:
            pass

    def _trigger_deactivate(self, m: Macro) -> None:
        try:
            self.shortcut_deactivated.emit(m.id)
        except RuntimeError:
            pass
