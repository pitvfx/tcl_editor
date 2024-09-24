import nuke
import pyui

class TCLEditorPanel(pyui.Dialog):
    def __init__(self):
        nuke.tcl("catch {load capture_puts}")
        pyui.Dialog.__init__(self, "TCL Editor", "pitvfx.tcl_editor", True)
        self.panel = nuke.PanelNode()
        self.build_panel()
        self.add(self.panel.createWidget())

    def build_panel(self):
        self.editor = nuke.Multiline_Eval_String_Knob("editor")
        self.run_button = nuke.Script_Knob("run_script", "run")
        self.run_button.setCommand("run_code")
        self.output = nuke.Multiline_Eval_String_Knob("output", "output")
        self.output.setFlag(nuke.READ_ONLY)
        for k in (self.editor, self.run_button, self.output):
            self.panel.addKnob(k)


editor = TCLEditorPanel()
