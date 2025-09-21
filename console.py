import os
import shutil
from PySide6.QtCore import QProcess, QByteArray, Qt, Slot, QEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit

class ConsoleWidget(QWidget):
    def __init__(self, cwd=None, parent=None):
        super().__init__(parent)
        self.cwd = os.path.abspath(cwd or os.getcwd())
        self.proc = None
        self.history = []
        self.history_index = -1
        self.input_start_pos = 0

        self.terminal = QPlainTextEdit(self)
        self.terminal.setObjectName("console")
        self.terminal.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.terminal)

        self.start()
        # Prepare input region at end
        self._move_cursor_to_end()
        self.input_start_pos = self._doc_length()

    def detect_shell(self):
        if os.name == 'nt':
            for exe in ("pwsh.exe", "powershell.exe", "cmd.exe"):
                path = shutil.which(exe)
                if path:
                    return path
            return "cmd.exe"
        # Unix-like fallback
        for exe in ("bash", "zsh", "fish", "sh"):
            path = shutil.which(exe)
            if path:
                return path
        return "sh"

    def start(self):
        self.stop()
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(self.cwd)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._on_ready_read)
        self.proc.readyReadStandardError.connect(self._on_ready_read)
        self.proc.started.connect(lambda: self._append_text(f"[shell started in {self.cwd}]\n"))
        self.proc.finished.connect(lambda code, status: self._append_text(f"\n[shell exited {code}]\n"))

        shell = self.detect_shell()
        if os.name == 'nt':
            if shell.lower().endswith('pwsh.exe'):
                program = shell
                args = ['-NoLogo']
            elif shell.lower().endswith('powershell.exe'):
                program = shell
                args = ['-NoLogo']
            else:
                program = shell
                args = ['/K']  # keep cmd.exe open
        else:
            program = shell
            args = ['-i']  # interactive

        self.proc.start(program, args)

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.waitForFinished(1000)
            except Exception:
                pass
            self.proc = None

    def restart(self):
        self.start()

    def clear(self):
        self.terminal.clear()
        self.input_start_pos = 0

    def set_working_directory(self, cwd):
        self.cwd = os.path.abspath(cwd)
        # Restart shell in new directory
        self.restart()

    def _append_text(self, text: str):
        # Preserve current pending input by temporarily removing it
        pending = self._current_input_text()
        if pending:
            self._replace_input("")
        self.terminal.moveCursor(QTextCursor.End)
        self.terminal.insertPlainText(text)
        self.terminal.moveCursor(QTextCursor.End)
        # Re-append pending input
        if pending:
            self.terminal.insertPlainText(pending)
        self._update_input_start()

    @Slot()
    def _on_ready_read(self):
        if not self.proc:
            return
        data = bytes(self.proc.readAllStandardOutput())
        if data:
            try:
                s = data.decode('utf-8', errors='ignore')
            except Exception:
                s = str(data)
            self._append_text(s)

    def eventFilter(self, obj, event):
        if obj is self.terminal and event.type() == QEvent.KeyPress:
            return self._handle_key_press(event)
        return super().eventFilter(obj, event)

    def _handle_key_press(self, event):
        key = event.key()
        cursor = self.terminal.textCursor()
        # Prevent editing before input_start_pos
        if key in (Qt.Key_Backspace, Qt.Key_Left):
            if cursor.position() <= self.input_start_pos and not cursor.hasSelection():
                return True
            if cursor.hasSelection() and cursor.selectionStart() < self.input_start_pos:
                return True
        if key == Qt.Key_Home:
            cursor.setPosition(self.input_start_pos)
            self.terminal.setTextCursor(cursor)
            return True
        if key in (Qt.Key_Up, Qt.Key_Down):
            if not self.history:
                return True
            if key == Qt.Key_Up:
                self.history_index = max(0, self.history_index - 1) if self.history_index != -1 else len(self.history) - 1
            else:
                if self.history_index == -1:
                    return True
                self.history_index = min(len(self.history) - 1, self.history_index + 1)
            self._replace_input(self.history[self.history_index])
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            cmd = self._current_input_text()
            # Let the newline be inserted visually
            self.terminal.insertPlainText("\n")
            self._send_command(cmd)
            self.history.append(cmd)
            self.history_index = -1
            self._update_input_start()
            return True
        # For all other keys, ensure cursor is in input region
        if cursor.position() < self.input_start_pos:
            cursor.setPosition(self._doc_length())
            self.terminal.setTextCursor(cursor)
        return False

    def _send_command(self, cmd: str):
        if cmd is None:
            cmd = ""
        if os.name == 'nt':
            data = (cmd + "\r\n").encode('utf-8', errors='ignore')
        else:
            data = (cmd + "\n").encode('utf-8', errors='ignore')
        if self.proc and self.proc.state() == QProcess.ProcessState.Running:
            self.proc.write(QByteArray(data))
            self.proc.waitForBytesWritten(100)

    def execute_line(self, cmd: str):
        # Programmatically execute a command without echoing it in the console
        self._send_command(cmd)

    # Helpers
    def _move_cursor_to_end(self):
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.terminal.setTextCursor(cursor)

    def _doc_length(self):
        return len(self.terminal.toPlainText())

    def _current_input_text(self) -> str:
        text = self.terminal.toPlainText()
        return text[self.input_start_pos:]

    def _replace_input(self, text: str):
        cursor = self.terminal.textCursor()
        cursor.setPosition(self.input_start_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.terminal.setTextCursor(cursor)

    def _update_input_start(self):
        self.input_start_pos = self._doc_length()

    def closeEvent(self, event):
        try:
            self.stop()
        finally:
            super().closeEvent(event)
