# Store the original puts command
 catch {rename puts original_puts}

# Create a global variable to store captured output
 set captured_output {}

# Define a new puts command that captures output and calls the original
proc puts {args} {
    global captured_output
    # Capture the output
    lappend captured_output [join $args]
}

proc run_code {} {
    set ret "[eval [knob this.code]]"
    get_and_clear_output
    knob this.output $ret
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