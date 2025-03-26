import subprocess
import shlex  # For safely splitting command-line arguments
import os     # For path expansion
import threading
import time
from nicegui import ui, run, app
from functools import partial  # For proper closure handling

# Define host and port for the application
HOST = "127.0.0.1"  # Localhost
PORT = 8080  # Default NiceGUI port

# A simple global to mark which tool is running (or None if none).
tool_in_progress = None

# We'll collect references to all "Run" buttons here so we can disable/enable them.
run_buttons = []

# Default save directory
DEFAULT_SAVE_DIR = os.path.expanduser("~/writing")

###############################################################################
# DATA: Rough Draft Tools and Editing/Rewriting Tools
###############################################################################

rough_draft_tools = [
    {
        "name": "brainstorm.py",
        "description": (
            "Helps generate initial story ideas, prompts, and creative angles. "
            "Outputs a brainstorming.txt with AI and your own thoughts."
        ),
    },
    {
        "name": "outline_writer.py",
        "description": (
            "Generates a plot outline from your brainstorming file. "
            "You can provide your own outline skeleton and let the AI fill in details."
        ),
    },
    {
        "name": "world_writer.py",
        "description": (
            "Takes your world-building prompts or an existing partial doc "
            "and expands it into a more detailed setting, geography, lore, etc."
        ),
    },
    {
        "name": "chapters_from_outline.py",
        "description": (
            "Creates individual chapter files based on your outline. "
            "Useful for organizing a multi-chapter project quickly."
        ),
    },
    {
        "name": "chapter_writer.py",
        "description": (
            "Drafts chapter text from the outline or a user-provided summary. "
            "You provide any amount of original text; the AI completes or expands it."
        ),
    },
]

editing_tools = [
    {
        "name": "character_analyzer.py",
        "description": (
            "Analyzes a manuscript, outline, and world file to identify and compare "
            "characters, extracting a master character list with appearances. "
            "Helps you maintain consistency in roles, relationships, and names."
        ),
    },
    {
        "name": "tense_consistency_checker.py",
        "description": (
            "Examines the manuscript for verb tense (past vs. present) to ensure "
            "a consistent narrative flow. Generates a report with suggested fixes."
        ),
    },
    {
        "name": "adjective_adverb_optimizer.py",
        "description": (
            "Scans for overused or weak adjectives/adverbs and suggests stronger "
            "verbs or nouns, following Ursula K. Le Guin's guidance."
        ),
    },
    {
        "name": "dangling_modifier_checker.py",
        "description": (
            "Detects dangling or misplaced modifiers that lead to confusing phrases. "
            "Generates a report with examples and revision suggestions."
        ),
    },
    {
        "name": "rhythm_analyzer.py",
        "description": (
            "Evaluates sentence-level rhythm and flow, highlighting monotony "
            "or mismatch of pacing. Offers suggestions for more varied prose."
        ),
    },
    {
        "name": "crowding_leaping_evaluator.py",
        "description": (
            "Checks for narrative 'crowding' (overly dense sections) or 'leaping' "
            "(abrupt time jumps) based on concepts inspired by Ursula K. Le Guin."
        ),
    },
    {
        "name": "punctuation_auditor.py",
        "description": (
            "Looks for run-on sentences, missing commas, or inconsistent punctuation. "
            "Generates a comprehensive punctuation usage report."
        ),
    },
    {
        "name": "consistency_checker.py",
        "description": (
            "Compares manuscript text against a world doc (and optional outline) "
            "to ensure consistency in characters, settings, timelines, etc."
        ),
    },
    {
        "name": "conflict_analyzer.py",
        "description": (
            "Analyzes conflict patterns and escalation at scene, chapter, and arc levels. "
            "Identifies types of conflict and suggests ways to strengthen them."
        ),
    },
    {
        "name": "foreshadowing_tracker.py",
        "description": (
            "Identifies foreshadowing elements (Chekhov's Gun, subtle hints) "
            "and checks if they're resolved. Helps ensure narrative payoffs."
        ),
    },
    {
        "name": "plot_thread_tracker.py",
        "description": (
            "Tracks distinct plot threads through the manuscript, showing "
            "where they diverge/converge. Can generate ASCII-based maps."
        ),
    },
]

###############################################################################
# FUNCTION: Actual script runner (subprocess or AI calls)
###############################################################################

