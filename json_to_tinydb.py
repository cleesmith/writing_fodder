import json
from tinydb import TinyDB

# Open the TinyDB database file named 'writers_toolkit.json'
db = TinyDB('writers_toolkit.json')

# Get references to the two tables: one for tools and one for global settings.
tools_table = db.table('tools')
settings_table = db.table('settings')

# Clear any existing data in the tables
tools_table.truncate()
settings_table.truncate()

# Read configuration from the file 'tools_config.json'
with open("tools_config.json", "r") as f:
    config = json.load(f)

# Insert each top-level key appropriately.
for key, value in config.items():
    if key == "_global_settings":
        # Insert global settings into the settings table
        settings_table.insert(value)
    else:
        # Insert tool configuration into the tools table.
        # Ensure the document has a "name" key.
        tool_doc = {"name": key}
        tool_doc.update(value)
        tools_table.insert(tool_doc)

print("Configuration has been successfully inserted into 'writers_toolkit.json'")

# Explicitly close the database
db.close()
