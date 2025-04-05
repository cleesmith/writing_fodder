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
    # Get the tool configuration to check for required parameters
    Tool = Query()
    tool = tools_table.get(Tool.name == script_name)
    options = tool.get('options', []) if tool else []

    # Get all required option names
    required_options = [opt['name'] for opt in options if opt.get('required', False)]
    print(f"\nrequired_options:\n{required_options}\n")
    
    # Create a mapping of option names to their types
    option_types = {opt['name']: opt.get('type', 'str') for opt in options}
    print(f"\noption_types:\n{option_types}\n")
    
    # Check if all required options are provided
    missing_required = [opt for opt in required_options if opt not in option_values]
    print(f"\nmissing_required:\n{missing_required}\n")
    if missing_required:
        ui.notify(f"Missing required options: {', '.join(missing_required)}", type="negative")
        # Add the missing required options with empty values to prompt user to fix
        for opt in missing_required:
            option_values[opt] = "outline_XXX.txt" #FIXME
    print(f"\noption_values:\n{option_values}\n")
    
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
                # Left side - Run button (primary action) and timer label
                with ui.row().classes('items-center gap-2'):
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
            ui.button('Tool Runner', on_click=lambda: start_runner_ui('tokens_words_counter.py', {}), icon='folder').props('no-caps')



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
