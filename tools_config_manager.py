#!/usr/bin/env python3
"""
Tools Config Manager GUI - A simple NiceGUI interface to manage the tools_config.json file
"""

import json
import os
import traceback
from nicegui import ui, app, run

# Configuration
HOST = "127.0.0.1"
PORT = 8082
DEFAULT_CONFIG_FILENAME = "tools_config.json"
DEFAULT_CONFIG_DIR = "."  # Current directory
DEFAULT_SAVE_DIR = os.path.expanduser("~")

###############################################################################
# JSON Config Functions
###############################################################################

def get_config_path():
    """Get the full path to the tools_config.json file"""
    return os.path.join(DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_FILENAME)

def load_config(force_reload=False):
    """Load tool configurations from JSON file"""
    global DEFAULT_SAVE_DIR, DEFAULT_CONFIG_DIR
    
    config_path = get_config_path()
    if not os.path.exists(config_path):
        ui.notify(f"Error: Config file not found at {config_path}", type="negative")
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update default save directory if available in config
        if "_global_settings" in config:
            if "default_save_dir" in config["_global_settings"]:
                DEFAULT_SAVE_DIR = os.path.expanduser(config["_global_settings"]["default_save_dir"])
            
            # Update default config directory if available
            if "tools_config_json_dir" in config["_global_settings"]:
                DEFAULT_CONFIG_DIR = os.path.expanduser(config["_global_settings"]["tools_config_json_dir"])
        
        return config
    except Exception as e:
        ui.notify(f"Error loading JSON config: {str(e)}", type="negative")
        return {}

