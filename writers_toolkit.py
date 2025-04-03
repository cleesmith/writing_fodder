# python -B writers_toolkit.json
# tools_config.json file must exist
import subprocess
import argparse
import os
import re
import json
import asyncio
import platform
import time
import uuid
import urllib.parse
from copy import deepcopy

from nicegui import ui, run, app

from file_folder_local_picker import local_file_picker

import editor_module

HOST = "127.0.0.1"
PORT = 8081

### claude code ###
# Default projects directory - all projects must be in this folder
PROJECTS_DIR = os.path.expanduser("~/writing")
# Ensure the projects directory exists
os.makedirs(PROJECTS_DIR, exist_ok=True)
# Default save directory - initially set to projects directory
DEFAULT_SAVE_DIR = PROJECTS_DIR
# Current project name and path
CURRENT_PROJECT = None
CURRENT_PROJECT_PATH = None
### end claude code ###

# Original:
# Default save directory
# DEFAULT_SAVE_DIR = os.path.expanduser("~")

# Default JSON file path for tool configurations
TOOLS_JSON_PATH = "tools_config.json"

# Add a global variable for the timer task
timer_task = None

# A simple global to mark which tool is running (or None if none).
tool_in_progress = None

# We'll collect references to all "Run" buttons here so we can disable/enable them.
run_buttons = []

def open_file_in_editor(file_path):
    """Open a file in the integrated text editor in a new tab."""
    try:
        encoded_path = urllib.parse.quote(os.path.abspath(file_path))
        ui.navigate.to(f"/editor?file={encoded_path}", new_tab=True)
    except Exception as e:
        ui.notify(f"Error opening file: {str(e)}", type="negative")

###############################################################################
# FUNCTION: Simplified JSON Config handling with Integer Enforcement
###############################################################################

def load_tools_config(force_reload=False):
    """
    Load tool configurations from the JSON file.
    Also loads global settings if available.
    
    Args:
        force_reload: If True, bypasses any caching and reloads directly from disk
    
    Returns:
        Dictionary of tool configurations or empty dict if file not found/invalid
    """
    global DEFAULT_SAVE_DIR, CURRENT_PROJECT, CURRENT_PROJECT_PATH  # Ensure we can modify the global variables
    
    if not os.path.exists(TOOLS_JSON_PATH):
        ui.notify(f"Error: Configuration file not found at {TOOLS_JSON_PATH}", type="negative")
        return {}
    
    try:
        with open(TOOLS_JSON_PATH, 'r') as f:
            config = json.load(f)
        
        # Check for global settings and update DEFAULT_SAVE_DIR if available
        if "_global_settings" in config:
            global_settings = config["_global_settings"]
            
            # Load project settings
            if "current_project" in global_settings:
                CURRENT_PROJECT = global_settings["current_project"]
            
            if "current_project_path" in global_settings:
                CURRENT_PROJECT_PATH = os.path.expanduser(global_settings["current_project_path"])
                
            # Prefer to use project path for save dir if available
            if "default_save_dir" in global_settings:
                saved_dir = global_settings["default_save_dir"]
                # Expand user path if needed (convert ~ to actual home directory)
                DEFAULT_SAVE_DIR = os.path.expanduser(saved_dir)
            elif CURRENT_PROJECT_PATH:
                # If no save dir but we have a project path, use that
                DEFAULT_SAVE_DIR = CURRENT_PROJECT_PATH
            else:
                # Fallback to projects directory
                DEFAULT_SAVE_DIR = PROJECTS_DIR
        
        return config
    except Exception as e:
        print(f"\nError loading JSON config:\n{str(e)}\n")
        ui.notify(f"Error loading JSON config: {str(e)}", type="negative")
        return {}

