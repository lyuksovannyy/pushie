from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QComboBox, QScrollArea, QFrame,
    QTabWidget, QFormLayout, QSpinBox, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from app.storage import Macro, ActionSpec

# Shared input style
_INPUT = """
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    selection-background-color: #264f78;
"""
_INPUT_FOCUS = "border-color: #388bfd;"
_LABEL = "color: #8b949e; font-size: 11px; font-weight: 500;"

_BTN_SUBTLE = """
    QPushButton {
        background-color: transparent;
        color: #8b949e;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 12px;
    }
    QPushButton:hover {
        color: #e6edf3;
        border-color: #8b949e;
        background-color: #21262d;
    }
"""
_BTN_PRIMARY = """
    QPushButton {
        background-color: #238636;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 8px 20px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton:hover { background-color: #2ea043; }
    QPushButton:pressed { background-color: #1a7f37; }
"""

_BTN_DANGER = """
    QPushButton {
        background-color: #3d1519;
        color: #f85149;
        border: 1px solid #da3633;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 12px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #5c1d24;
    }
"""


def _styled_input(widget):
    widget.setStyleSheet(f"""
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            {_INPUT}
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            {_INPUT_FOCUS}
        }}
    """)
    return widget


class ActionRow(QFrame):
    removed = Signal(QWidget)
    moved_up = Signal(QWidget)
    moved_down = Signal(QWidget)

    def __init__(self, action=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            ActionRow {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 8px;
            }
        """)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(10)

        # 1. Drag handle hint
        grip = QLabel("⠿", self)
        grip.setStyleSheet("color: #30363d; font-size: 16px;")
        grip.setFixedWidth(16)
        self.main_layout.addWidget(grip)

        # 2. Action type selector
        self.type_combo = QComboBox(self)
        self.type_combo.addItems([
            "key_press", "key_release", "key_tap",
            "mouse_click", "mouse_move", "delay",
            "mic_toggle", "mic_rules"
        ])
        _styled_input(self.type_combo)
        self.type_combo.setFixedWidth(120)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.main_layout.addWidget(self.type_combo)

        # 3. Properties container
        self.properties_widget = QWidget(self)
        self.properties_layout = QHBoxLayout(self.properties_widget)
        self.properties_layout.setContentsMargins(0, 0, 0, 0)
        self.properties_layout.setSpacing(8)
        self.main_layout.addWidget(self.properties_widget, stretch=1)

        # 4. Row action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.up_btn = QPushButton("▲", self)
        self.down_btn = QPushButton("▼", self)
        self.del_btn = QPushButton("✕", self)

        for btn, color in [
            (self.up_btn, "#388bfd"),
            (self.down_btn, "#388bfd"),
            (self.del_btn, "#f85149"),
        ]:
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #21262d;
                    border: 1px solid #30363d;
                    border-radius: 6px;
                    color: {color};
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background-color: #30363d;
                    border-color: {color};
                }}
            """)
            btn_layout.addWidget(btn)

        self.up_btn.clicked.connect(lambda: self.moved_up.emit(self))
        self.down_btn.clicked.connect(lambda: self.moved_down.emit(self))
        self.del_btn.clicked.connect(lambda: self.removed.emit(self))
        self.main_layout.addLayout(btn_layout)

        if action:
            self.type_combo.setCurrentText(action.type)
            self._load_properties(action.properties)
        else:
            self.on_type_changed(self.type_combo.currentText())

    def on_type_changed(self, action_type):
        while self.properties_layout.count():
            item = self.properties_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

        if action_type in ("key_press", "key_release", "key_tap"):
            lbl = QLabel("Key:", self)
            lbl.setStyleSheet(_LABEL)
            self.properties_layout.addWidget(lbl)

            key_in = QLineEdit(self)
            key_in.setObjectName("prop_key")
            key_in.setPlaceholderText("e.g. F13 or Escape")
            _styled_input(key_in)
            self.properties_layout.addWidget(key_in)

        elif action_type == "mouse_click":
            lbl = QLabel("Button:", self)
            lbl.setStyleSheet(_LABEL)
            self.properties_layout.addWidget(lbl)

            btn_combo = QComboBox(self)
            btn_combo.setObjectName("prop_button")
            btn_combo.addItems(["1 (Left)", "2 (Middle)", "3 (Right)", "4 (Scroll Up)", "5 (Scroll Down)"])
            _styled_input(btn_combo)
            self.properties_layout.addWidget(btn_combo)

        elif action_type == "mouse_move":
            for name, is_float in [("xp", True), ("x", False), ("yp", True), ("y", False)]:
                lbl = QLabel(f"{name}:", self)
                lbl.setStyleSheet(_LABEL)
                self.properties_layout.addWidget(lbl)

                if is_float:
                    box = QDoubleSpinBox(self)
                    box.setObjectName(f"prop_{name}")
                    box.setRange(0.0, 1.0)
                    box.setSingleStep(0.05)
                else:
                    box = QSpinBox(self)
                    box.setObjectName(f"prop_{name}")
                    box.setRange(-5000, 5000)
                _styled_input(box)
                self.properties_layout.addWidget(box)

        elif action_type == "delay":
            lbl = QLabel("Delay (ms):", self)
            lbl.setStyleSheet(_LABEL)
            self.properties_layout.addWidget(lbl)

            spin = QSpinBox(self)
            spin.setObjectName("prop_milliseconds")
            spin.setRange(1, 60000)
            spin.setValue(100)
            _styled_input(spin)
            self.properties_layout.addWidget(spin)

        elif action_type == "mic_toggle":
            chk = QCheckBox("Unmute mic", self)
            chk.setObjectName("prop_unmute")
            chk.setChecked(True)
            chk.setStyleSheet("color: #e6edf3; font-size: 12px;")
            self.properties_layout.addWidget(chk)

        elif action_type == "mic_rules":
            lbl = QLabel("Rules:", self)
            lbl.setStyleSheet(_LABEL)
            self.properties_layout.addWidget(lbl)

            rules_in = QLineEdit(self)
            rules_in.setObjectName("prop_rules")
            rules_in.setPlaceholderText("!vesktop, discord, all")
            _styled_input(rules_in)
            self.properties_layout.addWidget(rules_in)

            lbl_vol = QLabel("Vol:", self)
            lbl_vol.setStyleSheet(_LABEL)
            self.properties_layout.addWidget(lbl_vol)

            vol_in = QLineEdit(self)
            vol_in.setObjectName("prop_volume")
            vol_in.setText("1.0")
            vol_in.setFixedWidth(50)
            _styled_input(vol_in)
            self.properties_layout.addWidget(vol_in)

    def _load_properties(self, props):
        action_type = self.type_combo.currentText()
        if action_type in ("key_press", "key_release", "key_tap"):
            w = self.properties_widget.findChild(QLineEdit, "prop_key")
            if w:
                w.setText(props.get("key", ""))
        elif action_type == "mouse_click":
            combo = self.properties_widget.findChild(QComboBox, "prop_button")
            if combo:
                val = props.get("button", 1)
                for index in range(combo.count()):
                    if combo.itemText(index).startswith(str(val)):
                        combo.setCurrentIndex(index)
                        break
        elif action_type == "mouse_move":
            for name in ("xp", "yp"):
                box = self.properties_widget.findChild(QDoubleSpinBox, f"prop_{name}")
                if box:
                    box.setValue(props.get(name, 0.0))
            for name in ("x", "y"):
                box = self.properties_widget.findChild(QSpinBox, f"prop_{name}")
                if box:
                    box.setValue(props.get(name, 0))
        elif action_type == "delay":
            spin = self.properties_widget.findChild(QSpinBox, "prop_milliseconds")
            if spin:
                spin.setValue(props.get("milliseconds", 100))
        elif action_type == "mic_toggle":
            chk = self.properties_widget.findChild(QCheckBox, "prop_unmute")
            if chk:
                chk.setChecked(props.get("unmute", True))
        elif action_type == "mic_rules":
            rules_in = self.properties_widget.findChild(QLineEdit, "prop_rules")
            if rules_in:
                rules_in.setText(", ".join(props.get("rules", [])))
            vol_in = self.properties_widget.findChild(QLineEdit, "prop_volume")
            if vol_in:
                vol_in.setText(str(props.get("volume", "1.0")))

    def get_action_spec(self):
        action_type = self.type_combo.currentText()
        props = {}

        if action_type in ("key_press", "key_release", "key_tap"):
            w = self.properties_widget.findChild(QLineEdit, "prop_key")
            if w:
                props["key"] = w.text().strip()

        elif action_type == "mouse_click":
            combo = self.properties_widget.findChild(QComboBox, "prop_button")
            if combo:
                text = combo.currentText()
                props["button"] = int(text.split()[0])

        elif action_type == "mouse_move":
            for name in ("xp", "yp"):
                box = self.properties_widget.findChild(QDoubleSpinBox, f"prop_{name}")
                if box:
                    props[name] = box.value()
            for name in ("x", "y"):
                box = self.properties_widget.findChild(QSpinBox, f"prop_{name}")
                if box:
                    props[name] = box.value()

        elif action_type == "delay":
            spin = self.properties_widget.findChild(QSpinBox, "prop_milliseconds")
            if spin:
                props["milliseconds"] = spin.value()

        elif action_type == "mic_toggle":
            chk = self.properties_widget.findChild(QCheckBox, "prop_unmute")
            if chk:
                props["unmute"] = chk.isChecked()

        elif action_type == "mic_rules":
            rules_in = self.properties_widget.findChild(QLineEdit, "prop_rules")
            if rules_in:
                rules_raw = rules_in.text().split(",")
                props["rules"] = [r.strip() for r in rules_raw if r.strip()]
            vol_in = self.properties_widget.findChild(QLineEdit, "prop_volume")
            if vol_in:
                props["volume"] = vol_in.text().strip()

        return ActionSpec(action_type, props)


