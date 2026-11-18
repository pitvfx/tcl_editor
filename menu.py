import os

import nuke

import tcl_editor

# Nuke runs this file at startup because the tcl_editor folder is on its plugin path.
icon = os.path.join(os.path.dirname(tcl_editor.__file__), "icons", "tcl_editor.png")
nuke.menu("Nuke").addCommand("Edit/TCL Editor", tcl_editor.editor, icon=icon)
