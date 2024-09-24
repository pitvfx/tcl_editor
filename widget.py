from PySide2.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTextEdit, QPlainTextEdit)
from PySide2.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter
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


class TCLEditorUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("uk.co.thefoundry.NukeTCLEditor")
        self.setWindowTitle("Nuke TCL Editor")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Editor section
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier", 10))
        self.highlighter = TCLSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        # Button group
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.clear_button = QPushButton("Clear Output")
        self.save_button = QPushButton("Save Code")
        self.load_button = QPushButton("Load Code")
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        layout.addLayout(button_layout)

        # Output console
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        layout.addWidget(self.output_console)

        self.setLayout(layout)

        # Connect UI signals
        self.clear_button.clicked.connect(lambda: self.output_console.clear())
