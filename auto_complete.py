from pathlib import Path
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QCompleter
import json
import os

class TCLAutocomplete:
    def __init__(self, editor):
        self.editor = editor
        self.commands = {}
        self.load_tcl_commands()
        self.completer = self.setup_completer()


    def load_tcl_commands(self):
        json_path = Path(__file__).parent.joinpath('tcl_commands.json')
        if not json_path.exists():
            FileExistsError(f"TCL commands file not found at {json_path}. Run the extractor script first.")
        try:
            with open(json_path, 'r') as f:
                self.commands = json.load(f)
        except Exception as e:
            print(f"Error loading TCL commands:\n{e}")
            self.commands = {}
                          
    def setup_completer(self):
        completer = QCompleter(list(self.commands.keys()), self.editor)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        return completer

    def insert_completion(self, completion):
        tc = self.editor.textCursor()
        extra = len(completion) - len(self.editor.completer.completionPrefix())
        tc.movePosition(tc.Left)
        tc.movePosition(tc.EndOfWord)
        tc.insertText(completion[-extra:])
        self.editor.setTextCursor(tc)

    def get_command_description(self, command):
        return self.commands.get(command, {}).get("docs", "")