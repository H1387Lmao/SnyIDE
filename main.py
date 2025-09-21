import os
import sys

from texteditor import CodeEditor
from theme_to_stylesheet import get_stylesheet
from project_explorer import FileExplorerTree
from console import ConsoleWidget

from PySide6.QtWidgets import (
	QApplication, QMainWindow, QSplitter, QTabWidget, QFileDialog,
	QMenuBar, QMenu, QMessageBox, QDialog, QDialogButtonBox,
	QFormLayout, QLabel, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
	QPlainTextEdit
)
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QKeySequenceEdit
from PySide6.QtCore import Qt
import fnmatch

class SnyIDE(QMainWindow):
	def __init__(self, project_path, *args):
		super().__init__(*args)

		self.theme_path = os.path.join(os.path.dirname(__file__), "default.json")
		self.current_project = os.path.abspath(project_path)
		
		# Explorer
		self.Explorer = FileExplorerTree(self.current_project)
		self.Explorer.setObjectName("explorer")
		self.Explorer.doubleClicked.connect(self.on_explorer_double_clicked)

		# Tabs
		self.tabs = QTabWidget()
		self.tabs.setTabsClosable(True)
		self.tabs.setMovable(True)
		self.tabs.tabCloseRequested.connect(self.close_tab)

		# Console (bottom of right pane)
		self.console = ConsoleWidget(cwd=self.current_project, parent=self)

		# Right-side panel with topbar + (tabs|console) splitter
		self.right_panel = QWidget()
		right_layout = QVBoxLayout(self.right_panel)
		right_layout.setContentsMargins(0, 0, 0, 0)
		right_layout.setSpacing(0)
		# placeholder topbar; will be created in _create_topbar, but add a holder first
		self.topbar_holder = QWidget()
		right_layout.addWidget(self.topbar_holder)
		# Vertical splitter for editor tabs and console (resizable)
		self.editor_console_splitter = QSplitter(Qt.Vertical)
		self.editor_console_splitter.addWidget(self.tabs)
		self.editor_console_splitter.addWidget(self.console)
		self.editor_console_splitter.setStretchFactor(0, 3)
		self.editor_console_splitter.setStretchFactor(1, 1)
		self.editor_console_splitter.setSizes([800, 200])
		right_layout.addWidget(self.editor_console_splitter)
		self._console_prev_sizes = None

		# Main horizontal splitter
		self.splitter = QSplitter()
		self.setCentralWidget(self.splitter)
		self.splitter.addWidget(self.Explorer)
		self.splitter.addWidget(self.right_panel)
		self.splitter.setStretchFactor(0, 0)
		self.splitter.setStretchFactor(1, 1)

		# Menu and top status-like bar
		self._create_menu()
		self._create_topbar()

		# Load settings
		self._load_and_apply_shortcuts()
		self._load_run_options()

		# Theme
		self.setStyleSheet(get_stylesheet(self.theme_path))

		# Start with placeholder instead of an untitled editor
		self.show_placeholder()
		self._update_window_title()

		self.showMaximized()
	def _create_menu(self):
		menubar = self.menuBar() if hasattr(self, 'menuBar') else QMenuBar(self)
		if menubar is None:
			menubar = QMenuBar(self)
		self.setMenuBar(menubar)

		file_menu = menubar.addMenu("File")

		self.action_new_tab = QAction("New Tab", self)
		self.action_new_tab.triggered.connect(self.new_tab)
		file_menu.addAction(self.action_new_tab)

		self.action_open_file = QAction("Open File...", self)
		self.action_open_file.triggered.connect(self.open_file_dialog)
		file_menu.addAction(self.action_open_file)

		self.action_open_folder = QAction("Open Folder...", self)
		self.action_open_folder.triggered.connect(self.open_project_dialog)
		file_menu.addAction(self.action_open_folder)

		file_menu.addSeparator()

		self.action_close_tab = QAction("Close Tab", self)
		self.action_close_tab.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
		file_menu.addAction(self.action_close_tab)

		self.action_settings = QAction("Settings...", self)
		self.action_settings.triggered.connect(self.open_settings_dialog)
		file_menu.addAction(self.action_settings)

		self.action_exit = QAction("Exit", self)
		self.action_exit.triggered.connect(self.close)
		file_menu.addAction(self.action_exit)

		# Terminal menu
		terminal_menu = menubar.addMenu("Terminal")
		self.action_toggle_console = QAction("Toggle Console", self)
		self.action_toggle_console.triggered.connect(self.toggle_console)
		terminal_menu.addAction(self.action_toggle_console)

		self.action_terminal_clear = QAction("Clear", self)
		self.action_terminal_clear.triggered.connect(self.console.clear)
		terminal_menu.addAction(self.action_terminal_clear)

		self.action_terminal_restart = QAction("Restart Shell", self)
		self.action_terminal_restart.triggered.connect(self.console.restart)
		terminal_menu.addAction(self.action_terminal_restart)

	def _update_window_title(self):
		self.setWindowTitle(f"SnyIDE - {self.current_project}")

	def toggle_console(self):
		if self.console.isVisible():
			self._console_prev_sizes = self.editor_console_splitter.sizes()
			self.console.setVisible(False)
			# allocate all space to tabs automatically
		else:
			self.console.setVisible(True)
			if self._console_prev_sizes and len(self._console_prev_sizes) == 2:
				self.editor_console_splitter.setSizes(self._console_prev_sizes)
			else:
				self.editor_console_splitter.setSizes([800, 200])

	def _icon(self, name: str) -> QIcon:
		base_dir = os.path.dirname(__file__)
		return QIcon(os.path.join(base_dir, 'icons', name))

	def _create_topbar(self):
		# Create a flat status-like bar at the top (not a dock toolbar)
		bar = QFrame(self)
		bar.setObjectName("topBar")
		layout = QHBoxLayout(bar)
		layout.setContentsMargins(6, 4, 6, 4)
		layout.setSpacing(6)
		
		# Create actions (if not already)
		self.action_run_file = getattr(self, 'action_run_file', QAction(self._icon('run_file.svg'), "Run", self))
		self.action_run_file.triggered.connect(self.run_active_file)
		self.action_stop = getattr(self, 'action_stop', QAction(self._icon('stop_execution.svg'), "Stop", self))
		self.action_stop.triggered.connect(self.stop_execution)
		self.action_debug = getattr(self, 'action_debug', QAction(self._icon('debug_run.svg'), "Debug", self))
		self.action_debug.triggered.connect(self.debug_active_file)
		self.action_resume = getattr(self, 'action_resume', QAction(self._icon('resume_execution.svg'), "Resume", self))
		self.action_resume.triggered.connect(self.resume_execution)
		# Disable unimplemented actions for now
		self.action_debug.setEnabled(False)
		self.action_resume.setEnabled(False)
		
		# Buttons
		btn_run = QPushButton()
		btn_run.setObjectName("topbarButton")
		btn_run.setIcon(self.action_run_file.icon())
		btn_run.setToolTip("Run")
		btn_run.clicked.connect(self.action_run_file.trigger)
		layout.addWidget(btn_run)

		btn_stop = QPushButton()
		btn_stop.setObjectName("topbarButton")
		btn_stop.setIcon(self.action_stop.icon())
		btn_stop.setToolTip("Stop")
		btn_stop.clicked.connect(self.action_stop.trigger)
		layout.addWidget(btn_stop)

		btn_debug = QPushButton()
		btn_debug.setObjectName("topbarButton")
		btn_debug.setIcon(self.action_debug.icon())
		btn_debug.setToolTip("Debug")
		btn_debug.clicked.connect(self.action_debug.trigger)
		layout.addWidget(btn_debug)

		btn_resume = QPushButton()
		btn_resume.setObjectName("topbarButton")
		btn_resume.setIcon(self.action_resume.icon())
		btn_resume.setToolTip("Resume")
		btn_resume.clicked.connect(self.action_resume.trigger)
		layout.addWidget(btn_resume)

		layout.addStretch(1)
		# Replace holder
		self.topbar_holder.setParent(None)
		self.topbar = bar
		self.right_panel.layout().insertWidget(0, bar)

	def current_editor(self) -> CodeEditor:
		widget = self.tabs.currentWidget()
		return widget if isinstance(widget, CodeEditor) else None

	def run_active_file(self):
		editor = self.current_editor()
		if not editor or not getattr(editor, 'file_path', None):
			return  # No file selected; do nothing
		path = os.path.abspath(editor.file_path)
		cmd = self._command_for_file(path)
		if not cmd:
			return  # No matching run option; do nothing
		self.console.execute_line(cmd)

	def debug_active_file(self):
		# Not implemented; button is disabled
		pass

	def stop_execution(self):
		# Best-effort: restart the shell
		self.console.restart()

	def resume_execution(self):
		# Not implemented; button is disabled
		pass

	def new_tab(self):
		editor = CodeEditor(self.theme_path)
		idx = self.tabs.addTab(editor, os.path.basename(getattr(editor, 'file_path', '') or 'Untitled'))
		self.tabs.setCurrentIndex(idx)
		# Remove placeholder if present
		self._remove_placeholder_if_present()
		return editor

	def set_tab_title(self, index, path):
		name = os.path.basename(path) if path else "Untitled"
		self.tabs.setTabText(index, name)
		self.tabs.setTabToolTip(index, path or "")

	def open_file(self, path):
		if not os.path.isfile(path):
			return
		editor = CodeEditor(self.theme_path)
		editor.load_from_file(path)
		idx = self.tabs.addTab(editor, os.path.basename(path))
		self.tabs.setCurrentIndex(idx)
		self.tabs.setTabToolTip(idx, path)
		self._remove_placeholder_if_present()

	def close_tab(self, index):
		if index < 0:
			return
		widget = self.tabs.widget(index)
		# Ignore close if it's the placeholder
		if getattr(widget, 'objectName', lambda: '')() == 'noFileWidget':
			return
		# For future: prompt to save if modified
		self.tabs.removeTab(index)
		if widget is not None:
			widget.deleteLater()
		if self.tabs.count() == 0:
			self.show_placeholder()

	def open_file_dialog(self):
		path, _ = QFileDialog.getOpenFileName(self, "Open File", self.current_project)
		if path:
			self.open_file(path)

	def open_project_dialog(self):
		path = QFileDialog.getExistingDirectory(self, "Open Folder", self.current_project)
		if path:
			self.current_project = path
			self.Explorer.set_project_path(path)
			self.console.set_working_directory(path)
			self._update_window_title()

	def on_explorer_double_clicked(self, proxy_index):
		# Map from proxy to source to get the real path
		source_index = self.Explorer.proxy_model.mapToSource(proxy_index)
		path = self.Explorer.fs_model.filePath(source_index)
		if os.path.isfile(path):
			self.open_file(path)

	def show_placeholder(self):
		w = QWidget()
		w.setObjectName('noFileWidget')
		layout = QVBoxLayout(w)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)
		label = QLabel("No file selected")
		label.setAlignment(Qt.AlignCenter)
		layout.addStretch(1)
		layout.addWidget(label)
		layout.addStretch(2)
		idx = self.tabs.addTab(w, "No file selected")
		self.tabs.setCurrentIndex(idx)

	def _remove_placeholder_if_present(self):
		for i in range(self.tabs.count()):
			w = self.tabs.widget(i)
			if getattr(w, 'objectName', lambda: '')() == 'noFileWidget':
				self.tabs.removeTab(i)
				w.deleteLater()
				break

	# ---------- Settings / Shortcuts & Run Options ----------
	def _settings_path(self):
		return os.path.join(os.path.dirname(__file__), 'settings.json')

	def _default_shortcuts(self):
		return {
			'new_tab': 'Ctrl+N',
			'open_file': 'Ctrl+O',
			'open_folder': 'Ctrl+Shift+O',
			'close_tab': 'Ctrl+W',
			'exit': 'Alt+F4',
			'terminal_clear': 'Ctrl+L',
			'toggle_console': 'Ctrl+`',
			'settings': 'Ctrl+Alt+S',
			'run_file': 'Ctrl+Shift+F10',
			'stop': 'Ctrl+F2',
			'debug': 'Shift+F9',
			'resume': 'F9'
		}

	def _load_and_apply_shortcuts(self):
		import json
		shortcuts = self._default_shortcuts()
		try:
			with open(self._settings_path(), 'r', encoding='utf-8') as f:
				user = json.load(f).get('shortcuts', {})
				shortcuts.update(user)
		except Exception:
			pass
		self._apply_shortcuts(shortcuts)

	def _default_run_options(self):
		# pattern => command template
		return {
			"*.py": "python $path",
			"*.txt": "notepad $path"
		}

	def _load_run_options(self):
		import json
		opts = self._default_run_options()
		try:
			with open(self._settings_path(), 'r', encoding='utf-8') as f:
				user = json.load(f).get('run_options', {})
				if isinstance(user, dict):
					opts.update(user)
		except Exception:
			pass
		self.run_options = opts

	def _command_for_file(self, path: str) -> str | None:
		name = os.path.basename(path)
		for pattern, template in self.run_options.items():
			if fnmatch.fnmatch(name, pattern):
				cmd = template.replace("$path", f'"{path}"')
				return cmd
		return None

	def _apply_shortcuts(self, s):
		# Menu actions
		self.action_new_tab.setShortcut(QKeySequence(s['new_tab']))
		self.action_open_file.setShortcut(QKeySequence(s['open_file']))
		self.action_open_folder.setShortcut(QKeySequence(s['open_folder']))
		self.action_close_tab.setShortcut(QKeySequence(s['close_tab']))
		self.action_settings.setShortcut(QKeySequence(s['settings']))
		self.action_exit.setShortcut(QKeySequence(s['exit']))
		self.action_terminal_clear.setShortcut(QKeySequence(s['terminal_clear']))
		self.action_toggle_console.setShortcut(QKeySequence(s['toggle_console']))
		# Toolbar/Topbar actions
		self.action_run_file.setShortcut(QKeySequence(s['run_file']))
		self.action_stop.setShortcut(QKeySequence(s['stop']))
		self.action_debug.setShortcut(QKeySequence(s['debug']))
		self.action_resume.setShortcut(QKeySequence(s['resume']))

	def open_settings_dialog(self):
		from PySide6.QtWidgets import QWidget
		class SettingsDialog(QDialog):
			def __init__(self, parent, current_shortcuts, current_run_opts):
				super().__init__(parent)
				self.setWindowTitle('Settings')
				self.edits = {}
				self.run_opts_edit = QPlainTextEdit()
				# Build UI
				form = QFormLayout()
				self.setLayout(form)
				# Shortcuts editors
				labels = [
					('Run', 'run_file'), ('Stop', 'stop'), ('Debug', 'debug'), ('Resume', 'resume'),
					('Toggle Console', 'toggle_console'),
					('New Tab', 'new_tab'), ('Open File', 'open_file'), ('Open Folder', 'open_folder'),
					('Close Tab', 'close_tab'), ('Terminal: Clear', 'terminal_clear'), ('Settings', 'settings'), ('Exit', 'exit')
				]
				for label, key in labels:
					edit = QKeySequenceEdit()
					seq = current_shortcuts.get(key, '')
					if seq:
						edit.setKeySequence(QKeySequence(seq))
					self.edits[key] = edit
					form.addRow(QLabel(label+':'), edit)
				# Run options editor
				form.addRow(QLabel('Run options (one per line: pattern=command, use $path placeholder):'))
				lines = []
				for pat, cmd in current_run_opts.items():
					lines.append(f"{pat}={cmd}")
				self.run_opts_edit.setPlainText("\n".join(lines))
				form.addRow(self.run_opts_edit)
				# Buttons
				buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
				buttons.accepted.connect(self.accept)
				buttons.rejected.connect(self.reject)
				form.addRow(buttons)
			def shortcuts_values(self):
				res = {}
				for k, edit in self.edits.items():
					res[k] = edit.keySequence().toString()
				return res
			def run_opts_values(self):
				text = self.run_opts_edit.toPlainText()
				opts = {}
				for line in text.splitlines():
					line = line.strip()
					if not line or line.startswith('#'):
						continue
					if '=' not in line:
						continue
					pat, cmd = line.split('=', 1)
					pat = pat.strip()
					cmd = cmd.strip()
					if pat and cmd:
						opts[pat] = cmd
				return opts
		# Load current settings
		shortcuts = self._default_shortcuts()
		run_opts = self._default_run_options()
		import json
		try:
			with open(self._settings_path(), 'r', encoding='utf-8') as f:
				data = json.load(f)
				shortcuts.update(data.get('shortcuts', {}))
				run_opts.update(data.get('run_options', {}))
		except Exception:
			pass
		dlg = SettingsDialog(self, shortcuts, run_opts)
		if dlg.exec() == QDialog.Accepted:
			new_shortcuts = dlg.shortcuts_values()
			new_run_opts = dlg.run_opts_values()
			# Save (merge with any unknown future fields)
			data = {}
			try:
				with open(self._settings_path(), 'r', encoding='utf-8') as f:
					data = json.load(f)
			except Exception:
				data = {}
			data['shortcuts'] = new_shortcuts
			data['run_options'] = new_run_opts
			try:
				with open(self._settings_path(), 'w', encoding='utf-8') as f:
					json.dump(data, f, indent=2)
			except Exception as e:
				QMessageBox.warning(self, 'Settings', f'Failed to save settings: {e}')
			# Apply
			merged = self._default_shortcuts()
			merged.update(new_shortcuts)
			self._apply_shortcuts(merged)
			self.run_options = self._default_run_options()
			self.run_options.update(new_run_opts)


app = QApplication(sys.argv)
ide = SnyIDE('.')
ide.show()
sys.exit(app.exec())