def save_config(config):
    """Save tool configurations to JSON file"""
    try:
        config_path = get_config_path()
        config_dir = os.path.dirname(config_path)
        
        # Create directory if it doesn't exist
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except Exception as e:
                ui.notify(f"Error creating directory {config_dir}: {str(e)}", type="negative")
                return False
        
        # Create a backup first
        if os.path.exists(config_path):
            backup_path = f"{config_path}.bak"
            try:
                with open(config_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
            except Exception as e:
                ui.notify(f"Warning: Failed to create backup file: {str(e)}", type="warning")
        
        # Save the configuration
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        ui.notify("Configuration saved successfully", type="positive")
        return True
    except Exception as e:
        ui.notify(f"Error saving configuration: {str(e)}", type="negative")
        return False

def update_global_settings(settings_dict):
    """Update global settings in the config file"""
    try:
        config = load_config(force_reload=True)
        
        if "_global_settings" not in config:
            config["_global_settings"] = {}
        
        config["_global_settings"].update(settings_dict)
        
        result = save_config(config)
        return result
    except Exception as e:
        ui.notify(f"Error updating global settings: {str(e)}", type="negative")
        return False

###############################################################################
# Tool Management Functions
###############################################################################

def create_tool(tool_name, title, description, help_text):
    """Create a new tool in the configuration"""
    config = load_config(force_reload=True)
    
    if tool_name in config:
        ui.notify(f"Tool '{tool_name}' already exists", type="negative")
        return False
    
    # Create new tool with empty options
    config[tool_name] = {
        "title": title,
        "description": description,
        "help_text": help_text,
        "options": []
    }
    
    # Save the updated configuration
    if save_config(config):
        ui.notify(f"Created tool: {tool_name}", type="positive")
        return True
    return False

def delete_tool(tool_name):
    """Delete a tool from the configuration"""
    config = load_config(force_reload=True)
    
    if tool_name not in config:
        ui.notify(f"Tool '{tool_name}' not found", type="negative")
        return False
    
    if tool_name == "_global_settings":
        ui.notify("Cannot delete global settings", type="negative")
        return False
    
    # Delete the tool
    del config[tool_name]
    
    # Save the updated configuration
    if save_config(config):
        ui.notify(f"Deleted tool: {tool_name}", type="positive")
        return True
    return False

def update_tool(tool_name, new_title, new_description, new_help_text):
    """Update an existing tool's basic information"""
    config = load_config(force_reload=True)
    
    if tool_name not in config:
        ui.notify(f"Tool '{tool_name}' not found", type="negative")
        return False
    
    # Update tool information
    config[tool_name]["title"] = new_title
    config[tool_name]["description"] = new_description
    config[tool_name]["help_text"] = new_help_text
    
    # Save the updated configuration
    if save_config(config):
        ui.notify(f"Updated tool: {tool_name}", type="positive")
        return True
    return False

###############################################################################
# Option Management Functions
###############################################################################

def add_option(tool_name, option_data):
    """Add a new option to a tool"""
    config = load_config(force_reload=True)
    
    if tool_name not in config:
        ui.notify(f"Tool '{tool_name}' not found", type="negative")
        return False
    
    # Initialize options array if it doesn't exist
    if "options" not in config[tool_name]:
        config[tool_name]["options"] = []
    
    # Check if option with the same name already exists
    for i, option in enumerate(config[tool_name]["options"]):
        if option.get("name") == option_data["name"]:
            # Update existing option
            config[tool_name]["options"][i] = option_data
            if save_config(config):
                ui.notify(f"Updated option '{option_data['name']}' in tool '{tool_name}'", type="positive")
            return True
    
    # Add new option
    config[tool_name]["options"].append(option_data)
    
    if save_config(config):
        ui.notify(f"Added option '{option_data['name']}' to tool '{tool_name}'", type="positive")
        return True
    return False

def edit_option(tool_name, option_name, option_data):
    """Edit an existing option in a tool"""
    config = load_config(force_reload=True)
    
    if tool_name not in config:
        ui.notify(f"Tool '{tool_name}' not found", type="negative")
        return False
    
    if "options" not in config[tool_name]:
        ui.notify(f"Tool '{tool_name}' has no options", type="negative")
        return False
    
    # Find and update the option
    for i, option in enumerate(config[tool_name]["options"]):
        if option.get("name") == option_name:
            # Keep the original name to preserve any references
            option_data["name"] = option_name
            
            # Update the option with new data
            config[tool_name]["options"][i] = option_data
            
            if save_config(config):
                ui.notify(f"Updated option '{option_name}' in tool '{tool_name}'", type="positive")
            return True
    
    ui.notify(f"Option '{option_name}' not found in tool '{tool_name}'", type="negative")
    return False

def delete_option(tool_name, option_name):
    """Delete an option from a tool"""
    config = load_config(force_reload=True)
    
    if tool_name not in config:
        ui.notify(f"Tool '{tool_name}' not found", type="negative")
        return False
    
    if "options" not in config[tool_name]:
        ui.notify(f"Tool '{tool_name}' has no options", type="negative")
        return False
    
    # Find and delete the option
    for i, option in enumerate(config[tool_name]["options"]):
        if option.get("name") == option_name:
            del config[tool_name]["options"][i]
            if save_config(config):
                ui.notify(f"Deleted option '{option_name}' from tool '{tool_name}'", type="positive")
            return True
    
    ui.notify(f"Option '{option_name}' not found in tool '{tool_name}'", type="negative")
    return False

###############################################################################
# UI Dialogs
###############################################################################

async def edit_tool_dialog(tool_name):
    """Dialog for editing an existing tool"""
    config = load_config(force_reload=True)
    
    if tool_name not in config:
        ui.notify(f"Tool '{tool_name}' not found", type="negative")
        return False
    
    tool_info = config[tool_name]
    
    result = ui.dialog().props('maximized')
    with result, ui.card().classes('w-full h-full p-4'):
        ui.label(f'Edit Tool: {tool_name}').classes('text-h6 mb-4')
        
        title = ui.input('Title', value=tool_info.get('title', '')).props('outlined').classes('w-full mb-2')
        # description = ui.input('Description', value=tool_info.get('description', '')).props('outlined').classes('w-full mb-2')
        description = ui.textarea('Description', value=tool_info.get('description', '')).props('outlined').classes('w-full mb-2')

        help_text = ui.textarea('Help Text', value=tool_info.get('help_text', '')).props('outlined').classes('w-full mb-4').style('min-height: 200px')
        
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: result.close()).props('flat')
            
            def submit_handler():
                data = {
                    'title': title.value,
                    'description': description.value,
                    'help_text': help_text.value
                }
                result.submit(data)
                
            ui.button('Save', on_click=submit_handler).props('color=primary')
    
    try:
        data = await result
        if data:
            if not data['title']:
                ui.notify('Title is required', type='negative')
                return False
            
            # Update the tool
            return update_tool(
                tool_name,
                data['title'],
                data['description'],
                data['help_text']
            )
        return False
    except Exception as e:
        ui.notify(f"Error updating tool: {str(e)}", type="negative")
        return False

