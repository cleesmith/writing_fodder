import subprocess
import os
import re
import json
import argparse
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
# FUNCTION: JSON Config handling
###############################################################################

def load_tools_config(json_path=TOOLS_JSON_PATH):
    """
    Load tool configurations from a JSON file.
    Assumes the file exists, and displays an error if it doesn't.
    
    Args:
        json_path: Path to the JSON config file
        
    Returns:
        Dictionary of tool configurations
    """
    if not os.path.exists(json_path):
        ui.notify(f"Error: Configuration file not found at {json_path}", type="negative")
        return {}
    
    try:
        with open(json_path, 'r') as f:
            tools_config = json.load(f)
        return tools_config
    except Exception as e:
        ui.notify(f"Error loading JSON config: {str(e)}", type="negative")
        return {}

def save_tools_config(tools_config, json_path=TOOLS_JSON_PATH):
    """
    Save tool configurations to a JSON file.
    
    Args:
        tools_config: Dictionary of tool configurations
        json_path: Path to the JSON config file
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        # Create a backup of the current file if it exists
        if os.path.exists(json_path):
            backup_path = f"{json_path}.bak"
            try:
                with open(json_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
            except Exception as e:
                ui.notify(f"Warning: Failed to create backup file: {str(e)}", type="warning")
        
        # Write the updated configuration
        with open(json_path, 'w') as f:
            json.dump(tools_config, f, indent=4)
        
        ui.notify(f"Configuration saved to {json_path}", type="positive")
        return True
    except Exception as e:
        ui.notify(f"Error saving configuration: {str(e)}", type="negative")
        return False

def get_user_preferences(script_name):
    """
    Get user preferences for a specific tool.
    
    Args:
        script_name: The script filename
        
    Returns:
        Dictionary of user preferences for the tool
    """
    tools_config = load_tools_config()
    if script_name not in tools_config:
        return {}
    
    # Get the user_preferences if it exists, or create an empty dict
    return tools_config[script_name].get("user_preferences", {})

def save_user_preferences(script_name, preferences):
    """
    Save user preferences for a specific tool.
    
    Args:
        script_name: The script filename
        preferences: Dictionary of user preferences
        
    Returns:
        Boolean indicating success or failure
    """
    tools_config = load_tools_config()
    if script_name not in tools_config:
        ui.notify(f"Cannot save preferences: Tool {script_name} not found in configuration", type="negative")
        return False
    
    # Create a deep copy to avoid modifying the original
    updated_config = deepcopy(tools_config)
    
    # Update the user_preferences
    updated_config[script_name]["user_preferences"] = preferences
    
    # Print to console for debugging
    print(f"Saving preferences for {script_name}: {preferences}")
    
    # Save the updated configuration
    return save_tools_config(updated_config)

###############################################################################
# FUNCTION: Argument Parsing and Script runner
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
# FUNCTION: JSON-based Help Retrieval
###############################################################################

async def get_tool_options_from_json(script_name, log_output=None):
    """
    Get options for a script from the JSON configuration.
    
    Args:
        script_name: The script filename
        log_output: Optional log component to display information
        
    Returns:
        List of option dictionaries with name, arg_name, description, required, default
    """
    # Load the tool configurations
    tools_config = load_tools_config()
    
    if script_name not in tools_config:
        if log_output:
            log_output.push(f"Error: Configuration for {script_name} not found in JSON config")
        ui.notify(f"Configuration for {script_name} not found", type="negative")
        return []
    
    tool_config = tools_config[script_name]
    
    # Display the help information in the log if provided
    if log_output:
        log_output.push("Tool information from JSON config:")
        log_output.push(f"Name: {tool_config['name']}")
        log_output.push(f"Description: {tool_config['description']}")
        log_output.push(f"Help text: {tool_config['help_text']}")
        log_output.push(f"Options: {len(tool_config['options'])} found")
        
        # Check if user preferences exist
        if "user_preferences" in tool_config:
            log_output.push(f"User preferences found: {len(tool_config['user_preferences'])} settings")
        
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
    # Load user preferences if they exist
    user_preferences = get_user_preferences(script_name)
    print(f"Loaded preferences for {script_name}: {user_preferences}")
    
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
                        
                        # Check if we have a saved preference for this option
                        saved_value = user_preferences.get(name) if user_preferences else None
                        
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
                            
                            is_number = any(keyword in arg_name.lower() for keyword in ["num", "count", "threshold", "level", "tokens", "window", "timeout"])
                            
                            is_boolean = not arg_name or arg_name.lower() in ["flag", "enable", "disable"]
                            
                            # Create appropriate input fields based on the option type
                            if is_boolean:
                                # Boolean options (checkboxes)
                                # Use saved value if available
                                checkbox = ui.checkbox("Enable this option", value=saved_value if isinstance(saved_value, bool) else False)
                                input_elements[name] = checkbox
                            elif is_file:
                                # File/directory paths
                                with ui.row().classes('w-full items-center'):
                                    # Use saved value if available
                                    input_field = ui.input(
                                        placeholder="Enter path...",
                                        value=saved_value if saved_value else None
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
                                    
                                    ui.button("Default", icon='folder').props('flat dense').on('click', 
                                        lambda i=input_field, p=default_path: i.set_value(p))
                            elif is_number:
                                # Get default value from the option configuration if available
                                default_value = option.get('default')
                                
                                # If no default in config, try to extract from description
                                if default_value is None and not saved_value:
                                    # Match numbers with or without commas: 1000, 1,000, etc.
                                    default_match = re.search(r'default:\s*([\d,]+)', description)
                                    if default_match:
                                        # Remove commas and convert to int
                                        default_str = default_match.group(1).replace(',', '')
                                        try:
                                            default_value = int(default_str)
                                        except ValueError:
                                            default_value = None
                                
                                # Use saved value if available, otherwise use default
                                display_value = saved_value if saved_value is not None else default_value
                                input_field = ui.number(placeholder="Enter number...", value=display_value)
                                input_elements[name] = input_field
                            else:
                                # Default to text input with saved value if available
                                input_field = ui.input(
                                    placeholder="Enter value...",
                                    value=saved_value if saved_value else None
                                )
                                input_elements[name] = input_field
            
            # Add save preferences checkbox
            save_preferences_checkbox = ui.checkbox("Save these preferences for next time", value=True)
            
            # Button row
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=lambda: [dialog.close(), result_future.set_result((None, False))]) \
                   .props('flat').classes('text-grey')
                
                def on_submit():
                    # Collect values from input elements
                    option_values = {}
                    for name, input_element in input_elements.items():
                        # For numbered inputs, use value only if it's different from the default
                        # For other inputs, include if they have a value
                        if hasattr(input_element, 'value'):
                            # Find the original option to check if this is using a default value
                            original_option = next((opt for opt in options if opt['name'] == name), None)
                            default_value = original_option.get('default') if original_option else None
                            
                            # Always include the value if it exists
                            if input_element.value is not None:
                                # Special handling for empty strings
                                is_empty_string = isinstance(input_element.value, str) and input_element.value.strip() == ""
                                is_required = original_option and original_option.get('required', False)
                                
                                if is_required or not is_empty_string:
                                    # Include required params or non-empty values
                                    option_values[name] = input_element.value
                    
                    # Get the save preferences checkbox value
                    should_save = save_preferences_checkbox.value
                    
                    # Resolve the future with the option values and save flag
                    result_future.set_result((option_values, should_save))
                    dialog.close()
                
                ui.button('Apply', on_click=on_submit).props('color=primary').classes('text-white')
    
    # Show the dialog and wait for it to be resolved
    dialog.open()
    return await result_future

def build_command_string(script_name, option_values):
    """
    Build a command-line argument string from option values using argparse.
    
    Args:
        script_name: The script filename
        option_values: Dictionary mapping option names to their values
        
    Returns:
        Tuple of (full command string, args_list) for display and execution
    """
    # Load the tool configurations to check for required parameters
    tools_config = load_tools_config()
    tool_config = tools_config.get(script_name, {})
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
    
    for name, value in option_values.items():
        if value is not None:
            if isinstance(value, bool):
                if value:
                    # Just add the flag for boolean options
                    args_list.append(name)
            else:
                # Skip empty strings except for required parameters
                is_required = name in required_options
                is_empty_string = isinstance(value, str) and value.strip() == ""
                
                if not is_empty_string or is_required:
                    # For required params with empty strings, notify user
                    if is_required and is_empty_string:
                        ui.notify(f"Required parameter {name} is empty", type="warning")
                    
                    # For non-empty values, add the option and its value
                    if not is_empty_string:  
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

async def show_command_preview(script_name, option_values, should_save_preferences):
    """
    Show a dialog with the preview of the command to be executed.
    
    Args:
        script_name: The script filename
        option_values: Dictionary mapping option names to their values
        should_save_preferences: Boolean indicating if preferences should be saved
        
    Returns:
        Tuple of (should_run, args_dict, should_save) indicating whether to run the command,
        the arguments dictionary to use, and whether to save preferences
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
        
        # Show save preferences status
        if should_save_preferences:
            ui.label('These preferences will be saved for future use.').classes('text-positive text-caption mt-3')
        
        # Explanation text
        ui.label('Review the command above before running it. You can edit the options or proceed with execution.').classes('text-caption mt-3 mb-3')
        
        # Button row
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancel', on_click=lambda: [preview_dialog.close(), result_future.set_result((False, option_values, should_save_preferences))]) \
                .props('flat').classes('text-grey')
            
            ui.button('Edit Options', on_click=lambda: [preview_dialog.close(), result_future.set_result((None, option_values, should_save_preferences))]) \
                .props('flat').classes('text-blue')
            
            ui.button('Run', on_click=lambda: [preview_dialog.close(), result_future.set_result((True, option_values, should_save_preferences))]) \
                .props('color=primary').classes('text-white')
    
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
            ui.notify(f"Created backup at {backup_path}", type="positive")
            return True
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
        ui.notify(f"No backup file found at {backup_path}", type="negative")
        return False
    
    try:
        with open(backup_path, 'r') as src, open(TOOLS_JSON_PATH, 'w') as dst:
            dst.write(src.read())
        ui.notify(f"Configuration restored from {backup_path}", type="positive")
        return True
    except Exception as e:
        ui.notify(f"Error restoring from backup: {str(e)}", type="negative")
        return False

