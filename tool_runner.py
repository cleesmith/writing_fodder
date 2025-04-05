#!/usr/bin/env python3
import subprocess
import argparse
import os
import sys
import re
import json
import asyncio # IMPORTANT: this is only used for: timer_task, and nothing else!!!
import platform
import time
import uuid
import urllib.parse
import shutil
from copy import deepcopy

from nicegui import ui, run, app
from tinydb import TinyDB, Query, where

from file_folder_local_picker import local_file_picker

import editor_module


HOST = "127.0.0.1"
PORT = 8082

# Default projects directory - all projects must be in this folder
PROJECTS_DIR = os.path.expanduser("~/writing")
# Ensure the projects directory exists
os.makedirs(PROJECTS_DIR, exist_ok=True)
# Default save directory - initially set to projects directory
DEFAULT_SAVE_DIR = PROJECTS_DIR
# Current project name and path
CURRENT_PROJECT = None
CURRENT_PROJECT_PATH = None

# TinyDB database connection
DB_PATH = "writers_toolkit.json"
db = TinyDB(DB_PATH)
tools_table = db.table('tools')
settings_table = db.table('settings')

# Add a global variable for tool run options:
TOOL_OPTION_VALUES = {}

# Add a global variable for the timer task
timer_task = None

# A simple global to mark which tool is running (or None if none).
tool_in_progress = None

async def pick_file() -> None:
    result = await local_file_picker('~/writing', multiple=True)
    ui.notify(f'Result: {result}')

def open_file_in_editor(file_path):
    """Open a file in the integrated text editor in a new tab."""
    try:
        encoded_path = urllib.parse.quote(os.path.abspath(file_path))
        ui.navigate.to(f"/editor?file={encoded_path}", new_tab=True)
    except Exception as e:
        ui.notify(f"Error opening file: {str(e)}", type="negative")

def check_config_file():
    """
    Check if the database exists and has been initialized with tools.
    Display an error message if it doesn't.
    
    Returns:
        Boolean indicating whether the database is properly set up
    """
    global DB_PATH, db
    try:
        # Check if the DB file exists
        if not os.path.exists(DB_PATH):
            # Create the DB file
            db = TinyDB(DB_PATH)
            ui.notify(f"New database created at {DB_PATH}. Please add tools configuration.", 
                     type="negative", 
                     timeout=0)  # Set timeout to 0 to make the notification persistent
            return False
        
        # Check if any tools exist
        if len(tools_table.all()) == 0:
            ui.notify(f"No tools configured in the database at {DB_PATH}. Please add tools configuration.", 
                     type="negative", 
                     timeout=0)
            return False
            
        return True
    except Exception as e:
        ui.notify(f"Error checking database: {str(e)}", 
                 type="negative", 
                 timeout=0)
        return False

def load_tools_config(force_reload=False):
    """
    Load tool configurations from the TinyDB database.
    Also loads global settings if available.
    
    Args:
        force_reload: If True, bypasses any caching (not needed with TinyDB)
    
    Returns:
        Dictionary of tool configurations or empty dict if no tools found
    """
    global DEFAULT_SAVE_DIR, CURRENT_PROJECT, CURRENT_PROJECT_PATH
    
    # Create a dictionary with all tools
    config = {}
    
    # Get all tools from the tools table
    all_tools = tools_table.all()
    for tool in all_tools:
        tool_name = tool.get('name')
        if tool_name:
            # Remove the 'name' key as it's not part of the original structure
            tool_data = dict(tool)
            del tool_data['name']
            config[tool_name] = tool_data
    
    # Get global settings
    global_settings = settings_table.get(doc_id=1)
    if global_settings:
        config['_global_settings'] = global_settings
        
        # Update global variables based on settings
        if "current_project" in global_settings:
            CURRENT_PROJECT = global_settings["current_project"]
        
        if "current_project_path" in global_settings:
            loaded_path = os.path.expanduser(global_settings["current_project_path"])
            
            # Validate the path is within PROJECTS_DIR
            if os.path.exists(loaded_path) and os.path.commonpath([loaded_path, PROJECTS_DIR]) == PROJECTS_DIR:
                CURRENT_PROJECT_PATH = loaded_path
            else:
                # Path is invalid or outside PROJECTS_DIR
                ui.notify(f"Warning: Saved project path is not within {PROJECTS_DIR}", type="warning")
                CURRENT_PROJECT = None
                CURRENT_PROJECT_PATH = None
            
        # Prefer to use project path for save dir if available
        if "default_save_dir" in global_settings:
            saved_dir = os.path.expanduser(global_settings["default_save_dir"])
            
            # Validate the save directory is within PROJECTS_DIR
            if os.path.exists(saved_dir) and os.path.commonpath([saved_dir, PROJECTS_DIR]) == PROJECTS_DIR:
                DEFAULT_SAVE_DIR = saved_dir
            else:
                # Path is outside PROJECTS_DIR, fallback to PROJECTS_DIR
                ui.notify(f"Warning: Saved directory is not within {PROJECTS_DIR}", type="warning")
                DEFAULT_SAVE_DIR = PROJECTS_DIR
        elif CURRENT_PROJECT_PATH:
            # If no save dir but we have a project path, use that
            DEFAULT_SAVE_DIR = CURRENT_PROJECT_PATH
        else:
            # Fallback to projects directory
            DEFAULT_SAVE_DIR = PROJECTS_DIR
    
    return config

