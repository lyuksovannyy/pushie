import os

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtWidgets import QCompleter, QLineEdit

_POPUP_STYLE = """
    QListView {
        background-color: #161b22;
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 6px;
        font-size: 12px;
        outline: none;
    }
    QListView::item {
        padding: 4px 8px;
    }
    QListView::item:selected {
        background-color: #1f6feb;
        color: #ffffff;
    }
"""


def list_rule_candidates() -> list[str]:
    """Names that can be used in mic rules, most relevant first.

    "all", then apps that currently have an audio capture stream (what the
    rules are actually matched against), then every running process name.
    """
    from app.engine import PulseAudioHelper

    audio: set[str] = set()
    try:
        for _index, name, binary, _source in PulseAudioHelper.get_app_sources():
            for value in (binary, name):
                value = value.strip().lower()
                if value and value != "unknown*":
                    audio.add(value)
    except Exception:
        pass

    processes: set[str] = set()
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/comm", "r") as f:
                    comm = f.read().strip().lower()
            except Exception:
                continue
            # Skip kernel threads (no command line)
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    if not f.read(1):
                        continue
            except Exception:
                continue
            if comm:
                processes.add(comm)
    except Exception:
        pass

    return ["all"] + sorted(audio) + sorted(processes - audio - {"all"})


class RulesLineEdit(QLineEdit):
    """Line edit for comma-separated mic rules with per-rule autocomplete.

    Completion applies to the rule under the cursor only and keeps a leading
    "!" (mute marker), so typing "all, !dis" offers "discord" and yields
    "all, !discord".
    """

    def __init__(self, parent=None, candidates_provider=list_rule_candidates):
        super().__init__(parent)
        self._candidates_provider = candidates_provider
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setWidget(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setMaxVisibleItems(12)
        self._completer.popup().setStyleSheet(_POPUP_STYLE)
        self._completer.activated[str].connect(self._insert_completion)
        self.textEdited.connect(self._show_popup)

    # --- token helpers ---
    def _token_bounds(self) -> tuple[int, int]:
        """Start/end offsets of the comma-separated rule under the cursor."""
        text = self.text()
        pos = self.cursorPosition()
        start = text.rfind(",", 0, pos) + 1
        end = text.find(",", pos)
        if end == -1:
            end = len(text)
        return start, end

    def _current_prefix(self) -> str:
        start, _end = self._token_bounds()
        typed = self.text()[start:self.cursorPosition()]
        return typed.strip().lstrip("!").strip()

    # --- popup ---
    def refresh_candidates(self) -> None:
        try:
            self._model.setStringList(self._candidates_provider())
        except Exception:
            self._model.setStringList(["all"])

    def _show_popup(self, *_args) -> None:
        self._completer.setCompletionPrefix(self._current_prefix())
        popup = self._completer.popup()
        if self._completer.completionCount() == 0:
            popup.hide()
            return
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        self._completer.complete()

    def _insert_completion(self, completion: str) -> None:
        text = self.text()
        start, end = self._token_bounds()
        token = text[start:end]
        negated = token.strip().startswith("!")
        lead = "" if start == 0 else " "
        new_token = f"{lead}{'!' if negated else ''}{completion}"
        self.setText(text[:start] + new_token + text[end:])
        self.setCursorPosition(start + len(new_token))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Popup closing hands focus back; don't rescan the system for that.
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.refresh_candidates()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._show_popup()
