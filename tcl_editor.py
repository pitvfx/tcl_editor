import json
from pathlib import Path
import nuke
import pyui

from PySide2.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout, QPlainTextEdit, QCompleter
from PySide2.QtGui import  QFont,QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor, QFontMetrics, QFocusEvent
from PySide2.QtCore import QRegExp, Qt, QTimer, QEvent


class TCLSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, keywords: list[str], parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        for word in keywords:
            pattern = QRegExp("\\b" + word + "\\b")
            self.highlighting_rules.append((pattern, keyword_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((QRegExp("\".*\""), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((QRegExp("#[^\n]*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

class CustomTooltip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def showTooltip(self, text, pos, duration=60000):
        self.label.setText(text)
        self.adjustSize()
        self.adjustPosition(pos)
        self.show()
        self.timer.start(duration)

    def adjustPosition(self, pos):
        screen = QApplication.screenAt(pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        max_width = min(720, screen_geometry.width() // 2)
        max_height = screen_geometry.height() // 2

        self.label.setMaximumWidth(max_width)
        self.label.setMaximumHeight(max_height)
        self.adjustSize()

        tooltip_rect = self.geometry()
        tooltip_rect.moveTopLeft(pos)

        if tooltip_rect.right() > screen_geometry.right():
            tooltip_rect.moveRight(screen_geometry.right())
        if tooltip_rect.bottom() > screen_geometry.bottom():
            tooltip_rect.moveBottom(screen_geometry.bottom())
        if tooltip_rect.left() < screen_geometry.left():
            tooltip_rect.moveLeft(screen_geometry.left())
        if tooltip_rect.top() < screen_geometry.top():
            tooltip_rect.moveTop(screen_geometry.top())

        self.setGeometry(tooltip_rect)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.hide()
        return super().mousePressEvent(event)

class TCLEditor(QPlainTextEdit):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Monospace", 12))
        self.commands = self.get_tcl_commands()
        self.completer = self.setup_completer()
        self.highlighter = TCLSyntaxHighlighter(self.commands.keys(), self.document())
        self.custom_tooltip = CustomTooltip(self)
        # Set tab stop width
        font = self.font()
        fm = QFontMetrics(font)
        self.setTabStopDistance(4 * fm.horizontalAdvance(' '))
        self.auto_pairs = {'(': ')', '{': '}', '[': ']', '"': '"', "'": "'"}
        self.keep_focus = False
        
    def setup_completer(self) -> QCompleter:
        completer = QCompleter(list(self.commands.keys()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setWidget(self)
        completer.activated.connect(self.insertCompletion)
        return completer

    def get_tcl_commands(self):
        json_path = Path(__file__).parent.joinpath('tcl_commands.json')
        if not json_path.exists():
            FileExistsError(f"TCL commands file not found at {json_path}. Run the extractor script first.")
        try:
            with open(json_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading TCL commands:\n{e}")
            return {}

    def insertCompletion(self, completion):
        if self.completer.widget() != self:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        if extra > 0:
            tc.movePosition(QTextCursor.Left)
            tc.movePosition(QTextCursor.EndOfWord)
            tc.insertText(completion[-extra:])
            self.setTextCursor(tc)
            # reset completer
            self.completer.setCompletionPrefix('')
            
    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        word = tc.selectedText()
        
        if word in ("}]"):
            tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 2)
            tc.select(QTextCursor.WordUnderCursor)
            word = tc.selectedText()
        return word

    def focusInEvent(self, event):
        if self.completer:
            self.completer.setWidget(self)
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        # Auto-closing feature
        if event.key() in (Qt.Key_ParenLeft, Qt.Key_BracketLeft, Qt.Key_BraceLeft, Qt.Key_QuoteDbl, Qt.Key_Apostrophe):
            opening_char = event.text()
            closing_char = self.auto_pairs.get(opening_char)
            
            if closing_char:
                cursor = self.textCursor()
                cursor.insertText(opening_char + closing_char)
                cursor.movePosition(QTextCursor.Left)
                self.setTextCursor(cursor)
                return

        isShortcut = (event.modifiers() == Qt.ControlModifier and
                      event.key() == Qt.Key_Space)

        if not self.completer or not isShortcut:
            super().keyPressEvent(event)

        ctrlOrShift = event.modifiers() in (Qt.ControlModifier, Qt.ShiftModifier)
        if ctrlOrShift and event.text() == '':
            return

        eow = "~!@#$%^&*()_+{|:\"<>?,./'\\-[]]};="
        hasModifier = (event.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()
        
        if not isShortcut and (hasModifier or
                               len(completionPrefix) < 3 or
                               event.text()[-1] in eow):
            
            self.completer.popup().hide()
            return

        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(
                self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                    self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

        
    def get_command_description(self, command):
        info = self.commands.get(command, {})
        if not info:
            return
        docs = info.get("docs", "")
        if not docs:
            return
        params = info.get("params")
        if params:
            return f"<h3>{command} ({', '.join(params)})</h3>\n{docs}"
        return docs

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # If tooltip is visible, hide it and do nothing else
            if self.custom_tooltip.isVisible():
                self.custom_tooltip.hide()
                return True
            if event.modifiers() == Qt.ControlModifier:
                # Get the position of the mouse click
                pos = event.pos()
                
                # Get the cursor at the mouse position
                tc = self.cursorForPosition(pos)
                
                # Move to the start of the word
                tc.movePosition(QTextCursor.StartOfWord, QTextCursor.MoveAnchor)
                
                # Move to the end of the word, keeping the anchor at the start
                tc.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
                
                # Get the selected word
                word = tc.selectedText()
                
                description = self.get_command_description(word)
                
                if description:
                    global_pos = self.mapToGlobal(pos)
                    self.custom_tooltip.showTooltip(description, global_pos)
                else:
                    self.custom_tooltip.hide()
                
                # The selection is only temporary and won't be visible
                return True
        
        super().mousePressEvent(event)
class TCLEditorPanel(nuke.PanelNode):

    def __init__(self):
        super().__init__()
        nuke.tcl("catch {load tcl_editor.tcl}")
        self.dialog = pyui.Dialog("TCL Editor", "pitvfx.tcl_editor", True)
        self.build_panel()
        
    @property
    def panel(self):
        return self

    def build_panel(self):
        self.editor = nuke.PyCustom_Knob("editor", "", "tcl_editor.EditorKnob(nuke.thisNode())")
        self.code = nuke.Multiline_Eval_String_Knob("code", "")
        self.code.setFlag(nuke.READ_ONLY|nuke.INVISIBLE)
        self.run_button = nuke.Script_Knob("run", "run", "run_code")
        self.run_button.setFlag(nuke.STARTLINE)
        self.clear_button = nuke.Script_Knob("clear", "clear", 'knob this.output ""')
        self.output = nuke.Multiline_Eval_String_Knob("output", "")
        self.output.setFlag(nuke.READ_ONLY)
        for k in (self.editor, self.code, self.run_button, self.clear_button, self.output):
            self.addKnob(k)
        self.dialog.add(self.createWidget())

    def show(self):
        self.dialog.show()


class EditorKnob():

    def __init__(self, panel: TCLEditorPanel):
        self.qtwidget = TCLEditor()
        self.panel = panel
        self.qtwidget.textChanged.connect(self.code_changed)

    def code_changed(self):
        self.panel.code.setValue(self.qtwidget.toPlainText())

    def makeUI(self):
        return self.qtwidget


def editor():
    return TCLEditorPanel()
