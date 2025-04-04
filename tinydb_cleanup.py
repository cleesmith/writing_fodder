import json
from tinydb import TinyDB, Query

# Path to your existing database
DB_PATH = "writers_toolkit.json"

# Claude API parameter names to look for in tool options
CLAUDE_API_PARAMS = [
    '--request_timeout',
    '--max_retries',
    '--context_window',
    '--betas_max_tokens',
    '--thinking_budget_tokens',
    '--thinking_budget',
    '--desired_output_tokens',
    '--max_tokens'
]

# Parameter name mapping to standardized keys
PARAM_MAPPING = {
    '--request_timeout': 'request_timeout',
    '--max_retries': 'max_retries',
    '--context_window': 'context_window',
    '--betas_max_tokens': 'betas_max_tokens',
    '--thinking_budget_tokens': 'thinking_budget_tokens',
    '--thinking_budget': 'thinking_budget_tokens',
    '--desired_output_tokens': 'desired_output_tokens',
    '--max_tokens': 'desired_output_tokens'
}

# Default Claude API settings
DEFAULT_CLAUDE_API_SETTINGS = {
    "request_timeout": 300,
    "max_retries": 1,
    "context_window": 200000,
    "betas_max_tokens": 128000,
    "thinking_budget_tokens": 32000,
    "desired_output_tokens": 8000
}

def main():
    # Open the database
    db = TinyDB(DB_PATH)
    tools_table = db.table('tools')
    
    # Create new claude_api table
    claude_api_table = db.table('claude_api')
    
    # Dictionary to hold consolidated Claude API settings
    consolidated_settings = {}
    
    # Extract settings from all tools
    for tool in tools_table.all():
        if 'options' in tool:
            for option in tool['options']:
                param_name = option.get('name')
                
                if param_name in CLAUDE_API_PARAMS:
                    # Get standardized key name
                    key = PARAM_MAPPING.get(param_name)
                    
                    # Get value if it exists
                    default_value = option.get('default')
                    
                    # Only store non-None values
                    if default_value is not None:
                        # If we have multiple values for the same parameter, take the latest
                        consolidated_settings[key] = default_value
    
    # If we didn't find any settings, use defaults
    if not consolidated_settings:
        consolidated_settings = DEFAULT_CLAUDE_API_SETTINGS
    else:
        # Fill in any missing settings with defaults
        for key, value in DEFAULT_CLAUDE_API_SETTINGS.items():
            if key not in consolidated_settings:
                consolidated_settings[key] = value
    
    # Save consolidated settings to claude_api table
    # Clear the table first if it exists
    claude_api_table.truncate()
    claude_api_table.insert(consolidated_settings)
    
    # Ensure the document ID is 1
    claude_api_table.update(lambda _: True, doc_ids=[1])
    
    print(f"Claude API settings saved to claude_api table: {consolidated_settings}")
    
    # Now remove the Claude API settings from individual tools
    # This requires modifying each tool and updating the database
    modified_count = 0
    
    for tool in tools_table.all():
        tool_modified = False
        
        if 'options' in tool:
            # Keep only non-Claude API options
            new_options = []
            for option in tool['options']:
                param_name = option.get('name')
                
                # Keep the option in the tool configuration but update its default value
                # to reflect the centralized value
                if param_name in CLAUDE_API_PARAMS:
                    key = PARAM_MAPPING.get(param_name)
                    option['default'] = consolidated_settings.get(key)
                    tool_modified = True
                
                new_options.append(option)
            
            # Update the tool's options
            if tool_modified:
                tools_table.update({'options': new_options}, doc_ids=[tool.doc_id])
                modified_count += 1
    
    print(f"Modified {modified_count} tools to use centralized Claude API settings")
    
    # Close the database
    db.close()
    
    print("Database cleanup complete.")

if __name__ == "__main__":
    main()
