#!/usr/bin/env python3
"""
Text Editor Module for Writer's Toolkit
This version can be imported and integrated into writers_toolkit.py
"""
from file_folder_local_picker import local_file_picker
import os
import urllib.parse
from pathlib import Path
from nicegui import ui, app

# Global variables
FILENAME = None
FILE_CONTENT = None
darkness = None
editor = None
file_info = None

def add_static_files():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, 'static')
    app.add_static_files('/static', static_dir)

def read_text_file(filename=None):
    """Read a text file and return its contents"""
    try:
        if filename and os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            if filename:
                return f"File not found: {filename}\n\nStart typing to create content, or use the folder icon to select a .txt file."
            else:
                return "No file selected\n\nStart typing to create content, or use the folder icon to select a .txt file."
    except Exception as e:
        return f"Error reading file: {str(e)}\n\nStart typing to create content, or use the folder icon to select a .txt file."

def save_text_file(content, filename=None):
    """Save content to a text file"""
    if not filename:
        ui.notify('No file selected. Please use the folder icon to select a file or create a new one by typing.', type='warning')
        return
        
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)
        ui.notify('Text file saved successfully!', type='positive')
    except Exception as e:
        ui.notify(f'Error saving text file: {str(e)}', type='negative')

async def pick_file():
    """Open file picker dialog and load the selected file"""
    global FILENAME, FILE_CONTENT, editor, file_info
    result = await local_file_picker('.', multiple=False)
    
    if result:
        # Handle case where result is a list
        if isinstance(result, list):
            if len(result) > 0:
                FILENAME = result[0]  # Take the first item if it's a list
            else:
                ui.notify('No file selected', type='warning')
                return
        else:
            FILENAME = result
        
        # Convert to absolute path to ensure full path is displayed
        FILENAME = os.path.abspath(FILENAME)
            
        ui.notify(f'You chose {FILENAME}')
        FILE_CONTENT = read_text_file(FILENAME)
        
        # Update the editor with the file content
        editor.set_value(FILE_CONTENT)
        
        # Update file info with the FULL path
        file_info.text = FILENAME if FILENAME else "No file selected"
    else:
        ui.notify('No file selected', type='warning')

def show_help():
    """Show help dialog with visual icons"""
    with ui.dialog() as dialog, ui.card().classes('help-dialog'):
        ui.label('Help: Text Editor').classes('text-h6 text-center q-mb-md')
        
        ui.html("""
        <div style="padding: 8px; margin-bottom: 16px;">
            This is a browser-based simple editor for plain text (.txt) files only.
            <br>
            There is no formatting and no Markdown.
            <br>
            Includes line numbers and automatic line wrapping for improved readability.
            <br>
            It can be used without an internet connection; works offline.
        </div>
        
        <div style="padding: 8px; margin-bottom: 4px;">
            Toolbar:
        </div>
        
        <div style="padding: 8px;">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                1. &nbsp;&nbsp;
                <i class="fas fa-sun help-dialog-icon" style="margin-right: 12px;"></i>
                <i class="fas fa-moon help-dialog-icon" style="margin-right: 12px;"></i>
                <span>Toggle light/dark theme</span>
            </div>
            
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span>2. &nbsp;&nbsp;<i>displays:</i> <b>No file selected</b> or the <i>actual path to the file</i></b></span>
            </div>
            
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                3. &nbsp;&nbsp;
                <i class="fas fa-folder-open help-dialog-icon" style="margin-right: 12px;"></i>
                <span>Open a <b><i>.txt</i></b> file</span>
            </div>
            
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                4. &nbsp;&nbsp;
                <i class="fas fa-save help-dialog-icon" style="margin-right: 12px;"></i>
                <span>Save changes</span>
            </div>
            
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                5. &nbsp;&nbsp;
                <i class="fas fa-question-circle help-dialog-icon" style="margin-right: 12px;"></i>
                <span>Show this help</span>
            </div>

        </div>
        """)
        
        with ui.row().classes('justify-center').style('margin-top: -30px'):
            ui.button('Close', on_click=dialog.close).props('no-caps flat').classes('help-close-button')        

    dialog.open()
    return dialog

def toggle_dark_mode(is_dark):
    """Toggle between light and dark mode"""
    darkness.set_value(is_dark)