def save_global_settings(settings_dict):
    """
    Save global application settings to the config file.
    
    Args:
        settings_dict: Dictionary of global settings to save
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        # Read the current config - FORCE RELOAD to get the latest version
        config = load_tools_config(force_reload=True)
        
        # If we got an empty config, something went wrong - don't save it
        if not config:
            ui.notify("Error: Cannot save settings because config file couldn't be loaded", type="negative")
            return False
        
        # Create _global_settings section if it doesn't exist
        if "_global_settings" not in config:
            config["_global_settings"] = {}
        
        # Update the global settings with the provided values
        config["_global_settings"].update(settings_dict)
        
        # Sanity check: make sure we're not overwriting with just global settings
        # This ensures we're not accidentally removing tool configurations
        if len(config.keys()) <= 1:  # Only _global_settings or empty
            backup_path = f"{TOOLS_JSON_PATH}.before_error"
            try:
                with open(TOOLS_JSON_PATH, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
                ui.notify(f"Error: Configuration would be invalid. Created safety backup at {backup_path}", 
                         type="negative")
            except Exception:
                pass
            return False
        
        result = save_tools_config(config)
        return result
    except Exception as e:
        ui.notify(f"Error saving global settings: {str(e)}", type="negative")
        return False

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
        # SAFETY CHECK - never save an empty configuration
        if not config or len(config) == 0:
            ui.notify("Error: Refusing to save empty configuration", type="negative")
            return False
            
        # Ensure we're not just saving _global_settings
        has_real_tools = False
        for key in config.keys():
            if not key.startswith('_'):
                has_real_tools = True
                break
                
        if not has_real_tools:
            ui.notify("Error: Configuration contains no tool definitions", type="negative")
            return False
        
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
        
        # First process all preferences, converting floats to ints where needed
        for name, value in new_preferences.items():
            # Convert all floating-point values to integers if option type is int
            option_found = False
            for option in config[script_name]["options"]:
                if option["name"] == name:
                    option_found = True
                    option_type = option.get("type", "str")
                    
                    if option_type == "int" and isinstance(value, float):
                        processed_preferences[name] = int(value)
                    else:
                        processed_preferences[name] = value
                    break
            
            if not option_found:
                # If option not found, just pass the value as is
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
            # ui.notify("No changes were made to the configuration", type="info")
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
# FUNCTION: File Picker Integration
###############################################################################

async def select_file_or_folder(start_dir=None, multiple=False, dialog_title="Select Files or Folders", folders_only=False):
    if start_dir is None:
        start_dir = DEFAULT_SAVE_DIR
    
    # Ensure the directory exists
    os.makedirs(os.path.expanduser(start_dir), exist_ok=True)
    
    try:
        # Pass the folders_only parameter to the local_file_picker
        result = await local_file_picker(
            start_dir, 
            multiple=multiple,
            folders_only=folders_only
        )
        
        if result and not multiple:
            # If we're not allowing multiple selections, return the first item
            return result[0]
        return result
    except Exception as e:
        ui.notify(f"Error selecting files: {str(e)}", type="negative")
        return [] if multiple else None

###############################################################################
# FUNCTION: Argument Parsing and Script Runner
###############################################################################

def create_parser_for_tool(script_name, options):
    """
    Create an argparse parser for a specific tool based on its options.
    Uses the explicit type information from the JSON config.
    
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
        option_type = option.get("type", "str")  # Get the explicit type, default to "str"
        choices = option.get("choices", None)  # Optional list of choices
        
        # Handle different types of arguments based on the explicit type
        if option_type == "bool":
            # Boolean flags
            parser.add_argument(
                name, 
                action="store_true",
                help=description
            )
        elif option_type == "int":
            # Integer values
            parser.add_argument(
                name,
                metavar=arg_name,
                type=int,
                help=description,
                required=required,
                default=default,
                choices=choices
            )
        elif option_type == "float":
            # Float values
            parser.add_argument(
                name,
                metavar=arg_name,
                type=float,
                help=description,
                required=required,
                default=default,
                choices=choices
            )
        elif option_type == "choices":
            # Choice from a list of values
            parser.add_argument(
                name,
                metavar=arg_name,
                help=description,
                required=required,
                default=default,
                choices=choices
            )
        else:
            # Default to string for all other types
            parser.add_argument(
                name,
                metavar=arg_name,
                help=description,
                required=required,
                default=default,
                choices=choices
            )
    
    return parser

