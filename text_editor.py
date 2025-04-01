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
        
        # Update file info with just the filename
        file_info.text = f"{os.path.basename(FILENAME)}"
    else:
        ui.notify('No file selected', type='warning')


@ui.page('/')
async def main():
    global darkness, editor, file_info
    darkness = ui.dark_mode(True)
    
    def toggle_dark_mode(is_dark):
        darkness.set_value(is_dark)
        # Theme will update automatically due to binding
    
    with ui.row().classes('w-full items-center justify-between mb-4'):
        # Left section with theme toggle and title
        with ui.element().classes('flex items-center gap-4'):
            # Theme toggle buttons
            with ui.element():
                dark_button = ui.button(icon='dark_mode', on_click=lambda: toggle_dark_mode(True)) \
                    .props('flat fab-mini').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
                light_button = ui.button(icon='light_mode', on_click=lambda: toggle_dark_mode(False)) \
                    .props('flat fab-mini').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
            
            # Title and file info with path info button
            with ui.element().classes('flex items-baseline'):
                ui.label('Text Editor').classes('text-h4 font-bold')
                file_info = ui.label("No file selected").classes('text-caption text-grey pl-2')
                
                # Info icon that shows full path when clicked
                def show_full_path():
                    if FILENAME:
                        ui.notify(f"Full path: {FILENAME}", type='info', timeout=5000)
                    else:
                        ui.notify("No file currently selected", type='warning')
                        
                info_button = ui.button(icon='info', on_click=show_full_path).props('flat round dense size="xs"').classes('ml-1')
                info_button.tooltip('Show full file path')
        
        # Group all buttons on the right side
        with ui.element().classes('flex gap-2'):
            ui.button('Open', on_click=pick_file, icon='folder').props('no-caps flat dense')
            ui.button('Reload', on_click=lambda: editor.set_value(read_text_file(FILENAME))).props('no-caps flat dense')
            ui.button('Save', on_click=lambda: save_text_file(editor.value, FILENAME)).props('no-caps flat dense')
            ui.button(
                "Quit",
                on_click=lambda: [ui.notify("Shutting down...", type="warning"), app.shutdown()]
            ).props('no-caps flat dense')
    
    with ui.column().classes('w-full h-full'):
        # create the text editor
        editor = ui.codemirror(
            value="No file selected. Use the 'Open' button to select a file.",
            language='textile',
            line_wrapping=True,
            # highlight_whitespace=True
        ).classes('w-full h-full').props('autofocus')
        # editor._props['lineWrapping'] = True
        
        # Bind the editor theme to the dark mode state
        darkness.bind_value_to(
            target_object=editor,
            target_name='theme',
            forward=lambda is_dark: 'consoleDark' if is_dark else 'consoleLight'
        )


if __name__ == "__main__":
    ui.run(
        host=HOST,
        port=PORT,
        title="Text Editor",
        reload=False,
        show=True
    )
