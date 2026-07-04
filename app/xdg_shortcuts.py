import threading
from typing import TypedDict, Any, Optional
from collections.abc import Sequence
import uuid
import dbus
import logging
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("pushie.xdg_shortcuts")

class ShortcutBindSpec(TypedDict):
    id: str
    name: str
    trigger: str

class ShortcutQueryResult(TypedDict):
    id: str
    trigger: str

class XDGShortcutsClient(QObject):
    session_ready = Signal(str)
    shortcut_activated = Signal(str)
    shortcut_deactivated = Signal(str)
    shortcuts_configured = Signal(list)  # list of ShortcutQueryResult
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        
        # 1. Initialize DBus with GLib mainloop support
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        
        # 2. Get the GlobalShortcuts Portal interface proxy
        try:
            self.portal = self.bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
            self.shortcuts_iface = dbus.Interface(self.portal, "org.freedesktop.portal.GlobalShortcuts")
        except Exception as e:
            self.portal = None
            self.shortcuts_iface = None
            print(f"XDG GlobalShortcuts portal not available: {e}")
            
        self.session_path: Optional[str] = None
        self.glib_loop = GLib.MainLoop()
        
        # Start GLib loop in background thread to handle DBus signals
        self.dbus_thread = threading.Thread(target=self.glib_loop.run, daemon=True)
        self.dbus_thread.start()

        # Connect to global activation/deactivation signals
        if self.shortcuts_iface:
            self.bus.add_signal_receiver(
                self._on_activated,
                dbus_interface="org.freedesktop.portal.GlobalShortcuts",
                signal_name="Activated"
            )
            self.bus.add_signal_receiver(
                self._on_deactivated,
                dbus_interface="org.freedesktop.portal.GlobalShortcuts",
                signal_name="Deactivated"
            )
            self.bus.add_signal_receiver(
                self._on_shortcuts_changed,
                dbus_interface="org.freedesktop.portal.GlobalShortcuts",
                signal_name="ShortcutsChanged"
            )

    def start_session(self) -> None:
        if not self.shortcuts_iface:
            logger.error("Portal interface not initialized")
            self.error_occurred.emit("Portal interface not initialized")
            return
        
        logger.debug("Initializing XDG Global Shortcuts portal session...")
        token = f"pushie_session_{uuid.uuid4().hex[:8]}"
        try:
            req_path = self.shortcuts_iface.CreateSession({"session_handle_token": token})
            self.bus.add_signal_receiver(
                self._on_session_response,
                dbus_interface="org.freedesktop.portal.Request",
                signal_name="Response",
                path=req_path
            )
        except Exception as e:
            logger.error(f"Failed to call CreateSession: {e}")
            self.error_occurred.emit(f"Failed to call CreateSession: {e}")

    def _on_session_response(self, response_code: int, results: dict[str, Any]) -> None:
        if response_code == 0 and "session_handle" in results:
            self.session_path = str(results["session_handle"])
            logger.debug(f"XDG shortcuts session created successfully: {self.session_path}")
            self.session_ready.emit(self.session_path)
        else:
            logger.error(f"CreateSession failed with response code: {response_code}")
            self.error_occurred.emit(f"CreateSession failed with response code: {response_code}")

    def bind_shortcuts(self, shortcuts_list: Sequence[ShortcutBindSpec]) -> None:
        if not self.shortcuts_iface or not self.session_path:
            logger.error("Session not established for binding")
            self.error_occurred.emit("Session not established for binding")
            return

        logger.debug("Binding shortcuts dynamically on XDG portal session...")
        formatted_shortcuts = []
        for s in shortcuts_list:
            props = {"description": s["name"]}
            if s.get("trigger"):
                props["trigger_description"] = s["trigger"]
            formatted_shortcuts.append((s["id"], props))

        token = f"pushie_bind_{uuid.uuid4().hex[:8]}"
        try:
            req_path = self.shortcuts_iface.BindShortcuts(
                self.session_path,
                formatted_shortcuts,
                "", # parent_window
                {"handle_token": token}
            )
            self.bus.add_signal_receiver(
                self._on_bind_response,
                dbus_interface="org.freedesktop.portal.Request",
                signal_name="Response",
                path=req_path
            )
        except Exception as e:
            logger.error(f"Failed to call BindShortcuts: {e}")
            self.error_occurred.emit(f"Failed to call BindShortcuts: {e}")

    def _on_bind_response(self, response_code: int, results: dict[str, Any]) -> None:
        if response_code == 0:
            shortcuts_bound: list[ShortcutQueryResult] = []
            raw_shortcuts = results.get("shortcuts", [])
            for sid, props in raw_shortcuts:
                trigger_desc = str(props.get("trigger_description", ""))
                shortcuts_bound.append({
                    "id": str(sid),
                    "trigger": trigger_desc
                })
            self.shortcuts_configured.emit(shortcuts_bound)
        elif response_code == 1:
            self.shortcuts_configured.emit([])
        else:
            self.error_occurred.emit(f"BindShortcuts failed with code: {response_code}")

    def configure_shortcuts(self) -> None:
        if not self.shortcuts_iface or not self.session_path:
            logger.error("Session not established for configuration")
            self.error_occurred.emit("Session not established for configuration")
            return
        logger.debug("Opening portal configuration interface...")
        try:
            self.shortcuts_iface.ConfigureShortcuts(
                self.session_path,
                "", # parent_window
                {}  # options
            )
        except Exception as e:
            logger.error(f"Failed to call ConfigureShortcuts: {e}")
            self.error_occurred.emit(f"Failed to call ConfigureShortcuts: {e}")

    def _on_shortcuts_changed(self, session: object, shortcuts: list) -> None:
        if self.session_path and str(session) == self.session_path:
            logger.debug("ShortcutsChanged signal received from portal.")
            shortcuts_bound: list[ShortcutQueryResult] = []
            for sid, props in shortcuts:
                trigger_desc = str(props.get("trigger_description", ""))
                shortcuts_bound.append({
                    "id": str(sid),
                    "trigger": trigger_desc
                })
            self.shortcuts_configured.emit(shortcuts_bound)

    def _on_activated(self, session: object, shortcut_id: str, timestamp: int, options: dict[str, Any]) -> None:
        if self.session_path and str(session) == self.session_path:
            logger.debug(f"DBus Portal signal: Activated shortcut ID: {shortcut_id}")
            self.shortcut_activated.emit(str(shortcut_id))

    def _on_deactivated(self, session: object, shortcut_id: str, timestamp: int, options: dict[str, Any]) -> None:
        if self.session_path and str(session) == self.session_path:
            logger.debug(f"DBus Portal signal: Deactivated shortcut ID: {shortcut_id}")
            self.shortcut_deactivated.emit(str(shortcut_id))
