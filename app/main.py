import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QSystemTrayIcon, QMenu
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, SLOT, Slot

from app.storage import load_macros, save_macro, delete_macro
from app.engine import MacroEngine
from app.xdg_shortcuts import XDGShortcutsClient
from app.gui_home import HomePage
from app.gui_editor import MacroEditor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pushie - Push to Talk & Macro Builder")
        self.resize(700, 500)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
            }
        """)

        # 1. Models and Engines
        self.macros = load_macros()
        self.engine = MacroEngine()
        self.shortcuts_client = XDGShortcutsClient(self)

        # 2. Main Stacked Widget
        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        self.home_page = HomePage(self)
        self.editor_page = MacroEditor(self)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.editor_page)

        # 3. Connection wires
        # Page switching
        self.home_page.create_requested.connect(self.navigate_to_create)
        self.home_page.edit_requested.connect(self.navigate_to_edit)
        self.home_page.hotkey_requested.connect(self.trigger_hotkey_bind)
        self.home_page.toggle_mode_changed.connect(self.toggle_macro_work_mode)
        self.home_page.active_toggled.connect(self.on_active_toggled)

        self.editor_page.saved.connect(self.on_macro_saved)
        self.editor_page.cancelled.connect(self.navigate_to_home)
        self.editor_page.deleted.connect(self.on_macro_deleted)

        # Portal triggers
        self.shortcuts_client.session_ready.connect(self.on_portal_session_ready)
        self.shortcuts_client.shortcuts_configured.connect(self.on_portal_shortcuts_configured)
        self.shortcuts_client.shortcut_activated.connect(self.on_shortcut_activated)
        self.shortcuts_client.shortcut_deactivated.connect(self.on_shortcut_deactivated)

        # Wire clean exit hook to stop all macros when app exits
        q_app = QApplication.instance()
        if q_app:
            q_app.aboutToQuit.connect(self.engine.stop_all)

        # Load logo.ico as app and tray logo
        if getattr(sys, 'frozen', False):
            project_root = getattr(sys, "_MEIPASS")
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.logo_path = os.path.join(project_root, "logo.ico")
        self.logo_icon = QIcon(self.logo_path)
        self.setWindowIcon(self.logo_icon)

        # 4. System Tray Icon Setup
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.logo_icon)
        self.tray.setToolTip("Pushie Macro Daemon")

        tray_menu = QMenu(self)
        show_action = QAction("Show GUI", self)
        show_action.triggered.connect(self.showNormal)
        
        stop_action = QAction("Stop All Macros", self)
        stop_action.triggered.connect(self.engine.stop_all)

        exit_action = QAction("Exit", self)
        # Call exit cleanly
        exit_action.triggered.connect(self.clean_exit)

        tray_menu.addAction(show_action)
        tray_menu.addAction(stop_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.show()
        # Connect activation (click on tray icon shows app)
        self.tray.activated.connect(self.on_tray_activated)

        # Start loading configs & Portal session
        self.home_page.populate_macros(self.macros)
        self.shortcuts_client.start_session()

    def closeEvent(self, event):
        # Minimize to tray instead of quitting directly
        if self.tray.isVisible():
            self.hide()
            self.tray.showMessage(
                "Pushie Running",
                "Pushie has minimized to the system tray. Macros are active.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            self.clean_exit()

    def clean_exit(self):
        self.engine.stop_all()
        QApplication.quit()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    # --- Navigation ---
    def navigate_to_home(self):
        self.stack.setCurrentWidget(self.home_page)
        self.home_page.populate_macros(self.macros)

    def navigate_to_create(self):
        self.editor_page.create_empty()
        self.stack.setCurrentWidget(self.editor_page)

    def navigate_to_edit(self, macro_id):
        macro = self.find_macro_by_id(macro_id)
        if macro:
            self.editor_page.load_macro(macro)
            self.stack.setCurrentWidget(self.editor_page)

    # --- Macro updates & saves ---
    def on_macro_saved(self, macro):
        # Update or append
        existing = self.find_macro_by_id(macro.id)
        if existing:
            # Preserve hotkey when editing other properties
            macro.hotkey = existing.hotkey
            idx = self.macros.index(existing)
            self.macros[idx] = macro
        else:
            self.macros.append(macro)
            
        save_macro(macro)
        self.rebind_all_keys()
        self.navigate_to_home()

    def on_macro_deleted(self, macro_id):
        # Delete from list and storage
        self.macros = [m for m in self.macros if m.id != macro_id]
        delete_macro(macro_id)
        
        # Reset and refresh portal binds/GUI cards
        self.rebind_all_keys()
        self.home_page.populate_macros(self.macros)
        self.navigate_to_home()

    def on_active_toggled(self, macro_id, active):
        # Keep list in sync and save
        macro = self.find_macro_by_id(macro_id)
        if macro:
            macro.active = active
            save_macro(macro)
            # Rebind keys so deactivated ones don't trigger
            self.rebind_all_keys()

    def toggle_macro_work_mode(self, macro_id):
        macro = self.find_macro_by_id(macro_id)
        if macro:
            macro.work_only_pressed = not macro.work_only_pressed
            save_macro(macro)
            self.home_page.populate_macros(self.macros)
            # Update key bindings metadata on portal if necessary
            self.rebind_all_keys()

    def trigger_hotkey_bind(self, macro_id):
        # Trigger the portal shortcuts configuration settings dialog/view
        self.shortcuts_client.configure_shortcuts()

    # --- DBus Portal Callbacks ---
    def on_portal_session_ready(self, session_path):
        print(f"XDG desktop portal shortcuts session ready: {session_path}")
        self.rebind_all_keys()

    def rebind_all_keys(self):
        # Build portal binds list for all macros (active and inactive)
        # to ensure inactive ones are not unregistered from the portal session
        bind_list = []
        for m in self.macros:
            bind_list.append({"id": m.id, "name": m.name, "trigger": m.hotkey})
        
        self.shortcuts_client.bind_shortcuts(bind_list)

    def on_portal_shortcuts_configured(self, bound_list):
        # Update local macro hotkey state with portal response
        for item in bound_list:
            mid = item["id"]
            trigger = item["trigger"]
            macro = self.find_macro_by_id(mid)
            if macro:
                # Store the updated display or trigger label returned by portals
                macro.hotkey = trigger
                save_macro(macro)
        
        self.home_page.populate_macros(self.macros)

    def on_shortcut_activated(self, shortcut_id):
        macro = self.find_macro_by_id(shortcut_id)
        if macro and macro.active:
            self.engine.handle_activate(macro)

    def on_shortcut_deactivated(self, shortcut_id):
        macro = self.find_macro_by_id(shortcut_id)
        if macro and macro.active:
            self.engine.handle_deactivate(macro)

    # --- Helper methods ---
    def find_macro_by_id(self, macro_id):
        for m in self.macros:
            if m.id == macro_id:
                return m
        return None

def main():
    import signal
    from PySide6.QtCore import QTimer

    # Check for minimized launch argument
    minimized = "--minimized" in sys.argv
    qt_args = [arg for arg in sys.argv if arg != "--minimized"]

    app = QApplication(qt_args)
    app.setQuitOnLastWindowClosed(False) # Daemon mode
    window = MainWindow()
    
    if not minimized:
        window.show()

    def sigint_handler(sig, frame):
        print("\nCtrl+C detected, exiting...")
        window.clean_exit()

    signal.signal(signal.SIGINT, sigint_handler)

    # Periodic timer to allow Python signal handling when Qt events are running
    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)  # Dummy slot to force interpreter check

    sys.exit(app.exec())
