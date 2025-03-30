#!/usr/bin/env python3
from file_folder_local_picker import local_file_picker

from nicegui import ui, app


# Set dark mode as a global variable so it's accessible to all components
darkness = None

# Create a CSS style to force dark mode on dialogs
dark_mode_style = """
.dark-mode .q-dialog,
.dark-mode .q-card,
.dark-mode .q-table,
.dark-mode .ag-theme-alpine {
    color: white !important;
    background-color: #121212 !important;
}

.dark-mode .q-field__native,
.dark-mode .q-field__prefix,
.dark-mode .q-field__suffix,
.dark-mode .q-field__input {
    color: white !important;
}

.dark-mode .ag-header,
.dark-mode .ag-header-cell,
.dark-mode .ag-cell {
    color: white !important;
    background-color: #1e1e1e !important;
}

.dark-mode .ag-row-even {
    background-color: #262626 !important;
}

.dark-mode .ag-row-odd {
    background-color: #2d2d2d !important;
}
"""

async def pick_file() -> None:
    global darkness
    result = await local_file_picker('~/writing', multiple=True)
    ui.notify(f'You chose {result}')


@ui.page('/')
def index():
    global darkness
    
    # Add the dark mode styles to the page head
    ui.add_head_html(f'<style>{dark_mode_style}</style>')
    
    # Initialize dark mode (enabled by default)
    darkness = ui.dark_mode(True)
    
    # Add a class to the body element based on dark mode state
    ui.run_javascript("""
    function updateBodyClass(isDark) {
        if (isDark) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    }
    // Initialize with current state
    updateBodyClass(true);
    """)
    
    # Update the body class when dark mode changes
    darkness.bind_value_to(lambda val: ui.run_javascript(f"updateBodyClass({str(val).lower()})"))
    
    with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
        # Header row with dark mode toggle, title, and buttons
        with ui.row().classes('w-full items-center justify-between mb-4'):
            # Left side: Dark/light mode toggle
            with ui.element():
                dark_button = ui.button(icon='dark_mode', on_click=lambda: darkness.set_value(True)) \
                    .props('flat fab-mini no-caps').tooltip('Dark Mode').bind_visibility_from(darkness, 'value', value=False)
                light_button = ui.button(icon='light_mode', on_click=lambda: darkness.set_value(False)) \
                    .props('flat fab-mini no-caps').tooltip('Light Mode').bind_visibility_from(darkness, 'value', value=True)
            
            # Center: Title
            ui.label("File & Folder Picker").classes('text-h4 text-center')
            
            # Right side: Quit button
            with ui.row().classes('gap-2'):
                ui.button("Quit", 
                    on_click=lambda: [ui.notify("Standby shutting down...", type="warning"), app.shutdown()]
                    ).props('no-caps flat').classes('text-red-600')
        
        # Main content area
        with ui.card().classes('w-full'):
            # Description text
            ui.label('This file picker allows you to select .txt files and folders').classes('text-body1 mb-4')
            
            # File chooser button
            ui.button('Choose files or folders', on_click=pick_file, icon='folder').props('no-caps')


ui.run(
    title="File Folder picker",
    reload=False,
    show_welcome_message=False,
    storage_secret="your-secret-key"  # Adding this to help with state persistence
)
