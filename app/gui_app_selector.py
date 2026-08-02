from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal
import subprocess
import os


class AppSelectorDialog(QDialog):
    """Modal dialog for selecting target apps for a macro."""
    
    def __init__(self, macro, parent=None):
        super().__init__(parent)
        self.macro = macro
        self.selected_apps = set(macro.target_apps) if macro.target_apps else set()
        
        self.setWindowTitle(f"Target Apps - {macro.name}")
        self.setModal(True)
        self.resize(500, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
            }
            QLabel {
                color: #e6edf3;
            }
            QLineEdit {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #388bfd;
            }
            QListWidget {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #21262d;
            }
            QListWidget::item:hover {
                background-color: #1c2128;
            }
            QListWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton#cancel_btn {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
            }
            QPushButton#cancel_btn:hover {
                background-color: #30363d;
            }
            QPushButton#clear_btn {
                background-color: #3d1519;
                color: #f85149;
                border: 1px solid #da3633;
            }
            QPushButton#clear_btn:hover {
                background-color: #5c1d24;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Select Target Applications", self)
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e6edf3;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Choose which apps this macro should work in. Empty = works in all apps.", self)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px; padding-bottom: 8px;")
        layout.addWidget(desc)
        
        # Search bar
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Search apps...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)
        
        # List
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.list_widget)
        
        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        clear_btn = QPushButton("Clear All", self)
        clear_btn.setObjectName("clear_btn")
        clear_btn.clicked.connect(self._on_clear_clicked)
        btn_row.addWidget(clear_btn)
        
        btn_row.addStretch()
        
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)
        
        layout.addLayout(btn_row)
        
        # Populate
        self._all_apps = self._detect_running_apps()
        self._populate_list()
    
    def _detect_running_apps(self):
        """Detect running applications via /proc."""
        apps = set()
        try:
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    with open(f"/proc/{pid}/comm", "r") as f:
                        comm = f.read().strip()
                        if comm:
                            apps.add(comm)
                except Exception:
                    pass
        except Exception:
            pass
        return sorted(apps)
    
    def _populate_list(self, filter_text=""):
        """Populate list with apps, optionally filtered."""
        self.list_widget.clear()
        filter_lower = filter_text.lower()
        
        for app in self._all_apps:
            if filter_text and filter_lower not in app.lower():
                continue
            
            item = QListWidgetItem(app)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            if app in self.selected_apps:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            
            self.list_widget.addItem(item)
    
    def _on_search_changed(self, text):
        self._populate_list(text)
    
    def _on_clear_clicked(self):
        self.selected_apps.clear()
        self._populate_list(self.search_input.text())
    
    def get_selected_apps(self):
        """Return list of selected app names."""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected
