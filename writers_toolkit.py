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
# info: Rough Draft Tools and Editing/Rewriting Tools
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
        "description": ("""Analyzes manuscript, outline, and world files to
        identify and compare character appearances. It extracts
        a master character list that details which files each
        character appears in, examines consistency across documents,
        and highlights discrepancies in names, roles, or
        relationships. The analysis produces a detailed report with
        sections and recommendations to improve character coherence.
        This is needed because AI draft writing has a tendency to add new characters!
        """
        ),
    },
    {
        "name": "tense_consistency_checker.py",
        "description": ("""Examines the manuscript to evaluate verb tense consistency. 
        It identifies shifts between past and present
        tense that might confuse readers, focusing on unintentional
        changes in narrative flow. With customizable analysis levels
        and configurable chapter markers, it generates a detailed
        report with examples, explanations, and suggestions for
        improving consistency.
        """
        ),
    },
    {
        "name": "adjective_adverb_optimizer.py",
        "description": ("""Analyzes manuscript for adjective and adverb usage to pinpoint
        unnecessary modifiers and overused qualifiers, offering
        specific suggestions for replacing weak descriptive patterns
        with stronger verbs and nouns.
        """
        ),
    },
    {
        "name": "dangling_modifier_checker.py",
        "description": ("""Detects dangling and
        misplaced modifiers in a manuscript. It examines text to pinpoint instances
        where descriptive phrases don’t logically connect to their
        intended subjects, potentially causing confusion or
        unintended humor. With customizable analysis level,
        sensitivity, and specific modifier types, it generates a
        detailed report complete with examples, explanations, and
        revision suggestions to enhance clarity and precision.
        """
        ),
    },
    {
        "name": "rhythm_analyzer.py",
        "description": ("""Analyzes manuscript for the rhythm and flow
        of prose. It measures sentence length variations, detects
        monotonous patterns, and highlights sections where the
        writing’s rhythm doesn’t match the intended mood.
        Configurable analysis levels, selectable scene types, and
        adjustable sensitivity settings allow it to generate a
        detailed report with examples, explanations, and suggestions
        for enhancing overall narrative rhythm.
        """
        ),
    },
    {
        "name": "crowding_leaping_evaluator.py",
        "description": ("""Evaluate manuscript structure for pacing issues. 
        It identifies overly dense sections
        ("crowding") and abrupt transitions or time jumps
        ("leaping") based on concepts inspired by Ursula K. Le Guin.
        With configurable analysis levels and sensitivity settings,
        it produces a detailed report—including optional text-based
        visualizations—that offers feedback and suggestions for
        improving narrative rhythm and clarity.
        """
        ),
    },
    {
        "name": "punctuation_auditor.py",
        "description": ("""Focused on evaluating punctuation effectiveness in the manuscript. 
        It detects issues such as run-on sentences,missing commas, and 
        irregular punctuation patterns that may hinder clarity and flow. 
        Configurable analysis levels, strictness settings, and selectable punctuation 
        elements enable it to generate a detailed report with examples,
        explanations, and recommendations for enhancing punctuation
        and overall readability.
        """
        ),
    },
    {
        "name": "consistency_checker.py",
        "description": ("""Consistency checker utility that compares a manuscript
        against a world document (and optionally an outline). It supports
        various consistency checks—world, internal, development, and
        unresolved. Configurable options enable targeted analysis of
        character, setting, timeline, and thematic consistency, producing
        detailed reports with examples and recommendations for resolving
        discrepancies.
        """
        ),
    },
    {
        "name": "conflict_analyzer.py",
        "description": ("""Examines conflict patterns at different narrative levels. 
        It identifies conflict nature, escalation, and resolution at scene,
        chapter, and arc levels. With customizable analysis levels
        and selectable conflict types, it produces a detailed report
        featuring examples, assessments, and recommendations for
        strengthening narrative tension and coherence.
        """
        ),
    },
    {
        "name": "foreshadowing_tracker.py",
        "description": ("""Identifies foreshadowing elements and tracks their payoffs. 
        It pinpoints explicit clues, subtle hints, and Chekhov's Gun elements 
        to evaluate how well narrative setups are resolved. With customizable
        options to select foreshadowing types and organization modes
        (chronological or by type), it generates detailed reports
        featuring examples, assessments, and recommendations for
        fulfilling narrative promises.
        """
        ),
    },
    {
        "name": "plot_thread_tracker.py",
        "description": ("""Identifies and tracks distinct plot threads—revealing 
        how they interconnect, converge, and diverge throughout the narrative. 
        It uses text-based representations (with optional ASCII art
        visualization) and supports configurable analysis depth
        (basic, detailed, or comprehensive) to produce detailed
        reports with progression maps, thread connections, and
        narrative assessments, including manuscript excerpts and
        recommendations for strengthening the plot architecture.
        """
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

async def handle_run_button_click(script_name, args_textbox, log_output, runner_popup=None):
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
# TOOL RUNNER DIALOG
###############################################################################

async def run_tool_ui(script_name=None):
    with ui.dialog() as runner_popup:
        runner_popup.props("persistent")
        runner_popup.props("maximized")
        with runner_popup, ui.card().classes("w-full items-center"):
            with ui.column().classes("w-full"):
                # Header with title and close button
                with ui.row().classes("w-full items-center mb-0.1 space-x-2"):
                    ui.space()
                    ui.label(f'Running Tool: {script_name if script_name else ""}').style("font-size: 20px; font-weight: bold").classes("m-0")
                    
                    async def close_clear_dialog():
                        runner_popup.close()
                        runner_popup.clear()  # removes the hidden runner_popup ui.dialog
                    
                    ui.button(
                        icon='close', 
                        on_click=close_clear_dialog
                    ) \
                    .tooltip("Close") \
                    .props('no-caps flat fab-mini')
                
                # Add a textbox for command-line arguments
                with ui.row().classes('w-full items-center mt-0').style('margin-top: -1.75rem;'):
                    ui.label("Options:").style("margin-right: 0.5rem;")
                    args_textbox = ui.input(
                        placeholder="--manuscript my_story.txt --save_dir ~/writing"
                    ).classes('w-3/4 flex-grow')
                with ui.row().classes('w-full items-center justify-between mt-2 mb-0 flex-nowrap'):
                    # Left side - Run button (primary action)
                    run_btn = ui.button(
                        f"Run {script_name if script_name else 'Tool'}:",
                        on_click=lambda: handle_run_button_click(script_name, args_textbox, log_output, runner_popup)
                    ).classes('run-button').props('no-caps flat dense')
                    
                    # Push utility buttons to the right
                    ui.space()
                    
                    # Right side - utility buttons
                    with ui.row().classes('items-center gap-2 flex-nowrap'):
                        # Clear button with blue styling and tooltip
                        clear_btn = ui.button(
                            "Clear", icon="cleaning_services"
                        ).props('no-caps flat dense size="sm"').classes('bg-blue-600 text-white').tooltip("Clears the Tool output box")
                        
                        # Emergency exit button with warning styling
                        ui.button("Force Quit", icon="power_settings_new", on_click=lambda: app.shutdown()).props(
                            'no-caps flat dense size="sm"'
                        ).classes('bg-red-600 text-white').tooltip("Emergency exit if program gets stuck")
                
                # Add output area using ui.log for terminal display - MODIFIED JUST THIS PART
                with ui.element('div').classes('terminal-container w-full').style('margin-top: -0.75rem'):
                    # Create the log component for terminal output with responsive height using JavaScript
                    log_output = ui.log().classes('terminal-log w-full').style('height: calc(90vh - 150px); overflow: auto;')
                    ui.add_body_html("""
                    <script>
                        // Adjust terminal height based on window size
                        function adjustTerminalHeight() {
                            const terminals = document.querySelectorAll('.terminal-log');
                            terminals.forEach(terminal => {
                                // Calculate available height (90% of viewport minus estimated header height)
                                const availableHeight = window.innerHeight * 0.9 - 150;
                                terminal.style.height = `${availableHeight}px`;
                            });
                        }
                        
                        // Run on page load and when window is resized
                        window.addEventListener('load', adjustTerminalHeight);
                        window.addEventListener('resize', adjustTerminalHeight);
                    </script>
                    """)
                    log_output.push("Tool output will appear here...")
                
                # Set the clear button on_click after log_output is defined
                clear_btn.on_click(lambda: clear_output(log_output))

                # ui.separator().props("size=4px color=primary")  # insinuate bottom of settings

    runner_popup.open()
    return runner_popup, args_textbox, log_output

###############################################################################
# BUILD THE UI
###############################################################################

# Create dark mode control - default to dark mode
darkness = ui.dark_mode(True)

# Add custom styles to the page
ui.add_head_html(CUSTOM_STYLES)

with ui.column().classes('w-full items-center'):
    # add a header row with dark mode toggle to the left of the title
    with ui.row().classes('items-center justify-center w-full max-w-3xl'):
        # dark/light mode toggle buttons first (leftmost position)
        with ui.element():
            dark_button = ui.button(icon='dark_mode', on_click=lambda: [darkness.set_value(True), update_tooltip(dark_button, 'be Dark')]) \
                .props('flat fab-mini').tooltip('be Dark').bind_visibility_from(darkness, 'value', value=False)
            light_button = ui.button(icon='light_mode', on_click=lambda: [darkness.set_value(False), update_tooltip(light_button, 'be Light')]) \
                .props('flat fab-mini').tooltip('be Light').bind_visibility_from(darkness, 'value', value=True)
                
        # title comes after the dark mode toggle
        ui.label("Writer Toolkit Scripts").style("font-size: 1.5rem; font-weight: bold; margin-left: 0.5rem;")
        
        # add shutdown button on the right side
        ui.button("Quit", on_click=lambda: app.shutdown()).props(
            "no-caps flat fab"
        ).tooltip("quit Writer's Toolkit").style("margin-left: auto;")  # push to right side

    # --- Rough Draft Tools ---
    with ui.card().classes('w-full max-w-3xl'):
        with ui.row().classes('w-full justify-center'):
            ui.label("ROUGH DRAFT WRITING").classes('text-bold text-h6 text-green-7')
        with ui.expansion("Tools for initial drafting", icon="edit", value=False).classes('w-full'):
            for tool in rough_draft_tools:
                with ui.expansion(tool["name"], icon="description", value=False) as tool_expansion:
                    ui.label(tool["description"]).classes('tool-description')
                    
                    # Create a 'Run' button for this script that opens the tool runner dialog
                    with ui.row().classes('w-full justify-center mt-2 mb-4'):
                        run_btn = ui.button(
                            f"Run {tool['name'].lower()}",
                            on_click=lambda _, name=tool['name']: run_tool_ui(name)
                        ).classes('run-button').props('no-caps flat dense')
                        run_buttons.append(run_btn)
    
    # --- Editing and Rewriting Tools ---
    with ui.card().classes('w-full max-w-3xl'):
        with ui.row().classes('w-full justify-center'):
            ui.label("EDITING & REWRITING").classes('text-bold text-h6 text-red-7')
        with ui.expansion("Tools for refinement", icon="construction", value=False).classes('w-full'):
            for tool in editing_tools:
                with ui.expansion(tool["name"], icon="description", value=False) as tool_expansion:
                    ui.label(tool["description"]).classes('tool-description')
                    
                    # Create a 'Run' button for this script that opens the tool runner dialog
                    with ui.row().classes('w-full justify-center mt-2 mb-4'):
                        run_btn = ui.button(
                            f"Run {tool['name'].lower()}",
                            on_click=lambda _, name=tool['name']: run_tool_ui(name)
                        ).classes('run-button').props('no-caps flat dense')
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
