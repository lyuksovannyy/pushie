from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QMenu
)
from PySide6.QtCore import Qt, Signal

class HotkeyButton(QPushButton):
    rightClicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()
        else:
            super().mousePressEvent(event)

class MacroWidget(QFrame):
    edit_requested = Signal(str)      # macro_id
    hotkey_requested = Signal(str)    # macro_id
    toggle_mode_changed = Signal(str) # macro_id
    active_toggled = Signal(str, bool) # macro_id, active

    def __init__(self, macro, parent=None):
        super().__init__(parent)
        self.macro = macro
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setProperty("class", "macro-card")
        self.setStyleSheet("""
            QFrame.macro-card {
                background-color: #1e1e24;
                border: 1px solid #33333c;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header Row: Name & Hotkey Button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.name_label = QLabel(macro.name, self)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        header_layout.addWidget(self.name_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Hotkey Button with indicator
        self.hotkey_btn = HotkeyButton(self)
        self.update_hotkey_button_text()
        self.hotkey_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b35;
                color: #58a6ff;
                border: 1px solid #444c56;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-family: monospace;
            }
            QPushButton:hover {
                background-color: #383846;
                border-color: #58a6ff;
            }
        """)
        self.hotkey_btn.clicked.connect(lambda: self.hotkey_requested.emit(self.macro.id))
        self.hotkey_btn.rightClicked.connect(lambda: self.toggle_mode_changed.emit(self.macro.id))
        header_layout.addWidget(self.hotkey_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_layout)

        # Description
        self.desc_label = QLabel(macro.description or "No description", self)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.desc_label)

        # Spacer/flexible
        layout.addStretch()

        # Footer Row: Edit Button and Active Toggle
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)

        # Edit button (left)
        edit_btn = QPushButton("Edit", self)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.macro.id))
        footer_layout.addWidget(edit_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Active Toggle state button/switch (right)
        self.active_btn = QPushButton(self)
        self.update_active_button_state()
        self.active_btn.clicked.connect(self.on_active_clicked)
        footer_layout.addWidget(self.active_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(footer_layout)

    def update_hotkey_button_text(self):
        hotkey_prefix = "[Hold]" if self.macro.work_only_pressed else "[Toggle]"
        hotkey_text = self.macro.hotkey or "Bind Hotkey"
        self.hotkey_btn.setText(f"{hotkey_prefix} {hotkey_text}")

    def update_active_button_state(self):
        if self.macro.active:
            self.active_btn.setText("Active")
            self.active_btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
            """)
        else:
            self.active_btn.setText("Disabled")
            self.active_btn.setStyleSheet("""
                QPushButton {
                    background-color: #da3637;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #f85149;
                }
            """)

    def on_active_clicked(self):
        new_state = not self.macro.active
        self.macro.active = new_state
        self.update_active_button_state()
        self.active_toggled.emit(self.macro.id, new_state)

class HomePage(QWidget):
    create_requested = Signal()
    edit_requested = Signal(str)
    hotkey_requested = Signal(str)
    toggle_mode_changed = Signal(str)
    active_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: #0d1117;
                color: #c9d1d9;
            }
        """)

        # Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # Top Bar: Title & Create Macro Button
        top_bar = QHBoxLayout()
        title_label = QLabel("Pushie Macros", self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        top_bar.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignLeft)

        create_btn = QPushButton("Create macro", self)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        create_btn.clicked.connect(self.create_requested.emit)
        top_bar.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.main_layout.addLayout(top_bar)

        # Scroll Area for macros (flexible grid/list representation)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0d1117;
            }
        """)

        self.scroll_widget = QWidget(self)
        self.scroll_widget.setStyleSheet("background-color: #0d1117;")
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)

        # Store of active card widgets
        self.cards = {}

    def populate_macros(self, macros):
        # 1. Clear existing layout items
        for i in reversed(range(self.grid_layout.count())): 
            item = self.grid_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
        
        self.cards.clear()

        # 2. Add macro cards
        cols = 2
        for idx, macro in enumerate(macros):
            row = idx // cols
            col = idx % cols
            card = MacroWidget(macro, self)
            card.edit_requested.connect(self.edit_requested.emit)
            card.hotkey_requested.connect(self.hotkey_requested.emit)
            card.toggle_mode_changed.connect(self.toggle_mode_changed.emit)
            card.active_toggled.connect(self.active_toggled.emit)
            
            self.grid_layout.addWidget(card, row, col)
            self.cards[macro.id] = card
            
        # Push all to the top
        row_count = (len(macros) + 1) // cols
        self.grid_layout.setRowStretch(max(1, row_count), 1)
