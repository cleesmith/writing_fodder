import subprocess
import shlex
import os
import re
import asyncio
from nicegui import ui, run, app

# Define host and port for the application
HOST = "127.0.0.1"
PORT = 8081  # Using 8081 to avoid conflict with the main toolkit

# Default save directory
DEFAULT_SAVE_DIR = os.path.expanduser("~/writing")

# Sample tool lists - you can modify these to include just the scripts you want to test
# Each tool should have a "name" key with the script filename
tools = [
    {"name": "brainstorm.py", "description": "Generates initial story ideas"},
    {"name": "outline_writer.py", "description": "Creates plot outlines"},
    {"name": "chapter_writer.py", "description": "Drafts chapters"},
    {"name": "character_analyzer.py", "description": "Analyzes character consistency"},
    {"name": "tense_consistency_checker.py", "description": "Checks verb tense"},
    {"name": "rhythm_analyzer.py", "description": "Analyzes prose rhythm"}
]

###############################################################################
# FUNCTION: Script runner (subprocess calls)
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
    cmd = ["python", "-u", script_name] + args
    
    if log_output:
        # Log the command
        log_output.push(f"Running command: {' '.join(cmd)}")
        log_output.push("Working...")
    
    # Run the command and capture output
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if log_output:
        # Log the output
        if result.stdout:
            log_output.push(result.stdout)
        if result.stderr:
            log_output.push(f"ERROR: {result.stderr}")
        log_output.push(f"Process finished with return code {result.returncode}")
    
    return result.stdout, result.stderr

###############################################################################
# FUNCTION: Help Parser and Options Dialog
###############################################################################

async def parse_help_output(script_name, log_output=None):
    """
    Run a script with --help flag and parse the output to extract options.
    
    Args:
        script_name: The script filename to run
        log_output: Optional log component to display the help output
        
    Returns:
        List of option dictionaries with name, arg_name, description, required
    """
    # First run the script with --help to get the help text
    stdout, stderr = await run.io_bound(run_tool, script_name, "--help", log_output)
    
    if stderr and not stdout:
        if log_output:
            log_output.push(f"Error running {script_name} --help: {stderr}")
        ui.notify(f"Error getting help for {script_name}", type="negative")
        return []
    
    # Display the help text in the log if provided
    if log_output:
        log_output.push("Help information:")
        log_output.push(stdout)
    
    # Parse the help output to extract options
    options = []
    
    # Common patterns in argparse help output
    option_pattern = r'(--[\w\-]+)(?:\s+(\w+))?\s+(.*?)(?=(?:--[\w\-]+|\n\n|\Z))'
    required_pattern = r'required argument'
    
    # Find all options in the help text
    matches = re.finditer(option_pattern, stdout, re.DOTALL)
    
    for match in matches:
        option_name = match.group(1)  # --option_name
        arg_name = match.group(2) or ""  # The argument name if any (e.g., FILE)
        description = match.group(3).strip()  # Description text
        
        # Check if this option is marked as required
        is_required = bool(re.search(required_pattern, description, re.IGNORECASE))
        
        # Cleanup the description (remove newlines, extra spaces)
        description = re.sub(r'\s+', ' ', description)
        
        options.append({
            "name": option_name,
            "arg_name": arg_name,
            "description": description,
            "required": is_required
        })
    
    return options

async def build_options_dialog(script_name, options):
    """
    Create a dialog to collect options for a script.
    
    Args:
        script_name: The name of the script
        options: List of option dictionaries with name, arg_name, description, required
        
    Returns:
        Dictionary mapping option names to their values
    """
    # Create an async result that we'll resolve when the form is submitted
    result_future = asyncio.Future()
    
    # Dictionary to store the input elements and their values
    input_elements = {}
    
    # Create the dialog
    dialog = ui.dialog()
    dialog.props('persistent')
    
    with dialog, ui.card().classes('w-full max-w-3xl p-4'):
        ui.label(f'Options for {script_name}').classes('text-h6 mb-4')
        
        # Create the options container
        with ui.column().classes('w-full gap-2'):
            # For each option, create an appropriate input field
            for option in options:
                name = option["name"]
                description = option["description"]
                required = option["required"]
                arg_name = option["arg_name"]
                
                # Format the label
                label = f"{name}"
                if arg_name:
                    label += f" <{arg_name}>"
                if required:
                    label += " *"
                
                # Create a card for each option for better organization
                with ui.card().classes('w-full q-pa-sm q-mb-sm'):
                    ui.label(label).classes('text-bold')
                    ui.label(description).classes('text-caption text-grey-7')
                    
                    # Some common option types based on arg_name or name patterns
                    is_file = any(keyword in arg_name.lower() for keyword in ["file", "path", "dir", "directory"]) \
                           or any(keyword in name.lower() for keyword in ["file", "path", "dir", "directory", "save_dir"])
                    
                    is_number = any(keyword in arg_name.lower() for keyword in ["num", "count", "threshold", "level"])
                    
                    is_boolean = not arg_name or arg_name.lower() in ["flag", "enable", "disable"]
                    
                    # Create appropriate input fields based on the option type
                    if is_boolean:
                        # Boolean options (checkboxes)
                        checkbox = ui.checkbox("Enable this option")
                        input_elements[name] = checkbox
                    elif is_file:
                        # File/directory paths
                        with ui.row().classes('w-full items-center'):
                            input_field = ui.input(placeholder="Enter path...").classes('w-full')
                            input_elements[name] = input_field
                            
                            # Set a default value button
                            ui.button("Default", icon='folder').props('flat dense').on('click', 
                                lambda i=input_field: i.set_value(f"{DEFAULT_SAVE_DIR}/file.txt"))
                    elif is_number:
                        # Numeric inputs
                        input_field = ui.number(placeholder="Enter number...")
                        input_elements[name] = input_field
                    else:
                        # Default to text input
                        input_field = ui.input(placeholder="Enter value...")
                        input_elements[name] = input_field
            
            # Button row
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=lambda: [dialog.close(), result_future.set_result(None)]) \
                   .props('flat').classes('text-grey')
                
                def on_submit():
                    # Collect values from input elements
                    option_values = {}
                    for name, input_element in input_elements.items():
                        option_values[name] = input_element.value
                    
                    # Resolve the future with the option values
                    result_future.set_result(option_values)
                    dialog.close()
                
                ui.button('Apply', on_click=on_submit).props('color=primary').classes('text-white')
    
    # Show the dialog and wait for it to be resolved
    dialog.open()
    return await result_future

def build_command_string(script_name, option_values):
    """
    Build a command-line argument string from option values.
    
    Args:
        script_name: The script filename
        option_values: Dictionary mapping option names to their values
        
    Returns:
        Full command string and arguments string
    """
    args_parts = []
    
    for name, value in option_values.items():
        if value:
            if isinstance(value, bool):
                if value:
                    # Just add the flag for boolean options
                    args_parts.append(name)
            else:
                # For other inputs, add the option and its value
                args_parts.append(name)
                args_parts.append(str(value))
    
    # Join parts with spaces
    args_str = " ".join(args_parts)
    
    # Add default save_dir if not specified
    if not any(arg.startswith('--save_dir') for arg in args_parts):
        args_str += f" --save_dir {DEFAULT_SAVE_DIR}"
    
    # Build the full command
    full_command = f"python -u {script_name} {args_str}"
    
    return full_command, args_str

###############################################################################
# FUNCTION: Command Preview Dialog
###############################################################################

async def show_command_preview(script_name, option_values):
    """
    Show a dialog with the preview of the command to be executed.
    
    Args:
        script_name: The script filename
        option_values: Dictionary mapping option names to their values
        
    Returns:
        Tuple of (should_run, args_str) indicating whether to run the command
        and the arguments string to use
    """
    # Build the command and arguments strings
    full_command, args_str = build_command_string(script_name, option_values)
    
    # Create an async result
    result_future = asyncio.Future()
    
    # Create a dialog for the command preview
    preview_dialog = ui.dialog()
    preview_dialog.props('persistent')
    
    with preview_dialog, ui.card().classes('w-full max-w-3xl p-4'):
        ui.label('Command Preview').classes('text-h6 mb-2')
        
        # Display the full command
        ui.label('The following command will be executed:').classes('mt-2')
        
        # Command display area - IMPROVED CONTRAST
        with ui.element('div').classes('w-full p-3 rounded bg-grey-8 my-3'):
            ui.label(full_command).style('font-family: monospace; overflow-wrap: break-word; color: white;')
        
        # Display the arguments for clarity - IMPROVED CONTRAST
        ui.label('Arguments:').classes('mt-3')
        with ui.element('div').classes('w-full p-3 rounded bg-grey-8 my-2'):
            ui.label(args_str).style('font-family: monospace; overflow-wrap: break-word; color: white;')
        
        # Explanation text
        ui.label('Review the command above before running it. You can edit the options or proceed with execution.').classes('text-caption mt-3 mb-3')
        
        # Button row
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancel', on_click=lambda: [preview_dialog.close(), result_future.set_result((False, args_str))]) \
                .props('flat').classes('text-grey')
            
            ui.button('Edit Options', on_click=lambda: [preview_dialog.close(), result_future.set_result((None, args_str))]) \
                .props('flat').classes('text-blue')
            
            ui.button('Run', on_click=lambda: [preview_dialog.close(), result_future.set_result((True, args_str))]) \
                .props('color=primary').classes('text-white')
    
    # Show the dialog
    preview_dialog.open()
    return await result_future

###############################################################################
# FUNCTION: Tool Runner UI
###############################################################################

async def run_tool_ui(script_name, args_str=""):
    """
    Create a dialog to run a tool and show its output
    
    Args:
        script_name: The script to run
        args_str: Command-line arguments as a string
    """
    dialog = ui.dialog().props('maximized')
    
    with dialog, ui.card().classes('w-full h-full'):
        with ui.column().classes('w-full h-full'):
            # Header with title and close button
            with ui.row().classes('w-full justify-between items-center q-pa-md'):
                ui.label(f'Running Tool: {script_name}').classes('text-h6')
                ui.button(icon='close', on_click=dialog.close).props('flat round')
            
            # Arguments display
            ui.label(f"Arguments: {args_str}").classes('text-caption q-px-md')
            
            # Output area using a terminal-like log component
            log_output = ui.log().classes('w-full flex-grow') \
                .style('min-height: 60vh; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px; margin: 1rem;')
            log_output.push(f"Running {script_name} with args: {args_str}")
            
            # Buttons
            with ui.row().classes('w-full justify-end q-pa-md'):
                ui.button('Close', on_click=dialog.close).props('flat')
    
    # Open the dialog
    dialog.open()
    
    # Run the tool and display output
    await run.io_bound(run_tool, script_name, args_str, log_output)

###############################################################################
# Main UI and Workflow
###############################################################################

# Add a dark mode toggle
dark_mode = ui.dark_mode()
dark_mode.enable()

# Create the UI elements
with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
    ui.label('Writer\'s Toolkit Help Parser').classes('text-h4 text-center mb-4')
    
    ui.label('This tool parses the --help output of Writer\'s Toolkit scripts to create form-based UIs for their options').classes('text-subtitle1 text-center mb-6')
    
    # Tool selection
    with ui.card().classes('w-full mb-4 p-4'):
        ui.label('Select a tool to run:').classes('text-h6')
        
        # Create a simple dropdown with the tool names as string options
        selected_tool = ui.select(
            options=[tool['name'] for tool in tools],
            label='Tool',
            value=None
        ).classes('w-full')
        
        # Display the description of the selected tool
        tool_description = ui.label('').classes('text-caption text-grey-7 mt-2')
        
        # Update the description when the tool selection changes
        def update_description(e):
            selected_value = selected_tool.value
            if selected_value:
                for tool in tools:
                    if tool['name'] == selected_value:
                        tool_description.set_text(tool.get('description', ''))
                        break
            else:
                tool_description.set_text('')
        
        # Attach the update function to the select element's change event
        selected_tool.on('update:model-value', update_description)
    
    # Main control area - status and buttons
    with ui.card().classes('w-full mb-4 p-4'):
        status_label = ui.label('Select a tool to begin').classes('text-center')
        
        # Action buttons row
        with ui.row().classes('w-full justify-center gap-4 mt-3'):
            async def configure_and_run_tool():
                script_name = selected_tool.value
                if not script_name:
                    ui.notify('Please select a tool first', type='warning')
                    return
                
                # Update status
                status_label.set_text(f'Parsing help for {script_name}...')
                
                # Create a log dialog for displaying help information
                help_dialog = ui.dialog().props('maximized')
                
                with help_dialog, ui.card().classes('w-full'):
                    with ui.column().classes('w-full p-4'):
                        ui.label(f'Parsing help for {script_name}').classes('text-h6')
                        help_log = ui.log().classes('w-full') \
                            .style('height: 300px; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px;')
                        ui.button('Close', on_click=help_dialog.close).classes('self-end')
                
                help_dialog.open()
                
                # Parse help to get options
                options = await parse_help_output(script_name, help_log)
                
                # Close the help dialog
                help_dialog.close()
                
                if not options:
                    status_label.set_text('Failed to parse options. Check if the script exists and has help text.')
                    return
                
                # Loop to allow editing options
                while True:
                    # Update status
                    status_label.set_text(f'Configuring options for {script_name}...')
                    
                    # Show options dialog to collect values
                    option_values = await build_options_dialog(script_name, options)
                    
                    if option_values is None:
                        # User cancelled
                        status_label.set_text('Option configuration cancelled.')
                        break
                    
                    # Update status
                    status_label.set_text(f'Previewing command for {script_name}...')
                    
                    # Show command preview
                    should_run, args_str = await show_command_preview(script_name, option_values)
                    
                    if should_run is None:
                        # User wants to edit options
                        continue
                    elif should_run:
                        # User confirmed, run the tool
                        status_label.set_text(f'Running {script_name}...')
                        await run_tool_ui(script_name, args_str)
                        status_label.set_text(f'Finished running {script_name}.')
                        break
                    else:
                        # User cancelled
                        status_label.set_text('Command execution cancelled.')
                        break
            
            ui.button('Set Args/Options', on_click=configure_and_run_tool) \
                .props('no-caps').classes('bg-green-600 text-white')
            
            ui.button('Quit', on_click=lambda: app.shutdown()) \
                .props('no-caps').classes('bg-red-600 text-white')

# Run the app
ui.run(
    host=HOST,
    port=PORT,
    title="Writer's Toolkit Help Parser",
    reload=False,
    show_welcome_message=False,
)
