import platform
import os
from pathlib import Path
from typing import Optional, List, Union

from nicegui import events, ui


class local_file_picker(ui.dialog):

    def __init__(self, directory: str, *,
                 upper_limit: Optional[str] = None, multiple: bool = False, 
                 show_hidden_files: bool = False, folders_only: bool = False) -> None:
        """Local File Picker
        This is a simple file picker that allows you to select a file or folder from the 
        local filesystem where NiceGUI is running.
        
        :param directory: The directory to start in.
        :param upper_limit: The directory to stop at (None: no limit, which is the default).
        :param multiple: Whether to allow multiple files to be selected.
        :param show_hidden_files: Whether to show hidden files.
        :param folders_only: Whether to only show folders (no files).
        """
        super().__init__()

        # Ensure directory exists and is expanded
        try:
            directory = os.path.expanduser(directory)
            if not os.path.exists(directory):
                directory = os.path.expanduser("~")
        except Exception:
            directory = os.path.expanduser("~")
        
        # Store original parameters
        self.start_directory = Path(directory)
        
        # No upper limit by default (free navigation)
        self.upper_limit = None if upper_limit is None else Path(upper_limit).expanduser()
        
        # Set current path to starting directory
        self.path = Path(directory)
        
        # Store other parameters
        self.show_hidden_files = show_hidden_files
        self.folders_only = folders_only
        self.multiple = multiple
        
        # Define a special constant for parent directory navigation
        self.PARENT_NAV_ID = "__PARENT_DIRECTORY__"

        # Set up the dialog UI
        with self, ui.card().classes('w-full'):
            # Dialog title changes based on mode
            dialog_title = 'Select folder' if folders_only else 'Select folder or .txt file'
            ui.label(dialog_title).classes('text-bold')
            
            # Add current path display
            self.path_display = ui.label(f"Current directory: {self.path}").classes('text-caption text-primary w-full')
            
            # Add drives toggle for Windows
            self.drives_toggle = None
            self.add_drives_toggle()
            
            # Add navigation buttons row
            with ui.row().classes('w-full justify-start gap-2'):
                self.up_button = ui.button('↑ UP', on_click=self.navigate_up).props('outline')
                ui.button('↻ REFRESH', on_click=self.refresh).props('outline')
                
                # Add home button for quick navigation
                ui.button('🏠 HOME', on_click=lambda: self.navigate_to(Path.home())).props('outline')

            # Grid for displaying files and folders
            self.grid = ui.aggrid({
                'columnDefs': [{'field': 'name', 'headerName': 'File or Folder'}],
                'rowSelection': 'multiple' if multiple else 'single',
            }, html_columns=[0]).classes('w-full').on('cellDoubleClicked', self.handle_double_click)
            
            # Status message for feedback
            self.status_msg = ui.label("Ready").classes('text-caption text-grey w-full my-1')
            
            # Button row
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=self.close).props('outline')
                ui.button('Ok', on_click=self.handle_ok).props('color=primary')
                
        # Initialize grid
        self.update_grid()

    def add_drives_toggle(self):
        """Add drive selection toggle for Windows systems"""
        if platform.system() == 'Windows':
            try:
                import win32api
                drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
                if drives:
                    self.drives_toggle = ui.toggle(drives, value=drives[0], on_change=self.update_drive)
            except Exception as e:
                self.status_msg.text = f"Could not get drives: {str(e)}"

    def update_drive(self):
        """Update the current path when drive is changed"""
        if not self.drives_toggle:
            return
            
        try:
            self.path = Path(self.drives_toggle.value)
            self.update_grid()
            self.status_msg.text = f"Switched to drive: {self.drives_toggle.value}"
        except Exception as e:
            self.status_msg.text = f"Error changing drive: {str(e)}"

    def navigate_to(self, new_path):
        """Navigate to a specific directory"""
        try:
            # Ensure the path exists and is a directory
            if not os.path.exists(new_path) or not os.path.isdir(new_path):
                self.status_msg.text = f"Invalid directory: {new_path}"
                return
                
            # Check if new path is above upper_limit (if set)
            if self.upper_limit is not None:
                # Check if new path is not within upper_limit
                if not str(new_path).startswith(str(self.upper_limit)):
                    self.status_msg.text = f"Cannot navigate above {self.upper_limit}"
                    return
            
            # Set the new path
            self.path = Path(new_path)
            self.update_grid()
            self.status_msg.text = f"Navigated to: {self.path}"
        except Exception as e:
            self.status_msg.text = f"Navigation error: {str(e)}"

    def navigate_up(self):
        """Navigate to parent directory"""
        try:
            # Get the parent path
            parent = self.path.parent
            
            # Check if we're at the root directory
            if str(parent) == str(self.path):
                self.status_msg.text = "Already at root directory"
                return
                
            # Navigate to parent
            self.navigate_to(parent)
        except Exception as e:
            self.status_msg.text = f"Error navigating up: {str(e)}"

    def refresh(self):
        """Refresh the current directory listing"""
        try:
            self.update_grid()
            self.status_msg.text = f"Refreshed: {self.path}"
        except Exception as e:
            self.status_msg.text = f"Error refreshing: {str(e)}"

    def update_grid(self) -> None:
        """Update the file/folder grid with current directory contents"""
        try:
            # Update path display
            self.path_display.text = f"Current directory: {self.path}"
            
            # Check if at navigation limit
            at_upper_limit = False
            if self.upper_limit is not None and str(self.path) == str(self.upper_limit):
                at_upper_limit = True
                
            # Update up button state
            at_root = str(self.path) == str(self.path.parent)
            self.up_button.props(f'outline {"disabled" if at_root or at_upper_limit else ""}')
            
            # Get paths in current directory
            try:
                paths = list(self.path.glob('*'))
            except Exception:
                paths = []
                self.status_msg.text = f"Error reading directory: {self.path}"
            
            # Filter hidden files if needed
            if not self.show_hidden_files:
                paths = [p for p in paths if not p.name.startswith('.')]
            
            # Apply filters based on mode
            if self.folders_only:
                # Only show directories
                paths = [p for p in paths if p.is_dir()]
            else:
                # Show directories and .txt files
                paths = [p for p in paths if p.is_dir() or p.name.endswith('.txt')]
            
            # Sort paths
            paths.sort(key=lambda p: p.name.lower())
            paths.sort(key=lambda p: not p.is_dir())

            # Create row data for the grid
            self.grid.options['rowData'] = [
                {
                    'name': f'📁 <strong>{p.name}</strong>' if p.is_dir() else p.name,
                    'path': str(p),
                    'is_dir': p.is_dir(),
                }
                for p in paths
            ]
            
            # Always add parent directory option at the top
            parent_dir = {
                'name': '📁 <strong>..</strong> (Parent Directory)',
                'path': self.PARENT_NAV_ID,  # Special ID to identify parent navigation
                'is_dir': True,
            }
            self.grid.options['rowData'].insert(0, parent_dir)
            
            # Update the grid
            self.grid.update()
            
            # Show limit message if applicable
            if at_upper_limit:
                self.status_msg.text = f"At navigation limit: {self.path}"
            
        except Exception as e:
            self.status_msg.text = f"Error updating grid: {str(e)}"

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        """Handle double click on grid items"""
        try:
            data = e.args['data']
            
            # Special case for parent directory navigation
            if data['path'] == self.PARENT_NAV_ID:
                self.navigate_up()
                return
                
            # Regular file or directory
            path_str = data['path']
            is_dir = data.get('is_dir', False)
            
            if is_dir:
                # Navigate into directory
                self.navigate_to(path_str)
            elif not self.folders_only and path_str.endswith('.txt'):
                # Submit text file on double-click (only in files+folders mode)
                self.status_msg.text = f"Selected: {path_str}"
                self.submit([path_str])
            else:
                # Ignore other files
                self.status_msg.text = f"Cannot select this item: {path_str}"
                
        except Exception as e:
            self.status_msg.text = f"Error handling selection: {str(e)}"

    async def handle_ok(self):
        try:
            # Get selected rows from grid
            rows = await self.grid.get_selected_rows()
            valid_paths = []
            
            # Process each selected row
            for r in rows:
                # Skip parent directory navigation item
                if r['path'] == self.PARENT_NAV_ID:
                    continue
                    
                path = r['path']
                is_dir = r.get('is_dir', False)
                
                # Filter based on mode (folders only or files+folders)
                if self.folders_only:
                    if is_dir:
                        valid_paths.append(path)
                else:
                    if is_dir or path.endswith('.txt'):
                        valid_paths.append(path)
            
            # Log what we're about to submit
            self.status_msg.text = f"Submitting selection: {valid_paths}"
            # ui.notify(f"Selection: {valid_paths}", timeout=2000)
            
            # Submit the results and explicitly close the dialog
            self.submit(valid_paths)
            
        except Exception as e:
            # Handle errors gracefully
            error_msg = f"Error processing selection: {str(e)}"
            self.status_msg.text = error_msg
            ui.notify(error_msg, type="negative", timeout=3000)
            
            # Submit empty list to avoid hanging
            self.submit([])


# Helper function to use the file picker
async def select_file_or_folder(start_dir=None, multiple=False, dialog_title="Select File or Folder", folders_only=False):
    """
    Opens a file picker dialog for selecting files or folders.
    
    Args:
        start_dir: Starting directory (defaults to DEFAULT_SAVE_DIR if None)
        multiple: Whether to allow multiple selections
        dialog_title: Title to display in the picker dialog
        folders_only: Whether to only show folders (no files)
        
    Returns:
        List of selected file/folder paths, or single path if multiple=False
    """
    if start_dir is None:
        start_dir = os.path.expanduser("~/writing")  # Default to ~/writing
    
    # Ensure the directory exists
    try:
        os.makedirs(os.path.expanduser(start_dir), exist_ok=True)
    except Exception:
        # If we can't create the directory, fall back to home
        start_dir = "~"
    
    try:
        result = await local_file_picker(
            start_dir, 
            upper_limit=None,  # No upper limit by default - free navigation
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