class ActionListWidget(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(title, self)
        lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #e6edf3;")
        header.addWidget(lbl)

        header.addStretch()

        add_btn = QPushButton("+ Add Action", self)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(_BTN_SUBTLE)
        add_btn.clicked.connect(self.add_empty_row)
        header.addWidget(add_btn)
        self.main_layout.addLayout(header)

        # Scroll area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical {
                background-color: #161b22; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #30363d; min-height: 24px; border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover { background-color: #484f58; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.scroll_content = QWidget(self)
        self.scroll_content.setStyleSheet("background-color: transparent;")
        self.rows_layout = QVBoxLayout(self.scroll_content)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)

    def populate(self, actions):
        self.clear_all()
        for act in actions:
            self.add_row(act)

    def clear_all(self):
        for i in reversed(range(self.rows_layout.count())):
            item = self.rows_layout.itemAt(i)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)

    def add_row(self, action=None):
        row = ActionRow(action, self)
        row.removed.connect(self.remove_row)
        row.moved_up.connect(self.move_row_up)
        row.moved_down.connect(self.move_row_down)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)

    def add_empty_row(self):
        self.add_row(None)

    def remove_row(self, row_widget):
        row_widget.setParent(None)

    def move_row_up(self, row_widget):
        idx = self.rows_layout.indexOf(row_widget)
        if idx > 0:
            self.rows_layout.removeWidget(row_widget)
            self.rows_layout.insertWidget(idx - 1, row_widget)

    def move_row_down(self, row_widget):
        idx = self.rows_layout.indexOf(row_widget)
        if idx < self.rows_layout.count() - 2:
            self.rows_layout.removeWidget(row_widget)
            self.rows_layout.insertWidget(idx + 1, row_widget)

    def get_actions(self):
        actions = []
        for i in range(self.rows_layout.count()):
            item = self.rows_layout.itemAt(i)
            if item is not None:
                w = item.widget()
                if isinstance(w, ActionRow):
                    actions.append(w.get_action_spec())
        return actions


