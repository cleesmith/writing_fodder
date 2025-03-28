# python -B writers_toolkit.json
# tools_config.json file must exist
import subprocess
import argparse
import os
import re
import json
import asyncio
import platform
from nicegui import ui, run, app
from copy import deepcopy

# Define host and port for the application
HOST = "127.0.0.1"
PORT = 8081  # Using 8081 to avoid conflict with the main toolkit

# Default save directory
DEFAULT_SAVE_DIR = os.path.expanduser("~/writing")

# Default JSON file path for tool configurations
TOOLS_JSON_PATH = "tools_config.json"

###############################################################################
# FUNCTION: Simplified JSON Config handling with Integer Enforcement
###############################################################################

def load_tools_config(force_reload=False):
    """
    Load tool configurations from the JSON file.
    Simple function that loads the entire configuration at once.
    
    Args:
        force_reload: If True, bypasses any caching and reloads directly from disk
    
    Returns:
        Dictionary of tool configurations or empty dict if file not found/invalid
    """
    if not os.path.exists(TOOLS_JSON_PATH):
        ui.notify(f"Error: Configuration file not found at {TOOLS_JSON_PATH}", type="negative")
        return {}
    
    try:
        with open(TOOLS_JSON_PATH, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        ui.notify(f"Error loading JSON config: {str(e)}", type="negative")
        return {}

def ensure_integer_values(obj):
    """
    Recursively ensure all numeric values are integers, not floats.
    
    Args:
        obj: Any Python object (dict, list, etc.)
        
    Returns:
        The same object with all float values converted to integers
    """
    if isinstance(obj, float):
        # Convert all floats to integers
        return int(obj)
    elif isinstance(obj, dict):
        return {k: ensure_integer_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_integer_values(item) for item in obj]
    else:
        return obj

def save_tools_config(config):
    """
    Save tool configurations to the JSON file.
    Converts all numeric values to integers before saving.
    
    Args:
        config: Dictionary of tool configurations
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        # Create a backup of the current file if it exists
        if os.path.exists(TOOLS_JSON_PATH):
            backup_path = f"{TOOLS_JSON_PATH}.bak"
            try:
                with open(TOOLS_JSON_PATH, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
            except Exception as e:
                ui.notify(f"Warning: Failed to create backup file: {str(e)}", type="warning")
        
        # Convert all floats to integers
        integer_config = ensure_integer_values(config)
        
        # Write the entire configuration to the file
        with open(TOOLS_JSON_PATH, 'w') as f:
            json.dump(integer_config, f, indent=4)
        
        ui.notify(f"Configuration saved", type="positive")
        return True
    except Exception as e:
        ui.notify(f"Error saving configuration: {str(e)}", type="negative")
        return False

def update_tool_preferences(script_name, new_preferences):
    """
    Update tool preferences using a simple load-modify-save approach.
    Ensures all numeric values are integers.
    
    Args:
        script_name: The script filename
        new_preferences: Dictionary of preference name-value pairs to update
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        # LOAD: Read the entire configuration - force reload to get latest version
        config = load_tools_config(force_reload=True)
        
        # Check if the script exists in the configuration
        if script_name not in config:
            ui.notify(f"Tool {script_name} not found in configuration", type="negative")
            return False
        
        # MODIFY: Update the preferences
        changes_made = False
        processed_preferences = {}
        
        # First process all preferences, converting floats to ints
        for name, value in new_preferences.items():
            # Convert all floating-point values to integers
            if isinstance(value, float):
                processed_preferences[name] = int(value)
            else:
                processed_preferences[name] = value
        
        # Now update the configuration with the processed values
        for name, new_value in processed_preferences.items():
            # Find and update the option in the configuration
            for option in config[script_name]["options"]:
                if option["name"] == name:
                    # Ensure there's a default property
                    if "default" not in option:
                        option["default"] = ""
                    
                    # Update the default value
                    option["default"] = new_value
                    changes_made = True
                    break
        
        # Remove any legacy user_preferences section if it exists
        if "user_preferences" in config[script_name]:
            del config[script_name]["user_preferences"]
            changes_made = True
        
        if not changes_made:
            ui.notify("No changes were made to the configuration", type="info")
            return True  # Not an error, just no changes
        
        # SAVE: Write the entire configuration back to the file
        result = save_tools_config(config)
        
        if result:
            ui.notify(f"Default values updated for {script_name}", type="positive")
        
        return result
        
    except Exception as e:
        ui.notify(f"Error updating preferences: {str(e)}", type="negative")
        return False

###############################################################################
# FUNCTION: Argument Parsing and Script Runner
###############################################################################

def create_parser_for_tool(script_name, options):
    """
    Create an argparse parser for a specific tool based on its options.
    
    Args:
        script_name: The name of the script
        options: List of option dictionaries from the JSON config
        
    Returns:
        An argparse.ArgumentParser object configured for the tool
    """
    # Create a parser for the tool
    parser = argparse.ArgumentParser(
        prog=f"python {script_name}",
        description=f"Run {script_name} with specified options"
    )
    
    # Add arguments for each option
    for option in options:
        name = option["name"]
        description = option["description"]
        required = option.get("required", False)
        default = option.get("default", None)
        arg_name = option.get("arg_name", "")
        
        # Determine the appropriate argument type
        is_flag = not arg_name or arg_name.lower() in ["flag", "enable", "disable"]
        
        if is_flag:
            # Boolean flags
            parser.add_argument(
                name, 
                action="store_true",
                help=description
            )
        else:
            # Value arguments
            parser.add_argument(
                name,
                metavar=arg_name,
                help=description,
                required=required,
                default=default
            )
    
    return parser

def run_tool(script_name, args_dict, log_output=None):
    """
    Run a tool script with the provided arguments.

    Args:
        script_name: The script filename to run
        args_dict: Dictionary of argument name-value pairs
        log_output: A ui.log component to output to in real-time

    Returns:
        Tuple of (stdout, stderr) from the subprocess
    """
    # Convert the arguments dictionary into a command-line argument list
    args_list = []
    for name, value in args_dict.items():
        # Convert any floats to integers
        if isinstance(value, float):
            value = int(value)
            
        if isinstance(value, bool):
            if value:
                # Just add the flag for boolean options
                args_list.append(name)
        elif value is not None:
            # Add the option name and value as separate items
            args_list.append(name)
            args_list.append(str(value))
    
    # If --save_dir isn't specified, add the default
    if not any(arg.startswith('--save_dir') for arg in args_list):
        args_list.extend(['--save_dir', DEFAULT_SAVE_DIR])
    
    # Determine the Python executable based on platform
    if platform.system() == 'Windows':
        python_exe = 'python'  # Using python directly; change to 'py' if needed
    else:
        python_exe = 'python'
    
    # Construct the full command: python script_name [args]
    cmd = [python_exe, "-u", script_name] + args_list
    
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
# FUNCTION: Tool Options Retrieval
###############################################################################

async def get_tool_options(script_name, log_output=None):
    """
    Get options for a script from the JSON configuration.
    Always loads directly from the file to get the latest version.
    
    Args:
        script_name: The script filename
        log_output: Optional log component to display information
        
    Returns:
        List of option dictionaries with name, arg_name, description, required, default
    """
    # Always load the tool configurations fresh from disk
    config = load_tools_config(force_reload=True)
    
    if script_name not in config:
        if log_output:
            log_output.push(f"Error: Configuration for {script_name} not found in JSON config")
        ui.notify(f"Configuration for {script_name} not found", type="negative")
        return []
    
    tool_config = config[script_name]
    
    # Display the help information in the log if provided
    if log_output:
        log_output.push("Tool information from JSON config:")
        log_output.push(f"Name: {tool_config['name']}")
        log_output.push(f"Description: {tool_config['description']}")
        log_output.push(f"Help text: {tool_config['help_text']}")
        log_output.push(f"Options: {len(tool_config['options'])} found")
        
        # Display options by group for better organization
        groups = {}
        for option in tool_config['options']:
            group = option.get('group', 'Other')
            if group not in groups:
                groups[group] = []
            groups[group].append(option)
        
        for group_name, group_options in groups.items():
            log_output.push(f"\n{group_name}:")
            for option in group_options:
                required_mark = " (required)" if option.get('required', False) else ""
                log_output.push(f"  {option['name']} {option.get('arg_name', '')}{required_mark}")
                log_output.push(f"    {option['description']}")
                log_output.push(f"    Default: {option.get('default', 'None')}")
    
    return tool_config['options']

###############################################################################
# FUNCTION: Options Dialog
###############################################################################

async def build_options_dialog(script_name, options):
    """
    Create a dialog to collect options for a script.
    
    Args:
        script_name: The name of the script
        options: List of option dictionaries with name, arg_name, description, required, default
        
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
        
        # Group options by their group
        grouped_options = {}
        for option in options:
            group = option.get('group', 'Other')
            if group not in grouped_options:
                grouped_options[group] = []
            grouped_options[group].append(option)
        
        # Create the options container with sections by group
        with ui.column().classes('w-full gap-2'):
            # For each group, create a section
            for group_name, group_options in grouped_options.items():
                with ui.expansion(group_name, value=True).classes('w-full q-mb-md'):
                    # For each option in this group, create an appropriate input field
                    for option in group_options:
                        name = option["name"]
                        description = option["description"]
                        required = option.get("required", False)
                        arg_name = option.get("arg_name", "")
                        default_value = option.get("default")
                        
                        # If default_value is a float, convert to int
                        if isinstance(default_value, float):
                            default_value = int(default_value)
                        
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
                            
                            # Show current default value in the description
                            if default_value is not None:
                                ui.label(f"Default: {default_value}").classes('text-caption text-grey-7')
                            
                            # Some common option types based on arg_name or name patterns
                            is_file = any(keyword in arg_name.lower() for keyword in ["file", "path", "dir", "directory"]) \
                                   or any(keyword in name.lower() for keyword in ["file", "path", "dir", "directory", "save_dir"])
                            
                            is_number = any(keyword in arg_name.lower() for keyword in ["num", "count", "threshold", "level", "tokens", "window", "timeout"])
                            
                            is_boolean = not arg_name or arg_name.lower() in ["flag", "enable", "disable"]
                            
                            # Create appropriate input fields based on the option type
                            if is_boolean:
                                # Boolean options (checkboxes)
                                # Use default value
                                value_to_use = default_value if default_value is not None else False
                                checkbox = ui.checkbox("Enable this option", value=value_to_use)
                                input_elements[name] = checkbox
                            elif is_file:
                                # File/directory paths
                                with ui.row().classes('w-full items-center'):
                                    # Use default value
                                    input_field = ui.input(
                                        placeholder="Enter path...",
                                        value=default_value
                                    ).classes('w-full')
                                    input_elements[name] = input_field
                                    
                                    # Set a default value button
                                    if "manuscript" in name.lower():
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "manuscript.txt")
                                    elif "outline" in name.lower():
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "outline.txt")
                                    elif "world" in name.lower():
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "world.txt")
                                    elif "save_dir" in name.lower():
                                        default_path = DEFAULT_SAVE_DIR
                                    else:
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "file.txt")
                                    
                                    ui.button("Default", icon='folder').props('flat dense no-caps').on('click', 
                                        lambda i=input_field, p=default_path: i.set_value(p))
                            elif is_number:
                                # Use default value
                                value_to_use = default_value
                                
                                # If no value, try to extract from description
                                if value_to_use is None:
                                    # Match numbers with or without commas: 1000, 1,000, etc.
                                    default_match = re.search(r'default:\s*([\d,]+)', description)
                                    if default_match:
                                        # Remove commas and convert to int
                                        default_str = default_match.group(1).replace(',', '')
                                        try:
                                            value_to_use = int(default_str)
                                        except ValueError:
                                            value_to_use = None
                                
                                # Set precision=0 to force integer values for all number inputs
                                # This prevents users from entering decimal values
                                input_field = ui.number(
                                    placeholder="Enter number...", 
                                    value=value_to_use,
                                    precision=0  # Force integer values only - no decimals allowed
                                )
                                input_elements[name] = input_field
                            else:
                                # Default to text input with default value
                                input_field = ui.input(
                                    placeholder="Enter value...",
                                    value=default_value
                                )
                                input_elements[name] = input_field
            
            # Add save preferences checkbox
            save_preferences_checkbox = ui.checkbox("Save these settings as defaults", value=True)
            
            # Button row
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=lambda: [dialog.close(), result_future.set_result((None, False))]) \
                   .props('flat no-caps').classes('text-grey')
                
                def on_submit():
                    # Collect values from input elements
                    option_values = {}  # For running the tool
                    changed_options = {}  # For saving as preferences
                    
                    for name, input_element in input_elements.items():
                        if hasattr(input_element, 'value'):
                            # Find the original option to get its default value
                            original_option = next((opt for opt in options if opt['name'] == name), None)
                            if original_option is None:
                                continue
                                
                            current_value = input_element.value
                            
                            # Convert any float values to integers
                            if isinstance(current_value, float):
                                current_value = int(current_value)
                                
                            default_value = original_option.get('default')
                            # Convert default value to int if it's a float
                            if isinstance(default_value, float):
                                default_value = int(default_value)
                                
                            is_required = original_option.get('required', False)
                            
                            # Add to the command execution values if it has a value
                            if current_value is not None:
                                is_empty_string = isinstance(current_value, str) and current_value.strip() == ""
                                if not is_empty_string or is_required:
                                    option_values[name] = current_value
                            
                            # Track changed values for preference saving
                            if current_value != default_value:
                                changed_options[name] = current_value
                    
                    # Get the save preferences checkbox value
                    should_save = save_preferences_checkbox.value
                    
                    # Save preferences immediately if requested
                    if should_save and changed_options:
                        update_tool_preferences(script_name, changed_options)
                    
                    # Resolve the future with the option values and save flag
                    result_future.set_result((option_values, should_save))
                    dialog.close()
                
                ui.button('Apply', on_click=on_submit).props('color=primary no-caps').classes('text-white')
    
    # Show the dialog and wait for it to be resolved
    dialog.open()
    return await result_future

def build_command_string(script_name, option_values):
    """
    Build a command-line argument string from option values.
    Include ALL parameters in the command string.
    
    Args:
        script_name: The script filename
        option_values: Dictionary mapping option names to their values
        
    Returns:
        Tuple of (full command string, args_list) for display and execution
    """
    # Load the tool configurations to check for required parameters - always force reload
    config = load_tools_config(force_reload=True)
    tool_config = config.get(script_name, {})
    options = tool_config.get('options', [])
    
    # Get all required option names
    required_options = [opt['name'] for opt in options if opt.get('required', False)]
    
    # Check if all required options are provided
    missing_required = [opt for opt in required_options if opt not in option_values]
    if missing_required:
        ui.notify(f"Missing required options: {', '.join(missing_required)}", type="negative")
        # Add the missing required options with empty values to prompt user to fix
        for opt in missing_required:
            option_values[opt] = ""
    
    # Create a properly formatted argument list
    args_list = []
    
    # Simply include ALL parameters - don't check against defaults
    for name, value in option_values.items():
        # Convert any float values to integers
        if isinstance(value, float):
            value = int(value)
            
        if isinstance(value, bool):
            if value:
                # Just add the flag for boolean options
                args_list.append(name)
        else:
            # Handle empty strings
            is_empty_string = isinstance(value, str) and value.strip() == ""
            is_required = name in required_options
            
            # Include the parameter if it's not an empty string or if it's required
            if not is_empty_string or is_required:
                args_list.append(name)
                args_list.append(str(value))
    
    # Add default save_dir if not specified
    if not any(arg.startswith('--save_dir') for arg in args_list):
        args_list.extend(['--save_dir', DEFAULT_SAVE_DIR])
    
    # Determine the Python executable based on platform
    python_exe = 'python'  # Using python directly for all platforms
    
    # Build the full command for display
    # Use proper platform-specific quoting for display purposes
    quoted_args = []
    for arg in args_list:
        if platform.system() == 'Windows':
            # On Windows, quote if arg contains spaces
            if ' ' in arg:
                quoted_args.append(f'"{arg}"')
            else:
                quoted_args.append(arg)
        else:
            # On Unix, use shell-style quoting (simple version)
            if ' ' in arg or any(c in arg for c in '*?[]{}():,&|;<>~`!$'):
                quoted_args.append(f"'{arg}'")
            else:
                quoted_args.append(arg)
    
    full_command = f"{python_exe} -u {script_name} {' '.join(quoted_args)}"
    
    return full_command, args_list

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
        Boolean indicating whether to run the command
    """
    # Build the command string for display
    full_command, args_list = build_command_string(script_name, option_values)
    
    # Create a display-friendly version of the arguments
    args_display = []
    i = 0
    while i < len(args_list):
        if i+1 < len(args_list) and args_list[i].startswith('--'):
            # Combine argument name and value
            args_display.append(f"{args_list[i]} {args_list[i+1]}")
            i += 2
        else:
            # Just a flag
            args_display.append(args_list[i])
            i += 1
    
    args_str = " ".join(args_display)
    
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
            ui.button('Cancel', on_click=lambda: [preview_dialog.close(), result_future.set_result(False)]) \
                .props('flat no-caps').classes('text-grey')
            
            ui.button('Edit Options', on_click=lambda: [preview_dialog.close(), result_future.set_result(None)]) \
                .props('flat no-caps').classes('text-blue')
            
            ui.button('Run', on_click=lambda: [preview_dialog.close(), result_future.set_result(True)]) \
                .props('color=primary no-caps').classes('text-white')
    
    # Show the dialog
    preview_dialog.open()
    return await result_future

###############################################################################
# FUNCTION: Tool Runner UI
###############################################################################

async def run_tool_ui(script_name, args_dict=None):
    """
    Create a dialog to run a tool and show its output
    
    Args:
        script_name: The script to run
        args_dict: Dictionary of argument name-value pairs
    """
    if args_dict is None:
        args_dict = {}
    
    # Generate command and args list for display
    full_command, args_list = build_command_string(script_name, args_dict)
    
    # Create a readable version of args for display
    args_display = []
    i = 0
    while i < len(args_list):
        if i+1 < len(args_list) and args_list[i].startswith('--'):
            # Combine option and value
            args_display.append(f"{args_list[i]} {args_list[i+1]}")
            i += 2
        else:
            # Just a flag
            args_display.append(args_list[i])
            i += 1
    
    args_str = " ".join(args_display)
    
    dialog = ui.dialog().props('maximized')
    
    with dialog, ui.card().classes('w-full h-full'):
        with ui.column().classes('w-full h-full'):
            # Header with title and close button
            with ui.row().classes('w-full justify-between items-center q-pa-md'):
                ui.label(f'Running Tool: {script_name}').classes('text-h6')
                ui.button(icon='close', on_click=dialog.close).props('flat round no-caps')
            
            # Arguments display
            ui.label(f"Arguments: {args_str}").classes('text-caption q-px-md')
            
            # Output area using a terminal-like log component
            log_output = ui.log().classes('w-full flex-grow') \
                .style('min-height: 60vh; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px; margin: 1rem;')
            log_output.push(f"Running {script_name} with args: {args_str}")
            
            # Buttons
            with ui.row().classes('w-full justify-end q-pa-md'):
                ui.button('Close', on_click=dialog.close).props('flat no-caps')
    
    # Open the dialog
    dialog.open()
    
    # Run the tool and display output
    await run.io_bound(run_tool, script_name, args_dict, log_output)

###############################################################################
# Check for JSON config file existence
###############################################################################

def check_config_file():
    """
    Check if the JSON configuration file exists.
    Display an error message if it doesn't.
    
    Returns:
        Boolean indicating whether the configuration file exists
    """
    if not os.path.exists(TOOLS_JSON_PATH):
        ui.notify(f"Error: Configuration file not found at {TOOLS_JSON_PATH}. Please ensure it exists.", 
                 type="negative", 
                 timeout=0)  # Set timeout to 0 to make the notification persistent
        return False
    return True

###############################################################################
# Functions for managing preferences
###############################################################################

def backup_config_file():
    """
    Create a backup of the configuration file.
    
    Returns:
        Boolean indicating success or failure
    """
    try:
        if os.path.exists(TOOLS_JSON_PATH):
            backup_path = f"{TOOLS_JSON_PATH}.bak"
            with open(TOOLS_JSON_PATH, 'r') as src, open(backup_path, 'w') as dst:
                dst.write(src.read())
            ui.notify(f"Created backup", type="positive")
            return True
        else:
            ui.notify(f"Cannot create backup - file does not exist", type="negative")
    except Exception as e:
        ui.notify(f"Error creating backup: {str(e)}", type="negative")
    return False

def restore_config_from_backup():
    """
    Restore the configuration file from a backup.
    
    Returns:
        Boolean indicating success or failure
    """
    backup_path = f"{TOOLS_JSON_PATH}.bak"
    if not os.path.exists(backup_path):
        ui.notify(f"No backup file found", type="negative")
        return False
    
    try:
        with open(backup_path, 'r') as src, open(TOOLS_JSON_PATH, 'w') as dst:
            dst.write(src.read())
        ui.notify(f"Configuration restored from backup", type="positive")
        return True
    except Exception as e:
        ui.notify(f"Error restoring from backup: {str(e)}", type="negative")
        return False

###############################################################################
# Configuration Dialog
###############################################################################

async def show_config_dialog():
    """
    Show a configuration dialog for managing the application settings.
    """
    dialog = ui.dialog()
    dialog.props('persistent')
    
    with dialog, ui.card().classes('w-full max-w-3xl p-4'):
        ui.label('Configuration Settings').classes('text-h6 mb-4')
        
        with ui.column().classes('w-full gap-4'):
            # Config file path setting
            with ui.card().classes('w-full p-3'):
                ui.label('Configuration File Path').classes('text-bold')
                with ui.row().classes('w-full items-center'):
                    json_path_input = ui.input(
                        placeholder="Path to config file...",
                        value=TOOLS_JSON_PATH
                    ).classes('w-full')
                    
                    def update_config_path():
                        global TOOLS_JSON_PATH
                        new_path = json_path_input.value
                        TOOLS_JSON_PATH = new_path
                        check_config_file()
                        ui.notify(f"Config path updated", type="positive")
                    
                    ui.button('Update', on_click=update_config_path).props('no-caps')
            
            # Default save directory setting
            with ui.card().classes('w-full p-3'):
                ui.label('Default Save Directory').classes('text-bold')
                ui.label(f"Current: {DEFAULT_SAVE_DIR}").classes('text-caption text-grey-7')
                with ui.row().classes('w-full items-center'):
                    save_dir_input = ui.input(
                        placeholder="Path to save directory...",
                        value=DEFAULT_SAVE_DIR
                    ).classes('w-full')
                    
                    def update_save_dir():
                        global DEFAULT_SAVE_DIR
                        new_dir = save_dir_input.value
                        DEFAULT_SAVE_DIR = new_dir
                        ui.notify(f"Default save directory updated", type="positive")
                    
                    ui.button('Update', on_click=update_save_dir).props('no-caps')
            
            # Backup and restore options
            with ui.card().classes('w-full p-3'):
                ui.label('Backup & Restore').classes('text-bold')
                with ui.row().classes('w-full justify-between'):
                    ui.button('Backup Config', on_click=backup_config_file).props('outline no-caps')
                    ui.button('Restore from Backup', on_click=restore_config_from_backup).props('outline no-caps')
            
            # Close button
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Close', on_click=dialog.close).props('color=primary no-caps').classes('text-white')
    
    dialog.open()

###############################################################################
# Main UI and Workflow
###############################################################################

def main():
    """Main function to set up the UI."""
    # Check if configuration file exists
    check_config_file()
    
    # Create dark mode control - default to dark mode
    darkness = ui.dark_mode(True)
    
    # Create the UI elements
    with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
        # Header row with dark mode toggle, title, and buttons
        with ui.row().classes('w-full items-center justify-between mb-4'):
            # Left side: Dark/light mode toggle
            with ui.element():
                dark_button = ui.button(icon='dark_mode', on_click=lambda: [darkness.set_value(True)]) \
                    .props('flat fab-mini no-caps').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
                light_button = ui.button(icon='light_mode', on_click=lambda: [darkness.set_value(False)]) \
                    .props('flat fab-mini no-caps').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
            
            # Center: Title
            ui.label("Writer's Toolkit").classes('text-h4 text-center')
            
            # Right side: Config and Quit buttons
            with ui.row().classes('gap-2'):
                ui.button("Config", on_click=show_config_dialog).props('no-caps flat').classes('text-green-600')
                ui.button("Quit", on_click=lambda: app.shutdown()).props('no-caps flat').classes('text-red-600')
        
        # Combined main card for tool selection and action buttons
        with ui.card().classes('w-full mb-4 p-4'):
            ui.label('Select a tool to run:').classes('text-h6')
            
            # Load tool options from JSON file
            config = load_tools_config()
            tool_options = []
            
            if config:
                # Extract tool names and descriptions
                for tool_name, tool_data in config.items():
                    tool_options.append({
                        "name": tool_name,
                        "description": tool_data.get("description", "No description available")
                    })
            
            if not tool_options:
                ui.label("No tools found in configuration file. Please check the JSON file.").classes('text-negative')
                default_tool_name = ""
                default_description = ""
            else:
                default_tool_name = tool_options[0]["name"]
                default_description = tool_options[0]["description"]
            
            # Create a dropdown with the tool names
            selected_tool = ui.select(
                options=[tool["name"] for tool in tool_options] if tool_options else [],
                label='Tool',
                value=default_tool_name if tool_options else None
            ).classes('w-full')
            
            # Display the description of the selected tool
            tool_description = ui.label(default_description).classes('text-caption text-grey-7 mt-2')
            
            # Update the description when the tool selection changes
            def update_description(e):
                selected_value = selected_tool.value
                if selected_value:
                    for tool in tool_options:
                        if tool['name'] == selected_value:
                            tool_description.set_text(tool.get('description', ''))
                            break
                else:
                    tool_description.set_text('')
            
            # Attach the update function to the select element's change event
            selected_tool.on('update:model-value', update_description)
            
            # Spacer to create vertical space where the status message used to be
            ui.space().classes('h-4')
            
            # Action buttons row - with the modified button text
            with ui.row().classes('w-full justify-center gap-4 mt-3'):
                async def configure_and_run_tool():
                    script_name = selected_tool.value
                    if not script_name:
                        ui.notify('Please select a tool first', type='warning')
                        return
                    
                    # Use notifications for important status updates
                    ui.notify(f"Loading options for {script_name}...", type="info", timeout=2000)
                    
                    # Create a log dialog for displaying JSON information
                    json_dialog = ui.dialog().props('maximized')
                    
                    with json_dialog, ui.card().classes('w-full'):
                        with ui.column().classes('w-full p-4'):
                            ui.label(f'Loading options for {script_name} from JSON').classes('text-h6')
                            json_log = ui.log().classes('w-full') \
                                .style('height: 300px; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px;')
                            ui.button('Close', on_click=json_dialog.close).props('no-caps').classes('self-end')
                    
                    json_dialog.open()
                    
                    # Always get fresh options directly from the file - this is critical!
                    options = await get_tool_options(script_name, json_log)
                    
                    # Close the JSON dialog
                    json_dialog.close()
                    
                    if not options:
                        ui.notify('Failed to load options from JSON. Check if the configuration exists.', type="negative")
                        return
                    
                    # Loop to allow editing options
                    while True:
                        # Show options dialog to collect values and save preference
                        result = await build_options_dialog(script_name, options)
                        
                        if result[0] is None:
                            # User cancelled - don't show any status message
                            break
                            
                        option_values, should_save = result
                        
                        # Show command preview
                        should_run = await show_command_preview(script_name, option_values)
                        
                        if should_run is None:
                            # User wants to edit options
                            # Reload options to get the latest values
                            options = await get_tool_options(script_name)
                            continue
                        elif should_run:
                            # User confirmed, run the tool
                            ui.notify(f"Running {script_name}...", type="info")
                            await run_tool_ui(script_name, option_values)
                            ui.notify(f"Finished running {script_name}", type="positive")
                            break
                        else:
                            # User cancelled - don't show any status message
                            break
                
                # Changed button text from "Config and Run" to "Setup and/or Run"
                ui.button('Setup and/or Run', on_click=configure_and_run_tool) \
                    .props('no-caps').classes('bg-green-600 text-white')

if __name__ == "__main__":
    main()
    # Run the app
    ui.run(
        host=HOST,
        port=PORT,
        title="Writer's Toolkit",
        reload=False,
        show_welcome_message=False,
    )