async def create_tool_dialog():
    """Dialog for creating a new tool"""
    result = ui.dialog().props('maximized')
    with result, ui.card().classes('w-full h-full p-4'):
        ui.label('Create New Tool').classes('text-h6 mb-4')
        
        tool_name = ui.input('Tool Name (e.g., "tool_name.py")').props('outlined').classes('w-full mb-2')
        title = ui.input('Title').props('outlined').classes('w-full mb-2')
        # description = ui.input('Description').props('outlined').classes('w-full mb-2')
        description = ui.textarea('Description').props('outlined').classes('w-full mb-2')

        help_text = ui.textarea('Help Text').props('outlined').classes('w-full mb-4').style('min-height: 200px')
        
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: result.close()).props('flat')
            
            def submit_handler():
                data = {
                    'tool_name': tool_name.value,
                    'title': title.value,
                    'description': description.value,
                    'help_text': help_text.value
                }
                result.submit(data)
                
            ui.button('Create', on_click=submit_handler).props('color=primary')
    
    try:
        data = await result
        if data:
            if not data['tool_name'] or not data['title']:
                ui.notify('Tool name and title are required', type='negative')
                return False
            
            # Create the tool
            return create_tool(
                data['tool_name'],
                data['title'],
                data['description'],
                data['help_text']
            )
        return False
    except Exception as e:
        ui.notify(f"Error creating tool: {str(e)}", type="negative")
        return False

async def add_option_dialog(tool_name):
    """Dialog for adding a new option to a tool"""
    result = ui.dialog().props('maximized')
    with result, ui.card().classes('w-full h-full p-4'):
        ui.label(f'Add Option to {tool_name}').classes('text-h6 mb-4')
        
        option_name = ui.input('Option Name (e.g., "--option_name")').props('outlined').classes('w-full mb-2')
        arg_name = ui.input('Argument Name (e.g., "OPTION_NAME")').props('outlined').classes('w-full mb-2')
        # description = ui.input('Description').props('outlined').classes('w-full mb-2')
        description = ui.textarea('Description').props('outlined').classes('w-full mb-2')

        option_type = ui.select(
            label='Type',
            options=['str', 'int', 'bool', 'float'],
            value='str'
        ).props('outlined').classes('w-full mb-2')
        
        default_value = ui.input('Default Value').props('outlined').classes('w-full mb-2')
        required = ui.checkbox('Required')
        
        # Group dropdown instead of text input
        group = ui.select(
            label='Group',
            options=[
                'Input Files',
                'Claude API Configuration',
                'Output Configuration',
                'Content Configuration',
                'Operation Mode',
                'Analysis Options'
            ],
            value='Input Files'
        ).props('outlined').classes('w-full mb-4')
        
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: result.close()).props('flat')
            
            def submit_handler():
                # Prepare the option data
                option_type_val = option_type.value
                default_val = default_value.value
                
                # Convert default value based on type
                if default_val:
                    if option_type_val == 'int':
                        try:
                            default_val = int(default_val)
                        except ValueError:
                            default_val = None
                    elif option_type_val == 'float':
                        try:
                            default_val = float(default_val)
                        except ValueError:
                            default_val = None
                    elif option_type_val == 'bool':
                        default_val = default_val.lower() in ['true', 'yes', 'y', '1']
                else:
                    default_val = None
                
                data = {
                    'name': option_name.value,
                    'arg_name': arg_name.value,
                    'description': description.value,
                    'type': option_type_val,
                    'default': default_val,
                    'required': required.value,
                    'group': group.value
                }
                
                result.submit(data)
                
            ui.button('Add', on_click=submit_handler).props('color=primary')
    
    try:
        data = await result
        if data:
            if not data['name']:
                ui.notify('Option name is required', type='negative')
                return False
            
            # Add the option
            return add_option(tool_name, data)
        return False
    except Exception as e:
        ui.notify(f"Error adding option: {str(e)}", type="negative")
        return False

