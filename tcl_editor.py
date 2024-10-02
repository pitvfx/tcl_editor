import nuke
import pyui

from PySide2.QtWidgets import QPlainTextEdit
from PySide2.QtGui import  QFont,QColor, QTextCharFormat, QSyntaxHighlighter
from PySide2.QtCore import QRegExp


class TCLSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keywords = ["set", "proc", "if", "else", "elseif", "while",
                    "for", "foreach", "switch", "break", "continue", "return"]
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


class TCLEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.highlighter = TCLSyntaxHighlighter(self.document())
        self.setFont(QFont("Monospace"))

class TCLEditorPanel(nuke.PanelNode):

    def __init__(self):
        super().__init__()
        nuke.tcl("catch {load capture_puts}")
        self.dialog = pyui.Dialog("TCL Editor", "pitvfx.tcl_editor", True)
        self.build_panel()
        self.editor.getObject().setup()


    def build_panel(self):
        self.editor = nuke.PyCustom_Knob("editor", "", "tcl_editor.panel.EditorKnob(nuke.thisNode())")
        self.code = nuke.Multiline_Eval_String_Knob("code", "")
        self.code.setFlag(nuke.READ_ONLY|nuke.INVISIBLE)
        self.run_button = nuke.Script_Knob("run", "run", "run_code")
        self.run_button.setFlag(nuke.STARTLINE)
        self.output = nuke.Multiline_Eval_String_Knob("output", "")
        self.output.setFlag(nuke.READ_ONLY)
        for k in (self.editor, self.code, self.run_button, self.output):
            self.addKnob(k)
        self.dialog.add(self.createWidget())

    def show(self):
        self.dialog.show()


class EditorKnob():

    def __init__(self, panel: TCLEditorPanel):
        self.qtwidget = TCLEditor()
        self.panel = panel

    def setup(self):
        self.qtwidget.textChanged.connect(self.code_changed)      

    def code_changed(self):
        self.panel.code.setValue(self.qtwidget.toPlainText())

    def makeUI(self):
        return self.qtwidget


def editor():
    return TCLEditorPanel()