class MacroEditor(QWidget):
    saved = Signal(object)
    cancelled = Signal()
    deleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: #0d1117;
                color: #e6edf3;
            }
        """)

        self.editing_macro_id = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Title
        self.title_label = QLabel("Create Macro", self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #e6edf3;")
        main_layout.addWidget(self.title_label)

        # Separator
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #21262d;")
        sep.setFixedHeight(1)
        main_layout.addWidget(sep)

        # Form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        for lbl_widget in []:
            pass  # labels styled via form row

        self.name_in = QLineEdit(self)
        self.name_in.setPlaceholderText("Macro Name")
        _styled_input(self.name_in)
        name_lbl = QLabel("Name:", self)
        name_lbl.setStyleSheet(_LABEL)
        form.addRow(name_lbl, self.name_in)

        self.desc_in = QLineEdit(self)
        self.desc_in.setPlaceholderText("Optional description")
        _styled_input(self.desc_in)
        desc_lbl = QLabel("Description:", self)
        desc_lbl.setStyleSheet(_LABEL)
        form.addRow(desc_lbl, self.desc_in)

        # Mode checkboxes
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(16)

        self.hold_chk = QCheckBox("Hold Mode (work only when pressed)", self)
        self.hold_chk.setChecked(True)
        self.hold_chk.setStyleSheet("color: #e6edf3; font-size: 12px;")
        self.hold_chk.stateChanged.connect(self.on_hold_state_changed)
        mode_layout.addWidget(self.hold_chk)

        self.loop_chk = QCheckBox("Loop while held", self)
        self.loop_chk.setStyleSheet("color: #e6edf3; font-size: 12px;")
        mode_layout.addWidget(self.loop_chk)

        mode_lbl = QLabel("Settings:", self)
        mode_lbl.setStyleSheet(_LABEL)
        form.addRow(mode_lbl, mode_layout)
        main_layout.addLayout(form)

        # Tabs
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #21262d;
                background-color: #161b22;
                border-radius: 8px;
                padding: 8px;
            }
            QTabBar::tab {
                background-color: #0d1117;
                border: 1px solid #21262d;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                color: #8b949e;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #161b22;
                color: #e6edf3;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                color: #c9d1d9;
                background-color: #1c2128;
            }
        """)

        self.press_list_widget = ActionListWidget("On Press (Hotkey Activated)", self)
        self.tabs.addTab(self.press_list_widget, "Press Actions")

        self.release_list_widget = ActionListWidget("On Release (Hotkey Deactivated)", self)
        self.tabs.addTab(self.release_list_widget, "Release Actions")

        main_layout.addWidget(self.tabs, stretch=1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.delete_btn = QPushButton("Delete Macro", self)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setStyleSheet(_BTN_DANGER)
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(_BTN_SUBTLE)
        cancel_btn.clicked.connect(self.cancelled.emit)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Macro", self)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(_BTN_PRIMARY)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def on_delete_clicked(self):
        reply = QMessageBox.question(
            self, 
            "Delete Macro", 
            "Are you sure you want to delete this macro?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.deleted.emit(self.editing_macro_id)

    def on_hold_state_changed(self, state):
        is_hold = state == Qt.CheckState.Checked.value
        self.loop_chk.setEnabled(is_hold)
        self.tabs.setTabEnabled(1, is_hold)

    def load_macro(self, macro):
        self.editing_macro_id = macro.id
        self.title_label.setText(f"Edit Macro: {macro.name}")
        self.name_in.setText(macro.name)
        self.desc_in.setText(macro.description)
        self.hold_chk.setChecked(macro.work_only_pressed)
        self.loop_chk.setChecked(macro.loop_while_held)
        self.loop_chk.setEnabled(macro.work_only_pressed)
        self.press_list_widget.populate(macro.press_actions)
        self.release_list_widget.populate(macro.release_actions)
        self.delete_btn.setVisible(True)

    def create_empty(self):
        import uuid
        self.editing_macro_id = f"macro_{uuid.uuid4().hex[:8]}"
        self.title_label.setText("Create Macro")
        self.name_in.clear()
        self.desc_in.clear()
        self.hold_chk.setChecked(True)
        self.loop_chk.setChecked(False)
        self.loop_chk.setEnabled(True)
        self.press_list_widget.clear_all()
        self.release_list_widget.clear_all()
        self.delete_btn.setVisible(False)

    def save(self):
        name = self.name_in.text().strip()
        if not name:
            name = "Unnamed Macro"

        macro = Macro(
            self.editing_macro_id,
            name,
            self.desc_in.text().strip(),
            "",
            self.hold_chk.isChecked(),
            self.loop_chk.isChecked(),
            True,
            self.press_list_widget.get_actions(),
            self.release_list_widget.get_actions()
        )
        self.saved.emit(macro)
