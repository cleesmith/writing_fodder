# brainstorm --ideas_file ideas.txt --genre "Private eye Fiction Noir" --title "Tracking the Dead Wax"
# python -B brainstorm.py --ideas_file ideas.txt --genre "Science Fiction Noir" --title "Havre Dulac Grace"
# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
from datetime import datetime

parser = argparse.ArgumentParser(description='Generate concept and character files for writing development.')
parser.add_argument('--ideas_file', type=str, required=True, help="Path to ideas.txt file containing the concept and/or characters")
parser.add_argument('--continue', action='store_true', help="Continue building on existing ideas in the ideas file")
parser.add_argument('--request_timeout', type=int, default=300, help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds or about 5 minutes)')
parser.add_argument('--thinking_budget', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
parser.add_argument('--max_tokens', type=int, default=12000, help='Maximum tokens for output (default: 12000)')
parser.add_argument('--context_window', type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir', type=str, default=".")
parser.add_argument('--lang', type=str, default="English", help='Language for writing (default: English)')
parser.add_argument('--title', type=str, default=None, help='Suggested title for the writing (optional)')
parser.add_argument('--genre', type=str, default=None, help='Suggested genre for the writing (optional)')
parser.add_argument('--num_characters', type=int, default=5, help='Number of main characters to generate (default: 5)')
parser.add_argument('--worldbuilding_depth', type=int, default=3, help='Depth of worldbuilding detail (1-5, where 5 is most detailed) (default: 3)')
parser.add_argument('--character_relationships', action='store_true', help='Include detailed character relationships')
parser.add_argument('--concept_only', action='store_true', help='Generate only the concept file')
parser.add_argument('--characters_only', action='store_true', help='Generate only the characters file')
parser.add_argument('--allow_new_characters', action='store_true', help='Allow creation of new characters not in the ideas file')
args = parser.parse_args()

def count_words(text):
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())

def remove_markdown_format(text):
    """
    Remove all Markdown formatting:
    - Remove all Markdown headers (# symbols)
    - Normalize quotes
    - Remove any other Markdown formatting (bold, italic, code)
    """
    # Replace Markdown headers with plain text format
    text = re.sub(r'^#{1,6}\s+(.*?)$', r'\1', text, flags=re.MULTILINE)
    
    # Replace special quotes with regular quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r"[''']", "'", text)
    
    # Remove Markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # Code
    
    # Clean up any extra spaces but preserve line breaks
    text = re.sub(r' +', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    
    return text

def read_ideas_file(filepath):
    """
    Read the ideas.txt file and return its content as a simple string.
    Abort if the file doesn't exist.
    """
    if not os.path.exists(filepath):
        print(f"Error: Ideas file '{filepath}' not found.")
        print("Please specify an existing ideas file with --ideas_file parameter.")
        sys.exit(1)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return content.strip()

def append_to_ideas_file(filepath, new_content, content_type):
    """
    Append newly generated content to the ideas.txt file
    """
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write("\n\n")
        f.write(f"# {content_type} (Generated {datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n")
        f.write(new_content)

def calculate_max_tokens(prompt):
    # estimate the input tokens based on a rough character count approximation
    estimated_input_tokens = int(len(prompt) // 5.5)
    max_safe_tokens = max(5000, args.context_window - estimated_input_tokens - 1000)  # 1000 token buffer for safety
    # use the minimum of the requested max_tokens and what we calculated as safe:
    max_tokens = int(min(args.max_tokens, max_safe_tokens))
    
    # ensure max_tokens is always greater than thinking budget
    if max_tokens <= args.thinking_budget:
        max_tokens = args.thinking_budget + args.max_tokens
        print(f"Adjusted max_tokens to {max_tokens} to exceed thinking budget of {args.thinking_budget}")
    
    return max_tokens, estimated_input_tokens, max_safe_tokens

ideas_content = read_ideas_file(args.ideas_file)

title_suggestion = f"TITLE: {args.title}" if args.title else ""
genre_suggestion = f"GENRE: {args.genre}" if args.genre else ""

# Create prompt for concept generation
def create_concept_prompt():
    continue_flag = ""
    if getattr(args, 'continue', False) and ideas_content:
        continue_flag = "Continue and expand on the existing concept. Add new details and develop existing ideas further."
    
    concept_prompt = f"""You are a skilled novelist and worldbuilder helping to create a detailed concept document in fluent, authentic {args.lang}.
Draw upon your knowledge of worldwide literary traditions, narrative structure, and worldbuilding approaches from across cultures,
while expressing everything in natural, idiomatic {args.lang}.

=== IDEAS FILE CONTENT ===
{ideas_content}
{title_suggestion}
{genre_suggestion}
=== END IDEAS FILE CONTENT ===

{continue_flag}

Create a detailed concept document that explores and develops this writing idea. Focus on worldbuilding, setting, themes, and plot possibilities.
The depth level requested is {args.worldbuilding_depth}/5, so adjust your detail accordingly.

Structure your response as a CONCEPT DOCUMENT with these clearly labeled sections:

1. HIGH CONCEPT (1-2 paragraphs summarizing the core idea)
2. WORLD/SETTING (detailed description of the world, era, technology, social structures, etc.)
3. CENTRAL CONFLICT (the main tension driving the story)
4. THEMES & MOTIFS (3-5 major themes to be explored)
5. UNIQUE ELEMENTS (what makes this concept fresh and original)
6. PLOT POSSIBILITIES (2-3 paragraphs on possible story directions)
7. TONE & ATMOSPHERE (the feeling and mood of the story)
8. WORLDBUILDING NOTES (10-15 specific details about how this world works)

IMPORTANT FORMATTING INSTRUCTIONS:
1. DO NOT use Markdown formatting (no #, ##, ###, *, **, etc.)
2. Start with "CONCEPT DOCUMENT:" at the top of your response
3. Use plain text section headers like "HIGH CONCEPT:"
4. Use plain numbered or bullet lists where appropriate
5. Keep your writing clear, concise, and creative
6. This content will be appended to an ideas file for writing development
"""
    return concept_prompt

def create_character_prompt():
    continue_flag = ""
    if getattr(args, 'continue', False) and ideas_content:
        continue_flag = "Review the existing characters in the ideas file. Build on these characters by expanding their details and deepening their characterization. If appropriate, create additional characters to reach the requested total number."
    
    # determine character name handling based on arguments
    character_name_instructions = ""
    if args.allow_new_characters:
        character_name_instructions = """
You are permitted to create new characters that fit the concept.
Create characters that align with and enhance the world, themes, and plot described in the ideas file.
Use Title Case (camel-case) for all character names.
"""
    else:
        character_name_instructions = """
STRICT CHARACTER NAME INSTRUCTIONS:
- You MUST use ONLY the exact character names provided in: === CHARACTERS === through === END CHARACTERS === section, if provided
- DO NOT create any new character names not in: === CHARACTERS === through === END CHARACTERS ===
- DO NOT modify, expand, or add to the character names in any way (no adding first/last names, titles, etc.)
- Keep the exact capitalization/title case of each name as provided
- If a character has only a first name or nickname in the list, use ONLY that exact name
- If a character is referred to differently in different parts of the ideas file, use ONLY the specific format provided in the list

BACKGROUND CHARACTER INSTRUCTIONS:
- For incidental characters who briefly appear in scenes (cashiers, waiters, doormen, passersby, etc.), refer to them ONLY by their role or function (e.g., "the cashier," "the doorman").
- DO NOT assign names to these background characters unless they become recurring or important to the plot.
- DO NOT develop backstories for these functional characters.
- Background characters should only perform actions directly related to their function or brief interaction with named characters.
- Keep interactions with background characters brief and purposeful - they should serve the story without becoming story elements themselves.
- If a background character needs to speak, use phrases like "the clerk asked" rather than creating a name.
- Remember that background characters exist to create a realistic world but should remain in the background to keep focus on the main characters and plot.
"""
    
    character_prompt = f"""You are a skilled novelist and character developer helping to create detailed character descriptions in fluent, authentic {args.lang}.
Draw upon your knowledge of worldwide literary traditions, character development, and psychological complexity from across cultures,
while expressing everything in natural, idiomatic {args.lang}.

=== IDEAS FILE CONTENT ===
{ideas_content}
{title_suggestion}
{genre_suggestion}
=== END IDEAS FILE CONTENT ===

{character_name_instructions}

{continue_flag}

Structure your response as a CHARACTER DOCUMENT with these elements for EACH character:

1. NAME & ROLE (full name and their function in the story)
2. PHYSICAL DESCRIPTION (key physical traits and appearance)
3. PERSONALITY (core character traits, strengths, flaws)
4. BACKGROUND (relevant history and formative experiences)
5. MOTIVATION (what drives this character)
6. ARC (how this character might change throughout the story)
7. SPECIAL SKILLS/ABILITIES (what makes them effective in this world)
{"8. RELATIONSHIPS (how they connect to other characters)" if args.character_relationships else ""}

IMPORTANT FORMATTING INSTRUCTIONS:
1. DO NOT use Markdown formatting (no #, ##, ###, *, **, etc.)
2. Number each character entry like "1. Character Name"
3. Use plain text for character details with bullet points or dashes
4. For each character attribute use a dash or bullet format like:
   - role: protagonist
   - personality: determined, resourceful
5. Separate each character with a blank line
6. Keep your writing clear, concise, and psychologically insightful
7. This content will be appended to an ideas file for writing development
"""
    return character_prompt

# Print initial setup information
print(f"Starting concept and character generation using ideas file: '{args.ideas_file}'")
print(f"Save directory: {os.path.abspath(args.save_dir)}")
print(f"Max request timeout: {args.request_timeout} seconds")
print(f"Max AI model context window: {args.context_window} tokens")
print(f"AI model thinking budget: {args.thinking_budget} tokens")

if ideas_content:
    idea_words = count_words(ideas_content)
    print(f"Ideas file contains {idea_words} words")
else:
    print("Ideas file is empty")

client = anthropic.Anthropic(
    timeout=args.request_timeout,
    max_retries=0  # default is 2
)

# Function to make API call and append results to ideas file
def generate_and_append(prompt_type):
    if prompt_type == "concept":
        prompt = create_concept_prompt()
    else:  # characters
        prompt = create_character_prompt()
    
    max_tokens, estimated_input_tokens, max_safe_tokens = calculate_max_tokens(prompt)
    
    print(f"\n--- Generating {prompt_type} ---")
    print(f"Estimated input/prompt tokens: {estimated_input_tokens}")
    print(f"Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})")
    
    prompt_token_count = 0
    try:
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": prompt}],
            thinking={
                "type": "enabled",
                "budget_tokens": args.thinking_budget
            },
            betas=["output-128k-2025-02-19"]
        )
        prompt_token_count = response.input_tokens
        print(f"Actual input/prompt tokens: {prompt_token_count} (via client.beta.messages.count_tokens)")
    except Exception as e:
        print(f"Error counting tokens:\n{e}\n")
    
    full_response = ""
    thinking_content = ""
    
    start_time = time.time()
    
    dt = datetime.fromtimestamp(start_time)
    formatted_time = dt.strftime("%A %B %d, %Y %I:%M:%S %p").replace(" 0", " ").lower()
    print(f"****************************************************************************")
    print(f"*  sending to API at: {formatted_time}")
    print(f"*  ... standby, as this usually takes a few minutes")
    print(f"****************************************************************************")
    
    try:
        with client.beta.messages.stream(
            model="claude-3-7-sonnet-20250219",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            thinking={
                "type": "enabled",
                "budget_tokens": args.thinking_budget
            },
            betas=["output-128k-2025-02-19"]
        ) as stream:
            # track both thinking and text output
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "thinking_delta":
                        thinking_content += event.delta.thinking
                    elif event.delta.type == "text_delta":
                        full_response += event.delta.text
    except Exception as e:
        print(f"\nError during API call:\n{e}\n")
    
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    
    # remove markdown from the response
    cleaned_response = remove_markdown_format(full_response)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    append_to_ideas_file(args.ideas_file, cleaned_response, prompt_type.capitalize())
    
    # Save a backup copy of the generated content as a separate file
    backup_filename = f"{args.save_dir}/{prompt_type}_{timestamp}.txt"
    with open(backup_filename, 'w', encoding='utf-8') as file:
        file.write(cleaned_response)
    
    output_word_count = count_words(cleaned_response)
    
    print(f"\nElapsed time: {minutes} minutes, {seconds:.2f} seconds.")
    print(f"Generated {prompt_type} has {output_word_count} words.")
    
    output_token_count = 0
    try:
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": cleaned_response}],
            thinking={
                "type": "enabled",
                "budget_tokens": args.thinking_budget
            },
            betas=["output-128k-2025-02-19"]
        )
        output_token_count = response.input_tokens
        print(f"Output is {output_token_count} tokens (via client.beta.messages.count_tokens)")
    except Exception as e:
        print(f"Error counting output tokens:\n{e}\n")
    
    stats = f"""
Details:
Max request timeout: {args.request_timeout} seconds
Max retries: 0 (anthropic's default was 2)
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget} tokens
Max output tokens: {args.max_tokens} tokens

Estimated input/prompt tokens: {estimated_input_tokens}
Actual    input/prompt tokens: {prompt_token_count} (via client.beta.messages.count_tokens)
Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})

Elapsed time: {minutes} minutes, {seconds:.2f} seconds
Output has {output_word_count} words
Output is {output_token_count} tokens (via client.beta.messages.count_tokens)
Content appended to: {args.ideas_file}
Backup saved to: {backup_filename}
###
"""
    
    if thinking_content:
        thinking_filename = f"{args.save_dir}/{prompt_type}_thinking_{timestamp}.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== PROMPT USED ===\n")
            file.write(prompt)
            file.write("\n\n=== AI'S THINKING PROCESS ===\n\n")
            file.write(thinking_content)
            file.write("\n=== END AI'S THINKING PROCESS ===\n")
            file.write(stats)
        print(f"Content appended to: {args.ideas_file}")
        print(f"Backup saved to: {backup_filename}")
        print(f"AI thinking saved to: {thinking_filename}\n")
    else:
        print(f"Content appended to: {args.ideas_file}")
        print(f"Backup saved to: {backup_filename}")
        print("No AI thinking content was captured.\n")
    
    return args.ideas_file

try:
    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)
        print(f"Created directory: {args.save_dir}")
    
    # Check if ideas file exists but don't create it
    if not os.path.exists(args.ideas_file):
        print(f"Error: Ideas file '{args.ideas_file}' not found.")
        print("Please specify an existing ideas file with --ideas_file parameter.")
        sys.exit(1)
    
    if args.characters_only:
        generate_and_append("characters")
    elif args.concept_only:
        generate_and_append("concept")
    else:
        generate_and_append("concept")
        generate_and_append("characters")
    
    print("\nGeneration complete!")
    print(f"All content has been appended to: {args.ideas_file}")
    print(f"To continue developing this story, use: python brainstorm.py --ideas_file {args.ideas_file} --continue")
    
except Exception as e:
    print(f"\nAn error occurred: {e}")
    sys.exit(1)
finally:
    # clean up resources
    client = None
