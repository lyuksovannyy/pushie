from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt

from app import evdev_shortcuts

SETUP_COMMAND = "sudo usermod -aG input $USER"


class EvdevSetupDialog(QDialog):
    """Explains how to grant Pushie direct (evdev) input access when it is not configured."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Evdev not configured")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
            }
            QLabel {
                color: #e6edf3;
                font-size: 13px;
            }
            QLabel#title_lbl {
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#hint_lbl {
                color: #8b949e;
                font-size: 12px;
            }
            QLabel#command_lbl {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px 12px;
                font-family: monospace;
                font-size: 13px;
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
            QPushButton#copy_btn {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
            }
            QPushButton#copy_btn:hover {
                background-color: #30363d;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("⚠️ Evdev is not configured", self)
        title.setObjectName("title_lbl")
        layout.addWidget(title)

        package_missing = evdev_shortcuts.evdev is None
        if package_missing:
            body_text = (
                "The <b>evdev</b> Python package is not installed, so the evdev "
                "bind method cannot be used. Install it and restart Pushie."
            )
        else:
            body_text = (
                "Pushie cannot read all of your input devices, so macros bound with "
                "the <b>evdev</b> method may not trigger.<br><br>"
                "Grant your user read access to <code>/dev/input/event*</code> by "
                "adding it to the <b>input</b> group:"
            )
        body = QLabel(body_text, self)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        layout.addWidget(body)

        self.copy_btn = None
        if not package_missing:
            command = QLabel(SETUP_COMMAND, self)
            command.setObjectName("command_lbl")
            command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(command)

            hint = QLabel(
                "Then log out and back in (or reboot) for the change to take effect. "
                "Until then you can keep using the xdg bind method.",
                self,
            )
            hint.setObjectName("hint_lbl")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        if not package_missing:
            self.copy_btn = QPushButton("Copy command", self)
            self.copy_btn.setObjectName("copy_btn")
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.clicked.connect(self._copy_command)
            buttons.addWidget(self.copy_btn)

        ok_btn = QPushButton("OK", self)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

    def _copy_command(self):
        QApplication.clipboard().setText(SETUP_COMMAND)
        if self.copy_btn:
            self.copy_btn.setText("Copied ✓")
