#!/usr/bin/env python3
import subprocess
import argparse
import os
import sys
import re
import json
import asyncio # IMPORTANT: this is only used for: TIMER_TASK, and nothing else!!!
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

from writers_toolkit_state import ToolState

ToolState.initialize()

# this is not used in this app, but only for testing popup dialogs:
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
    try:
        # Check if the DB file exists
        if not os.path.exists(ToolState.DB_PATH):
            # Create the DB file
            ToolState.db = TinyDB(ToolState.DB_PATH)
            ui.notify(f"New database created at {ToolState.DB_PATH}. Please add tools configuration.", 
                     type="negative", 
                     timeout=0)  # Set timeout to 0 to make the notification persistent
            return False
        
        # Check if any tools exist
        if len(ToolState.tools_table.all()) == 0:
            ui.notify(f"No tools configured in the database at {ToolState.DB_PATH}. Please add tools configuration.", 
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
    
    # Create a dictionary with all tools
    config = {}
    
    # Get all tools from the tools table
    all_tools = ToolState.tools_table.all()
    for tool in all_tools:
        tool_name = tool.get('name')
        if tool_name:
            # Remove the 'name' key as it's not part of the original structure
            tool_data = dict(tool)
            del tool_data['name']
            config[tool_name] = tool_data
    
    # Get global settings
    global_settings = ToolState.settings_table.get(doc_id=1)
    if global_settings:
        config['_global_settings'] = global_settings
        
        # Update global variables based on settings
        project_name = global_settings.get("current_project")
        project_path = None
        
        if "current_project_path" in global_settings:
            loaded_path = os.path.expanduser(global_settings["current_project_path"])
            
            # Validate the path is within PROJECTS_DIR
            if os.path.exists(loaded_path) and os.path.commonpath([loaded_path, ToolState.PROJECTS_DIR]) == ToolState.PROJECTS_DIR:
                project_path = loaded_path
            else:
                # Path is invalid or outside PROJECTS_DIR
                ui.notify(f"Warning: Saved project path is not within {ToolState.PROJECTS_DIR}", type="warning")
                project_name = None
                project_path = None
        
        # Use the class method to update both variables at once
        ToolState.set_current_project(project_name, project_path)
            
        # Prefer to use project path for save dir if available
        if "default_save_dir" in global_settings:
            saved_dir = os.path.expanduser(global_settings["default_save_dir"])
            
            # Validate the save directory is within PROJECTS_DIR
            if os.path.exists(saved_dir) and os.path.commonpath([saved_dir, ToolState.PROJECTS_DIR]) == ToolState.PROJECTS_DIR:
                ToolState.DEFAULT_SAVE_DIR = saved_dir
            else:
                # Path is outside PROJECTS_DIR, fallback to PROJECTS_DIR
                ui.notify(f"Warning: Saved directory is not within {ToolState.PROJECTS_DIR}", type="warning")
                ToolState.DEFAULT_SAVE_DIR = ToolState.PROJECTS_DIR
        elif ToolState.CURRENT_PROJECT_PATH:
            # If no save dir but we have a project path, use that
            ToolState.DEFAULT_SAVE_DIR = ToolState.CURRENT_PROJECT_PATH
        else:
            # Fallback to projects directory
            ToolState.DEFAULT_SAVE_DIR = ToolState.PROJECTS_DIR
    
    return config

def clear_output(log_output, timer_label=None, file_selector_row=None):
    """Clear the content of a log area and reset timer if provided."""
    log_output.clear()
    log_output.push("Tool output will appear here...")
    if timer_label:
        timer_label.text = "elapsed time: 0m 0s"
    if file_selector_row:
        file_selector_row.style('display: none;')

def get_tool_options():
    # Query the database for the tool
    # # diagnostic information
    # print(f"Checking options for tool: {ToolState.SELECTED_TOOL}")
    # print(f"Database connection exists: {ToolState.db is not None}")
    # print(f"Tools table exists: {ToolState.tools_table is not None}")
    # print(f"Number of tools in database: {len(ToolState.tools_table.all()) if ToolState.tools_table else 0}")
    Tool = Query()
    tool = ToolState.tools_table.get(Tool.name == ToolState.SELECTED_TOOL)
    if not tool:
        ui.notify(f"Configuration for {ToolState.SELECTED_TOOL} not found", type="negative")
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
        tool = ToolState.tools_table.get(Tool.name == script_name)
        
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
        ToolState.tools_table.update({'options': options}, Tool.name == script_name)
        
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

async def update_tool_setup(option_values):
    ToolState.update_tool_setup(option_values)

def build_command_string():
    args_list = []

    for key, value in ToolState.OPTION_VALUES.items():
        if isinstance(value, bool):
            if value:  # only include flag if True
                args_list.append(key)
        else:
            args_list.append(key)
            args_list.append(str(value))
    
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
    
    ToolState.FULL_COMMAND = f"python -u {ToolState.SELECTED_TOOL} {' '.join(quoted_args)}"
    return

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

async def run_tool_execution(file_options, log_output, timer_label, file_select, file_selector_row):
    """
    Execute a tool script with user-selected options.
    
    Args:
        file_options: Dictionary to store output file paths and display names
        log_output: UI component for displaying log messages
        timer_label: UI component for displaying elapsed time
        file_select: UI dropdown for selecting created files
        file_selector_row: UI row containing file selection controls
    """
    
    # If another tool is running, don't start a new one
    if ToolState.IS_RUNNING:
        ui.notify(f"Cannot run '{ToolState.SELECTED_TOOL}' because a is already in progress.")
        return
    
    # Check if we have options and a command string
    if not ToolState.OPTION_VALUES or not ToolState.FULL_COMMAND:
        ui.notify(f"Please set up options for {ToolState.SELECTED_TOOL} before running.")
        return
    
    # Get the command string for display
    args_str = ToolState.FULL_COMMAND.replace(f"python -u {ToolState.SELECTED_TOOL} ", "")
    
    # Mark this script as running
    ToolState.IS_RUNNING = True
    
    # Clear output and show starting message
    log_output.clear()
    log_output.push(f"Running {ToolState.SELECTED_TOOL} with args: {args_str}")
    
    # Reset file selection and hide the selector
    file_options.clear()
    file_select.set_options([])
    file_selector_row.style('display: none;')
    
    # Initialize the timer
    start_time = time.time()
    timer_task = None
                
    # Update the displayed elapsed time
    async def update_timer(timer_label):
        try:
            while ToolState.IS_RUNNING:
                elapsed = time.time() - start_time
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                timer_label.text = f"elapsed time: {minutes}m {seconds}s"
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Timer error: {str(e)}")
    
    # Start the timer
    try:
        if ToolState.TIMER_TASK:
            ToolState.TIMER_TASK.cancel()
        timer_task = asyncio.create_task(update_timer(timer_label))
        ToolState.TIMER_TASK = timer_task
    except Exception as e:
        log_output.push(f"Timer setup error: {str(e)}")
    
    # Define a function to handle the tool execution completion
    def on_tool_completion(result):
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
        
        ui.notify(f"Finished running {ToolState.SELECTED_TOOL}", type="positive")
    
    try:
        # Run the tool in a background task
        result = await run.io_bound(
            run_tool, 
            ToolState.SELECTED_TOOL, 
            ToolState.OPTION_VALUES, 
            log_output
        )
        
        # Process results
        on_tool_completion(result)
    
        # Mark this script as not running = done!
        ToolState.IS_RUNNING = False
        
        # Log any additional output
        if isinstance(result, tuple) and len(result) > 0:
            log_output.push(f"\nTool output: {result[0]}")
        else:
            log_output.push("\nTool completed with no output.")
            
    except Exception as e:
        log_output.push(f"ERROR running tool: {str(e)}")
        ui.notify(f"Error running {ToolState.SELECTED_TOOL}: {str(e)}", type="negative")
    
    finally:
        # Always reset the tool state when done, regardless of success or failure
        ToolState.IS_RUNNING = False
            
        # Always stop the timer
        if timer_task and not timer_task.done():
            timer_task.cancel()
            
        # Make sure global timer task is cleared if it's our timer
        if ToolState.TIMER_TASK == timer_task:
            ToolState.TIMER_TASK = None

async def build_options_dialog():
    """
    Create a dialog to collect options for a script.
    Uses explicit type information from the JSON config.
    Returns the dialog object which can be awaited.
    """
    options = get_tool_options()
    
    # Check if options were retrieved successfully
    if options is None:
        ui.notify(f"Failed to retrieve options for {ToolState.SELECTED_TOOL}", type="negative")
        return None
    
    # Create the dialog as an awaitable object
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-3xl p-4'):
        ui.label(f'Options for {ToolState.SELECTED_TOOL}').classes('text-h6 mb-4')
        
        # Dictionary to store input elements
        input_elements = {}
        
        # Group options by their group
        grouped_options = {}
        for option in options:
            group = option.get('group', 'Other')
            # Skip items where group is "Claude API Configuration"
            if group == "Claude API Configuration":
                continue
            # Add item to the appropriate group
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
                        option_type = option.get("type", "str")
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
                                        default_path = os.path.join(ToolState.DEFAULT_SAVE_DIR, "manuscript.txt")
                                    elif "outline" in name.lower():
                                        default_path = os.path.join(ToolState.DEFAULT_SAVE_DIR, "outline.txt")
                                    elif "world" in name.lower():
                                        default_path = os.path.join(ToolState.DEFAULT_SAVE_DIR, "world.txt")
                                    elif "save_dir" in name.lower():
                                        default_path = ToolState.DEFAULT_SAVE_DIR
                                    else:
                                        default_path = ToolState.DEFAULT_SAVE_DIR
                                    
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
            
            # Button row
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                # Cancel button - submit None to indicate cancellation
                ui.button('Cancel', on_click=lambda: dialog.submit(None)).props('flat no-caps').classes('text-grey')
                
                # Ok button - collect values and submit them
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
                    
                    # Save preferences if there are changes
                    if changed_options:
                        update_tool_preferences(ToolState.SELECTED_TOOL, changed_options)
                    
                    # Submit the collected values through the dialog
                    dialog.submit(option_values)
                
                ui.button('Ok', on_click=on_submit).props('color=primary no-caps').classes('text-white')
    
    # Return the dialog object (not showing it yet)
    return dialog

async def handle_setup(setup_completed, run_btn, log_output):
    """
    Handle the setup process for a tool.
    Uses the awaitable dialog pattern to properly wait for user interaction.
    
    Args:
        setup_completed: Reference to setup completion status
        run_btn: Reference to the run button UI element
        log_output: Reference to the log output UI element
    """
    
    # Ensure we have a valid tool selected
    if not ToolState.SELECTED_TOOL:
        error_msg = "No tool is currently selected."
        print(error_msg)
        log_output.push(error_msg)
        ui.notify(error_msg, type="negative")
        return
    
    try:
        # Clear state at the beginning
        ToolState.OPTION_VALUES = {}
        
        # Create the dialog on-demand
        dialog = await build_options_dialog()
        
        # Check if dialog creation was successful
        if not dialog:
            log_output.push("Failed to create options dialog.")
            return
        
        # Open the dialog
        dialog.open()
        
        # Wait for the dialog result
        option_values = await dialog
        
        # If dialog was cancelled (returned None)
        if option_values is None:
            log_output.push("Setup cancelled.")
            return
        
        # Update tool setup with the collected values
        ToolState.update_tool_setup(option_values)
        
        # Now build the command string AFTER the state is updated
        build_command_string()
        
        # Update UI state
        setup_completed = True
        run_btn.enable()
        
        # Update log display
        log_output.clear()
        log_output.push(f"Setup completed. Ready to run with options:")
        log_output.push(f"Command: {ToolState.FULL_COMMAND}")
    except Exception as e:
        # Handle any errors during the setup process
        error_msg = f"Error during setup: {str(e)}"
        print(error_msg)
        log_output.push(error_msg)
        ui.notify(error_msg, type="negative")

async def start_runner_ui(script_name):
    ToolState.SELECTED_TOOL = script_name
    
    # dictionary to store outputs(results) file paths and display names
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
                    setup_btn = ui.button('Setup',
                        on_click=lambda: handle_setup(setup_completed, run_btn, log_output)
                    ).classes('bg-blue-600 text-white').props('no-caps flat dense')

                    # Function to handle tool execution
                    async def handle_run():
                        # disable both buttons during run
                        setup_btn.disable()
                        run_btn.disable()
                        try:
                            await run_tool_execution(file_options, log_output, timer_label, file_select, file_selector_row)
                        finally:
                            # re-enable buttons after completion
                            setup_btn.enable()
                            run_btn.enable()
                    
                    run_btn = ui.button('Run', on_click=handle_run
                    ).classes('bg-green-600 text-white').props('no-caps flat dense')
                    
                    # disable run button initially
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
                    
                    # Clear button with blue styling
                    clear_btn = ui.button(
                        "Clear", icon="cleaning_services",
                        on_click=clear_output_handler
                    ).props('no-caps flat dense').classes('bg-blue-600 text-white')
                    
                    # Function to handle force quit
                    def force_quit_handler():
                        # # Re-enable buttons when force quit is clicked
                        # setup_btn.enable()
                        # run_btn.enable() if setup_completed else run_btn.disable()
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

def select_project_dialog(on_project_selected=None):
    """
    Display a dialog for selecting or creating a project.
    All projects must be within the ~/writing directory.
    This dialog is shown on startup and is required before using the toolkit.
    
    Args:
        on_project_selected: Callback function that receives (project_name, project_path)
    """
    
    # Ensure the projects directory exists
    os.makedirs(ToolState.PROJECTS_DIR, exist_ok=True)
    
    # Get list of existing projects (folders in ~/writing)
    existing_projects = []
    try:
        # List all directories in the projects folder
        for item in os.listdir(ToolState.PROJECTS_DIR):
            # Skip hidden directories (starting with dot)
            if item.startswith('.'):
                continue
                
            item_path = os.path.join(ToolState.PROJECTS_DIR, item)
            if os.path.isdir(item_path):
                existing_projects.append(item)
                
        # Sort the projects alphabetically
        existing_projects.sort()
    except Exception as e:
        print(f"Error listing projects: {e}")
    
    # Create the project_dialog
    project_dialog = ui.dialog()
    project_dialog.props('persistent')
    
    # Helper function to process dialog closure
    def process_dialog_close(project_name, project_path):
        """
        Handle the dialog closure and call the callback if provided.
        
        Args:
            project_name: Selected project name
            project_path: Selected project path
        """
        # Close the dialog
        project_dialog.close()
        
        # Call the callback if provided
        if on_project_selected and callable(on_project_selected):
            on_project_selected(project_name, project_path)
            
        # Reload if needed to reflect changes
        if project_name and project_path:
            ui.navigate.reload()
    
    with project_dialog, ui.card().classes('w-full max-w-3xl p-4'):
        # Header with title and close button
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label('Select or Create a Project').classes('text-h6')
            ui.button(icon='close', on_click=lambda: process_dialog_close(None, None)).props('flat round no-caps')
        
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
                    def use_selected_project():
                        selected_project = project_select.value
                        if not selected_project:
                            ui.notify("Please select a project first", type="warning")
                            return
                        
                        project_path = os.path.join(ToolState.PROJECTS_DIR, selected_project)
                        
                        # Set the current project using ToolState method
                        ToolState.set_current_project(selected_project, project_path)
                        
                        # Save to TinyDB regardless of tools existence
                        # This ensures the project persists between sessions
                        success = ToolState.save_global_settings({
                            "default_save_dir": project_path,
                            "current_project": selected_project,
                            "current_project_path": project_path
                        })
                        
                        if success:
                            ui.notify(f"Project '{selected_project}' set successfully", type="positive")
                        else:
                            ui.notify(f"Project set but settings not saved to database", type="warning")
                        
                        # Close dialog and call callback
                        process_dialog_close(selected_project, project_path)
                    
                    ui.button('Open Selected Project', on_click=use_selected_project).props('no-caps').classes('bg-blue-600 text-white')
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
                        project_path = os.path.join(ToolState.PROJECTS_DIR, new_project_name)
                        
                        try:
                            # Check if project already exists
                            if os.path.exists(project_path):
                                ui.notify(f"Project '{new_project_name}' already exists", type="warning")
                                return
                            
                            # Create the directory
                            os.makedirs(project_path, exist_ok=True)
                            
                            # Set the current project using ToolState method
                            ToolState.set_current_project(new_project_name, project_path)
                            
                            # Save to TinyDB regardless of tools existence
                            # This ensures the project persists between sessions
                            success = ToolState.save_global_settings({
                                "default_save_dir": project_path,
                                "current_project": new_project_name,
                                "current_project_path": project_path
                            })
                            
                            if success:
                                ui.notify(f"Project '{new_project_name}' created successfully", type="positive")
                            else:
                                ui.notify(f"Project created but settings not saved to database", type="warning")
                            
                            # Close dialog and call callback
                            process_dialog_close(new_project_name, project_path)
                            
                        except Exception as e:
                            ui.notify(f"Error creating project: {str(e)}", type="negative")
                    
                    ui.button('Create Project', on_click=create_new_project).props('no-caps').classes('bg-green-600 text-white')
            
            # Project path information
            ui.label(f"All projects are stored in: {ToolState.PROJECTS_DIR}").classes('text-caption text-grey-7 mt-2')
            ui.label("Projects can only be created within this directory.").classes('text-caption text-grey-7')
            ui.label("You must select or create a project to continue.").classes('text-caption text-grey-7')
            
            # Bottom buttons including Close
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button(icon='close', on_click=lambda: process_dialog_close(None, None)).props('flat round no-caps')
    
    # Show the dialog
    project_dialog.open()

@ui.page('/', response_timeout=999)
async def main():
    darkness = ui.dark_mode(True)
    # with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
    #     with ui.row().classes('w-full items-center justify-between mb-4'):
    #         ui.label("Run Tool").classes('text-h4 text-center')
    #         with ui.row().classes('gap-2'):
    #             ui.button("Quit", 
    #                 on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
    #                 ).props('no-caps flat').classes('text-red-600')

    # Create the main UI components
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
                # ui.button("Config", on_click=show_config_dialog).props('no-caps flat').classes('text-green-600')
                ui.button("Quit", 
                    on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                    ).props('no-caps flat').classes('text-red-600')
        
        # Project information card
        with ui.card().classes('w-full mb-4 p-3'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.column().classes('gap-1'):
                    ui.label('Current Project').classes('text-h6')
                    
                    # Display project info or select project message
                    if ToolState.CURRENT_PROJECT:
                        ui.label(f"{ToolState.CURRENT_PROJECT}").classes('text-subtitle1')
                        ui.label(f"Project Path: {ToolState.CURRENT_PROJECT_PATH}").classes('text-caption text-grey-7')
                    else:
                        ui.label("No project selected").classes('text-subtitle1 text-orange-600 font-bold')
                        ui.label("You must create or select a project before using any tools").classes('text-caption text-orange-400')
                
                # Button to change project
                def change_project():
                    def handle_project_selection(project_name, project_path):
                        # If a new project was selected, update globals and refresh
                        if project_name and project_path:
                            ToolState.CURRENT_PROJECT = project_name
                            ToolState.CURRENT_PROJECT_PATH = project_path
                            ToolState.DEFAULT_SAVE_DIR = project_path
                            # Refresh the page
                            ui.navigate.reload()
                    
                    # Show the project selection dialog
                    select_project_dialog(on_project_selected=handle_project_selection)
                
                ui.button('Select Project', on_click=change_project).props('no-caps').classes('bg-blue-600 text-white')
        
        # Combined main card for tool selection and action buttons
        with ui.card().classes('w-full mb-4 p-4'):
            ui.label('Select a tool to run:').classes('text-h6')


            tools = ToolState.get_tool_options()
            if not tools:
                ui.label("No tools found in database. Please add tools configurations.").classes('text-negative')
                default_tool_name = ""
                default_description = ""
            else:
                default_tool_name = tools[0]["name"]
                default_description = tools[0]["description"]

            # Create a dictionary mapping tool names to their titles
            options_dict = {tool["name"]: tool["title"] for tool in tools} if tools else {}

            selected_tool = ui.select(
                options=options_dict,
                label='Tool',
                value=tools[0]["name"] if tools else None
            ).classes('w-full')

            # Display the description of the selected tool
            tool_description = ui.label(default_description).classes('text-caption text-grey-7 mt-2')
            
            def update_description(e):
                selected_value = selected_tool.value  # This is the tool name
                if selected_value:
                    for tool in tools:
                        if tool['name'] == selected_value:  # Compare with name, not title
                            tool_description.set_text(tool.get('description', ''))
                            break
                else:
                    tool_description.set_text('')            

            # Attach the update function to the select element's change event
            selected_tool.on('update:model-value', update_description)
            
            # Spacer to create vertical space
            ui.space().classes('h-4')

            # Action buttons row
            with ui.row().classes('w-full justify-center gap-4 mt-3'):

                run_button = ui.button('Setup then Run', 
                                      on_click=lambda: start_runner_ui(selected_tool.value)) \
                    .props('no-caps').classes('bg-green-600 text-white') \
                    .tooltip('Setup settings for a tool run')
        
        # # Main content area
        # with ui.card().classes('w-full'):
        #     # Description text
        #     ui.label('Run a selected writing tool.').classes('text-body1 mb-4')
            
        #     # File chooser button
        #     ui.button('Tool Runner', on_click=lambda: start_runner_ui('tokens_words_counter.py'), icon='folder').props('no-caps')

if __name__ == "__main__":
    # Check for database initialization
    if not check_config_file():
        print("Database not properly initialized. Please add tool configurations.")
        # Don't exit, let the app start to show UI notifications

    # Load configuration before starting the app to initialize settings
    load_tools_config(force_reload=True)

    print(f"api={ToolState.settings_claude_api_configuration}")

    # Make sure the projects directory exists
    os.makedirs(ToolState.PROJECTS_DIR, exist_ok=True)
    
    ui.run(
        host=ToolState.HOST,
        port=ToolState.PORT,
        title="Writer's Toolkit",
        reload=False,
        show_welcome_message=False,
    )



