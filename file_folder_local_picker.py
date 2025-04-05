import platform
import os
from pathlib import Path
from typing import Optional, List, Union

from nicegui import events, ui


class local_file_picker(ui.dialog):

    def __init__(self, directory: str, *,
                 upper_limit: Optional[str] = None, 
                 multiple: bool = False, 
                 show_hidden_files: bool = False, 
                 folders_only: bool = False) -> None:
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
        
        # Always force upper_limit to be ~/writing
        writing_dir = os.path.realpath(os.path.expanduser("~/writing"))
        
        # Always use the writing directory as the upper limit
        upper_limit = writing_dir
        
        # Use consistent path handling with realpath for security
        try:
            expanded_dir = os.path.realpath(os.path.abspath(os.path.expanduser(directory)))
            if not os.path.exists(expanded_dir):
                expanded_dir = writing_dir
        except Exception:
            expanded_dir = writing_dir
        
        # Force starting directory to be within writing directory
        if not os.path.samefile(expanded_dir, writing_dir) and not expanded_dir.startswith(writing_dir):
            # Reset to writing directory if outside of it
            expanded_dir = writing_dir
        
        # Store original parameters
        self.start_directory = Path(expanded_dir)
        self.upper_limit = Path(writing_dir)
        
        # Set current path to starting directory
        self.path = Path(expanded_dir)
        
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
            
            # Grid for displaying files and folders
            self.grid = ui.aggrid({
                'columnDefs': [{'field': 'name', 'headerName': 'File or Folder'}],
                'rowSelection': 'multiple' if multiple else 'single',
            }, html_columns=[0]).classes('w-full').on('cellDoubleClicked', self.handle_double_click)
            
            # Status message for feedback (only used for errors and important info)
            self.status_msg = ui.label("").classes('text-caption text-grey w-full my-1')
            
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
            # Don't allow drive changes if it would escape the writing directory
            new_drive_path = Path(self.drives_toggle.value)
            
            # Only allow drive change if it's within writing directory
            new_drive_real = os.path.realpath(str(new_drive_path))
            writing_real = os.path.realpath(str(self.upper_limit))
            
            if not new_drive_real.startswith(writing_real):
                self.status_msg.text = f"Cannot navigate outside projects directory"
                return
                
            self.path = new_drive_path
            self.update_grid()
        except Exception as e:
            self.status_msg.text = f"Error changing drive: {str(e)}"

    def navigate_to(self, new_path):
        """Navigate to a specific directory"""
        try:
            # Get the writing directory (our security boundary)
            writing_dir = os.path.realpath(os.path.expanduser("~/writing"))
            
            # Ensure the path exists and is a directory
            if not os.path.exists(new_path) or not os.path.isdir(new_path):
                self.status_msg.text = f"Invalid directory: {new_path}"
                return
                
            # Security checks
            try:
                # First check: Is new_path exactly the writing directory? (allowed)
                is_at_writing_dir = os.path.samefile(new_path, writing_dir)
                
                # Second check: Is new_path within writing directory?
                is_within_writing = os.path.realpath(new_path).startswith(writing_dir)
                
                # Decide whether to allow navigation
                if is_at_writing_dir:
                    # Allow navigation to the boundary itself
                    pass
                elif not is_within_writing:
                    self.status_msg.text = f"Cannot navigate outside projects directory"
                    return
            except Exception as e:
                # If path comparison fails, assume it's unsafe
                self.status_msg.text = f"Path validation error"
                return
            
            # If we get here, navigation is allowed
            self.path = Path(new_path)
            self.update_grid()
        except Exception as e:
            self.status_msg.text = f"Navigation error: {str(e)}"

    def navigate_up(self):
        """Navigate to parent directory"""
        # Get the writing directory (our security boundary)
        writing_dir = os.path.realpath(os.path.expanduser("~/writing"))
        parent = self.path.parent
        
        try:
            # Check if we're at the root directory
            if os.path.samefile(str(parent), str(self.path)):
                self.status_msg.text = "Already at root directory"
                return
            
            # Check if we're already at the writing directory
            if os.path.samefile(str(self.path), writing_dir):
                self.status_msg.text = "Already at projects root directory"
                return
                
            # Check if parent would be outside the writing directory
            if not os.path.realpath(str(parent)).startswith(writing_dir):
                self.status_msg.text = "Cannot navigate outside projects directory"
                return
                
            # Navigate to parent if allowed
            self.navigate_to(parent)
        except Exception as e:
            self.status_msg.text = f"Error navigating up: {str(e)}"

    def refresh(self):
        """Refresh the current directory listing"""
        try:
            self.update_grid()
        except Exception as e:
            self.status_msg.text = f"Error refreshing: {str(e)}"

    def update_grid(self) -> None:
        """Update the file/folder grid with current directory contents"""
        try:
            # Get the writing directory (our security boundary)
            writing_dir = os.path.realpath(os.path.expanduser("~/writing"))
            
            # Force reset if outside writing directory
            try:
                is_at_writing_dir = os.path.samefile(str(self.path), writing_dir)
                is_within_writing = os.path.realpath(str(self.path)).startswith(writing_dir)
                
                if not (is_at_writing_dir or is_within_writing):
                    self.path = Path(writing_dir)
                    self.status_msg.text = "Path has been reset to projects directory"
            except Exception:
                # If comparison fails, force reset to writing directory
                self.path = Path(writing_dir)
                self.status_msg.text = "Path has been reset due to error"
            
            # Update path display
            self.path_display.text = f"Current directory: {self.path}"
            
            # Check if at navigation limit
            at_writing_dir = False
            
            try:
                # Check if exactly at writing directory
                if os.path.samefile(str(self.path), writing_dir):
                    at_writing_dir = True
                
                # Check if parent would be outside writing directory
                parent_real = os.path.realpath(str(self.path.parent))
                
                if not parent_real.startswith(writing_dir):
                    at_writing_dir = True
            except Exception:
                # If comparison fails, assume we're at the limit for safety
                at_writing_dir = True
            
            # Get paths in current directory
            try:
                paths = list(self.path.glob('*'))
            except Exception as e:
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
            
            # Only add parent directory option if NOT at the writing directory
            if not at_writing_dir:
                parent_dir = {
                    'name': '📁 <strong>..</strong> (Parent Directory)',
                    'path': self.PARENT_NAV_ID,  # Special ID to identify parent navigation
                    'is_dir': True,
                }
                self.grid.options['rowData'].insert(0, parent_dir)
            
            # Update the grid
            self.grid.update()
            
            # Clear status message on successful updates
            if not self.status_msg.text or self.status_msg.text.startswith("Navigated to"):
                self.status_msg.text = ""
            
        except Exception as e:
            self.status_msg.text = f"Error updating grid: {str(e)}"

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        """Handle double click on grid items"""
        try:
            data = e.args['data']
            
            # Special case for parent directory navigation
            if data['path'] == self.PARENT_NAV_ID:
                # Get the writing directory (our security boundary)
                writing_dir = os.path.realpath(os.path.expanduser("~/writing"))
                
                # Get the parent path
                parent = self.path.parent
                
                # Security checks for parent directory navigation
                try:
                    # Check if at writing directory
                    if os.path.samefile(str(self.path), writing_dir):
                        self.status_msg.text = "Already at projects root directory"
                        return
                        
                    # Check if parent would be outside writing directory
                    parent_real = os.path.realpath(str(parent))
                    
                    if not parent_real.startswith(writing_dir):
                        self.status_msg.text = "Cannot navigate outside projects directory"
                        return
                except Exception:
                    # If comparison fails, block for safety
                    self.status_msg.text = "Path validation error"
                    return
                
                # If we passed all checks, navigate up
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
            
            # Final security check: ensure all selections are within writing directory
            writing_dir = os.path.realpath(os.path.expanduser("~/writing"))
            secure_paths = []
            
            for path in valid_paths:
                path_real = os.path.realpath(path)
                if path_real.startswith(writing_dir):
                    secure_paths.append(path)
            
            # Submit the results and explicitly close the dialog
            self.submit(secure_paths)
            
        except Exception as e:
            # Handle errors gracefully
            error_msg = f"Error processing selection: {str(e)}"
            self.status_msg.text = error_msg
            
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
    # Get absolute path to the writing directory (~/writing)
    writing_dir = os.path.realpath(os.path.abspath(os.path.expanduser("~/writing")))
    
    # Create the writing directory if it doesn't exist
    try:
        os.makedirs(writing_dir, exist_ok=True)
    except Exception as e:
        ui.notify(f"Error creating writing directory: {str(e)}", type="negative")
        return [] if multiple else None
    
    # Force start directory to be exactly the writing directory
    start_dir = writing_dir
    
    try:
        # Create the file picker
        picker = local_file_picker(
            directory=start_dir,
            upper_limit=writing_dir,
            multiple=multiple,
            folders_only=folders_only
        )
        
        # Wait for the file picker result
        result = await picker
        
        if not result:
            return [] if multiple else None
            
        # Final validation: ensure all results are within the writing directory
        valid_results = []
        for path in result:
            # Use realpath for reliable path comparison
            path_real = os.path.realpath(path)
            
            if path_real.startswith(writing_dir):
                valid_results.append(path)
            else:
                ui.notify(f"Invalid selection outside writing directory: {path}", type="negative")
        
        if not valid_results:
            ui.notify("No valid selections within writing directory", type="negative")
            return [] if multiple else None
            
        if not multiple:
            # Return first item for single selection mode
            return valid_results[0]
        return valid_results
    except Exception as e:
        ui.notify(f"Error in file selection: {str(e)}", type="negative")
        return [] if multiple else None
