import json
from pathlib import Path
import nuke # pylint: disable=import-error
import pyui # pylint: disable=import-error

from PySide2.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout, QPlainTextEdit, QCompleter
from PySide2.QtGui import  QFont,QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor, QFontMetrics
from PySide2.QtCore import QRegExp, Qt, QTimer, QStringListModel


class TCLSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, keywords: list[str], variables: list[str], parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        self.variables = variables

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        for word in keywords:
            pattern = QRegExp("\\b" + word + "\\b")
            self.highlighting_rules.append((pattern, keyword_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((QRegExp("\".*\""), string_format))
        self.highlighting_rules.append((QRegExp("\'.*\'"), string_format))
        
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((QRegExp("#[^\n]*"), comment_format))
        

    def update_variables(self, variables: list[str]):
        self.variables = variables
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
                
        for variable in self.variables:
            expression = QRegExp(r'\$' + QRegExp.escape(variable))
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, QColor(173, 216, 230))
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
        self.variables = self.get_vars()
        self.completer = self.setup_completer()
        self.var_completer = self.setup_var_completer()
        self.highlighter = TCLSyntaxHighlighter(self.commands.keys(), self.variables, self.document())
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

    def setup_var_completer(self) -> QCompleter:
        model = QStringListModel(self.variables)
        completer = QCompleter( self)
        completer.setModel(model)
        completer.setCaseSensitivity(Qt.CaseSensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setWidget(self)
        completer.activated.connect(self.insertVarCompletion)
        return completer

    def get_tcl_commands(self):
        json_path = Path(__file__).parent.joinpath('tcl_commands.json')
        if not json_path.exists():
            raise FileExistsError(f"TCL commands file not found at {json_path}. Run the extractor script first.")
        try:
            with open(json_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading TCL commands:\n{e}")
            return {}

    def get_vars(self):
        return [var for var in nuke.tcl("info vars").split() if var != "captured_output"]

    def update_variables(self):
        self.variables = self.get_vars()
        self.var_completer.model().setStringList(self.variables)
        self.highlighter.update_variables(self.variables)

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
            self.completer.setCompletionPrefix('')

    def insertVarCompletion(self, completion):
        if self.var_completer.widget() != self:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self.var_completer.completionPrefix())
        if extra > 0:
            tc.movePosition(QTextCursor.Left)
            tc.movePosition(QTextCursor.EndOfWord)
            tc.insertText(completion[-extra:])
            self.setTextCursor(tc)
            self.var_completer.setCompletionPrefix('')
            
    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self.keep_focus:
            self.keep_focus = False
            self.setFocus()
                
    def keyPressEvent(self, event):
        if (self.completer and self.completer.popup().isVisible()) or (self.var_completer and self.var_completer.popup().isVisible()):
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return
            
        # Auto-closing feature
        if event.key() in (Qt.Key_ParenLeft, Qt.Key_BracketLeft, Qt.Key_BraceLeft, Qt.Key_QuoteDbl, Qt.Key_Apostrophe) and event.text() in self.auto_pairs:
            opening_char = event.text()
            closing_char = self.auto_pairs[opening_char]
            cursor = self.textCursor()
            if not cursor.hasSelection():
                cursor.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
            selected_text = cursor.selectedText()
            if selected_text == opening_char or selected_text in self.auto_pairs.values():
                selected_text = ""
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
            cursor.insertText(f"{opening_char}{selected_text}{closing_char}")
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return

        # Variable auto-completion
        if event.text() == '$':
            super().keyPressEvent(event)
            self.showVarCompletion()
            return

        isShortcut = (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Space)

        if not self.completer or not isShortcut:
            super().keyPressEvent(event)

        ctrlOrShift = event.modifiers() in (Qt.ControlModifier, Qt.ShiftModifier)
        if ctrlOrShift and event.text() == '':
            return
        
        if event.key() == Qt.Key_Backspace:
            return

        eow = "~!@#$%^&*()_+{|:\"<>?,./'\\-[]]};="
        hasModifier = (event.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()
        
        if not isShortcut and (hasModifier or event.text() == '' or
                               len(completionPrefix) < 3 or
                               event.text()[-1] in eow):
            if event.key() == Qt.Key_Space:
                return True
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

    def showVarCompletion(self):
        completionPrefix = self.textUnderCursor()
        if completionPrefix != self.var_completer.completionPrefix():
            self.var_completer.setCompletionPrefix(completionPrefix)
            self.var_completer.popup().setCurrentIndex(
                self.var_completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.var_completer.popup().sizeHintForColumn(0) +
                    self.var_completer.popup().verticalScrollBar().sizeHint().width())
        self.var_completer.complete(cr)
        
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
            if self.custom_tooltip.isVisible():
                self.custom_tooltip.hide()
                return True
            if event.modifiers() == Qt.ControlModifier:
                pos = event.pos()
                tc = self.cursorForPosition(pos)
                tc.movePosition(QTextCursor.StartOfWord, QTextCursor.MoveAnchor)
                tc.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
                word = tc.selectedText()
                
                description = self.get_command_description(word)
                
                if description:
                    global_pos = self.mapToGlobal(pos)
                    self.custom_tooltip.showTooltip(description, global_pos)
                else:
                    self.custom_tooltip.hide()
                
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
        self.editor = nuke.PyCustom_Knob("editor", "", "__import__('tcl_editor').EditorKnob(nuke.thisNode())")
        self.code = nuke.Multiline_Eval_String_Knob("code", "")
        self.code.setFlag(nuke.READ_ONLY|nuke.INVISIBLE)
        self.run_button = nuke.Script_Knob("run", "run", "load tcl_editor.tcl;run_code")
        self.run_button.setFlag(nuke.STARTLINE)
        self.clear_button = nuke.Script_Knob("clear", "clear", 'knob this.output ""')
        self.output = nuke.Multiline_Eval_String_Knob("output", "")
        self.output.setFlag(nuke.READ_ONLY)
        for k in (self.editor, self.code, self.run_button, self.clear_button, self.output):
            self.addKnob(k)
        self.dialog.add(self.createWidget())

    def show(self):
        pane = nuke.getPaneFor("uk.co.thefoundry.scripteditor.1") or nuke.thisPane()
        
        if pane:
            pane.add(self.dialog)
        else:
            self.dialog.show()
        nuke.addKnobChanged(TCLEditorPanel.onKnobChanged, args=(self.panel, ), nodeClass='PanelNode', node=self.panel)
        return self.dialog
    
    def onKnobChanged(self):
        self.knobChanged(nuke.thisKnob())

    def knobChanged(self, knob):
        if knob is self.run_button:
            self.editor.getObject().qtwidget.update_variables()
            

class EditorKnob():

    def __init__(self, panel: TCLEditorPanel):
        self.qtwidget = TCLEditor()
        self.panel = panel
        self.qtwidget.textChanged.connect(self.code_changed)

    def code_changed(self):
        self.panel.code.setValue(self.qtwidget.toPlainText())

    def makeUI(self):
        return self.qtwidget

_editor = TCLEditorPanel()

def editor():
    return _editor.show()