def run_tool(script_name, args_dict, log_output=None):
    """
    Run a tool script with the provided arguments and track output files.
    Args:
        script_name: The script filename to run
        args_dict: Dictionary of argument name-value pairs
        log_output: A ui.log component to output to in real-time
    Returns:
        Tuple of (stdout, stderr, created_files) from the subprocess
    """
    # Get the tool configuration to determine types
    config = load_tools_config()
    options = config.get(script_name, {}).get("options", [])
    
    # Create a mapping of option names to their types
    option_types = {opt["name"]: opt.get("type", "str") for opt in options}
    
    # Generate a unique ID for this tool run
    run_uuid = str(uuid.uuid4())
    
    # Create a path for the output tracking file with absolute path
    current_dir = os.path.abspath('.')
    tracking_file = os.path.join(current_dir, f"{run_uuid}.txt")
    tracking_file = os.path.abspath(tracking_file)
    
    if log_output:
        log_output.push(f"DEBUG: Creating tracking file: {tracking_file}")
        log_output.push(f"DEBUG: Directory exists: {os.path.exists(os.path.dirname(tracking_file))}")
        log_output.push(f"DEBUG: Directory is writable: {os.access(os.path.dirname(tracking_file), os.W_OK)}")
    
    # Add the tracking file parameter to the tool arguments
    args_dict["--output_tracking"] = tracking_file
    
    # Convert the arguments dictionary into a command-line argument list
    args_list = []
    for name, value in args_dict.items():
        # Get the option type, default to "str"
        option_type = option_types.get(name, "str")
        
        # Handle different types
        if option_type == "int" and isinstance(value, float):
            value = int(value)
        elif option_type == "bool":
            if value:
                # Just add the flag for boolean options
                args_list.append(name)
            continue  # Skip adding value for boolean options
        
        # For all non-boolean options, add the name and value
        if value is not None:
            args_list.append(name)
            args_list.append(str(value))
    
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
        if result.stdout:
            log_output.push(result.stdout)
        if result.stderr:
            log_output.push(f"ERROR: {result.stderr}")
        log_output.push(f"\nProcess finished with return code {result.returncode}")
        log_output.push("Done!")
    
    # Check for the output tracking file
    created_files = []
    created_files = ['Terminal Saved Output.txt', 'manuscript.txt', 'outline_XXX.txt']
    if os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
                
            with open(tracking_file, 'r', encoding='utf-8') as f:
                for line in f:
                    file_path = line.strip()
                    abs_file_path = os.path.abspath(file_path)
                    
                    if abs_file_path and os.path.exists(abs_file_path):
                        if log_output:
                            log_output.push(f"DEBUG: Valid file found: {abs_file_path}")
                        created_files.append(abs_file_path)
                    elif abs_file_path:
                        if log_output:
                            log_output.push(f"DEBUG: Listed file doesn't exist: {abs_file_path}")
        except Exception as e:
            if log_output:
                log_output.push(f"Error reading output files list: {e}")
    else:
        if log_output:
            log_output.push(f"DEBUG ERROR: Tracking file not found after tool execution")
    
    return result.stdout, result.stderr, created_files

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
        List of option dictionaries with name, arg_name, description, required, default, type
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
        log_output.push(f"Name: {tool_config['title']}")
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
                option_type = option.get('type', 'str')
                log_output.push(f"  {option['name']} {option.get('arg_name', '')}{required_mark} [Type: {option_type}]")
                log_output.push(f"    {option['description']}")
                log_output.push(f"    Default: {option.get('default', 'None')}")
                if option.get('choices'):
                    log_output.push(f"    Choices: {', '.join(str(c) for c in option['choices'])}")
    
    return tool_config['options']

###############################################################################
# FUNCTION: Options Dialog
###############################################################################

async def browse_files_handler(input_element, start_path, option_name, option_type):
    """Global handler for file browsing that's not affected by loop closures"""
    try:
        # Determine parameters from option name
        is_dir_selection = "dir" in option_name.lower() or "directory" in option_name.lower() or "folder" in option_name.lower()
        allow_multiple = "multiple" in option_name.lower() or "files" in option_name.lower()
        
        # Get starting directory
        start_dir = input_element.value if input_element.value else start_path
        if os.path.isfile(os.path.expanduser(start_dir)):
            start_dir = os.path.dirname(start_dir)
        
        # Use file picker
        selected = await select_file_or_folder(
            start_dir=start_dir,
            multiple=allow_multiple,
            dialog_title=f"Select {'Folder' if is_dir_selection else 'File'}",
            folders_only=is_dir_selection
        )
        
        # Process selection
        if selected:
            # Format selection appropriately
            if isinstance(selected, list) and selected and allow_multiple:
                formatted_value = ", ".join(selected)
            else:
                formatted_value = selected[0] if isinstance(selected, list) and len(selected) == 1 else selected
            
            # Direct approach to update the input
            input_element.value = formatted_value
            input_element.set_value(formatted_value)
            
            # Force UI updating with a direct JavaScript approach
            element_id = input_element.id
            js_code = f"""
            setTimeout(function() {{
                document.querySelectorAll('input').forEach(function(el) {{
                    if (el.id && el.id.includes('{element_id}')) {{
                        el.value = '{formatted_value}';
                        el.dispatchEvent(new Event('change'));
                    }}
                }});
            }}, 100);
            """
            ui.run_javascript(js_code)
            return True
        else:
            ui.notify("No selection made", type="warning")
            return False
    except Exception as e:
        ui.notify(f"Error: {str(e)}", type="negative")
        return False

