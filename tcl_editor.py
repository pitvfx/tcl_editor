import json
import re
from pathlib import Path
import nuke # pylint: disable=import-error
import pyui # pylint: disable=import-error

from PySide6.QtWidgets import (QWidget, QApplication, QLabel, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                               QCompleter, QTextEdit, QLineEdit, QPushButton, QSplitter, QButtonGroup)
from PySide6.QtGui import  QFont,QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor, QFontMetrics, \
    QPainter, QTextFormat, QTextDocument, QIcon
from PySide6.QtCore import Qt, QTimer, QStringListModel, QSize, QRect, QEvent, Signal


INDENT = "\t"
OPEN_BRACKETS = {'(': ')', '[': ']', '{': '}'}
CLOSE_BRACKETS = {v: k for k, v in OPEN_BRACKETS.items()}

# Line scanner states / span kinds.
NORMAL, IN_STRING = 0, 1
STRING, COMMENT, ESCAPE = "string", "comment", "escape"


def scan_line(text: str, state: int = NORMAL):
    """Find strings, comments and backslash escapes in one line of TCL.

    Returns (spans, end_state). Each span is (start, end, kind, closed) with `end`
    exclusive. A string continued from the previous line starts at -1.
    """
    spans = []
    n = len(text)
    i = 0
    command_start = True
    string_start = -1 if state == IN_STRING else None
    while i < n:
        ch = text[i]
        if string_start is not None:
            if ch == '\\':
                i += 2
                continue
            if ch == '"':
                spans.append((string_start, i + 1, STRING, True))
                string_start = None
                command_start = False
            i += 1
            continue
        if ch == '\\':
            spans.append((i, min(i + 2, n), ESCAPE, True))
            command_start = False
            i += 2
            continue
        if ch == '#' and command_start:
            # In TCL "#" only starts a comment where a command could start.
            spans.append((i, n, COMMENT, False))
            return spans, NORMAL
        if ch == '"' and (i == 0 or text[i - 1] in ' \t[{;'):
            string_start = i
        elif ch in ';[':
            command_start = True
        elif not ch.isspace():
            command_start = False
        i += 1
    if string_start is not None:
        spans.append((string_start, n, STRING, False))
        return spans, IN_STRING
    return spans, NORMAL


BUILTIN_VARS_FILE = Path(__file__).parent.joinpath('tcl_builtin_vars.json')


# Toolbar icons, drawn by icons/make_icons.py.
ICON_DIR = Path(__file__).parent.joinpath("icons", "toolbar")
if not ICON_DIR.is_dir():
    ICON_DIR = None
ICON_SIZE = QSize(22, 22)


def load_builtin_vars() -> set:
    """Variables Nuke/TCL define themselves. Captured once from "info vars" into
    tcl_builtin_vars.json; delete that file to take a new snapshot."""
    if BUILTIN_VARS_FILE.exists():
        try:
            return set(json.loads(BUILTIN_VARS_FILE.read_text()))
        except (OSError, ValueError) as e:
            print(f"Error loading {BUILTIN_VARS_FILE}:\n{e}")
    names = sorted(nuke.tcl("info vars").split())
    try:
        BUILTIN_VARS_FILE.write_text(json.dumps(names, indent=4))
    except OSError as e:
        print(f"Could not write {BUILTIN_VARS_FILE}:\n{e}")
    return set(names)


def _alternation(words) -> str:
    """Escaped regex alternation, longest words first so they win over prefixes."""
    return "|".join(re.escape(w) for w in sorted({w for w in words if w}, key=len, reverse=True))


def editor_font() -> QFont:
    """Use the Script Editor font from Nuke's preferences when available."""
    try:
        from hiero.core import ApplicationSettings # pylint: disable=import-error
        font = QFont()
        if font.fromString(ApplicationSettings().value("scripteditor/font")):
            return font
    except Exception: # pylint: disable=broad-except
        pass
    return QFont("Monospace", 12)


class TCLSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, keywords: list[str], variables: list[str], parent=None):
        super().__init__(parent)
        self.keyword_pattern = None
        self.variable_pattern = None

        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#569CD6"))

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#CE9178"))

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))

        self.variable_format = QTextCharFormat()
        self.variable_format.setForeground(QColor(173, 216, 230))

        self.set_keywords(keywords, rehighlight=False)
        self.update_variables(variables)

    def set_keywords(self, keywords, rehighlight=True):
        alternation = _alternation(keywords)
        self.keyword_pattern = re.compile(rf"(?<![\w$:])(?:{alternation})(?![\w:])") if alternation else None
        if rehighlight:
            self.rehighlight()

    def update_variables(self, variables: list[str]):
        self.variables = variables
        alternation = _alternation(variables)
        self.variable_pattern = re.compile(rf"\$(?:{alternation})(?![\w:])") if alternation else None
        self.rehighlight()

    def highlightBlock(self, text):
        state = self.previousBlockState()
        spans, end_state = scan_line(text, NORMAL if state < 0 else state)
        self.setCurrentBlockState(end_state)

        if self.keyword_pattern:
            for match in self.keyword_pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)

        for start, end, kind, _ in spans:
            if kind == STRING:
                start = max(0, start)
                self.setFormat(start, end - start, self.string_format)

        if self.variable_pattern:
            for match in self.variable_pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.variable_format)

        for start, end, kind, _ in spans:
            if kind == COMMENT:
                self.setFormat(start, end - start, self.comment_format)


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


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class TCLEditor(QPlainTextEdit):

    runRequested = Signal()
    lineNumberWidthChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(editor_font())
        # Stop Nuke from taking key presses (e.g. Ctrl+Enter) while typing.
        self.setProperty("fnDontStealEvents", True)
        self.commands = self.get_tcl_commands()
        self.procs = []
        self.builtin_vars = load_builtin_vars()
        self.variables = self.get_vars()
        self.completer = self.setup_completer()
        self.var_completer = self.setup_var_completer()
        self.highlighter = TCLSyntaxHighlighter(self.commands.keys(), self.variables, self.document())
        self.custom_tooltip = CustomTooltip(self)
        # Set tab stop width
        font = self.font()
        fm = QFontMetrics(font)
        self.setTabStopDistance(4 * fm.horizontalAdvance(' '))
        self.keep_focus = False
        self.error_line = 0
        self.find_bar = None
        self._masked = ("", "")

        self.proc_timer = QTimer(self)
        self.proc_timer.setSingleShot(True)
        self.proc_timer.setInterval(500)
        self.proc_timer.timeout.connect(self.scan_procs)

        self.line_numbers = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self.update_extra_selections)
        self.document().contentsChange.connect(self._on_contents_change)
        self._update_line_number_width()

        self.update_extra_selections()

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)

    def setup_completer(self) -> QCompleter:
        completer = QCompleter(self)
        completer.setModel(QStringListModel(list(self.commands.keys()), completer))
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
        hidden = ("captured_output", "tcl_editor_error_line")
        return [var for var in nuke.tcl("info vars").split()
                if var not in hidden and var not in self.builtin_vars]

    def update_variables(self):
        self.variables = self.get_vars()
        self.var_completer.model().setStringList(self.variables)
        self.highlighter.update_variables(self.variables)

    def scan_procs(self):
        """Add procs defined in the editor to completion and highlighting."""
        procs = sorted(set(re.findall(r"^\s*proc\s+([^\s{}\[\]]+)", self.toPlainText(), re.MULTILINE))
                       - set(self.commands))
        if procs == self.procs:
            return
        self.procs = procs
        names = list(self.commands) + procs
        self.completer.model().setStringList(names)
        self.highlighter.set_keywords(names)

    def _on_contents_change(self, _position, removed, added):
        # Highlighting also reports changes, with nothing added or removed.
        if not (removed or added):
            return
        self.proc_timer.start()
        if self.error_line:
            self.set_error_line(0)

    # ---- Line numbers -------------------------------------------------

    def line_number_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_number_width(self, *_):
        width = self.line_number_width()
        self.setViewportMargins(width, 0, 0, 0)
        self.lineNumberWidthChanged.emit(width)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_numbers.scroll(0, dy)
        else:
            self.line_numbers.update(0, rect.y(), self.line_numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_numbers.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_numbers)
        painter.fillRect(event.rect(), self.palette().base().color().darker(115))
        font = QFont(self.font())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        width = self.line_numbers.width() - 6
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if number + 1 == self.error_line:
                    painter.setPen(QColor(230, 80, 80))
                elif number == current:
                    painter.setPen(self.palette().text().color())
                else:
                    painter.setPen(QColor(120, 120, 120))
                font.setBold(number == current or number + 1 == self.error_line)
                painter.setFont(font)
                painter.drawText(0, top, width, height, Qt.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1
        painter.end()

    # ---- Line / bracket / find / error highlights --------------------

    def set_error_line(self, line: int):
        self.error_line = line
        self.update_extra_selections()

    def _line_selection(self, cursor, color):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = QTextCursor(cursor)
        selection.cursor.clearSelection()
        return selection

    def _char_selection(self, position, background, foreground=None):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(background)
        if foreground:
            selection.format.setForeground(foreground)
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        selection.cursor = cursor
        return selection

    def update_extra_selections(self):
        selections = [self._line_selection(self.textCursor(), QColor(255, 255, 255, 18))]

        if self.error_line:
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                selections.append(self._line_selection(QTextCursor(block), QColor(255, 0, 0, 50)))

        if self.find_bar and self.find_bar.isVisible():
            term = self.find_bar.find_edit.text()
            if term:
                cursor = self.document().find(term, 0)
                while not cursor.isNull() and len(selections) < 1000:
                    match = QTextEdit.ExtraSelection()
                    match.format.setBackground(QColor(155, 124, 87))
                    match.cursor = cursor
                    selections.append(match)
                    cursor = self.document().find(term, cursor)

        for position in self._matching_brackets():
            selections.append(self._char_selection(position, QColor("#A9D2EF"), QColor(Qt.black)))

        self.setExtraSelections(selections)
        self.line_numbers.update()

    def masked_text(self) -> str:
        """Document text with strings, comments and escapes blanked out, so the
        brackets left in it are real ones. Positions match the document."""
        text = self.toPlainText()
        if self._masked[0] != text:
            lines = []
            state = NORMAL
            for line in text.split("\n"):
                spans, state = scan_line(line, state)
                if spans:
                    chars = list(line)
                    for start, end, _, _ in spans:
                        start = max(0, start)
                        chars[start:end] = " " * (end - start)
                    line = "".join(chars)
                lines.append(line)
            self._masked = (text, "\n".join(lines))
        return self._masked[1]

    @staticmethod
    def find_matching_bracket(text: str, position: int):
        char = text[position]
        if char in OPEN_BRACKETS:
            target, step = OPEN_BRACKETS[char], 1
        else:
            target, step = CLOSE_BRACKETS[char], -1
        depth = 0
        i = position
        while 0 <= i < len(text):
            if text[i] == char:
                depth += 1
            elif text[i] == target:
                depth -= 1
                if depth == 0:
                    return i
            i += step
        return None

    def _matching_brackets(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            return []
        text = self.masked_text()
        pos = cursor.position()
        for p in (pos, pos - 1):
            if 0 <= p < len(text) and (text[p] in OPEN_BRACKETS or text[p] in CLOSE_BRACKETS):
                match = self.find_matching_bracket(text, p)
                return [p, match] if match is not None else []
        return []

    # ---- Typing helpers -----------------------------------------------

    def context_at(self, cursor):
        """STRING or COMMENT if the cursor is inside one, otherwise None."""
        block = cursor.block()
        previous = block.previous()
        state = previous.userState() if previous.isValid() else NORMAL
        spans, _ = scan_line(block.text(), NORMAL if state < 0 else state)
        column = cursor.positionInBlock()
        for start, end, kind, closed in spans:
            if kind != ESCAPE and start < column and (column < end or (column == end and not closed)):
                return kind
        return None

    def handle_pairs(self, event) -> bool:
        """Auto-close brackets and quotes, and step over closing ones."""
        char = event.text()
        if char not in OPEN_BRACKETS and char not in CLOSE_BRACKETS and char != '"':
            return False
        cursor = self.textCursor()
        document = self.document()

        if cursor.hasSelection():
            if char in CLOSE_BRACKETS:
                return False
            # Wrap the selection.
            closing = OPEN_BRACKETS.get(char, '"')
            cursor.insertText(f"{char}{cursor.selectedText()}{closing}")
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return True

        position = cursor.position()
        next_char = document.characterAt(position)
        prev_char = document.characterAt(position - 1) if position else ""
        context = self.context_at(cursor)

        if char in CLOSE_BRACKETS:
            if next_char == char and context is None:
                cursor.movePosition(QTextCursor.Right)
                self.setTextCursor(cursor)
                return True
            if char == '}' and context is None and not cursor.block().text()[:cursor.positionInBlock()].strip():
                return self.insert_dedented_brace(cursor)
            return False

        if context == COMMENT or prev_char == '\\':
            return False
        if char == '"':
            if context == STRING:
                if next_char == '"':
                    cursor.movePosition(QTextCursor.Right)
                    self.setTextCursor(cursor)
                    return True
                return False
            if prev_char.isalnum():
                return False
        elif context == STRING and char != '[':
            # Only "[" (command substitution) is auto-closed inside strings.
            return False

        if next_char and not next_char.isspace() and next_char not in CLOSE_BRACKETS \
                and next_char not in ('', '\x00'):
            return False

        cursor.insertText(char + OPEN_BRACKETS.get(char, '"'))
        cursor.movePosition(QTextCursor.Left)
        self.setTextCursor(cursor)
        return True

    def delete_pair(self) -> bool:
        """Backspace between an empty pair, e.g. {|}, removes both characters."""
        cursor = self.textCursor()
        position = cursor.position()
        if cursor.hasSelection() or position == 0:
            return False
        document = self.document()
        prev_char = document.characterAt(position - 1)
        next_char = document.characterAt(position)
        if OPEN_BRACKETS.get(prev_char) != next_char and not prev_char == next_char == '"':
            return False
        if self.context_at(cursor) == COMMENT:
            return False
        cursor.movePosition(QTextCursor.Left)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2)
        cursor.removeSelectedText()
        return True

    def insert_dedented_brace(self, cursor) -> bool:
        """Type "}" on a blank line, lined up with the line of its matching "{"."""
        text = self.masked_text()
        depth = 0
        i = cursor.position() - 1
        while i >= 0:
            if text[i] == '}':
                depth += 1
            elif text[i] == '{':
                if depth == 0:
                    break
                depth -= 1
            i -= 1
        if i < 0:
            return False
        indent = re.match(r"[ \t]*", self.document().findBlock(i).text()).group()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        cursor.insertText(indent + '}')
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def insert_newline(self):
        """Enter keeps the line's indentation, and indents after an opening bracket."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        line = cursor.block().text()
        column = cursor.positionInBlock()
        before = line[:column].rstrip()
        indent = re.match(r"[ \t]*", line).group()[:column]
        opener = before[-1:] if before[-1:] in OPEN_BRACKETS and self.context_at(cursor) is None else ""
        if opener:
            after = line[column:]
            stripped = after.lstrip(" \t")
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(after) - len(stripped))
            cursor.removeSelectedText()
            cursor.insertText("\n" + indent + INDENT)
            if stripped[:1] == OPEN_BRACKETS[opener]:
                keep = cursor.position()
                cursor.insertText("\n" + indent)
                cursor.setPosition(keep)
        else:
            cursor.insertText("\n" + indent)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    # ---- Completion ---------------------------------------------------

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
        # The word characters left of the cursor. Qt's WordUnderCursor would pick
        # the "]" in "[sele|]" instead of "sele".
        tc = self.textCursor()
        text = tc.block().text()[:tc.positionInBlock()]
        return re.search(r"[\w:]*$", text).group()

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

        modifiers = event.modifiers() & ~Qt.KeypadModifier

        # Ctrl+Enter runs the code
        if event.key() in (Qt.Key_Enter, Qt.Key_Return) and modifiers == Qt.ControlModifier:
            self.runRequested.emit()
            return

        # Ctrl+F opens find / replace
        if event.key() == Qt.Key_F and modifiers == Qt.ControlModifier and self.find_bar:
            self.find_bar.open()
            return

        if event.key() == Qt.Key_Escape and self.find_bar and self.find_bar.isVisible():
            self.find_bar.close_bar()
            return

        if event.key() == Qt.Key_Backspace and modifiers == Qt.NoModifier and self.delete_pair():
            return

        # Auto-indent
        if event.key() in (Qt.Key_Enter, Qt.Key_Return) and modifiers == Qt.NoModifier:
            self.insert_newline()
            return

        # Auto-closing feature
        if self.handle_pairs(event):
            return

        # Variable auto-completion
        if event.text() == '$':
            super().keyPressEvent(event)
            self.completer.popup().hide()
            self.showVarCompletion()
            return

        isShortcut = (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Space)

        if not self.completer or not isShortcut:
            super().keyPressEvent(event)

        ctrlOrShift = event.modifiers() in (Qt.ControlModifier, Qt.ShiftModifier)
        if ctrlOrShift and event.text() == '':
            return

        # After "$", complete variables instead of commands.
        if self.after_dollar():
            self.completer.popup().hide()
            if event.key() != Qt.Key_Backspace or self.var_completer.popup().isVisible():
                self.showVarCompletion()
            return
        self.var_completer.popup().hide()

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

        # Nothing left to complete: the only suggestion is what's already typed.
        matches = self.completer.completionModel()
        if matches.rowCount() == 1 and matches.index(0, 0).data() == completionPrefix:
            self.completer.popup().hide()
            return

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                    self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def after_dollar(self):
        """True if the word left of the cursor starts with "$"."""
        tc = self.textCursor()
        text = tc.block().text()[:tc.positionInBlock()]
        return text[:len(text) - len(self.textUnderCursor())].endswith('$')

    def showVarCompletion(self):
        completionPrefix = self.textUnderCursor()
        if completionPrefix != self.var_completer.completionPrefix():
            self.var_completer.setCompletionPrefix(completionPrefix)
            self.var_completer.popup().setCurrentIndex(
                self.var_completer.completionModel().index(0, 0))

        # Nothing left to complete: the only suggestion is what's already typed.
        matches = self.var_completer.completionModel()
        if matches.rowCount() == 0 or (matches.rowCount() == 1 and matches.index(0, 0).data() == completionPrefix):
            self.var_completer.popup().hide()
            return

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
                pos = event.position().toPoint()
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


class OutputView(QPlainTextEdit):
    """Read-only output with an empty left gutter, so its text lines up with
    the code next to the editor's line numbers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.gutter = QWidget(self)
        self.gutter.paintEvent = self._paint_gutter
        self.gutter_width = 0

    def set_gutter_width(self, width):
        if width != self.gutter_width:
            self.gutter_width = width
            self.setViewportMargins(width, 0, 0, 0)
            self._place_gutter()

    def _place_gutter(self):
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width, cr.height()))

    def _paint_gutter(self, event):
        painter = QPainter(self.gutter)
        # Same colour as the editor's line number area
        painter.fillRect(event.rect(), self.palette().base().color().darker(115))
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_gutter()


