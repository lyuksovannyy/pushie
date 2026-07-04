from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QComboBox, QScrollArea, QFrame,
    QTabWidget, QFormLayout, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal
from app.storage import Macro, ActionSpec

class ActionRow(QFrame):
    removed = Signal(QWidget)
    moved_up = Signal(QWidget)
    moved_down = Signal(QWidget)

    def __init__(self, action=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("""
            ActionRow {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 4px;
            }
        """)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)

        # 1. Action Type selector
        self.type_combo = QComboBox(self)
        self.type_combo.addItems([
            "key_press",
            "key_release",
            "key_tap",
            "mouse_click",
            "mouse_move",
            "delay",
            "mic_toggle",
            "mic_rules"
        ])
        self.type_combo.setStyleSheet("""
            QComboBox {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.main_layout.addWidget(self.type_combo)

        # 2. Properties Form Container
        self.properties_widget = QWidget(self)
        self.properties_layout = QHBoxLayout(self.properties_widget)
        self.properties_layout.setContentsMargins(0, 0, 0, 0)
        self.properties_layout.setSpacing(6)
        self.main_layout.addWidget(self.properties_widget, stretch=1)

        # 3. Actions (Up, Down, Delete buttons)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)

        self.up_btn = QPushButton("▲", self)
        self.down_btn = QPushButton("▼", self)
        self.del_btn = QPushButton("✕", self)

        for btn, style in [
            (self.up_btn, "color: #388bfd;"),
            (self.down_btn, "color: #388bfd;"),
            (self.del_btn, "color: #f85149;")
        ]:
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #30363d;
                    border: 1px solid #21262d;
                    border-radius: 4px;
                    {style}
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background-color: #444c56;
                }}
            """)
            btn_layout.addWidget(btn)

        self.up_btn.clicked.connect(lambda: self.moved_up.emit(self))
        self.down_btn.clicked.connect(lambda: self.moved_down.emit(self))
        self.del_btn.clicked.connect(lambda: self.removed.emit(self))
        self.main_layout.addLayout(btn_layout)

        # Load dynamic properties inputs
        if action:
            self.type_combo.setCurrentText(action.type)
            self._load_properties(action.properties)
        else:
            self.on_type_changed(self.type_combo.currentText())

    def on_type_changed(self, action_type):
        # Clear properties layout
        while self.properties_layout.count():
            item = self.properties_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
        
        # Build UI based on selected type
        if action_type in ("key_press", "key_release", "key_tap"):
            lbl = QLabel("Key:", self)
            lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            self.properties_layout.addWidget(lbl)
            
            key_in = QLineEdit(self)
            key_in.setObjectName("prop_key")
            key_in.setPlaceholderText("e.g. F13 or Escape")
            key_in.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 4px; border-radius: 4px;")
            self.properties_layout.addWidget(key_in)

        elif action_type == "mouse_click":
            lbl = QLabel("Btn:", self)
            lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            self.properties_layout.addWidget(lbl)
            
            btn_combo = QComboBox(self)
            btn_combo.setObjectName("prop_button")
            btn_combo.addItems(["1 (Left)", "2 (Middle)", "3 (Right)", "4 (Scroll Up)", "5 (Scroll Down)"])
            btn_combo.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 4px; border-radius: 4px;")
            self.properties_layout.addWidget(btn_combo)

        elif action_type == "mouse_move":
            for name, is_float in [("xp", True), ("x", False), ("yp", True), ("y", False)]:
                lbl = QLabel(f"{name}:", self)
                lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
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
                box.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px;")
                self.properties_layout.addWidget(box)

        elif action_type == "delay":
            lbl = QLabel("Delay (ms):", self)
            lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            self.properties_layout.addWidget(lbl)
            
            spin = QSpinBox(self)
            spin.setObjectName("prop_milliseconds")
            spin.setRange(1, 60000)
            spin.setValue(100)
            spin.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 4px; border-radius: 4px;")
            self.properties_layout.addWidget(spin)

        elif action_type == "mic_toggle":
            chk = QCheckBox("Unmute mic", self)
            chk.setObjectName("prop_unmute")
            chk.setChecked(True)
            chk.setStyleSheet("color: #c9d1d9;")
            self.properties_layout.addWidget(chk)

        elif action_type == "mic_rules":
            lbl = QLabel("Rules:", self)
            lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
            self.properties_layout.addWidget(lbl)
            
            rules_in = QLineEdit(self)
            rules_in.setObjectName("prop_rules")
            rules_in.setPlaceholderText("!vesktop, discord, all")
            rules_in.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 4px; border-radius: 4px;")
            self.properties_layout.addWidget(rules_in)
            
            lbl_vol = QLabel("Vol:", self)
            lbl_vol.setStyleSheet("color: #8b949e; font-size: 10px;")
            self.properties_layout.addWidget(lbl_vol)
            
            vol_in = QLineEdit(self)
            vol_in.setObjectName("prop_volume")
            vol_in.setText("1.0")
            vol_in.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 4px; border-radius: 4px;")
            self.properties_layout.addWidget(vol_in)

    def _load_properties(self, props):
        action_type = self.type_combo.currentText()
        if action_type in ("key_press", "key_release", "key_tap"):
            in_widget = self.properties_widget.findChild(QLineEdit, "prop_key")
            if in_widget:
                in_widget.setText(props.get("key", ""))
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
            in_widget = self.properties_widget.findChild(QLineEdit, "prop_key")
            if in_widget:
                props["key"] = in_widget.text().strip()
                
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
        
        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        
        # Top panel: Title and Add Action Button
        header = QHBoxLayout()
        lbl = QLabel(title, self)
        lbl.setStyleSheet("font-weight: bold; color: #ffffff;")
        header.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignLeft)
        
        add_btn = QPushButton("+ Add Action", self)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
        """)
        add_btn.clicked.connect(self.add_empty_row)
        header.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.main_layout.addLayout(header)

        # Scroll Area for rows
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background-color: #0d1117;")
        
        self.scroll_content = QWidget(self)
        self.scroll_content.setStyleSheet("background-color: #0d1117;")
        self.rows_layout = QVBoxLayout(self.scroll_content)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.rows_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)

    def populate(self, actions):
        # Clear existing
        self.clear_all()
        # Add new
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
        
        # Insert before the stretch item
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
        # Note: the last item in lay is the stretch spacer
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
    saved = Signal(object) # Macro
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: #0d1117;
                color: #c9d1d9;
            }
        """)

        # Keep reference to macro being edited (None if creating)
        self.editing_macro_id = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Title
        self.title_label = QLabel("Create Macro", self)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        main_layout.addWidget(self.title_label)

        # Form Layout details
        form = QFormLayout()
        form.setSpacing(6)
        
        self.name_in = QLineEdit(self)
        self.name_in.setPlaceholderText("Macro Name")
        self.name_in.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 6px 12px; font-size: 12px;")
        form.addRow("Name:", self.name_in)

        self.desc_in = QLineEdit(self)
        self.desc_in.setPlaceholderText("Optional description")
        self.desc_in.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 6px 12px; font-size: 12px;")
        form.addRow("Description:", self.desc_in)

        # Checkboxes/modes
        mode_layout = QHBoxLayout()
        self.hold_chk = QCheckBox("Work Only When Pressed (Hold Mode)", self)
        self.hold_chk.setChecked(True)
        self.hold_chk.setStyleSheet("color: #c9d1d9;")
        self.hold_chk.stateChanged.connect(self.on_hold_state_changed)
        mode_layout.addWidget(self.hold_chk)

        self.loop_chk = QCheckBox("Loop while held", self)
        self.loop_chk.setChecked(False)
        self.loop_chk.setStyleSheet("color: #c9d1d9;")
        mode_layout.addWidget(self.loop_chk)
        form.addRow("Settings:", mode_layout)
        main_layout.addLayout(form)

        # Tabs for Actions
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #30363d;
                background-color: #161b22;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-bottom-color: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 12px;
                color: #8b949e;
            }
            QTabBar::tab:selected {
                background-color: #161b22;
                color: #ffffff;
                border-bottom-color: #161b22;
            }
        """)

        # Tab 1: Press Actions
        self.press_list_widget = ActionListWidget("On Press (Hotkey Activated)", self)
        self.tabs.addTab(self.press_list_widget, "Press actions")

        # Tab 2: Release Actions
        self.release_list_widget = ActionListWidget("On Release (Hotkey Deactivated)", self)
        self.tabs.addTab(self.release_list_widget, "Release actions (Hold Mode only)")

        main_layout.addWidget(self.tabs, stretch=1)

        # Bottom row: Save and Cancel
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        save_btn = QPushButton("Save", self)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
        """)
        cancel_btn.clicked.connect(self.cancelled.emit)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

    def on_hold_state_changed(self, state):
        is_hold = state == Qt.CheckState.Checked.value
        self.loop_chk.setEnabled(is_hold)
        self.tabs.setTabEnabled(1, is_hold) # Toggle "Release actions" tab

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

    def save(self):
        name = self.name_in.text().strip()
        if not name:
            name = "Unnamed Macro"
        
        macro = Macro(
            self.editing_macro_id,
            name,
            self.desc_in.text().strip(),
            "", # hotkey gets registered later
            self.hold_chk.isChecked(),
            self.loop_chk.isChecked(),
            True, # active by default
            self.press_list_widget.get_actions(),
            self.release_list_widget.get_actions()
        )
        self.saved.emit(macro)