async def build_options_dialog(script_name, options):
    """
    Create a dialog to collect options for a script.
    Uses explicit type information from the JSON config.
    
    Args:
        script_name: The name of the script
        options: List of option dictionaries with name, arg_name, description, required, default, type
        
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
                        option_type = option.get("type", "str")  # Get the explicit type
                        choices = option.get("choices", None)
                        
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
                            
                            # Create appropriate input fields based on the explicit type
                            if option_type == "bool":
                                # Boolean options (checkboxes)
                                value_to_use = default_value if default_value is not None else False
                                checkbox = ui.checkbox("Enable this option", value=value_to_use)
                                input_elements[name] = checkbox
                            elif option_type == "int":
                                # Integer input fields
                                value_to_use = default_value if default_value is not None else None
                                
                                # If the option has choices, create a dropdown
                                if choices:
                                    dropdown = ui.select(
                                        options=choices,
                                        value=value_to_use,
                                        label=f"Select value for {name}"
                                    )
                                    input_elements[name] = dropdown
                                else:
                                    # Regular number input for integers
                                    input_field = ui.number(
                                        placeholder="Enter number...", 
                                        value=value_to_use,
                                        precision=0  # Force integer values only
                                    )
                                    input_elements[name] = input_field
                            elif option_type == "float":
                                # Float input fields
                                value_to_use = default_value if default_value is not None else None
                                
                                # If the option has choices, create a dropdown
                                if choices:
                                    dropdown = ui.select(
                                        options=choices,
                                        value=value_to_use,
                                        label=f"Select value for {name}"
                                    )
                                    input_elements[name] = dropdown
                                else:
                                    # Regular number input for floats
                                    input_field = ui.number(
                                        placeholder="Enter number...", 
                                        value=value_to_use
                                    )
                                    input_elements[name] = input_field
                            elif option_type == "choices":
                                # Dropdown for choices
                                if choices:
                                    dropdown = ui.select(
                                        options=choices,
                                        value=default_value,
                                        label=f"Select value for {name}"
                                    )
                                    input_elements[name] = dropdown
                                else:
                                    # Fallback to text input if no choices provided
                                    input_field = ui.input(
                                        placeholder="Enter value...",
                                        value=default_value
                                    )
                                    input_elements[name] = input_field
                            elif option_type == "file" or option_type == "path" or any(kw in name.lower() for kw in ["file", "path", "dir", "directory"]):
                                # File/directory paths with integrated file picker
                                with ui.row().classes('w-full items-center'):
                                    input_field = ui.input(
                                        placeholder="Enter path...",
                                        value=default_value
                                    ).classes('w-full')
                                    input_elements[name] = input_field
                                    
                                    # Set a default path based on option name
                                    if "manuscript" in name.lower():
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "manuscript.txt")
                                    elif "outline" in name.lower():
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "outline.txt")
                                    elif "world" in name.lower():
                                        default_path = os.path.join(DEFAULT_SAVE_DIR, "world.txt")
                                    elif "save_dir" in name.lower():
                                        default_path = DEFAULT_SAVE_DIR
                                    else:
                                        default_path = DEFAULT_SAVE_DIR
                                    
                                    # Default button sets the default path without opening file picker
                                    ui.button("Default", icon='description').props('flat dense no-caps').on('click', 
                                        lambda i=input_field, p=default_path: i.set_value(p))

                                    # Store the needed variables for the current iteration in the closure
                                    current_name = name
                                    current_option_type = option_type
                                    current_default_path = default_path
                                    current_input = input_field  # Create a stable reference

                                    # Define the button click handler to explicitly pass the captured references
                                    ui.button("Browse", icon='folder_open').props('flat dense no-caps').on('click', 
                                        lambda e, input=current_input, path=current_default_path, n=current_name, t=current_option_type: 
                                            browse_files_handler(input, path, n, t))
                            else:
                                # Default to text input for all other types
                                input_field = ui.input(
                                    placeholder="Enter value...",
                                    value=default_value
                                )
                                input_elements[name] = input_field
            
            # Add save preferences checkbox
            save_preferences_checkbox = True # ui.checkbox("Save these settings as defaults", value=True)
            
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
                            # Find the original option to get its default value and type
                            original_option = next((opt for opt in options if opt['name'] == name), None)
                            if original_option is None:
                                continue
                                
                            current_value = input_element.value
                            default_value = original_option.get('default')
                            option_type = original_option.get('type', 'str')
                            is_required = original_option.get('required', False)
                            
                            # Convert values to correct type if needed
                            if option_type == "int" and isinstance(current_value, float):
                                current_value = int(current_value)
                            
                            # Add to the command execution values if it has a value
                            if current_value is not None:
                                is_empty_string = isinstance(current_value, str) and current_value.strip() == ""
                                if not is_empty_string or is_required:
                                    option_values[name] = current_value
                            
                            # Track changed values for preference saving
                            if current_value != default_value:
                                changed_options[name] = current_value
                    
                    # Get the save preferences checkbox value, no, always save:
                    should_save = True
                    
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
    
    # Create a mapping of option names to their types
    option_types = {opt['name']: opt.get('type', 'str') for opt in options}
    
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
        # Get the option type
        option_type = option_types.get(name, 'str')
        
        # Convert values to correct type if needed
        if option_type == "int" and isinstance(value, float):
            value = int(value)
        
        if option_type == "bool":
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
    # if not any(arg.startswith('--save_dir') for arg in args_list):
    #     args_list.extend(['--save_dir', DEFAULT_SAVE_DIR])
    
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
        ui.label('Review the command above before running it.').classes('text-caption mt-3 mb-3')
        ui.label('You can edit the options or proceed with the run.').classes('text-caption mt-3 mb-3')
        
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
# FUNCTION: Clear Output Helper
###############################################################################

def clear_output(log_output, timer_label=None):
    """Clear the content of a log area and reset timer if provided."""
    log_output.clear()
    log_output.push("Tool output will appear here...")
    if timer_label:
        timer_label.text = "elapsed time: 0m 0s"

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
    global tool_in_progress, timer_task
    
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
    
    # Dictionary to store file paths and display names
    file_options = {}
    
    dialog = ui.dialog().props('maximized')
    
    with dialog, ui.card().classes('w-full h-full'):
        with ui.column().classes('w-full h-full'):
            # Header with title and close button
            with ui.row().classes('w-full justify-between items-center q-pa-md'):
                ui.label(f'Running Tool: {script_name}').classes('text-h6')
                ui.button(icon='close', on_click=dialog.close).props('flat round no-caps')
            
            # Create the toolbar with run button, timer, and file selection
            with ui.row().classes('w-full items-center justify-between mt-0 mb-0 q-px-md'):
                # Left side - Run button (primary action) and timer label
                with ui.row().classes('items-center gap-2'):
                    run_btn = ui.button(
                        f"Run {script_name}:",
                        on_click=lambda: run_tool_execution()
                    ).classes('bg-green-600 text-white').props('no-caps flat dense')
                    
                    # Add timer label next to the run button
                    timer_label = ui.label("elapsed time: 0m 0s").classes('text-italic mr-12').style('margin-left: 10px; min-width: 120px;')
                
                # Center - file selection elements (initially hidden)
                file_selector_row = ui.row().classes('items-center gap-2 flex-grow').style('display: none;')
                
                with file_selector_row:
                    # Icon-only button with icon on the left
                    open_btn = ui.button(
                        icon="edit",
                        on_click=lambda: open_selected_file()
                    ).props('no-caps flat dense round').classes('bg-blue-600 text-white')
                    
                    # Add dropdown for file selection with more readable text size
                    file_select = ui.select(
                        options=[],
                        multiple=True,
                        label="Edit/View:"
                    ).classes(f'flex-grow').style('min-width: 300px; max-width: 600px;')
                    file_select.style('font-size: 12px;')
                    file_select.props('popupContentClass="small-text"')
                    file_select.props('use-chips')

                    css_string = f"""
                    <style>
                        .small-text {{
                            font-size: 12px;
                        }}
                    </style>
                    """
                    ui.add_head_html(css_string)
                    
                    # Function to handle file selection
                    def open_selected_file():
                        selected_files = file_select.value
                        if selected_files:
                            for file_id in selected_files:
                                if file_id in file_options:
                                    open_file_in_editor(file_options[file_id])
                    
                # Right side - utility buttons
                with ui.row().classes('items-center gap-2'):
                    # Clear button with blue styling
                    clear_btn = ui.button(
                        "Clear", icon="cleaning_services",
                        on_click=lambda: clear_output(log_output, timer_label)
                    ).props('no-caps flat dense').classes('bg-blue-600 text-white')
                    
                    # Force Quit button
                    force_quit_btn = ui.button(
                        "Force Quit", icon="power_settings_new",
                        on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                    ).props('no-caps flat dense').classes('bg-red-600 text-white')
            
            # Output area using a terminal-like log component
            log_output = ui.log().classes('w-full flex-grow') \
                .style('min-height: 60vh; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px; margin: 1rem;')
            log_output.push("Tool output will appear here...")

            async def run_tool_execution():
                global tool_in_progress, timer_task
                
                # If another tool is running, don't start a new one
                if tool_in_progress is not None:
                    ui.notify(f"Cannot run '{script_name}' because '{tool_in_progress}' is already in progress.")
                    return
                
                # Mark this script as running
                tool_in_progress = script_name
                
                # Clear output and show starting message
                log_output.clear()
                log_output.push(f"Running {script_name} with args: {args_str}")
                
                # Reset file selection and hide the selector
                file_options.clear()
                file_select.set_options([])
                file_selector_row.style('display: none;')
                
                # Initialize the timer
                start_time = time.time()
                
                # Update timer function
                async def update_timer():
                    while tool_in_progress:
                        elapsed = time.time() - start_time
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        timer_label.text = f"elapsed time: {minutes}m {seconds}s"
                        await asyncio.sleep(1)
                
                # Start the timer
                if timer_task:
                    timer_task.cancel()
                timer_task = asyncio.create_task(update_timer())
                
                try:
                    # Run the tool and display output
                    stdout, stderr, created_files = await run.io_bound(run_tool, script_name, args_dict, log_output)
                    
                    # If files were created, update the file selection dropdown
                    if created_files:
                        log_output.push("\n\n--- Text Files Created ---")
                        
                        # Collect text files for the dropdown
                        text_files = [f for f in created_files if f.endswith('.txt')]
                        
                        if text_files:
                            # Create a mapping of display names to file paths and log the files
                            file_options.clear()
                            file_names = []
                            
                            for file_path in text_files:
                                file_name = os.path.basename(file_path)
                                file_options[file_name] = file_path
                                file_names.append(file_name)
                                log_output.push(f"• {file_path}")
                            
                            # Update the dropdown options and show the selector row
                            file_select.set_options(file_names)
                            if file_names:
                                file_select.set_value(file_names[0])  # Select first file by default
                                file_selector_row.style('display: flex;')  # Show the file selector
                    
                    ui.notify(f"Finished running {script_name}", type="positive")
                
                except Exception as e:
                    log_output.push(f"Error running {script_name}: {e}")
                    ui.notify(f"Error: {e}")
                
                finally:
                    # Reset the tool in progress
                    tool_in_progress = None
                    
                    # Stop the timer
                    if timer_task:
                        timer_task.cancel()
    
    # Open the dialog
    dialog.open()

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
# Project Management Functions
###############################################################################

async def select_project_dialog():
    """
    Display a dialog for selecting or creating a project.
    All projects must be within the ~/writing directory.
    This dialog is shown on startup and is required before using the toolkit.
    
    Returns:
        Tuple of (project_name, project_path) or (None, None) if closed without selection
    """
    global CURRENT_PROJECT, CURRENT_PROJECT_PATH, DEFAULT_SAVE_DIR
    
    # Create an async result that we'll resolve when a project is selected
    result_future = asyncio.Future()
    
    # Ensure the projects directory exists
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    
    # Get list of existing projects (folders in ~/writing)
    existing_projects = []
    try:
        # List all directories in the projects folder
        for item in os.listdir(PROJECTS_DIR):
            item_path = os.path.join(PROJECTS_DIR, item)
            if os.path.isdir(item_path):
                existing_projects.append(item)
    except Exception as e:
        print(f"Error listing projects: {e}")
    
    # Create the dialog
    dialog = ui.dialog()
    dialog.props('persistent')
    
    with dialog, ui.card().classes('w-full max-w-3xl p-4'):
        # Header with title and close button
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label('Select or Create a Project').classes('text-h6')
            # Close button in the header
            ui.button(icon='close', on_click=lambda: [dialog.close(), result_future.set_result((None, None))]) \
                .props('flat round dense').tooltip('Close without selecting')
        
        with ui.column().classes('w-full gap-4'):
            # Project selection section
            with ui.card().classes('w-full p-3'):
                ui.label('Select Existing Project').classes('text-bold')
                
                if existing_projects:
                    # Create a select dropdown with existing projects
                    project_select = ui.select(
                        options=existing_projects,
                        label='Project',
                        value=None
                    ).classes('w-full')
                    
                    # Open selected project button
                    ui.button('Open Selected Project', 
                              on_click=lambda: use_selected_project()).props('no-caps').classes('bg-blue-600 text-white')
                else:
                    ui.label("No existing projects found in ~/writing").classes('text-italic')
            
            # Project creation section
            with ui.card().classes('w-full p-3'):
                ui.label('Create New Project').classes('text-bold')
                
                with ui.row().classes('w-full items-center'):
                    new_project_input = ui.input(
                        placeholder="Enter new project name...",
                        value=""
                    ).classes('w-full')
                    
                    # Create project button
                    ui.button('Create Project', 
                             on_click=lambda: create_new_project()).props('no-caps').classes('bg-green-600 text-white')
            
            # Project path information
            ui.label(f"All projects are stored in: {PROJECTS_DIR}").classes('text-caption text-grey-7 mt-2')
            ui.label("You must select or create a project to continue.").classes('text-caption text-grey-7')
            
            # Bottom buttons including Cancel/Close
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=lambda: [dialog.close(), result_future.set_result((None, None))]) \
                   .props('no-caps').classes('text-grey-8')
        
        def use_selected_project():
            selected_project = project_select.value
            if not selected_project:
                ui.notify("Please select a project first", type="warning")
                return
            
            project_path = os.path.join(PROJECTS_DIR, selected_project)
            
            # Set the global variables
            CURRENT_PROJECT = selected_project
            CURRENT_PROJECT_PATH = project_path
            DEFAULT_SAVE_DIR = project_path
            
            # Be careful with config saving - make sure we have tools first
            config = load_tools_config(force_reload=True)
            has_tools = False
            for key in config.keys():
                if not key.startswith('_'):
                    has_tools = True
                    break
            
            if has_tools:
                # Only save settings if we have valid tools in the config
                success = save_global_settings({
                    "default_save_dir": project_path,
                    "current_project": selected_project,
                    "current_project_path": project_path
                })
                
                if success:
                    ui.notify(f"Project '{selected_project}' opened successfully", type="positive")
                else:
                    ui.notify(f"Project set but settings not saved to config", type="warning")
            else:
                ui.notify(f"Project '{selected_project}' set (no settings saved)", type="info")
            
            dialog.close()
            result_future.set_result((selected_project, project_path))
        
        def create_new_project():
            new_project_name = new_project_input.value.strip()
            
            # Validate project name
            if not new_project_name:
                ui.notify("Please enter a project name", type="warning")
                return
            
            # Ensure the name is valid for a directory
            invalid_chars = r'[<>:"/\\|?*]'
            if re.search(invalid_chars, new_project_name):
                ui.notify("Project name contains invalid characters", type="negative")
                return
            
            # Create the project directory
            project_path = os.path.join(PROJECTS_DIR, new_project_name)
            
            try:
                # Check if project already exists
                if os.path.exists(project_path):
                    ui.notify(f"Project '{new_project_name}' already exists", type="warning")
                    return
                
                # Create the directory
                os.makedirs(project_path, exist_ok=True)
                
                # Set the global variables
                CURRENT_PROJECT = new_project_name
                CURRENT_PROJECT_PATH = project_path
                DEFAULT_SAVE_DIR = project_path
                
                # Be careful with config saving - make sure we have tools first
                config = load_tools_config(force_reload=True)
                has_tools = False
                for key in config.keys():
                    if not key.startswith('_'):
                        has_tools = True
                        break
                
                if has_tools:
                    # Only save settings if we have valid tools in the config
                    success = save_global_settings({
                        "default_save_dir": project_path,
                        "current_project": new_project_name,
                        "current_project_path": project_path
                    })
                    
                    if success:
                        ui.notify(f"Project '{new_project_name}' created successfully", type="positive")
                    else:
                        ui.notify(f"Project created but settings not saved to config", type="warning")
                else:
                    ui.notify(f"Project '{new_project_name}' created (no settings saved)", type="info")
                
                dialog.close()
                result_future.set_result((new_project_name, project_path))
                
            except Exception as e:
                ui.notify(f"Error creating project: {str(e)}", type="negative")
    
    # Show the dialog and wait for it to be resolved
    dialog.open()
    return await result_future

###############################################################################
# Configuration Dialog
###############################################################################


async def show_config_dialog():
    """
    Show a simplified configuration dialog with only the Default Save Directory setting.
    """
    dialog = ui.dialog()
    dialog.props('persistent')
    
    with dialog, ui.card().classes('w-full max-w-3xl p-4'):
        # Header with title and top close button
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label('Configuration Settings').classes('text-h6')
            ui.button('Close', on_click=dialog.close).props('flat no-caps').classes('text-primary')
        
        with ui.column().classes('w-full gap-4'):
            ### claude code ###
            # Project selection section
            with ui.card().classes('w-full p-3'):
                ui.label('Current Project').classes('text-bold')
                ui.label(f"Project: {CURRENT_PROJECT or 'None'}").classes('text-caption text-grey-7')
                ui.label(f"Path: {CURRENT_PROJECT_PATH or 'None'}").classes('text-caption text-grey-7')
                
                # Button to change project
                ui.button('Change Project', 
                         on_click=lambda: [dialog.close(), change_project()]).props('no-caps').classes('bg-blue-600 text-white mt-2')
                
                async def change_project():
                    # Show the project selection dialog
                    await select_project_dialog()
                    # Refresh the configuration dialog
                    await show_config_dialog()
            ### end claude code ###
            
            # Default save directory setting - the only section we're keeping
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
                        save_global_settings({"default_save_dir": new_dir})
                        ui.notify(f"Updated save directory.", type="positive", timeout=2000)
                    
                    async def browse_save_dir():
                        try:
                            # Get starting directory from current input value or default to home
                            start_dir = save_dir_input.value if save_dir_input.value else "~"
                            
                            # Use the file picker to select a directory
                            selected = await select_file_or_folder(
                                start_dir=start_dir,
                                multiple=False,
                                dialog_title="Select Default Save Directory",
                                folders_only=True
                            )
                            
                            # Update the input field with the selection if we got one
                            if selected:
                                # Use normalized path
                                normalized_path = os.path.normpath(os.path.expanduser(selected))
                                save_dir_input.set_value(normalized_path)
                            else:
                                ui.notify("No directory selected", type="warning", timeout=2000)
                        except Exception as e:
                            # Handle any errors
                            error_msg = f"Error selecting directory: {str(e)}"
                            ui.notify(error_msg, type="negative", timeout=3000)

                    
                    # Add browse button for directory selection
                    ui.button('Browse', icon='folder_open', on_click=browse_save_dir).props('flat dense no-caps')
                    ui.button('Update', on_click=update_save_dir).props('no-caps')
            
            # Bottom close button - styled like the top one
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Close', on_click=dialog.close).props('flat no-caps').classes('text-primary')
    
    dialog.open()

###############################################################################
# Main UI and Workflow
###############################################################################

### claude code ###
@ui.page('/')
async def main():
    darkness = ui.dark_mode(True)
    
    global CURRENT_PROJECT, CURRENT_PROJECT_PATH, DEFAULT_SAVE_DIR

    # Check for config file first
    if not check_config_file():
        ui.label("Configuration file not found. Please ensure tools_config.json exists.").classes('text-negative')
        return
    
    # Ensure we have a current project before showing the main interface
    if not CURRENT_PROJECT or not CURRENT_PROJECT_PATH:
        # Show project selection dialog
        try:
            project_name, project_path = await select_project_dialog()
            
            # User opted to exit without selecting
            if project_name is None:
                ui.label("Application requires a project to be selected. Please restart and select a project.").classes('text-negative')
                return
            
            # Explicitly update global variables again to ensure they're set in this scope
            CURRENT_PROJECT = project_name
            CURRENT_PROJECT_PATH = project_path
            DEFAULT_SAVE_DIR = project_path
                
        except Exception as e:
            ui.notify(f"Error selecting project: {str(e)}", type="negative")
            ui.label("Encountered an error during project selection. Please restart the application.").classes('text-negative')
            return
    
    # Re-check that we now have a project set
    if not CURRENT_PROJECT or not CURRENT_PROJECT_PATH:
        ui.notify("Project selection is required to use the toolkit.", type="negative")
        ui.label("Please restart the application and select a project.")
        return
    
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
                ui.button("Quit", 
                    on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                    ).props('no-caps flat').classes('text-red-600')
        
        # Project information card
        with ui.card().classes('w-full mb-4 p-3'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.column().classes('gap-1'):
                    ui.label('Current Project').classes('text-h6')
                    ui.label(f"{CURRENT_PROJECT}").classes('text-subtitle1')
                    ui.label(f"Project Path: {CURRENT_PROJECT_PATH}").classes('text-caption text-grey-7')
                
                # Button to change project
                ui.button('Change Project', on_click=lambda: change_project()).props('no-caps').classes('bg-blue-600 text-white')
                
                async def change_project():
                    # Show the project selection dialog
                    project_name, project_path = await select_project_dialog()
                    
                    # If a new project was selected, update globals and refresh
                    if project_name and project_path:
                        global CURRENT_PROJECT, CURRENT_PROJECT_PATH, DEFAULT_SAVE_DIR
                        CURRENT_PROJECT = project_name
                        CURRENT_PROJECT_PATH = project_path
                        DEFAULT_SAVE_DIR = project_path
                        # Refresh the page
                        ui.navigate.reload()
        
        # Combined main card for tool selection and action buttons
        with ui.card().classes('w-full mb-4 p-4'):
            ui.label('Select a tool to run:').classes('text-h6')
            
            # Load tool options from JSON file
            config = load_tools_config()

            tool_options = []

            if config:
                # Extract tool names and descriptions
                for tool_name, tool_data in config.items():
                    if not tool_name.startswith('_'):  # skip special configuration sections
                        tool_options.append({
                            "name": tool_name,
                            "title": tool_data.get("title", tool_name),
                            "description": tool_data.get("description", "No description available")
                        })
            
            if not tool_options:
                ui.label("No tools found in configuration file. Please check the JSON file.").classes('text-negative')
                default_tool_name = ""
                default_description = ""
            else:
                default_tool_name = tool_options[0]["name"]
                default_description = tool_options[0]["description"]

            # Create a dictionary mapping tool names to their titles
            options_dict = {tool["name"]: tool["title"] for tool in tool_options} if tool_options else {}

            selected_tool = ui.select(
                options=options_dict,
                label='Tool',
                value=tool_options[0]["name"] if tool_options else None
            ).classes('w-full')

            # Display the description of the selected tool
            tool_description = ui.label(default_description).classes('text-caption text-grey-7 mt-2')
            
            def update_description(e):
                selected_value = selected_tool.value  # This is the tool name
                if selected_value:
                    for tool in tool_options:
                        if tool['name'] == selected_value:  # Compare with name, not title
                            tool_description.set_text(tool.get('description', ''))
                            break
                else:
                    tool_description.set_text('')            

            # Attach the update function to the select element's change event
            selected_tool.on('update:model-value', update_description)
            
            # Spacer to create vertical space where the status message used to be
            ui.space().classes('h-4')
            
            # Action buttons row
            with ui.row().classes('w-full justify-center gap-4 mt-3'):
                async def configure_and_run_tool():
                    script_name = selected_tool.value
                    if not script_name:
                        ui.notify('Please select a tool first', type='warning')
                        return
                    
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
                    
                    while True:
                        result = await build_options_dialog(script_name, options)
                        
                        if result[0] is None:
                            # User cancelled - don't show any status message
                            break
                            
                        option_values, should_save = result
                        
                        should_run = await show_command_preview(script_name, option_values)
                        
                        if should_run is None:
                            # User wants to edit options
                            # Reload options to get the latest values
                            options = await get_tool_options(script_name)
                            continue
                        elif should_run:
                            await run_tool_ui(script_name, option_values)
                            break
                        else:
                            # User cancelled - don't show any status message
                            break
                
                ui.button('Setup then Run', on_click=configure_and_run_tool) \
                    .props('no-caps').classes('bg-green-600 text-white') \
                    .tooltip('Setup settings for a tool run')
### end claude code ###

if __name__ == "__main__":
    ### claude code ###
    # Load configuration before starting the app to initialize settings
    load_tools_config(force_reload=True)
    
    # Make sure the projects directory exists
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    ### end claude code ###
    
    ui.run(
        host=HOST,
        port=PORT,
        title="Writer's Toolkit",
        reload=False,
        show_welcome_message=False,
    )
