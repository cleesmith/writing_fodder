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
    DB_PATH = "writers_toolkit.json"
    db = None
    tools_table = None
    settings_table = None
    
    # Tool execution state
    IN_PROGRESS = None
    OPTION_VALUES = {}
    FULL_COMMAND = None
    TIMER_TASK = None
    
    @classmethod
    def initialize(cls):
        """Initialize the application state and create necessary directories/database."""
        # Ensure the projects directory exists
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
        
        # Initialize the database connection
        cls.db = TinyDB(cls.DB_PATH)
        cls.tools_table = cls.db.table('tools')
        cls.settings_table = cls.db.table('settings')
        
        return True
    
    @classmethod
    def update_tool_setup(cls, option_values):
        """Update the tool options values."""
        cls.OPTION_VALUES = option_values
    
    @classmethod
    def set_in_progress(cls, tool_name):
        """Set the currently running tool name."""
        cls.IN_PROGRESS = tool_name
        
    @classmethod
    def set_full_command(cls, command):
        """Set the full command string for the current tool."""
        cls.FULL_COMMAND = command
        
    @classmethod
    def set_timer_task(cls, task):
        """Set the async timer task reference."""
        cls.TIMER_TASK = task
    
    @classmethod
    def set_current_project(cls, project_name, project_path):
        """Set the current project name and path."""
        cls.CURRENT_PROJECT = project_name
        cls.CURRENT_PROJECT_PATH = project_path
        # Update the default save directory to the project path if available
        if project_path and os.path.exists(project_path):
            cls.DEFAULT_SAVE_DIR = project_path
    
    @classmethod
    def set_port(cls, port):
        """Set the server port."""
        cls.PORT = port
    
    @classmethod
    def reset(cls):
        """Reset all state variables to their default values."""
        cls.IN_PROGRESS = None
        cls.OPTION_VALUES = {}
        cls.FULL_COMMAND = None
        if cls.TIMER_TASK:
            try:
                cls.TIMER_TASK.cancel()
            except:
                pass
        cls.TIMER_TASK = None