async def edit_option_dialog(tool_name, option_name):
    """Dialog for editing an existing option"""
    try:
        config = load_config(force_reload=True)
        
        if tool_name not in config or "options" not in config[tool_name]:
            ui.notify(f"Tool '{tool_name}' or its options not found", type="negative")
            return False
        
        # Find the option to edit
        option_data = None
        for option in config[tool_name]["options"]:
            if option.get("name") == option_name:
                option_data = option
                break
        
        if not option_data:
            ui.notify(f"Option '{option_name}' not found", type="negative")
            return False
        
        result = ui.dialog().props('maximized')
        with result, ui.card().classes('w-full h-full p-4'):
            ui.label(f'Edit Option: {option_name}').classes('text-h6 mb-4')
            
            # Pre-populate fields with existing values
            arg_name = ui.input('Argument Name', value=option_data.get('arg_name', '')).props('outlined').classes('w-full mb-2')
            # description = ui.input('Description', value=option_data.get('description', '')).props('outlined').classes('w-full mb-2')
            description = ui.textarea('Description', value=option_data.get('description', '')).props('outlined').classes('w-full mb-2')
            
            option_type_val = option_data.get('type', 'str')
            option_type = ui.select(
                label='Type',
                options=['str', 'int', 'bool', 'float'],
                value=option_type_val
            ).props('outlined').classes('w-full mb-2')
            
            # Convert default value to string for display
            default_val = option_data.get('default')
            default_str = str(default_val) if default_val is not None else ''
            
            default_value = ui.input('Default Value', value=default_str).props('outlined').classes('w-full mb-2')
            required = ui.checkbox('Required', value=option_data.get('required', False))
            
            # Group dropdown with current value pre-selected
            group_val = option_data.get('group', 'Input Files')
            group_options = [
                'Input Files',
                'Claude API Configuration',
                'Output Configuration',
                'Content Configuration',
                'Operation Mode',
                'Analysis Options'
            ]
            
            # If current group value isn't in standard options, add it
            if group_val and group_val not in group_options:
                group_options.append(group_val)
            
            group = ui.select(
                label='Group',
                options=group_options,
                value=group_val
            ).props('outlined').classes('w-full mb-4')
            
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: result.close()).props('flat')
                
                def submit_handler():
                    # Prepare the option data
                    option_type_val = option_type.value
                    default_val = default_value.value
                    
                    # Convert default value based on type
                    if default_val:
                        if option_type_val == 'int':
                            try:
                                default_val = int(default_val)
                            except ValueError:
                                default_val = None
                        elif option_type_val == 'float':
                            try:
                                default_val = float(default_val)
                            except ValueError:
                                default_val = None
                        elif option_type_val == 'bool':
                            default_val = default_val.lower() in ['true', 'yes', 'y', '1']
                    else:
                        default_val = None
                    
                    data = {
                        'name': option_name,  # Keep the original name
                        'arg_name': arg_name.value,
                        'description': description.value,
                        'type': option_type_val,
                        'default': default_val,
                        'required': required.value,
                        'group': group.value
                    }
                    
                    result.submit(data)
                    
                ui.button('Save', on_click=submit_handler).props('color=primary')
        
        result.open()
        
        data = await result
        if data:
            # Update the option
            return edit_option(tool_name, option_name, data)
        return False
    except Exception as e:
        error_info = traceback.format_exc()
        ui.notify(f"Error editing option: {str(e)}", type="negative", timeout=0)
        print(f"Error in edit_option_dialog: {error_info}")
        return False

async def confirm_delete_tool(tool_name):
    """Confirmation dialog for deleting a tool"""
    result = ui.dialog()
    with result, ui.card().classes('w-full p-4'):
        ui.label(f'Delete Tool: {tool_name}').classes('text-h6 mb-4')
        ui.label('Are you sure you want to delete this tool? This action cannot be undone.').classes('mb-4')
        
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: result.close()).props('flat')
            ui.button('Delete', on_click=lambda: result.submit(True)).props('color=negative')
    
    try:
        confirm = await result
        if confirm:
            return delete_tool(tool_name)
        return False
    except Exception:
        return False

async def confirm_delete_option(tool_name, option_name):
    """Confirmation dialog for deleting an option"""
    result = ui.dialog()
    with result, ui.card().classes('w-full p-4'):
        ui.label(f'Delete Option: {option_name}').classes('text-h6 mb-4')
        ui.label('Are you sure you want to delete this option? This action cannot be undone.').classes('mb-4')
        
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: result.close()).props('flat')
            ui.button('Delete', on_click=lambda: result.submit(True)).props('color=negative')
    
    try:
        confirm = await result
        if confirm:
            return delete_option(tool_name, option_name)
        return False
    except Exception:
        return False

