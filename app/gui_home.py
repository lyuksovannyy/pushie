from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal

THEME = """
    * {
        font-family: "Segoe UI", "SF Pro Display", system-ui, sans-serif;
    }
    QWidget#home_root {
        background-color: #0d1117;
    }
    QScrollArea {
        background-color: transparent;
        border: none;
    }
    QScrollArea > QWidget > QWidget {
        background-color: transparent;
    }
    QScrollBar:vertical {
        background-color: #161b22;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background-color: #30363d;
        min-height: 24px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #484f58;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
"""

class HotkeyButton(QPushButton):
    rightClicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()
        else:
            super().mousePressEvent(event)


class MacroWidget(QFrame):
    edit_requested = Signal(str)
    hotkey_requested = Signal(str)
    toggle_mode_changed = Signal(str)
    active_toggled = Signal(str, bool)
    bind_method_toggled = Signal(str, str)

    def __init__(self, macro, parent=None):
        super().__init__(parent)
        self.macro = macro
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(120)
        self.setStyleSheet("""
            MacroWidget {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 10px;
            }
            MacroWidget:hover {
                border-color: #388bfd;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # -- Header: Name + Hotkey --
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        self.name_label = QLabel(macro.name, self)
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #e6edf3;")
        header.addWidget(self.name_label)

        header.addStretch()

        self.hotkey_btn = HotkeyButton(self)
        self._update_hotkey_text()
        self.hotkey_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d1117;
                color: #79c0ff;
                border: 1px solid #21262d;
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-family: "JetBrains Mono", "Fira Code", monospace;
            }
            QPushButton:hover {
                border-color: #388bfd;
                background-color: #1c2128;
            }
        """)
        self.hotkey_btn.clicked.connect(lambda: self.hotkey_requested.emit(self.macro.id))
        self.hotkey_btn.rightClicked.connect(lambda: self.toggle_mode_changed.emit(self.macro.id))
        header.addWidget(self.hotkey_btn)
        layout.addLayout(header)

        # -- Description --
        desc_text = macro.description or "No description"
        self.desc_label = QLabel(desc_text, self)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #8b949e; font-size: 12px; padding-top: 2px;")
        layout.addWidget(self.desc_label)

        layout.addStretch()

        # -- Footer: Edit + Active toggle --
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)

        edit_btn = QPushButton("✎ Edit", self)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #e6edf3;
                border-color: #8b949e;
                background-color: #21262d;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.macro.id))
        footer.addWidget(edit_btn)

        self.method_toggle_btn = QPushButton(self)
        self.method_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.method_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #e6edf3;
                border-color: #8b949e;
                background-color: #21262d;
            }
        """)
        self._update_method_toggle()
        self.method_toggle_btn.clicked.connect(self._on_method_toggle_clicked)
        footer.addWidget(self.method_toggle_btn)

        footer.addStretch()

        self.active_btn = QPushButton(self)
        self.active_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_active_state()
        self.active_btn.clicked.connect(self._on_active_clicked)
        footer.addWidget(self.active_btn)
        layout.addLayout(footer)

    def _update_hotkey_text(self):
        mode = "Hold" if self.macro.work_only_pressed else "Toggle"
        key = self.macro.hotkey or "Click to bind"
        self.hotkey_btn.setText(f"⌨ {key}  [{mode}]")

    def _update_method_toggle(self):
        method = getattr(self.macro, "bind_method", "xdg")
        if method == "evdev":
            self.method_toggle_btn.setText("⚡ evdev")
        else:
            self.method_toggle_btn.setText("🌐 xdg")

    def _on_method_toggle_clicked(self):
        current_method = getattr(self.macro, "bind_method", "xdg")
        new_method = "xdg" if current_method == "evdev" else "evdev"
        self.macro.bind_method = new_method
        from app.storage import save_macro
        save_macro(self.macro)
        self._update_method_toggle()
        self._update_hotkey_text() # hotkey changes based on bind method property!
        self.bind_method_toggled.emit(self.macro.id, new_method)

    def _update_active_state(self):
        if self.macro.active:
            self.active_btn.setText("● Active")
            self.active_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d4429;
                    color: #3fb950;
                    border: 1px solid #238636;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1a5c37;
                }
            """)
        else:
            self.active_btn.setText("○ Disabled")
            self.active_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3d1519;
                    color: #f85149;
                    border: 1px solid #da3633;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #5c1d24;
                }
            """)

    def _on_active_clicked(self):
        new_state = not self.macro.active
        self.macro.active = new_state
        self._update_active_state()
        self.active_toggled.emit(self.macro.id, new_state)


class HomePage(QWidget):
    create_requested = Signal()
    edit_requested = Signal(str)
    hotkey_requested = Signal(str)
    toggle_mode_changed = Signal(str)
    active_toggled = Signal(str, bool)
    bind_method_toggled = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("home_root")
        self.setStyleSheet(THEME)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # -- Top bar --
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Pushie", self)
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #e6edf3;")
        top_bar.addWidget(title)

        top_bar.addStretch()

        # Evdev status label
        self.evdev_status_lbl = QLabel("🔄 Scanning evdev...", self)
        self.evdev_status_lbl.setStyleSheet("""
            color: #f2cc60;
            font-size: 11px;
            font-weight: 600;
            background-color: transparent;
            border: none;
            padding: 4px 0px;
            margin-right: 12px;
        """)
        top_bar.addWidget(self.evdev_status_lbl)

        create_btn = QPushButton("+ Create Macro", self)
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1a7f37;
            }
        """)
        create_btn.clicked.connect(self.create_requested.emit)
        top_bar.addWidget(create_btn)
        main_layout.addLayout(top_bar)

        # -- Separator --
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #21262d;")
        sep.setFixedHeight(1)
        main_layout.addWidget(sep)

        # -- Scroll area for macro grid --
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setContentsMargins(0, 0, 8, 0)

        self.scroll_area.setWidget(self.scroll_widget)
        main_layout.addWidget(self.scroll_area)

        self.cards: dict[str, MacroWidget] = {}

    def populate_macros(self, macros):
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

        self.cards.clear()

        cols = 2
        for idx, macro in enumerate(macros):
            row = idx // cols
            col = idx % cols
            card = MacroWidget(macro, self)
            card.edit_requested.connect(self.edit_requested.emit)
            card.hotkey_requested.connect(self.hotkey_requested.emit)
            card.toggle_mode_changed.connect(self.toggle_mode_changed.emit)
            card.active_toggled.connect(self.active_toggled.emit)
            card.bind_method_toggled.connect(self.bind_method_toggled.emit)

            self.grid_layout.addWidget(card, row, col)
            self.cards[macro.id] = card

        # Push cards to top
        row_count = (len(macros) + cols - 1) // cols
        self.grid_layout.setRowStretch(max(1, row_count), 1)

    def set_evdev_status(self, status: str) -> None:
        if status == "scanning":
            self.evdev_status_lbl.setText("🔄 Scanning evdev...")
            self.evdev_status_lbl.setStyleSheet("""
                color: #f2cc60;
                font-size: 11px;
                font-weight: 600;
                background-color: transparent;
                border: none;
                padding: 4px 0px;
                margin-right: 12px;
            """)
            self.evdev_status_lbl.show()
        elif status == "ready":
            self.evdev_status_lbl.hide()
        elif status == "unavailable":
            self.evdev_status_lbl.setText("⚠️ evdev unavailable")
            self.evdev_status_lbl.setStyleSheet("""
                color: #f85149;
                font-size: 11px;
                font-weight: 600;
                background-color: transparent;
                border: none;
                padding: 4px 0px;
                margin-right: 12px;
            """)
            self.evdev_status_lbl.show()

    def set_hotkey_btn_recording(self, macro_id, recording):
        card = self.cards.get(macro_id)
        if card:
            if recording:
                card.hotkey_btn.setText("⌨ Press any key...")
                card.hotkey_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3d1519;
                        color: #f85149;
                        border: 1px solid #da3633;
                        border-radius: 6px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-family: "JetBrains Mono", "Fira Code", monospace;
                    }
                """)
            else:
                card._update_hotkey_text()
                card.hotkey_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0d1117;
                        color: #79c0ff;
                        border: 1px solid #21262d;
                        border-radius: 6px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-family: "JetBrains Mono", "Fira Code", monospace;
                    }
                    QPushButton:hover {
                        border-color: #388bfd;
                        background-color: #1c2128;
                    }
                """)
