import os
from nicegui import ui, app
from nicegui.elements.codemirror import CodeMirror

# Configuration
HOST = "127.0.0.1"
PORT = 8080
DEFAULT_CONFIG_FILENAME = "manuscript.txt"

def read_manuscript():
    try:
        if os.path.exists(DEFAULT_CONFIG_FILENAME):
            with open(DEFAULT_CONFIG_FILENAME, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            return f"File not found: {DEFAULT_CONFIG_FILENAME}\n\nStart typing to create content!"
    except Exception as e:
        return f"Error reading file: {str(e)}\n\nStart typing to create content!"

def save_manuscript(content):
    try:
        with open(DEFAULT_CONFIG_FILENAME, 'w', encoding='utf-8') as file:
            file.write(content)
        ui.notify('Manuscript saved successfully!', type='positive')
    except Exception as e:
        ui.notify(f'Error saving file: {str(e)}', type='negative')

@ui.page('/')
def main():
    # Initialize dark mode state
    darkness = ui.dark_mode(True)
    
    # Function to update theme based on dark mode toggle
    def toggle_dark_mode(is_dark):
        darkness.set_value(is_dark)
        # Theme will update automatically due to binding
    
    with ui.row().classes('w-full items-center justify-between mb-4'):
        with ui.element():
            dark_button = ui.button(icon='dark_mode', on_click=lambda: toggle_dark_mode(True)) \
                .props('flat fab-mini').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
            light_button = ui.button(icon='light_mode', on_click=lambda: toggle_dark_mode(False)) \
                .props('flat fab-mini').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
        
        ui.label('Text Editor').classes('text-h4 font-bold')
        
        # Group all buttons on the right side
        with ui.element().classes('flex gap-2'):
            ui.button('Refresh', on_click=lambda: editor.set_value(read_manuscript())).props('no-caps flat dense')
            ui.button('Save', on_click=lambda: save_manuscript(editor.value)).props('no-caps flat dense')
            ui.button(
                "Quit",
                on_click=lambda: [ui.notify("Shutting down...", type="warning"), app.shutdown()]
            ).props('no-caps flat dense')
    
    with ui.column().classes('w-full h-full'):
        # Create the editor
        editor = ui.codemirror(
            value=read_manuscript(),
            language='textile',
        ).classes('w-full h-full')
        editor._props['lineWrapping'] = True
        
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
        title="Manuscript Editor",
        reload=False,
        show=True
    )