class FindBar(QWidget):
    """Find / replace bar. Enter = next, Shift+Enter = previous, Esc = close."""

    def __init__(self, editor: TCLEditor, parent=None):
        super().__init__(parent)
        self.editor = editor
        editor.find_bar = self

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.find_edit)
        for text, tooltip, slot in (("<", "Find previous (Shift+Enter)", lambda: self.find(False)),
                                    (">", "Find next (Enter)", self.find)):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setFixedWidth(28)
            button.clicked.connect(slot)
            layout.addWidget(button)
        layout.addWidget(self.replace_edit)
        for text, slot in (("Replace", self.replace), ("All", self.replace_all), ("x", self.close_bar)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            layout.addWidget(button)

        for line_edit in (self.find_edit, self.replace_edit):
            line_edit.installEventFilter(self)
        self.find_edit.textChanged.connect(editor.update_extra_selections)
        self.find_edit.returnPressed.connect(
            lambda: self.find(not QApplication.keyboardModifiers() & Qt.ShiftModifier))
        self.replace_edit.returnPressed.connect(self.replace)
        self.hide()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.close_bar()
            return True
        return super().eventFilter(obj, event)

    def open(self):
        selected = self.editor.textCursor().selectedText()
        if selected and '' not in selected:
            self.find_edit.setText(selected)
        self.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self.editor.update_extra_selections()

    def close_bar(self):
        self.hide()
        self.editor.setFocus()
        self.editor.update_extra_selections()

    def find(self, forward=True):
        term = self.find_edit.text()
        if not term:
            return False
        editor = self.editor
        found = editor.find(term) if forward else editor.find(term, QTextDocument.FindBackward)
        if not found:
            # Wrap around
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.Start if forward else QTextCursor.End)
            editor.setTextCursor(cursor)
            found = editor.find(term) if forward else editor.find(term, QTextDocument.FindBackward)
        return found

    def replace(self):
        term = self.find_edit.text()
        cursor = self.editor.textCursor()
        if term and cursor.selectedText().lower() == term.lower():
            cursor.insertText(self.replace_edit.text())
        self.find()

    def replace_all(self):
        term = self.find_edit.text()
        if not term:
            return
        document = self.editor.document()
        edit = QTextCursor(document)
        edit.beginEditBlock()
        cursor = document.find(term, 0)
        while not cursor.isNull():
            cursor.insertText(self.replace_edit.text())
            cursor = document.find(term, cursor)
        edit.endEditBlock()


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
        self.file = nuke.File_Knob("file", "file")
        self.file.setTooltip("File to load/save the code to.")
        # Toolbar, editor and output are all drawn by the EditorKnob widget.
        self.editor = nuke.PyCustom_Knob("editor", "", "__import__('tcl_editor').EditorKnob(nuke.thisNode())")
        self.editor.setFlag(nuke.STARTLINE)
        # Hidden knobs used by run_code in tcl_editor.tcl ("knob this.code" / "knob this.output").
        self.code = nuke.Multiline_Eval_String_Knob("code", "")
        self.code.setFlag(nuke.READ_ONLY|nuke.INVISIBLE)
        self.run_button = nuke.Script_Knob("run", "run", "load tcl_editor.tcl;run_code")
        self.run_button.setFlag(nuke.INVISIBLE)
        self.output = nuke.Multiline_Eval_String_Knob("output", "")
        self.output.setFlag(nuke.READ_ONLY|nuke.INVISIBLE)
        for k in (self.file, self.editor, self.code, self.run_button, self.output):
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
            self.editor.getObject().after_run()


