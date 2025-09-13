import os
import sys

from texteditor import *
from theme_to_stylesheet import *
from project_explorer import *

from PySide6.QtWidgets import QApplication, QMainWindow, QSplitter

class SnyIDE(QMainWindow):
	def __init__(self, project_path, *args):
		super().__init__(*args)

		self.theme_path = os.path.dirname(__file__)+"/default.json"

		self.editor = CodeEditor(self.theme_path)
		self.editor.setObjectName("Editor")
		self.Explorer = FileExplorerTree(project_path)
		self.Explorer.setObjectName("explorer")
		
		self.splitter = QSplitter()
		self.setCentralWidget(self.splitter)

		self.splitter.addWidget(self.Explorer)
		self.splitter.addWidget(self.editor)

		self.setStyleSheet(get_stylesheet(self.theme_path))
		

app = QApplication(sys.argv)
ide = SnyIDE('.')
ide.show()
sys.exit(app.exec())
