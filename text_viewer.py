from nicegui import ui
import os

# Function to read the manuscript file
def read_manuscript():
    try:
        if os.path.exists('manuscript.txt'):
            with open('manuscript.txt', 'r', encoding='utf-8') as file:
                return file.read()
        else:
            return "File not found: manuscript.txt\n\nStart typing to create content!"
    except Exception as e:
        return f"Error reading file: {str(e)}\n\nStart typing to create content!"

# Function to save content to file
def save_manuscript(content):
    try:
        with open('manuscript.txt', 'w', encoding='utf-8') as file:
            file.write(content)
        ui.notify('Manuscript saved successfully!', type='positive')
    except Exception as e:
        ui.notify(f'Error saving file: {str(e)}', type='negative')

# Function to update preview
def update_preview():
    preview_area.content = editor.value

# Create the page layout
ui.label('Manuscript Editor & Viewer').style('font-size: 24px; font-weight: bold; margin-bottom: 10px')

# Add buttons for file operations
with ui.row().style('margin-bottom: 20px'):
    ui.button('Refresh', on_click=lambda: editor.set_value(read_manuscript()))
    ui.button('Save', on_click=lambda: save_manuscript(editor.value))
    ui.button('Update Preview', on_click=update_preview)

# Create a clear divider between sections
with ui.row().style('width: 100%'):
    ui.separator()

# Create the editor section
ui.label('Edit').style('font-size: 18px; font-weight: bold; margin-top: 10px')
editor = ui.editor(value=read_manuscript()).style('width: 100%; min-height: 300px; margin-bottom: 20px')

# Clear separator between editor and preview
with ui.row().style('width: 100%'):
    ui.separator()

# Create the preview section
ui.label('Preview').style('font-size: 18px; font-weight: bold; margin-top: 20px')
preview_area = ui.markdown().style('width: 100%; min-height: 300px; border: 1px solid #ccc; padding: 10px; background-color: #f9f9f9')

# Initialize preview with current content
update_preview()

# Set up automatic preview updates when editor changes
editor.on('change', update_preview)

# Run the application
ui.run(title='Manuscript Editor & Viewer')
