#!/usr/bin/env python3
from file_folder_local_picker import local_file_picker

import os
from nicegui import ui, app
from nicegui.elements.codemirror import CodeMirror

HOST = "127.0.0.1"
PORT = 8080
FILENAME = None
FILE_CONTENT = None

def read_text_file(filename=None):
    try:
        if filename and os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                ui.notify('Read text file successfully!', type='positive')
                return file.read()
        else:
            if filename:
                return f"File not found: {filename}\n\nStart typing to create content!"
            else:
                return "No file selected\n\nStart typing to create content!"
    except Exception as e:
        return f"Error reading file: {str(e)}\n\nStart typing to create content!"

def save_text_file(content, filename=None):
    if not filename:
        ui.notify('No file selected. Please use "Open" to select a file or create a new one.', type='warning')
        return
        
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)
        ui.notify('Text file saved successfully!', type='positive')
    except Exception as e:
        ui.notify(f'Error saving text file: {str(e)}', type='negative')

async def pick_file() -> None:
    global darkness, FILENAME, FILE_CONTENT, editor
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
            
        ui.notify(f'You chose {FILENAME}')
        FILE_CONTENT = read_text_file(FILENAME)
        
        # Update the editor with the file content
        editor.set_value(FILE_CONTENT)
        
        # Update file info with the FULL path
        file_info.text = FILENAME if FILENAME else "No file selected"
    else:
        ui.notify('No file selected', type='warning')


@ui.page('/')
async def main():
    global darkness, editor, file_info
    
    # Add CSS for both dark and soft light themes before initializing dark mode
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
    
    # Add HTML for creating a dialog with actual Material Icons
    ui.add_head_html("""
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    """)
    
    # Initialize dark mode
    darkness = ui.dark_mode(True)
    
    def toggle_dark_mode(is_dark):
        darkness.set_value(is_dark)
    
    # Function to show help dialog with visual icons
    def show_help():
        # Create a dialog with HTML that includes the actual Material Icons
        with ui.dialog() as dialog, ui.card().classes('help-dialog'):
            ui.label('Help: text editor').classes('text-h6 text-center q-mb-md')
            
            ui.html("""
            <div style="padding: 8px; margin-bottom: 16px;">
                A simple editor for plain text (.txt) files only - no formatting.
                <br>
                Includes line numbers and automatic line wrapping for improved readability.
            </div>
            
            <div style="padding: 8px; margin-bottom: 4px;">
                Toolbar:
            </div>
            
            <div style="padding: 8px;">
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    1. &nbsp;&nbsp;
                    <i class="material-icons help-dialog-icon" style="margin-right: 12px;">light_mode</i>
                    <i class="material-icons help-dialog-icon" style="margin-right: 12px;">dark_mode</i>
                    <span>Toggle light/dark theme</span>
                </div>
                
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <span>2. &nbsp;&nbsp;<b>displays: No file selected or the <i>Actual file path</i></b></span>
                </div>
                
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    3. &nbsp;&nbsp;
                    <i class="material-icons help-dialog-icon" style="margin-right: 12px;">folder</i>
                    <span>Open a <b><i>.txt</i></b> file</span>
                </div>
                
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    4. &nbsp;&nbsp;
                    <i class="material-icons help-dialog-icon" style="margin-right: 12px;">save</i>
                    <span>Save changes</span>
                </div>
                
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    5. &nbsp;&nbsp;
                    <i class="material-icons help-dialog-icon" style="margin-right: 12px;">help</i>
                    <span>Show this help</span>
                </div>
                
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    6. &nbsp;&nbsp;
                    <i class="material-icons help-dialog-icon" style="margin-right: 12px;">exit_to_app</i>
                    <span>Quit the application</span>
                </div>
            </div>
            """)
            
            with ui.row().classes('justify-center q-mt-md'):
                ui.button('close', on_click=dialog.close).props('no-caps flat').classes('help-close-button')
        
        dialog.open()
        return dialog
    
    with ui.row().classes('w-full items-center justify-between mb-4'):
        # Left section with theme toggle and FULL file path (no more "Text Editor" label)
        with ui.element().classes('flex items-center gap-4'):
            # Theme toggle buttons
            with ui.element():
                dark_button = ui.button(icon='dark_mode', on_click=lambda: toggle_dark_mode(True)) \
                    .props('flat fab-mini').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
                light_button = ui.button(icon='light_mode', on_click=lambda: toggle_dark_mode(False)) \
                    .props('flat fab-mini').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
            
            # Full file path display (more prominent now)
            file_info = ui.label("No file selected").classes('text-subtitle1 text-weight-medium')
        
        # Group all buttons on the right side
        with ui.element().classes('flex gap-2'):
            ui.button(icon='folder', on_click=pick_file).props('flat fab-mini').tooltip('Open File')
            ui.button(icon='save', on_click=lambda: save_text_file(editor.value, FILENAME)).props('flat fab-mini').tooltip('Save File')
            ui.button(icon='help', on_click=show_help).props('flat fab-mini').tooltip('Help')
            ui.button(
                icon='exit_to_app',
                on_click=lambda: [ui.notify("Shutting down...", type="warning"), app.shutdown()]
            ).props('flat fab-mini').tooltip('Quit')
    
    with ui.column().classes('w-full h-full'):
        editor = ui.codemirror(
            value="No file selected. Use the folder icon to select a file.",
            language='textile',
            line_wrapping=True,
        ).classes('w-full h-full').props('autofocus')
        
        # Bind the editor theme to the dark mode state using the proper binding approach
        darkness.bind_value_to(
            target_object=editor,
            target_name='theme',
            forward=lambda is_dark: 'darcula' if is_dark else 'solarizedLight'
        )


if __name__ == "__main__":
    ui.run(
        host=HOST,
        port=PORT,
        title="Text Editor",
        reload=False,
        show=True
    )