def run_tool(script_name: str, args_str: str = "", log_output=None):
    """
    Run a tool script with the provided arguments.
    
    Args:
        script_name: The script filename to run
        args_str: Command-line arguments as a string
        log_output: A ui.log component to output to in real-time
    
    Returns:
        Tuple of (stdout, stderr) from the subprocess
    """
    # Split the arguments string safely using shlex
    if args_str:
        args = shlex.split(args_str)
    else:
        args = []
    
    # If --save_dir isn't specified, add the default
    if not any(arg.startswith('--save_dir') for arg in args):
        args.extend(['--save_dir', DEFAULT_SAVE_DIR])
    
    # Construct the full command: python script_name [args]
    cmd = ["python", script_name] + args
    
    if log_output:
        # Log the command
        log_output.push(f"Running command: {' '.join(cmd)}")
        log_output.push("Working...")
        
        # Start the process
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Collect outputs
        stdout_lines = []
        stderr_lines = []
        
        # Function to read from stdout and stderr in real-time
        def read_output():
            # Read and process stdout
            for line in process.stdout:
                stdout_lines.append(line)
                log_output.push(line.rstrip())
                
            # Read and process stderr
            for line in process.stderr:
                stderr_lines.append(line)
                log_output.push(f"ERROR: {line.rstrip()}")
        
        # Start a thread to read output
        output_thread = threading.Thread(target=read_output)
        output_thread.daemon = True
        output_thread.start()
        
        # Wait for process to complete
        process.wait()
        output_thread.join(timeout=1.0)  # Wait for thread to finish with timeout
        
        # Get return code
        return_code = process.returncode
        log_output.push(f"Process finished with return code {return_code}")
        
        # Combine collected output
        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)
        
        return stdout, stderr
    else:
        # Run the command and capture output (not real-time)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout, result.stderr

###############################################################################
# HANDLER: Initiates the run in a background thread so the UI won't block
###############################################################################

async def handle_run_button_click(script_name, args_textbox, log_output):
    global tool_in_progress

    # If something else is running, bail out
    if tool_in_progress is not None:
        ui.notify(f"Cannot run '{script_name}' because '{tool_in_progress}' is already in progress.")
        return

    # Mark that a script is now in progress
    tool_in_progress = script_name

    # Disable all run buttons
    for btn in run_buttons:
        btn.disable()

    # Get the arguments from the textbox
    args_str = args_textbox.value

    # Clear previous output and show running message
    log_output.clear()
    log_output.push(f"{script_name} output:")
    log_output.push(f"Running {script_name} with args: {args_str}")
    
    # Notify user that the tool is running
    ui.notify(f"Running {script_name}...")

    try:
        # Run the script in a background thread so the UI remains responsive
        stdout, stderr = await run.io_bound(run_tool, script_name, args_str, log_output)
        
        # Show a completion notification
        ui.notify(f"Finished {script_name}")

    except Exception as ex:
        log_output.push(f"Error while running {script_name}: {ex}")
        ui.notify(f"Error: {ex}")

    finally:
        # Reset and re-enable all buttons
        tool_in_progress = None
        for btn in run_buttons:
            btn.enable()

###############################################################################
# CLEAR OUTPUT HANDLER
###############################################################################

def clear_output(log_output):
    """Clear the content of a log area."""
    log_output.clear()

###############################################################################
# Dark Mode Handling
###############################################################################

def update_tooltip(button, text):
    """Update the tooltip text for a button."""
    button.tooltip(text)

###############################################################################
# Custom CSS for styling
###############################################################################

CUSTOM_STYLES = """
<style>
/* Terminal styling for log component */
.terminal-log {
    background-color: #0f1222 !important;
    color: #b2f2bb !important;
    font-family: 'Courier New', monospace !important;
    border-radius: 4px !important;
    padding: 0 !important;
}

.terminal-log .q-virtual-scroll__content,
.terminal-log .q-virtual-scroll__content > div {
    white-space: pre-wrap !important;
    word-break: break-word !important;
}

.terminal-log .q-virtual-scroll__content > div {
    padding: 2px 12px !important;
    line-height: 1.4 !important;
}

/* Terminal container styling */
.terminal-container {
    border: 1px solid #2d3748;
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.terminal-header {
    background-color: #1a1f36;
    color: #78edbb;
    padding: 8px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: bold;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Button styling */
.run-button {
    background-color: #38a169 !important;
    color: white !important;
}

.clear-button {
    color: #cbd5e0 !important;
}

/* Tool card styling */
.tool-description {
    font-style: italic;
    margin-bottom: 0.5rem;
    color: #a0aec0;
}
</style>
"""

###############################################################################
# BUILD THE UI
###############################################################################

# Create dark mode control - default to dark mode
darkness = ui.dark_mode(True)

# Add custom styles to the page
ui.add_head_html(CUSTOM_STYLES)