class EditorKnob():

    def __init__(self, panel: TCLEditorPanel):
        self.qtwidget = TCLEditor()
        self.panel = panel
        self.qtwidget.textChanged.connect(self.code_changed)
        self.qtwidget.runRequested.connect(self.run)

        # Input: find bar + editor
        self.input_widget = QWidget()
        input_layout = QVBoxLayout(self.input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(2)
        input_layout.addWidget(FindBar(self.qtwidget))
        input_layout.addWidget(self.qtwidget)

        # Output
        self.output_view = OutputView()
        self.output_view.setFont(self.qtwidget.font())
        self.output_view.set_gutter_width(self.qtwidget.line_number_width())
        self.qtwidget.lineNumberWidthChanged.connect(self.output_view.set_gutter_width)

        # Draggable divider between input and output, like the Script Editor
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.input_widget)
        self.splitter.addWidget(self.output_view)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)

        self.widget = QWidget()
        self.widget.setMinimumHeight(400)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addLayout(self.build_toolbar())
        layout.addWidget(self.splitter)
        self.refresh_output()

    def build_toolbar(self):
        """Icon buttons laid out like the Script Editor's toolbar."""
        def button(text, tooltip, slot, icon_on, icon_off=None):
            icon = QIcon()
            if ICON_DIR:
                icon.addFile(str(ICON_DIR / icon_on), ICON_SIZE, QIcon.Normal, QIcon.On)
                if icon_off:
                    icon.addFile(str(ICON_DIR / icon_off), ICON_SIZE, QIcon.Normal, QIcon.Off)
            # Fall back to text if Nuke's icons can't be found.
            b = QPushButton(icon, "" if ICON_DIR else text)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(tooltip)
            b.clicked.connect(slot)
            return b

        load = button("load", "Load the code from the file", self.load, "load.png")
        save = button("save", "Save the code to the file", self.save, "save.png")
        run = button("run", "Run the code<br>Hotkey: Ctrl+Return", self.run, "run.png")
        show_input = button("input", "Show input only", lambda: self.set_view(True, False),
                            "inputOn.png", "inputOff.png")
        show_output = button("output", "Show output only", lambda: self.set_view(False, True),
                             "outputOn.png", "outputOff.png")
        show_both = button("both", "Show both input and output", lambda: self.set_view(True, True),
                           "bothOn.png", "bothOff.png")
        clear_input = button("clear", "Clear input", lambda: self.set_code(""), "clearHistory.png")
        clear_output = button("clear output", "Clear output window", self.clear_output, "clearOutput.png")

        self.view_buttons = QButtonGroup(self.widget)
        for b in (show_input, show_output, show_both):
            b.setCheckable(True)
            self.view_buttons.addButton(b)
        show_both.setChecked(True)

        toolbar = QHBoxLayout()
        self.toolbar = toolbar
        self.align_toolbar(self.qtwidget.line_number_width())
        self.qtwidget.lineNumberWidthChanged.connect(self.align_toolbar)
        toolbar.setSpacing(0)
        for item in (load, save, run, 15, show_input, show_output, show_both, 15, clear_input, clear_output):
            if isinstance(item, int):
                toolbar.addSpacing(item)
            else:
                toolbar.addWidget(item)
        toolbar.setAlignment(Qt.AlignLeft)
        return toolbar

    def align_toolbar(self, line_number_width):
        """Indent the buttons so they start where the code starts."""
        left = self.qtwidget.frameWidth() + line_number_width
        if self.toolbar.contentsMargins().left() != left:
            self.toolbar.setContentsMargins(left, 0, 0, 0)

    def set_view(self, show_input, show_output):
        self.input_widget.setVisible(show_input)
        self.output_view.setVisible(show_output)

    def refresh_output(self):
        self.output_view.setPlainText(self.panel.output.value())
        scrollbar = self.output_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_output(self):
        self.panel.output.setValue("")
        self.output_view.clear()

    def code_changed(self):
        self.panel.code.setValue(self.qtwidget.toPlainText())

    def run(self):
        self.panel.run_button.execute()
        self.after_run()

    def after_run(self):
        self.refresh_output()
        self.qtwidget.update_variables()
        try:
            line = int(nuke.tcl("set ::tcl_editor_error_line"))
        except (RuntimeError, ValueError):
            line = 0
        self.qtwidget.set_error_line(line)

    def set_code(self, text):
        """Replace the editor text as one undoable edit."""
        cursor = QTextCursor(self.qtwidget.document())
        cursor.select(QTextCursor.Document)
        cursor.insertText(text)

    def file_path(self, save=False):
        """The path in the file knob, or ask for one if it is empty."""
        path = self.panel.file.evaluate() or ""
        if path:
            return path
        path = nuke.getFilename("Save TCL file" if save else "Load TCL file", "*.tcl",
                                type="save" if save else None)
        if not path:
            return ""
        if save and not Path(path).suffix:
            path += ".tcl"
        if save and Path(path).exists() and not nuke.ask(f"{path} already exists.\nOverwrite it?"):
            return ""
        self.panel.file.setValue(path)
        return path

    def load(self):
        path = self.file_path()
        if not path:
            return
        try:
            self.set_code(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as e:
            nuke.message(f"Could not load {path}:\n{e}")

    def save(self):
        path = self.file_path(save=True)
        if not path:
            return
        try:
            Path(path).write_text(self.qtwidget.toPlainText(), encoding="utf-8")
        except OSError as e:
            nuke.message(f"Could not save {path}:\n{e}")

    def makeUI(self):
        return self.widget

_editor = TCLEditorPanel()

def editor():
    return _editor.show()