###############################################################################
# Main UI and Workflow
###############################################################################

def main():
    """Main function to set up the UI."""
    # Check if configuration file exists
    check_config_file()
    
    # Add a dark mode toggle
    dark_mode = ui.dark_mode()
    dark_mode.enable()
    
    # Create the UI elements
    with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
        ui.label('Writer\'s Toolkit').classes('text-h4 text-center mb-4')
        
        # Combined main card for tool selection and action buttons
        with ui.card().classes('w-full mb-4 p-4'):
            ui.label('Select a tool to run:').classes('text-h6')
            
            # Load tool options from JSON file
            tools_config = load_tools_config()
            tool_options = []
            
            if tools_config:
                # Extract tool names and descriptions
                for tool_name, tool_data in tools_config.items():
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
            
            # Action buttons row - no status message
            with ui.row().classes('w-full justify-center gap-4 mt-3'):
                async def configure_and_run_tool():
                    script_name = selected_tool.value
                    if not script_name:
                        ui.notify('Please select a tool first', type='warning')
                        return
                    
                    # Use notifications for important status updates instead of labels
                    ui.notify(f"Loading options for {script_name}...", type="info", timeout=2000)
                    
                    # Create a log dialog for displaying JSON information
                    json_dialog = ui.dialog().props('maximized')
                    
                    with json_dialog, ui.card().classes('w-full'):
                        with ui.column().classes('w-full p-4'):
                            ui.label(f'Loading options for {script_name} from JSON').classes('text-h6')
                            json_log = ui.log().classes('w-full') \
                                .style('height: 300px; background-color: #0f1222; color: #b2f2bb; font-family: monospace; padding: 1rem; border-radius: 4px;')
                            ui.button('Close', on_click=json_dialog.close).classes('self-end')
                    
                    json_dialog.open()
                    
                    # Get options from JSON
                    options = await get_tool_options_from_json(script_name, json_log)
                    
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
                            
                        option_values, should_save_preferences = result
                        
                        # Show command preview
                        should_run, option_values, should_save_preferences = await show_command_preview(
                            script_name, option_values, should_save_preferences)
                        
                        if should_run is None:
                            # User wants to edit options
                            continue
                        elif should_run:
                            # Save preferences if requested
                            if should_save_preferences:
                                print(f"Preferences to save: {option_values}")
                                if save_user_preferences(script_name, option_values):
                                    ui.notify(f"Preferences saved for {script_name}", type="positive")
                                else:
                                    ui.notify(f"Failed to save preferences for {script_name}", type="warning")
                            
                            # User confirmed, run the tool
                            # Don't update any static status label, just use notifications
                            ui.notify(f"Running {script_name}...", type="info")
                            await run_tool_ui(script_name, option_values)
                            ui.notify(f"Finished running {script_name}", type="positive")
                            break
                        else:
                            # User cancelled - don't show any status message
                            break
                
                ui.button('Set Args/Options', on_click=configure_and_run_tool) \
                    .props('no-caps').classes('bg-green-600 text-white')
                
                ui.button('Quit', on_click=lambda: app.shutdown()) \
                    .props('no-caps').classes('bg-red-600 text-white')
        
        # Configuration section (as a separate card)
        with ui.card().classes('w-full mb-4 p-4'):
            ui.label('Configuration').classes('text-h6 mb-2')
            
            with ui.row().classes('w-full items-center'):
                json_path_input = ui.input(
                    label='Config Path',
                    value=TOOLS_JSON_PATH
                ).classes('w-full')
                
                def reload_config():
                    global TOOLS_JSON_PATH
                    TOOLS_JSON_PATH = json_path_input.value
                    check_config_file()
                    # Force reload the page to refresh the tool selection
                    ui.run_javascript('window.location.reload()')
                
                ui.button('RELOAD', icon='refresh').props('flat').on('click', reload_config)
            
            # Add backup and restore buttons
            with ui.row().classes('w-full justify-end gap-2 mt-3'):
                ui.button('BACKUP CONFIG', icon='save').props('outline').on('click', backup_config_file)
                ui.button('RESTORE FROM BACKUP', icon='settings_backup_restore').props('outline').on('click', restore_config_from_backup)

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
