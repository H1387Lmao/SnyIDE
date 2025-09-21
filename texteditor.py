from PySide6.QtWidgets import QPlainTextEdit, QWidget, QCompleter, QApplication
from PySide6.QtGui import (
	QSyntaxHighlighter, QTextCharFormat, QColor, 
	QFont, QPainter, QTextCursor
)
from PySide6.QtCore import Qt, QSize, QRegularExpression, QStringListModel

import json
import os
import re

class CodeEditor(QPlainTextEdit):
	def __init__(self, c):
		super().__init__()
		self.setFont(QFont("Cascadia Code", 14))

		self.Highlighter = Highlighter(c, self.document(), "python")

		with open(c) as f:
			self.colors = json.load(f)
		
		self.file_path = None
		
		self.class_regex = re.compile(self.Highlighter.auto_regex['class'])
		self.defs = re.compile(self.Highlighter.auto_regex['def']) 
		self.dynamic_completions = self.Highlighter.completions

		self.completer = QCompleter(sorted(self.dynamic_completions))
		self.completer.setCaseSensitivity(Qt.CaseInsensitive)
		self.completer.setWidget(self)
		self.completer.activated.connect(self.insertCompletion)
		# Style the popup via objectName for QSS
		popup = self.completer.popup()
		popup.setObjectName('completerPopup')

		self.pairs = {'(': ')', '[': ']', '{': f'}}', '"': '"', "'": "'"} 

		self._init_line_number_area()
		self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))

		# Connect textChanged signal to update completions dynamically
		self.textChanged.connect(self.updateDynamicCompletions)

	def load_from_file(self, path, encoding='utf-8'):
		with open(path, 'r', encoding=encoding, errors='replace') as f:
			self.setPlainText(f.read())
		self.file_path = path

	def updateDynamicCompletions(self):
		# Get full document text
		text = self.toPlainText()

		# Find all class names in the document
		matches = set(self.class_regex.findall(text)+self.defs.findall(text))

		# Find new completions that aren't in current set
		new_items = matches - self.dynamic_completions
		if new_items:
			self.dynamic_completions.update(new_items)
			# Update completer model
			model = QStringListModel(sorted(self.dynamic_completions))
			self.completer.setModel(model)

	def wheelEvent(self, event):
		if event.modifiers() & Qt.ControlModifier:
			delta = event.angleDelta().y()
			# Zoom in/out based on wheel delta
			current_font = self.font()
			current_size = current_font.pointSizeF()
			if current_size < 1:  # fallback for invalid sizes
				current_size = 12

			# Increase/decrease font size by 1 per wheel step (120 units)
			if delta > 0:
				new_size = current_size + 1
			else:
				new_size = max(1, current_size - 1)  # Don't go below 1

			current_font.setPointSizeF(new_size)
			self.setFont(current_font)
			event.accept()
		else:
			super().wheelEvent(event)


	def insertCompletion(self, text):
		tc = self.textCursor()
		prefix_len = len(self.completer.completionPrefix())

		# Move cursor to select the word under cursor (prefix)
		tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, prefix_len)
		tc.removeSelectedText()
		tc.insertText(text)
		self.setTextCursor(tc)


	def keyPressEvent(self, event):
		cursor = self.textCursor()
		char = event.text()
		key = event.key()

		if key == Qt.Key_Backspace and not cursor.hasSelection():
			pos = cursor.position()
			if pos > 0:
				text = self.toPlainText()
				prev_char = text[pos - 1]
				next_char = text[pos] if pos < len(text) else ''
				if prev_char in self.pairs and self.pairs[prev_char] == next_char:
					# Delete both
					cursor.beginEditBlock()
					cursor.deletePreviousChar()  # delete opening
					cursor.deleteChar()          # delete closing
					cursor.endEditBlock()
					self.setTextCursor(cursor)
					return

		# Handle auto-close
		if char in self.pairs:
			closing_char = self.pairs[char]
			super().keyPressEvent(event)
			self.insertPlainText(closing_char)
			cursor.movePosition(QTextCursor.Left)  # FIXED
			self.setTextCursor(cursor)
			return

		# Handle overtyping closing char
		if char and cursor.position() < len(self.toPlainText()):
			next_char = self.toPlainText()[cursor.position()]
			if char in self.pairs.values() and char == next_char:
				cursor.movePosition(QTextCursor.Right)  # FIXED
				self.setTextCursor(cursor)
				return

		if key == Qt.Key_Tab:
			prefix = self.textUnderCursor()
			popup = self.completer.popup()
			if popup.isVisible():
				index = popup.currentIndex()
				if index.isValid():
					text = index.data()
					self.insertCompletion(text)
					self.completer.popup().hide()
					return
				self.completer.setCompletionPrefix(prefix)
				completions = self.completer.model().match(
					self.completer.model().index(0, 0),
					Qt.DisplayRole,
					prefix,
					-1,
					Qt.MatchStartsWith
				)
				if completions:
					best_match_index = completions[0]
					best_match = best_match_index.data()
					if best_match and best_match != prefix:
						tc = self.textCursor()
						tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
						tc.insertText(best_match)
						self.setTextCursor(tc)
					self.completer.popup().hide()
					return

			# fallback: insert tab
			self.insertPlainText('\t')
			return





		if key == Qt.Key_Return or key == Qt.Key_Enter:
			cursor.select(QTextCursor.LineUnderCursor)
			line_text = cursor.selectedText()
			indent = ''
			for ch in line_text:
				if ch in [' ', '\t']:
					indent += ch
				else:
					break
			super().keyPressEvent(event)
			self.insertPlainText(indent)
			return

		super().keyPressEvent(event)

		# Trigger autocomplete
			# --- Show/hide autocomplete popup ---
		prefix = self.textUnderCursor()
		if prefix:
			self.completer.setCompletionPrefix(prefix)
			completions = self.completer.model().match(
				self.completer.model().index(0, 0),
				Qt.DisplayRole,
				prefix,
				-1,
				Qt.MatchStartsWith
			)

			if not completions:
				self.completer.popup().hide()
			else:
				# If the only match is the exact word already typed, hide
				first_match = completions[0].data()
				if len(completions) == 1 and first_match.lower() == prefix.lower():
					self.completer.popup().hide()
				else:
					font_metrics = self.fontMetrics()
					model = self.completer.model()
					longest = max((model.data(model.index(i, 0)) for i in range(model.rowCount())), key=len, default='')
					popup_width = font_metrics.horizontalAdvance(longest) + 30  # padding for scrollbar/margin

					# Set popup width based on longest completion
					rect = self.cursorRect()
					rect.setWidth(popup_width)
					self.completer.complete(rect)
		else:
			self.completer.popup().hide()

	def textUnderCursor(self):
		tc = self.textCursor()
		tc.select(QTextCursor.WordUnderCursor)
		return tc.selectedText()

	# ---------- Line Numbers ----------

	def _init_line_number_area(self):
		self.line_number_area = LineNumberArea(self)
		self.line_number_area.setObjectName("numberline")
		self.blockCountChanged.connect(self.update_line_number_area_width)
		self.updateRequest.connect(self.update_line_number_area)
		self.cursorPositionChanged.connect(self.line_number_area.update)

		self.update_line_number_area_width(0)

	def line_number_area_width(self):
		digits = len(str(max(1, self.blockCount())))
		return self.fontMetrics().horizontalAdvance('9') * digits + 10

	def update_line_number_area_width(self, _):
		self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

	def update_line_number_area(self, rect, dy):
		if dy:
			self.line_number_area.scroll(0, dy)
		else:
			self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

		if rect.contains(self.viewport().rect()):
			self.update_line_number_area_width(0)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		cr = self.contentsRect()
		self.line_number_area.setGeometry(cr.x(), cr.y(),
										  self.line_number_area_width(), cr.height())
		self.line_number_area.update()

	def paintEvent(self, event):
		super().paintEvent(event)

		painter = QPainter(self.viewport())
		painter.setPen(QColor("#e0e0e0"))  # Light gray color for indent guides

		block = self.firstVisibleBlock()
		top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
		bottom = top + self.blockBoundingRect(block).height()

		indent_width = self.fontMetrics().horizontalAdvance(' ') * 4  # assuming 4-space indent

		while block.isValid() and top <= event.rect().bottom():
			text = block.text()
			indent_level = 0
			for ch in text:
				if ch == '\t':
					indent_level += 1
				elif ch == ' ':
					indent_level += 1 / 4  # 4 spaces = 1 indent
				else:
					break

			for i in range(int(indent_level)):
				x = i * indent_width
				painter.drawLine(int(x), int(top), int(x), int(bottom))

			block = block.next()
			top = bottom
			bottom = top + self.blockBoundingRect(block).height()



	def lineNumberAreaPaintEvent(self, event):
		painter = QPainter(self.line_number_area)
		painter.fillRect(event.rect(), QColor(self.colors['LineBG']))
		block = self.firstVisibleBlock()
		top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
		bottom = top + self.blockBoundingRect(block).height()

		while block.isValid() and top <= event.rect().bottom():
			if block.isVisible() and bottom >= event.rect().top():
				number = str(block.blockNumber() + 1)
				painter.setPen(QColor(self.colors['LineFG']))
				painter.drawText(0, int(top), self.line_number_area.width() - 5,
								 self.fontMetrics().height(), Qt.AlignRight, number)
			block = block.next()
			top = bottom
			bottom = top + self.blockBoundingRect(block).height()