with ui.column().classes('w-full items-center'):
    # Add a header row with dark mode toggle to the left of the title
    with ui.row().classes('items-center justify-center w-full max-w-3xl'):
        # Dark/Light mode toggle buttons first (leftmost position)
        with ui.element():
            dark_button = ui.button(icon='dark_mode', on_click=lambda: [darkness.set_value(True), update_tooltip(dark_button, 'be Dark')]) \
                .props('flat fab-mini').tooltip('be Dark').bind_visibility_from(darkness, 'value', value=False)
            light_button = ui.button(icon='light_mode', on_click=lambda: [darkness.set_value(False), update_tooltip(light_button, 'be Light')]) \
                .props('flat fab-mini').tooltip('be Light').bind_visibility_from(darkness, 'value', value=True)
                
        # Title comes after the dark mode toggle
        ui.label("Writer Toolkit Scripts").style("font-size: 1.5rem; font-weight: bold; margin-left: 0.5rem;")
        
        # Add shutdown button on the right side
        ui.button("Shutdown", on_click=lambda: app.shutdown()).props(
            "flat fab"
        ).tooltip("shutdown the server for this app").classes(
            "prevent-uppercase"
        ).style("margin-left: auto;")  # Push to right side

    # --- Rough Draft Tools ---
    with ui.card().classes('w-full max-w-3xl'):
        with ui.row().classes('w-full justify-center'):
            ui.label("ROUGH DRAFT WRITING").classes('text-bold text-h6 text-green-7')
        with ui.expansion("Tools for initial drafting", icon="edit", value=False).classes('w-full'):
            for tool in rough_draft_tools:
                with ui.expansion(tool["name"], icon="description", value=False) as tool_expansion:
                    ui.label(tool["description"]).classes('tool-description')
                    
                    # Add a textbox for command-line arguments
                    with ui.row().classes('w-full justify-center mt-2'):
                        ui.label("Command-line arguments:").style("margin-right: 0.5rem;")
                        args_textbox = ui.input(
                            placeholder="e.g. --manuscript manuscript.txt --save_dir ~/writing"
                        ).classes('w-3/4')
                    
                    # Add output area using ui.log for terminal display
                    with ui.element('div').classes('terminal-container w-full'):
                        # Terminal header with title and clear button
                        with ui.element('div').classes('terminal-header'):
                            ui.label(f"{tool['name']} output")
                            # Create the log component for terminal output
                            log_output = ui.log().classes('terminal-log w-full h-64')
                            log_output.push(f"{tool['name']} output here:")
                            
                            # Create a clear button with proper event handler
                            # Using lambda with default arguments to capture the current log_output
                            clear_btn = ui.button(
                                "Clear", 
                                on_click=lambda _, log=log_output: clear_output(log)
                            ).props('flat dense').classes('clear-button text-xs')
                    
                    # Create a 'Run' button for this script
                    with ui.row().classes('w-full justify-center mt-2 mb-4'):
                        # Use lambda with default arguments to capture the current tool, args_textbox, and log_output
                        run_btn = ui.button(
                            f"Run {tool['name'].lower()}",
                            on_click=lambda _, name=tool['name'], args=args_textbox, log=log_output: 
                                handle_run_button_click(name, args, log)
                        ).classes('run-button')
                        run_buttons.append(run_btn)
    
    # --- Editing and Rewriting Tools ---
    with ui.card().classes('w-full max-w-3xl'):
        with ui.row().classes('w-full justify-center'):
            ui.label("EDITING & REWRITING").classes('text-bold text-h6 text-red-7')
        with ui.expansion("Tools for refinement", icon="construction", value=False).classes('w-full'):
            for tool in editing_tools:
                with ui.expansion(tool["name"], icon="description", value=False) as tool_expansion:
                    ui.label(tool["description"]).classes('tool-description')
                    
                    # Add a textbox for command-line arguments
                    with ui.row().classes('w-full justify-center mt-2'):
                        ui.label("Command-line arguments:").style("margin-right: 0.5rem;")
                        args_textbox = ui.input(
                            placeholder="e.g. --manuscript manuscript.txt --save_dir ~/writing"
                        ).classes('w-3/4')
                    
                    # Add output area using ui.log for terminal display
                    with ui.element('div').classes('terminal-container w-full'):
                        # Terminal header with title and clear button
                        with ui.element('div').classes('terminal-header'):
                            ui.label(f"{tool['name']} output")
                            # Create the log component for terminal output
                            log_output = ui.log().classes('terminal-log w-full h-64')
                            log_output.push(f"{tool['name']} output here:")
                            
                            # Create a clear button with proper event handler
                            clear_btn = ui.button(
                                "Clear", 
                                on_click=lambda _, log=log_output: clear_output(log)
                            ).props('flat dense').classes('clear-button text-xs')
                    
                    # Create a 'Run' button for this script with proper event handler
                    with ui.row().classes('w-full justify-center mt-2 mb-4'):
                        run_btn = ui.button(
                            f"Run {tool['name'].lower()}",
                            on_click=lambda _, name=tool['name'], args=args_textbox, log=log_output: 
                                handle_run_button_click(name, args, log)
                        ).classes('run-button')
                        run_buttons.append(run_btn)

try:
    ui.run(
        host=HOST,
        port=PORT,
        title="Writer's Toolkit",
        reload=False,
        show_welcome_message=False,
    )
except Exception as e:
    print(f"Error running the application: {e}")
    app.shutdown()
