# Store the original puts command
if {[llength [info commands original_puts]] == 0} {
    catch {rename puts original_puts}
}
# Create a global variable to store captured output
 set captured_output {}

# Define a new puts command that captures output and calls the original
proc puts {args} {
    global captured_output
    # Capture the output
    lappend captured_output [join $args]
}

proc run_code {} {
    # Line of the editor code that raised the error, 0 if none
    set ::tcl_editor_error_line 0
    if {[catch {uplevel 1 [knob this.code]} result]} {
        set new_output [list "ERROR: $result"]
        # The last "uplevel" body line in the trace is the line in the editor
        foreach {- line} [regexp -all -inline {\("uplevel" body line (\d+)\)} $::errorInfo] {
            set ::tcl_editor_error_line $line
        }
    } else {
        set new_output [get_and_clear_output]
    }
    set output [knob this.output]
    if {[llength $new_output] > 0} {
        append output [join $new_output "\n"]\n
    }
    knob this.output $output
}

# Function to get and clear the captured output
proc get_and_clear_output {} {
    global captured_output
    set output $captured_output
    set captured_output {}
    return $output
}

# Function to restore the original puts command
proc restore_original_puts {} {
    rename puts {}
    rename original_puts puts
}