def clear_output(log_output, timer_label=None, file_selector_row=None):
    """Clear the content of a log area and reset timer if provided."""
    log_output.clear()
    log_output.push("Tool output will appear here...")
    if timer_label:
        timer_label.text = "elapsed time: 0m 0s"
    if file_selector_row:
        file_selector_row.style('display: none;')

def get_tool_options(script_name):
    """
    Get options for a script from the database.
    
    Args:
        script_name: The script filename
        log_output: Optional log component to display information
    """
    # Query the database for the tool
    Tool = Query()
    tool = tools_table.get(Tool.name == script_name)

    if not tool:
        ui.notify(f"Configuration for {script_name} not found", type="negative")
        return
    
    return tool['options']

def update_tool_preferences(script_name, new_preferences):
    """
    Update tool preferences using TinyDB operations.
    Ensures all numeric values are integers.
    
    Args:
        script_name: The script filename
        new_preferences: Dictionary of preference name-value pairs to update
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        # Query to find the tool
        Tool = Query()
        tool = tools_table.get(Tool.name == script_name)
        
        if not tool:
            ui.notify(f"Tool {script_name} not found in configuration", type="negative")
            return False
        
        # MODIFY: Update the preferences
        changes_made = False
        processed_preferences = {}
        
        # Get the tool options
        options = tool.get('options', [])
        
        # First process all preferences, converting floats to ints where needed
        for name, value in new_preferences.items():
            # Convert all floating-point values to integers if option type is int
            option_found = False
            for option in options:
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
        
        # Now update the options with the processed values
        for name, new_value in processed_preferences.items():
            # Find and update the option
            for option in options:
                if option["name"] == name:
                    # Ensure there's a default property
                    if "default" not in option:
                        option["default"] = ""
                    
                    # Update the default value
                    option["default"] = new_value
                    changes_made = True
                    break
        
        # Remove any legacy user_preferences section if it exists
        if "user_preferences" in tool:
            del tool["user_preferences"]
            changes_made = True
        
        if not changes_made:
            return True  # Not an error, just no changes
        
        # Update the tool in the database
        tools_table.update({'options': options}, Tool.name == script_name)
        
        ui.notify(f"Default values updated for {script_name}", type="positive")
        
        return True
        
    except Exception as e:
        ui.notify(f"Error updating preferences: {str(e)}", type="negative")
        return False

async def tool_select_file_or_folder(start_dir=None, multiple=False, dialog_title="Select Files or Folders", folders_only=False):
    """
    Display a file/folder picker dialog.
    
    Args:
        start_dir: Initial directory to display
        multiple: Allow multiple selections
        dialog_title: Title for the dialog
        folders_only: Only allow folder selection
        
    Returns:
        Selected file/folder path(s) or None/[] if cancelled
    """
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
        selected = await tool_select_file_or_folder(
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

def update_tool_setup(script_name, option_values):
    global TOOL_OPTION_VALUES
    TOOL_OPTION_VALUES = option_values
    print(f"update_tool_setup:\nTOOL_OPTION_VALUES={TOOL_OPTION_VALUES}\n")

async def build_options_dialog(script_name):
    """
    Create a dialog to collect options for a script.
    Uses explicit type information from the JSON config.
    
    Args:
        script_name: The name of the script
        options: List of option dictionaries with name, arg_name, description, required, default, type
    """

    options = get_tool_options(script_name)

    # dictionary to store the input elements and their values
    input_elements = {}
    
    # create the dialog
    dialog = ui.dialog()
    dialog.props('persistent')
    
    with dialog, ui.card().classes('w-full max-w-3xl p-4'):
        ui.label(f'Options for {script_name}').classes('text-h6 mb-4')

        # Group options by their group
        grouped_options = {}
        for option in options:
            group = option.get('group', 'Other')
            # skip items where group is "Claude API Configuration"
            if group == "Claude API Configuration":
                continue
            # add item to the appropriate group
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
            
            # Add save preferences checkbox - always True for simplicity
            save_preferences = True
            
            # Button row
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                # Cancel button
                def on_cancel():
                    dialog.close()
                    
                ui.button('Cancel', on_click=on_cancel).props('flat no-caps').classes('text-grey')
                
                # Ok button
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
                    
                    # Get the save preferences checkbox value, always True for simplicity
                    should_save = True
                    
                    # Save preferences immediately if requested
                    if should_save and changed_options:
                        update_tool_preferences(script_name, changed_options)

                    update_tool_setup(script_name, option_values)
                    
                    dialog.close()

                ui.button('Ok', on_click=on_submit).props('color=primary no-caps').classes('text-white')
    
    # Show the dialog
    dialog.open()

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

    # print(f"\nbuild_command_string: \noption_values:\n{option_values}")
    # # Get the tool configuration to check for required parameters
    # Tool = Query()
    # tool = tools_table.get(Tool.name == script_name)
    # options = tool.get('options', []) if tool else []
    # print(f"build_command_string:\noptions:\n{options}\n")

    # # Get all required option names
    # required_options = [opt['name'] for opt in options if opt.get('required', False)]
    # print(f"required_options:\n{required_options}\n")
    
    # # Create a mapping of option names to their types
    # option_types = {opt['name']: opt.get('type', 'str') for opt in options}
    # print(f"option_types:\n{option_types}\n")
    
    # # Check if all required options are provided
    # missing_required = [opt for opt in required_options if opt not in option_values]
    # print(f"missing_required:\n{missing_required}\n")
    # if missing_required:
    #     ui.notify(f"Missing required options: {', '.join(missing_required)}", type="negative")
    #     # Add the missing required options with empty values to prompt user to fix
    #     for opt in missing_required:
    #         option_values[opt] = "" # "outline_XXX.txt" #FIXME
    
    # # Create a properly formatted argument list
    # args_list = []
    
    # # Simply include ALL parameters - don't check against defaults
    # print(f"build_command_string:\noption_values:\n{option_values}\n")
    # for name, value in option_values.items():
    #     # Get the option type
    #     option_type = option_types.get(name, 'str')
        
    #     # Convert values to correct type if needed
    #     if option_type == "int" and isinstance(value, float):
    #         value = int(value)
        
    #     if option_type == "bool":
    #         if value:
    #             # Just add the flag for boolean options
    #             args_list.append(name)
    #     else:
    #         # Handle empty strings
    #         is_empty_string = isinstance(value, str) and value.strip() == ""
    #         is_required = name in required_options
            
    #         # Include the parameter if it's not an empty string or if it's required
    #         if not is_empty_string or is_required:
    #             args_list.append(name)
    #             args_list.append(str(value))

    print(f"build_command_string:\nscript_name={script_name}\noption_values={option_values}\n")
    args_list = []
    print(f"TOOL_OPTION_VALUES={TOOL_OPTION_VALUES}\n")
    for key, value in TOOL_OPTION_VALUES.items():
        if isinstance(value, bool):
            if value:  # Only include flag if True
                args_list.append(key)
        else:
            args_list.append(key)
            args_list.append(str(value))

    print(f"args_list={args_list}\n")
    
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
    #        **********.***
    
    if log_output:
        if result.stdout:
            log_output.push(result.stdout)
        if result.stderr:
            log_output.push(f"ERROR: {result.stderr}")
        log_output.push(f"\nProcess finished with return code {result.returncode}")
        log_output.push("Done!")
    
    # Check for the output tracking file
    created_files = []
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


async def run_tool_execution(script_name, args_str, args_dict, file_options, log_output, timer_label, file_select, file_selector_row):
    global tool_in_progress, timer_task

    # if another tool is running, don't start a new one
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
                
    # update the displayed elapsed time:
    async def update_timer(timer_label):
        while tool_in_progress:
            elapsed = time.time() - start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            timer_label.text = f"elapsed time: {minutes}m {seconds}s"
            await asyncio.sleep(1)
    
    # start the timer
    if timer_task:
        timer_task.cancel()
    timer_task = asyncio.create_task(update_timer(timer_label))
    
    # define a function to handle the tool execution completion
    def on_tool_completion(result):
        global tool_in_progress
        stdout, stderr, created_files = result
        
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
    
    # Run the tool in a background task
    result = await run.io_bound(
        run_tool, 
        script_name, 
        args_dict, 
        log_output
    )

    # await asyncio.sleep(10) # for testing, coz time.sleep blocks thread
        
    # reset the tool in progress
    tool_in_progress = None

    # stop the timer
    if timer_task:
        timer_task.cancel()

    on_tool_completion(result)
    log_output.push(result)

'''
async def start_runner_ui(script_name, args_dict):
    if not args_dict:
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
    
    # Create the runner dialog
    runner_dialog = ui.dialog().props('maximized')
    
    with runner_dialog, ui.card().classes('w-full h-full'):
        with ui.column().classes('w-full h-full'):
            # Header with title and close button
            with ui.row().classes('w-full justify-between items-center q-pa-md'):
                ui.label(f'Writing Tool: {script_name}').classes('text-h6')
                ui.button(icon='close', on_click=runner_dialog.close).props('flat round no-caps')
            
            # Create the toolbar with run button, timer, and file selection
            with ui.row().classes('w-full items-center justify-between mt-0 mb-0 q-px-md'):

                # Left side: Setup and Run buttons (primary actions) and timer label
                with ui.row().classes('items-center gap-2'):
                    run_btn = ui.button(
                        f"Setup",
                        on_click=lambda: build_options_dialog(script_name)
                    ).classes('bg-blue-600 text-white').props('no-caps flat dense')

                    run_btn = ui.button(
                        f"Run",
                        on_click=lambda: run_tool_execution(script_name, args_str, args_dict, file_options, log_output, timer_label, file_select, file_selector_row)
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
                        label="Edit:"
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
                        on_click=lambda: clear_output(log_output, timer_label, file_selector_row)
                    ).props('no-caps flat dense').classes('bg-blue-600 text-white')
                    
                    # Force Quit button
                    force_quit_btn = ui.button(
                        "Force Quit", icon="power_settings_new",
                        on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                    ).props('no-caps flat dense').classes('bg-red-600 text-white')
            
            # Output area using a terminal-like log component
            log_output = ui.log().classes('w-full flex-grow') \
                .style('min-height: 60vh; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px; margin-right: 20px;')
            log_output.push("Tool output will appear here...")
    
    # Show the runner dialog
    runner_dialog.open()
'''
async def handle_setup(script_name, setup_completed, run_btn, log_output):
    # handle Setup before Run

    await build_options_dialog(script_name)

    if True: #setup_result:
        # Now generate command and args list for display
        # full_command, args_list = build_command_string(script_name, args_dict)
        full_command, args_list = build_command_string(script_name, TOOL_OPTION_VALUES)

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
        
        setup_completed = True
        # enable run button
        run_btn.enable()

        # Show options in log output
        log_output.clear()
        log_output.push(f"Setup completed. Ready to run with options:")
        log_output.push(f"Command: {full_command}")
        log_output.push(f"Arguments: {args_list}")
        # for key, value in args_dict.items():
        #     log_output.push(f"  {key}: {value}")

async def start_runner_ui(script_name, args_dict):
    if not args_dict:
        args_dict = {}
    
    # dictionary to store file paths and display names
    file_options = {}
    
    # variable to track setup status
    setup_completed = False
    
    # Create the runner dialog
    runner_dialog = ui.dialog().props('maximized')
    
    with runner_dialog, ui.card().classes('w-full h-full'):
        with ui.column().classes('w-full h-full'):
            # Header with title and close button
            with ui.row().classes('w-full justify-between items-center q-pa-md'):
                ui.label(f'Writing Tool: {script_name}').classes('text-h6')
                ui.button(icon='close', on_click=runner_dialog.close).props('flat round no-caps')
            
            # Create the toolbar with run button, timer, and file selection
            with ui.row().classes('w-full items-center justify-between mt-0 mb-0 q-px-md'):

                # Left side: Setup and Run buttons (primary actions) and timer label
                with ui.row().classes('items-center gap-2'):
                    setup_btn = ui.button(
                        f"Setup",
                        on_click=lambda: handle_setup(script_name, setup_completed, run_btn, log_output)
                    ).classes('bg-blue-600 text-white').props('no-caps flat dense')

                    # Function to handle tool execution
                    async def handle_run():
                        # Regenerate the command string to ensure it's current
                        # full_command, args_list = build_command_string(script_name, args_dict)
                        full_command, args_list = build_command_string(script_name, TOOL_OPTION_VALUES)

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
                        
                        # Disable both buttons during run
                        setup_btn.disable()
                        run_btn.disable()
                        
                        try:
                            await run_tool_execution(script_name, args_str, args_dict, file_options, log_output, timer_label, file_select, file_selector_row)
                        finally:
                            # Re-enable buttons after completion
                            setup_btn.enable()
                            run_btn.enable()
                    
                    run_btn = ui.button(
                        f"Run",
                        on_click=handle_run
                    ).classes('bg-green-600 text-white').props('no-caps flat dense')
                    
                    # Disable run button initially
                    run_btn.disable()
                    
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
                        label="Edit:"
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
                    # Function to handle clear output
                    def clear_output_handler():
                        clear_output(log_output, timer_label, file_selector_row)
                        # If setup was completed before, show that info again
                        if setup_completed:
                            # Regenerate the command display
                            # full_command, args_list = build_command_string(script_name, args_dict)
                            full_command, args_list = build_command_string(script_name, TOOL_OPTION_VALUES)
                            
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
                            
                            log_output.push(f"Setup completed. Ready to run with options:")
                            log_output.push(f"Command: {script_name}")
                            log_output.push(f"Arguments: {args_str}")
                            for key, value in args_dict.items():
                                log_output.push(f"  {key}: {value}")
                    
                    # Clear button with blue styling
                    clear_btn = ui.button(
                        "Clear", icon="cleaning_services",
                        on_click=clear_output_handler
                    ).props('no-caps flat dense').classes('bg-blue-600 text-white')
                    
                    # Function to handle force quit
                    def force_quit_handler():
                        # Re-enable buttons when force quit is clicked
                        setup_btn.enable()
                        run_btn.enable() if setup_completed else run_btn.disable()
                        ui.notify("Standby shutting down...", type="warning")
                        app.shutdown()
                    
                    # Force Quit button
                    force_quit_btn = ui.button(
                        "Force Quit", icon="power_settings_new",
                        on_click=force_quit_handler
                    ).props('no-caps flat dense').classes('bg-red-600 text-white')
            
            # Output area using a terminal-like log component
            log_output = ui.log().classes('w-full flex-grow') \
                .style('min-height: 60vh; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px; margin-right: 20px;')
            log_output.push("Tool output will appear here...")
            log_output.push("Please click 'Setup' before running the tool.")
    
    # Show the runner dialog
    runner_dialog.open()

@ui.page('/', response_timeout=999)
async def main():
    ui.dark_mode(True)
    with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label("Run Tool").classes('text-h4 text-center')
            with ui.row().classes('gap-2'):
                ui.button("Quit", 
                    on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                    ).props('no-caps flat').classes('text-red-600')
        
        # Main content area
        with ui.card().classes('w-full'):
            # Description text
            ui.label('Run a selected writing tool.').classes('text-body1 mb-4')
            
            # File chooser button
            ui.button('Tool Runner', on_click=lambda: start_runner_ui('brainstorm.py', {}), icon='folder').props('no-caps')


if __name__ == "__main__":
    # Check for database initialization
    if not check_config_file():
        print("Database not properly initialized. Please add tool configurations.")
        # Don't exit, let the app start to show UI notifications

    # Load configuration before starting the app to initialize settings
    load_tools_config(force_reload=True)
    
    # Make sure the projects directory exists
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    
    ui.run(
        host=HOST,
        port=PORT,
        title="Writer's Toolkit",
        reload=False,
        show_welcome_message=False,
    )