async def view_edit_options_dialog(tool_name):
    """Dialog for viewing and editing options for a tool"""
    config = load_config(force_reload=True)
    if tool_name not in config:
        ui.notify(f"Tool {tool_name} not found", type="negative")
        return
    
    tool_options = config[tool_name].get("options", [])
    
    dialog = ui.dialog().props('maximized')
    with dialog, ui.card().classes('w-full h-full p-4'):
        ui.label(f'Options for {tool_name}').classes('text-h6 mb-4')
        
        # No options message
        if not tool_options:
            ui.label('No options found for this tool.').classes('text-italic')
        
        # Options list using grid layout
        else:
            # Header row with bold styling
            with ui.row().classes('w-full bg-blue-100 dark:bg-blue-900 p-2 font-bold'):
                ui.label('Name').classes('w-1/6')
                ui.label('Type').classes('w-1/12')
                ui.label('Description').classes('w-1/4')
                ui.label('Required').classes('w-1/12')
                ui.label('Default').classes('w-1/6')
                ui.label('Group').classes('w-1/8')
            
            # Create a row for each option
            for option in tool_options:
                with ui.row().classes('w-full border-b p-2 items-center'):
                    ui.label(option.get('name', '')).classes('w-1/6 overflow-hidden text-ellipsis')
                    ui.label(option.get('type', 'str')).classes('w-1/12')
                    # ui.label(option.get('description', '')).classes('w-1/4 overflow-hidden text-ellipsis')
                    ui.label(option.get('description', '')).classes('w-1/4 overflow-hidden text-ellipsis').style('white-space: pre-wrap')
                    ui.label('Yes' if option.get('required', False) else 'No').classes('w-1/12')
                    ui.label(str(option.get('default', 'None'))).classes('w-1/6 overflow-hidden text-ellipsis')
                    ui.label(option.get('group', '')).classes('w-1/8 overflow-hidden text-ellipsis')
                    
                    # Action buttons (edit and delete) with captured option name
                    with ui.element().classes('w-1/6 flex gap-2'):
                        current_option = option.get('name', '')
                        
                        # Edit button
                        ui.button(icon='edit', color='primary', on_click=lambda o=current_option: 
                            handle_edit_option(tool_name, o)).props('flat dense')
                        
                        # Delete button
                        ui.button(icon='delete', color='negative', on_click=lambda o=current_option: 
                            handle_delete_option(tool_name, o)).props('flat dense')
        
        # Add option button and close button
        with ui.row().classes('w-full justify-between mt-4'):
            ui.button('Add Option', on_click=lambda: handle_add_option(tool_name)).props('color=primary')
            ui.button('Close', on_click=dialog.close).props('flat')
    
    # Functions for button actions - defined inside to access dialog
    async def handle_add_option(tool):
        if await add_option_dialog(tool):
            # Refresh the options view
            dialog.close()
            await view_edit_options_dialog(tool)
    
    async def handle_edit_option(tool, option_name):
        # Open the edit dialog first - don't close main dialog yet
        result = await edit_option_dialog(tool, option_name)
        if result:
            # Only if successful, close and reopen to refresh
            dialog.close()
            await view_edit_options_dialog(tool)
    
    async def handle_delete_option(tool, option_name):
        if await confirm_delete_option(tool, option_name):
            # Refresh the options view
            dialog.close()
            await view_edit_options_dialog(tool)
    
    dialog.open()