class LineNumberArea(QWidget):
	def __init__(self, editor):
		super().__init__(editor)
		self.editor = editor

	def sizeHint(self):
		return QSize(self.editor.line_number_area_width(), 0)

	def paintEvent(self, event):
		self.editor.lineNumberAreaPaintEvent(event)
		
class Highlighter(QSyntaxHighlighter):
	def __init__(self, c, document, language):
		super().__init__(document)
		self.language = language
		self.rules = []
		self.multiline_rules = []

		# Load JSON config
		with open(os.path.dirname(__file__)+"/syntax_rules.json", 'r', encoding='utf-8') as f:
			config = json.load(f)

		if language not in config:
			raise ValueError(f"Language '{language}' not found in config")

		lang_config = config[language]
		self.auto_regex = lang_config['autocomplete_regexes']
		self.completions = set(lang_config['auto_keyword'])
		with open(c) as f:
			self.colors = json.load(f)['colors']

		# For each scope (e.g. keywords, comments, strings), add rules
		for scope, details in lang_config.items():
			if isinstance(details, list): continue
			format = QTextCharFormat()

			color = self.colors.get(details.get("format", {}).get("color"), self.colors['default'])
			format.setForeground(QColor(color))

			if details.get("format", {}).get("bold"):
				format.setFontWeight(QFont.Bold)

			if details.get("format", {}).get("italic"):
				format.setFontItalic(True)

			if details.get("format", {}).get("underline"):
				format.setFontUnderline(True)

			for regex_str in details.get("regexes", []):
				regex = QRegularExpression(regex_str)
				self.rules.append((regex, format))

	def highlightBlock(self, text):
		for regex, fmt in self.rules:
			it = regex.globalMatch(text)
			while it.hasNext():
				match = it.next()
				start = match.capturedStart()
				length = match.capturedLength()
				self.setFormat(start, length, fmt)


if __name__ == '__main__':
	import sys
	app = QApplication(sys.argv)
	editor = CodeEditor()
	editor.resize(800, 600)
	editor.show()
	sys.exit(app.exec())

