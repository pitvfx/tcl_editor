import nuke
import nukescripts
import traceback
from PySide2.QtWidgets import QFileDialog
from .widget import TCLEditorUI


class TCLEditor:
    _widget = TCLEditorUI()

    def __init__(self):
        super().__init__()
        nuke.tcl("load capture_puts")

        # Connect UI signals to logic slots
        self._widget.run_button.clicked.connect(self.run_code)
        self._widget.save_button.clicked.connect(self.save_code)
        self._widget.load_button.clicked.connect(self.load_code)

    def run_code(self):
        code = self._widget.editor.toPlainText()
        try:
            nuke.tcl(code)
            captured_output = nuke.tcl("get_and_clear_output")
            # Display the output
            if captured_output:
                for line in captured_output.split("} {"):
                    cleaned_line = line.strip("{}").replace("\n", "")
                    self._widget.output_console.append(cleaned_line)
            else:
                self._widget.output_console.append("(No output)")

        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self._widget.output_console.append(error_msg)

    def save_code(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self._widget, "Save TCL Code", "", "TCL Files (*.tcl)")
        if file_path:
            with open(file_path, 'w') as f:
                f.write(self._widget.editor.toPlainText())
            self._widget.output_console.append(f"Code saved to: {file_path}")

    def load_code(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self._widget, "Load TCL Code", "", "TCL Files (*.tcl)")
        if file_path:
            with open(file_path, 'r') as f:
                code = f.read()
            self._widget.editor.setPlainText(code)

    def __del__(self):
        self._widget.deleteLater()


def add_tcl_editor_panel(self):
    tcl_editor_panel = self
    nukescripts.panels.registerWidgetAsPanel(
        'TCLEditor', 'TCL Editor', 'pit.vfx.TCLEditor')
    return tcl_editor_panel