async def settings_dialog():
    """Dialog for editing global settings"""
    global DEFAULT_CONFIG_DIR
    config = load_config(force_reload=True)
    global_settings = config.get("_global_settings", {})
    default_save_dir = global_settings.get("default_save_dir", DEFAULT_SAVE_DIR)
    config_dir = global_settings.get("tools_config_json_dir", DEFAULT_CONFIG_DIR)
    
    result = ui.dialog().props('maximized')
    with result, ui.card().classes('w-full h-full p-4'):
        ui.label('Global Settings').classes('text-h6 mb-4')
        
        # Settings fields
        save_dir = ui.input('Default Save Directory (for tool output files)', value=default_save_dir).props('outlined').classes('w-full mb-4')
        config_json_dir = ui.input('Tools Config JSON Directory (where tools_config.json is saved)', value=config_dir).props('outlined').classes('w-full mb-4')
        
        # Help text to explain the difference
        with ui.card().classes('w-full mb-4 p-2 bg-blue-100 dark:bg-blue-900'):
            ui.label('Settings Explanation').classes('font-bold')
            ui.label('• Default Save Directory: Where tool output files are saved (e.g., ~/writing/SomeBook)').classes('text-sm')
            ui.label('• Tools Config JSON Directory: Where the tools_config.json file itself is saved').classes('text-sm')
        
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: result.close()).props('flat')
            
            def submit_handler():
                data = {
                    'default_save_dir': save_dir.value,
                    'tools_config_json_dir': config_json_dir.value
                }
                result.submit(data)
                
            ui.button('Save', on_click=submit_handler).props('color=primary')
    
    try:
        data = await result
        if data:
            settings_to_update = {}
            
            if data.get('default_save_dir'):
                settings_to_update["default_save_dir"] = data['default_save_dir']
                
            if data.get('tools_config_json_dir'):
                settings_to_update["tools_config_json_dir"] = data['tools_config_json_dir']
                
            if settings_to_update:
                success = update_global_settings(settings_to_update)
                
                # If we updated the config directory, we need to reload the page
                # to ensure we're looking at the correct location
                if success and 'tools_config_json_dir' in settings_to_update:
                    DEFAULT_CONFIG_DIR = os.path.expanduser(data['tools_config_json_dir'])
                    ui.notify("Config directory updated. Refreshing page...", type="positive")
                    ui.navigate.to('/')
                
                return success
            
        return False
    except Exception as e:
        ui.notify(f"Error updating settings: {str(e)}", type="negative")
        return False

###############################################################################
# Main UI
###############################################################################

