#!/usr/bin/env python3
"""
ToolState - A class to manage the global state for the Writing Tools application.
This replaces global variables to prevent issues with async/await boundaries.
"""
import os
from tinydb import TinyDB, Query, where

class ToolState:
    """
    A class that maintains the global state for the application.
    Uses class variables instead of global variables to ensure 
    consistent state across asynchronous function boundaries.
    """
    # Network settings
    HOST = "127.0.0.1"
    PORT = 8000
    
    # File system paths
    PROJECTS_DIR = os.path.expanduser("~/writing")
    DEFAULT_SAVE_DIR = PROJECTS_DIR
    
    # Project tracking
    CURRENT_PROJECT = None
    CURRENT_PROJECT_PATH = None
    
    # Database configuration
    DB_PATH = "writers_toolkit_tinydb.json"
    db = None
    tools_table = None
    settings_table = None
    
    # Tool selection and execution state
    SELECTED_TOOL = None     # Name of the currently selected tool (e.g., "brainstorm.py")
    IS_RUNNING = False       # Flag indicating whether a tool is currently executing
    OPTION_VALUES = {}       # Dictionary of tool option values
    FULL_COMMAND = None      # Complete command string for display/execution
    TIMER_TASK = None        # Reference to timer update task
    
    @classmethod
    def initialize(cls):
        """Initialize the application state and create necessary directories/database."""
        # Ensure the projects directory exists
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)

        # Initialize the database connection
        cls.db = TinyDB(cls.DB_PATH)
        cls.tools_table = cls.db.table('tools')
        cls.settings_table = cls.db.table('settings')

        # Load claude_api_configuration from settings (if available)
        settings = cls.settings_table.get(doc_id=1) if cls.settings_table.contains(doc_id=1) else {}
        cls.settings_claude_api_configuration = settings.get('claude_api_configuration', {})

        # Reset any stale state
        cls.reset()

        return True

    @classmethod
    def initialize_claude_api_defaults(cls):
        """Initialize default Claude API settings if they don't exist."""
        # Default values for Claude API configuration
        default_config = {
            "max_retries": 1,
            "request_timeout": 300,
            "context_window": 200000,
            "thinking_budget_tokens": 32000,
            "betas_max_tokens": 128000,
            "desired_output_tokens": 12000
        }
        
        # Only initialize if the settings don't exist or are empty
        if not cls.settings_claude_api_configuration:
            cls.settings_claude_api_configuration = default_config
            
            # Save to database if needed
            settings = cls.settings_table.get(doc_id=1) if cls.settings_table.contains(doc_id=1) else {}
            settings['claude_api_configuration'] = default_config
            cls.save_global_settings(settings)
            
        return cls.settings_claude_api_configuration
    
    @classmethod
    def update_tool_setup(cls, option_values):
        """
        Update the tool options values.
        
        Args:
            option_values: Dictionary mapping option names to their values
        """
        cls.OPTION_VALUES = option_values
    
    @classmethod
    def select_tool(cls, tool_name):
        """
        Set the currently selected tool.
        
        Args:
            tool_name: Name of the tool to select (e.g., "brainstorm.py")
        """
        cls.SELECTED_TOOL = tool_name
        
    @classmethod
    def start_tool_execution(cls):
        """
        Mark the selected tool as currently running.
        
        Returns:
            Boolean indicating whether execution could be started
        """
        if cls.IS_RUNNING:
            return False
        
        if not cls.SELECTED_TOOL:
            return False
            
        cls.IS_RUNNING = True
        return True
        
    @classmethod
    def stop_tool_execution(cls):
        """
        Mark the tool execution as completed.
        Also cancels any running timer task.
        """
        cls.IS_RUNNING = False
        
        # Cancel any running timer
        if cls.TIMER_TASK:
            try:
                cls.TIMER_TASK.cancel()
            except:
                pass
            cls.TIMER_TASK = None
    
    @classmethod
    def set_full_command(cls, command):
        """
        Set the full command string for the current tool.
        
        Args:
            command: Complete command string for display/execution
        """
        cls.FULL_COMMAND = command
        
    @classmethod
    def set_timer_task(cls, task):
        """
        Set the async timer task reference.
        
        Args:
            task: Asyncio task for updating timer display
        """
        cls.TIMER_TASK = task
    
    @classmethod
    def set_current_project(cls, project_name, project_path):
        """
        Set the current project name and path.
        
        Args:
            project_name: Name of the current project
            project_path: File system path to the project
        """
        cls.CURRENT_PROJECT = project_name
        cls.CURRENT_PROJECT_PATH = project_path
        # Update the default save directory to the project path if available
        if project_path and os.path.exists(project_path):
            cls.DEFAULT_SAVE_DIR = project_path
    
    @classmethod
    def set_port(cls, port):
        """
        Set the server port.
        
        Args:
            port: Port number for the server to listen on
        """
        cls.PORT = port
    
    @classmethod
    def reset(cls):
        """Reset all state variables to their default values."""
        cls.SELECTED_TOOL = None
        cls.IS_RUNNING = False
        cls.OPTION_VALUES = {}
        cls.FULL_COMMAND = None
        
        # Cancel any running timer task
        if cls.TIMER_TASK:
            try:
                cls.TIMER_TASK.cancel()
            except:
                pass
        cls.TIMER_TASK = None
    
    @classmethod
    def get_in_progress(cls):
        """
        Get the currently selected tool name. (Legacy method)
        
        Returns:
            Name of the currently selected tool, or None if no tool is selected
        """
        return cls.SELECTED_TOOL

    @classmethod
    def get_tool_options(cls):
        """
        Retrieve tool options from the TinyDB tools_table.

        Returns:
            list: A list of dictionaries, each containing 'name', 'title', and 'description'
                  for each tool that does not have a name starting with an underscore.
        """
        # Ensure that the tools table is initialized
        if cls.tools_table is None:
            return []

        tool_options = []
        # Retrieve all records from the tools table
        for tool in cls.tools_table.all():
            tool_name = tool.get("name")
            if tool_name and not tool_name.startswith('_'):
                tool_options.append({
                    "name": tool_name,
                    "title": tool.get("title", tool_name),
                    "description": tool.get("description", "No description available")
                })
        return tool_options

    @classmethod
    def save_global_settings(cls, settings):
        """
        Save global settings to the TinyDB settings table.
        
        Args:
            settings: Dictionary of settings to save
                
        Returns:
            Boolean indicating success or failure
        """
        try:
            # Make sure the settings table exists
            if not cls.settings_table:
                print("Warning: settings_table not initialized")
                return False
                    
            # Update or insert settings
            if cls.settings_table.contains(doc_id=1):
                # If the document exists, update it
                cls.settings_table.update(settings, doc_ids=[1])
            else:
                # If document doesn't exist, insert it without specifying doc_id
                # TinyDB doesn't accept doc_id as a parameter for insert()
                cls.settings_table.insert(settings)
                    
            return True
        except Exception as e:
            print(f"Error saving settings: {str(e)}")
            return False
