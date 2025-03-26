import subprocess
from nicegui import ui, run, app

# Define host and port for the application
HOST = "127.0.0.1"  # Localhost
PORT = 8080  # Default NiceGUI port

# A simple global to mark which tool is running (or None if none).
tool_in_progress = None

# We'll collect references to all "Run" buttons here so we can disable/enable them.
run_buttons = []

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

def run_tool(script_name: str):
    """
    In your real implementation, you might call:
      subprocess.run(['python', script_name, '--options', ...])
    or make direct AI API calls with streaming responses to .txt files.

    Here we just simulate with a short command and return its output for the UI.
    """
    # Example, purely for demonstration:
    result = subprocess.run(["python", script_name], capture_output=True, text=True)
    return result.stdout, result.stderr

###############################################################################
# HANDLER: Initiates the run in a background thread so the UI won't block
###############################################################################

async def handle_run_button_click(script_name: str):
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

    ui.notify(f"Running {script_name}...")

    try:
        # Run the script in a background thread so the UI remains responsive
        stdout, stderr = await run.io_bound(run_tool, script_name)

        # Show final status or partial logs
        msg = f"Finished {script_name}.\n\nSTDOUT:\n{stdout}"
        if stderr:
            msg += f"\n\nSTDERR:\n{stderr}"
        ui.notify(msg)

    except Exception as ex:
        ui.notify(f"Error while running {script_name}: {ex}")

    finally:
        # Reset and re-enable all buttons
        tool_in_progress = None
        for btn in run_buttons:
            btn.enable()

###############################################################################
# Dark Mode Handling
###############################################################################

def update_tooltip(button, text):
    """Update the tooltip text for a button."""
    button.tooltip(text)

###############################################################################
# BUILD THE UI
###############################################################################

# Create dark mode control - default to dark mode
darkness = ui.dark_mode(True)

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
                with ui.expansion(tool["name"], icon="description", value=False):
                    ui.label(tool["description"]).style("font-style: italic; margin-bottom: 0.5rem;")
                    # Create a 'Run' button for this script
                    with ui.row().classes('w-full justify-center'):
                        b = ui.button(f"Run {tool['name'].lower()}",
                                    on_click=lambda s=tool['name']: handle_run_button_click(s)
                        ).props('no-caps flat fab-mini')
                        run_buttons.append(b)
    
    # Add a separator between tool groups
    # ui.separator().classes('w-full max-w-3xl my-4')
    
    # --- Editing and Rewriting Tools ---
    with ui.card().classes('w-full max-w-3xl'):
        with ui.row().classes('w-full justify-center'):
            ui.label("EDITING & REWRITING").classes('text-bold text-h6 text-red-7')
        with ui.expansion("Tools for refinement", icon="construction", value=False).classes('w-full'):
            for tool in editing_tools:
                with ui.expansion(tool["name"], icon="description", value=False):
                    ui.label(tool["description"]).style("font-style: italic; margin-bottom: 0.5rem;")
                    # Create a 'Run' button for this script
                    with ui.row().classes('w-full justify-center'):
                        b = ui.button(f"Run {tool['name'].lower()}",
                                    on_click=lambda s=tool['name']: handle_run_button_click(s)
                        ).props('no-caps flat fab-mini')
                        run_buttons.append(b)

try:
    ui.run(
        host=HOST,
        port=PORT,
        title="Writer's Toolkit",
        reload=False,
        show_welcome_message=False,
        # native=True,
        # window_size=(810, 830),
        # dark=None,
        # show=False,
        # this causes issues: 
        # frameless=True,
    )
except Exception as e:
    app.shutdown()  # is not required but feels logical and says it all