@ui.page('/')
def main():
    darkness = ui.dark_mode(True)
    
    # Define handler functions first before using them in the UI
    async def create_new_tool():
        if await create_tool_dialog():
            # Reload the page to show the new tool
            ui.notify("Tool created. Refreshing page...", type="positive")
            ui.navigate.to('/')
    
    async def edit_selected_tool(tool_name):
        if tool_name:
            if await edit_tool_dialog(tool_name):
                # Reload page to show updated info
                ui.notify("Tool updated. Refreshing page...", type="positive")
                ui.navigate.to('/')
    
    async def delete_selected_tool(tool_name):
        if tool_name:
            if await confirm_delete_tool(tool_name):
                # Reload page
                ui.notify("Tool deleted. Refreshing page...", type="positive")
                ui.navigate.to('/')
    
    async def view_edit_selected_options(tool_name):
        if tool_name:
            await view_edit_options_dialog(tool_name)
    
    with ui.column().classes('w-full max-w-6xl mx-auto p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between mb-4'):
            # Dark/Light mode toggle
            with ui.element():
                dark_button = ui.button(icon='dark_mode', on_click=lambda: darkness.set_value(True)) \
                    .props('flat fab-mini').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
                light_button = ui.button(icon='light_mode', on_click=lambda: darkness.set_value(False)) \
                    .props('flat fab-mini').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
            
            # Title
            ui.label("Tools Config Manager").classes('text-h4 text-center')
            
            # Settings and Quit buttons
            with ui.row().classes('gap-2'):
                ui.button("Settings", on_click=settings_dialog).props('no-caps flat').classes('text-green-600')
                # ui.button("Quit", on_click=lambda: app.shutdown()).props('flat').classes('text-red-600')
                ui.button(
                    "Quit",
                    on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                ).props('no-caps flat dense').classes('bg-red-600 text-white')
        
        # Config Path Display
        with ui.card().classes('w-full mb-2 p-2 bg-gray-100 dark:bg-gray-800'):
            ui.label(f'Config File: {get_config_path()}').classes('text-sm')
        
        # Main content
        with ui.card().classes('w-full mb-4 p-4'):
            ui.label('Manage Tools').classes('text-h6 mb-4')
            
            # Load tool configurations
            config = load_config()
            
            # Create tool options for dropdown
            tool_options = {}
            tool_descriptions = {}
            
            if config:
                for tool_name, tool_data in config.items():
                    if not tool_name.startswith('_'):  # Skip special sections
                        tool_options[tool_name] = tool_data.get("title", tool_name)
                        tool_descriptions[tool_name] = tool_data.get("description", "No description available")
            
            # Tool selection and description
            with ui.row().classes('w-full items-center'):
                selected_tool = ui.select(
                    options=tool_options,
                    label='Tool',
                    value=next(iter(tool_options), None) if tool_options else None
                ).classes('w-full')
                
                # Add new tool button
                ui.button(icon='add', on_click=create_new_tool) \
                    .props('color=positive').tooltip('Create New Tool')
                
                # The following buttons are only visible when a tool is selected
                ui.button(icon='edit', on_click=lambda: edit_selected_tool(selected_tool.value)) \
                    .props('color=primary').tooltip('Edit Tool') \
                    .bind_visibility_from(selected_tool, 'value', backward=lambda v: bool(v))
                
                ui.button(icon='delete', on_click=lambda: delete_selected_tool(selected_tool.value)) \
                    .props('color=negative').tooltip('Delete Tool') \
                    .bind_visibility_from(selected_tool, 'value', backward=lambda v: bool(v))
            
            # Tool description
            tool_description = ui.label(
                tool_descriptions.get(next(iter(tool_options), None), "") if tool_options else ""
            ).classes('text-caption text-grey-7 mt-2')
            
            # Update description when tool selection changes
            def update_description(e):
                selected = selected_tool.value
                if selected:
                    tool_description.set_text(tool_descriptions.get(selected, ""))
                else:
                    tool_description.set_text("")
            
            selected_tool.on('update:model-value', update_description)
            
            # Action buttons
            with ui.row().classes('w-full justify-center gap-4 mt-4'):
                # View/Edit Options button
                ui.button('Manage Options', icon='settings', on_click=lambda: view_edit_selected_options(selected_tool.value)) \
                    .props('no-caps color=primary') \
                    .bind_visibility_from(selected_tool, 'value', backward=lambda v: bool(v))
        
        # Status or help information
        # with ui.card().classes('w-full p-4'):
        #     ui.label('Quick Help').classes('text-h6 mb-2')
        #     ui.label('• Select a tool from the dropdown to work with it').classes('text-body1')
        #     ui.label('• Create new tools with the + button').classes('text-body1')
        #     ui.label('• Edit tool properties with the pencil button').classes('text-body1')
        #     ui.label('• Delete tools with the trash button').classes('text-body1')
        #     ui.label('• Click "Manage Options" to add, edit, or delete options for the selected tool').classes('text-body1')
        #     ui.label('• Change global settings using the "Settings" button in the header').classes('text-body1')

    # Check if config file exists
    config_path = get_config_path()
    config_dir = os.path.dirname(config_path)
    
    if not os.path.exists(config_path):
        with ui.dialog().props('persistent') as dialog:
            with ui.card():
                ui.label(f"Config file not found at {config_path}").classes('text-h6 text-negative')
                
                # If directory doesn't exist, show message about it
                if not os.path.exists(config_dir):
                    ui.label(f"Directory {config_dir} does not exist.").classes('mb-2')
                
                ui.label("Would you like to create a new empty configuration?").classes('mb-4')
                with ui.row().classes('justify-end'):
                    ui.button('No', on_click=lambda: [dialog.close(), app.shutdown()]).props('flat')
                    def create_new_config():
                        # Try to create directory if it doesn't exist
                        if not os.path.exists(config_dir):
                            try:
                                os.makedirs(config_dir, exist_ok=True)
                            except Exception as e:
                                ui.notify(f"Error creating directory {config_dir}: {str(e)}", type="negative")
                                return
                        
                        # Create initial config with both directory settings
                        initial_config = {
                            "_global_settings": {
                                "default_save_dir": DEFAULT_SAVE_DIR,
                                "tools_config_json_dir": DEFAULT_CONFIG_DIR
                            }
                        }
                        
                        # Save and close dialog
                        if save_config(initial_config):
                            dialog.close()
                            ui.notify("Configuration created. Refreshing page...", type="positive")
                            ui.navigate.to('/')
                    
                    ui.button('Yes', on_click=create_new_config).props('color=primary')
        dialog.open()

if __name__ == "__main__":
    ui.run(
        host=HOST,
        port=PORT,
        title="Tools Config Manager",
        reload=False,
        show=True
    )