def add_editor_css():
    """Add CSS for both dark and soft light themes"""
    ui.add_head_html("""
    <style>
    /* SOFT LIGHT MODE THEME */
    body:not(.dark) {
        /* Soft beige background instead of stark white */
        background-color: #f2f0e6 !important;
        color: #333 !important;
    }
    
    /* Customize toolbar and button colors */
    body:not(.dark) .q-toolbar,
    body:not(.dark) .q-page,
    body:not(.dark) .q-footer,
    body:not(.dark) .q-header {
        background-color: #e8e6dc !important;
    }
    
    /* Soften buttons, cards, and input fields */
    body:not(.dark) .q-btn:not(.q-btn--flat),
    body:not(.dark) .q-card,
    body:not(.dark) .q-input__control,
    body:not(.dark) .q-field__control {
        background-color: #eae8de !important;
        color: #3a3a3a !important;
    }
    
    /* Softer borders for UI elements */
    body:not(.dark) .q-field__control,
    body:not(.dark) .q-card {
        border-color: #d8d6cc !important;
    }
    
    /* CodeMirror editor customization - soften everything */
    body:not(.dark) .cm-editor,
    body:not(.dark) .cm-scroller,
    body:not(.dark) .cm-content {
        background-color: #f5f3e9 !important;
        color: #333 !important;
    }
    
    body:not(.dark) .cm-gutters {
        background-color: #e8e6dc !important;
        color: #666 !important;
        border-right: 1px solid #d8d6cc !important;
    }
    
    body:not(.dark) .cm-cursor {
        border-left-color: #333 !important;
    }
    
    body:not(.dark) .cm-activeLine {
        background-color: #eceade !important;
    }
    
    body:not(.dark) .cm-activeLineGutter {
        background-color: #e0ded4 !important;
        color: #444 !important;
    }
    
    /* Set softer scrollbar colors */
    body:not(.dark) ::-webkit-scrollbar-track {
        background: #e8e6dc;
    }
    
    body:not(.dark) ::-webkit-scrollbar-thumb {
        background: #ccc8b8;
    }
    
    body:not(.dark) ::-webkit-scrollbar-thumb:hover {
        background: #b8b4a4;
    }

    /* Custom notification styling for help */
    .help-notification {
        min-width: 320px !important;
        max-width: 420px !important;
    }
    
    /* Custom help dialog styling */
    .help-dialog .q-card {
        max-width: 400px;
    }
    
    /* Proper spacing for help text */
    .help-dialog .q-card__section {
        padding: 16px;
    }
    
    /* Style the close button */
    .help-close-button {
        color: #2196F3 !important;
    }
    
    /* Style for help dialog icons - matching the blue color */
    .help-dialog-icon {
        color: #2196F3 !important;
    }
    </style>
    """)

    # include FontAwesome for icons
    ui.add_head_html("""
    <link rel="stylesheet" href="/static/fontawesome/css/all.min.css">
    """)

@ui.page('/editor')
async def editor_page(file: str = None):
    """Main text editor page at /editor path"""
    global darkness, editor, file_info, FILENAME, FILE_CONTENT

    add_static_files()
    
    # Add CSS for both dark and soft light themes
    add_editor_css()
    
    # Initialize dark mode
    darkness = ui.dark_mode(True)
    
    # Handle file parameter if present
    if file:
        try:
            file_path = urllib.parse.unquote(file)
            if os.path.exists(file_path):
                FILENAME = file_path
                FILE_CONTENT = read_text_file(FILENAME)
        except Exception as e:
            print(f"Error processing file parameter: {e}")
    
    with ui.row().classes('w-full items-center justify-between mb-4'):
        # Left section with theme toggle and FULL file path
        with ui.element().classes('flex items-center gap-4'):
            # Theme toggle buttons with FontAwesome icons
            with ui.element():
                dark_button = ui.button(icon='fas fa-moon', on_click=lambda: toggle_dark_mode(True)) \
                    .props('flat fab-mini').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
                light_button = ui.button(icon='fas fa-sun', on_click=lambda: toggle_dark_mode(False)) \
                    .props('flat fab-mini').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
            
            # Full file path display
            file_info = ui.label("No file selected").classes('text-subtitle1 text-weight-medium')
        
        # Group all buttons on the right side with FontAwesome icons
        with ui.element().classes('flex gap-2'):
            ui.button(icon='fas fa-folder-open', on_click=pick_file).props('flat fab-mini').tooltip('Open File')
            ui.button(icon='fas fa-save', on_click=lambda: save_text_file(editor.value, FILENAME)).props('flat fab-mini').tooltip('Save File')
            ui.button(icon='fas fa-question-circle', on_click=show_help).props('flat fab-mini').tooltip('Help')
    
    with ui.column().classes('w-full h-full'):
        default_content = "No file selected. Use the folder icon to select a file."
        if FILENAME and FILE_CONTENT:
            default_content = FILE_CONTENT
            
        editor = ui.codemirror(
            value=default_content,
            language='textile',
            line_wrapping=True,
        ).classes('w-full h-full').props('autofocus')
        
        # Bind the editor theme to the dark mode state using the proper binding approach
        darkness.bind_value_to(
            target_object=editor,
            target_name='theme',
            forward=lambda is_dark: 'darcula' if is_dark else 'solarizedLight'
        )
        
        # Update the file info if loaded via URL parameter
        if FILENAME:
            file_info.text = FILENAME
