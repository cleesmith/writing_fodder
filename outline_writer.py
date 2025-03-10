# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
from datetime import datetime

parser = argparse.ArgumentParser(description='Generate a novel outline based on high-level concept and any additional information.')
parser.add_argument('--request', type=str, required=True, help="Short description of the novel concept to outline")
parser.add_argument('--request_timeout', type=int, default=1000, help='Maximum timeout for output (default: 1000 seconds or about 16 minutes)')
parser.add_argument('--example_outline', type=str, default="outline.txt", help="Example outline for reference (default: outline.txt)")
parser.add_argument('--concept_file', type=str, default=None, help="File containing detailed concept information (optional)")
parser.add_argument('--characters', type=str, default=None, help="File containing character descriptions (optional)")
parser.add_argument('--thinking_budget', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
parser.add_argument('--max_tokens', type=int, default=12000, help='Maximum tokens for output (default: 12000)')
parser.add_argument('--context_window', type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir', type=str, default=".")
parser.add_argument('--sections', type=int, default=5, help='Number of main parts/sections in the outline (default: 5)')
parser.add_argument('--chapters', type=int, default=25, help='Number of chapters in the outline (default: 25)')
parser.add_argument('--lang', type=str, default="English", help='Language for writing (default: English)')
parser.add_argument('--detailed', action='store_true', help='Generate a more detailed outline with chapter summaries')
parser.add_argument('--title', type=str, default=None, help='Suggested title for the novel (optional)')
parser.add_argument('--genre', type=str, default=None, help='Suggested genre for the novel (optional)')
args = parser.parse_args()

def count_words(text):
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())

def remove_markdown_format(text):
    """
    Remove all Markdown formatting and standardize chapter formats:
    - Remove all Markdown headers (# symbols)
    - Remove POV markers
    - Normalize quotes
    - Remove any other Markdown formatting (bold, italic, code)
    - Clean up to ensure simple chapter numbering format
    """
    # Replace Markdown headers with plain text format
    text = re.sub(r'^#{1,6}\s+Chapter\s+(\d+):\s+(.*?)$', r'\1. \2', text, flags=re.MULTILINE)
    text = re.sub(r'^#{1,6}\s+PART\s+([IVXLCDM]+):\s+(.*?)$', r'PART \1: \2', text, flags=re.MULTILINE)
    text = re.sub(r'^#{1,6}\s+(.*?)$', r'\1', text, flags=re.MULTILINE)
    
    # Remove POV markers
    text = re.sub(r'POV:\s+\w+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'POV:\s+\w+\s*\n', '\n', text, flags=re.MULTILINE)
    
    # Replace special quotes with regular quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r"[''']", "'", text)
    
    # Remove Markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # Code
    text = re.sub(r'^\s*[-*+]\s+', '- ', text, flags=re.MULTILINE)  # Standardize bullet points
    
    # Clean up any extra spaces but preserve line breaks
    text = re.sub(r' +', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    
    # Ensure consistent chapter formatting when numbers are present
    text = re.sub(r'^Chapter\s+(\d+):\s+(.*?)$', r'\1. \2', text, flags=re.MULTILINE)
    
    return text

# Load example outline if provided
example_outline_content = ""
if args.example_outline:
    try:
        with open(args.example_outline, 'r', encoding='utf-8') as file:
            example_outline_content = file.read()
        print(f"Loaded example outline from: {args.example_outline}")
    except FileNotFoundError:
        print(f"Note: Example outline file not found: {args.example_outline}")
        print("Continuing without example outline.")
    except Exception as e:
        print(f"Warning: Could not read example outline file: {e}")
        print("Continuing without example outline.")

# Load concept file if provided
concept_content = ""
if args.concept_file:
    try:
        with open(args.concept_file, 'r', encoding='utf-8') as file:
            concept_content = file.read()
        print(f"Loaded concept from: {args.concept_file}")
    except FileNotFoundError:
        print(f"Note: Concept file not found: {args.concept_file}")
        print("Continuing with just the request description.")
    except Exception as e:
        print(f"Warning: Could not read concept file: {e}")
        print("Continuing with just the request description.")

# Load characters file if provided
characters_content = ""
if args.characters:
    try:
        with open(args.characters, 'r', encoding='utf-8') as file:
            characters_content = file.read()
        print(f"Loaded characters from: {args.characters}")
    except FileNotFoundError:
        print(f"Note: Characters file not found: {args.characters}")
        print("Continuing without characters information.")
    except Exception as e:
        print(f"Warning: Could not read characters file: {e}")
        print("Continuing without characters information.")

# Title and genre placeholders
title_suggestion = f"Suggested title: {args.title}" if args.title else "Please create an appropriate title for this novel."
genre_suggestion = f"Genre: {args.genre}" if args.genre else ""

# create prompt with explicit instructions for AI
prompt = f"""You are a skilled novelist and story architect helping to create a detailed novel outline in fluent, authentic {args.lang}.
Draw upon your knowledge of worldwide literary traditions, narrative structure, and plot development approaches from across cultures,
while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

=== CONCEPT ===
{args.request}
{concept_content}
=== END CONCEPT ===

=== CHARACTERS ===
{characters_content}
=== END CHARACTERS ===

=== EXAMPLE OUTLINE FORMAT ===
{example_outline_content}
=== END EXAMPLE OUTLINE FORMAT ===

Create a detailed novel outline with approximately {args.chapters} chapters organized into {args.sections} main parts or sections.
{title_suggestion}
{genre_suggestion}
Your outline should follow the general format and level of detail shown in the example (if provided), while being completely original.

Consider the following in your thinking:
- Refer to the included CHARACTERS, if provided
- Follow the structure of the EXAMPLE OUTLINE if provided
- Create a compelling narrative arc with rising tension, climax, and resolution
- Develop character arcs that show growth and change
- Include key plot points, conflicts, and important scenes
- Balance external plot with internal character development
- Ensure that each chapter has a clear purpose in advancing the story

IMPORTANT FORMATTING INSTRUCTIONS:
1. DO NOT use Markdown formatting (no #, ##, ###, *, **, etc.)
2. Start with "OUTLINE:" followed by the novel title on the next line
3. For parts/sections, use plain text like: "PART I: THE BEGINNING"
4. For chapters, use ONLY simple numbering like: "1. Chapter Title" (no "Chapter" word, just the number and title)
5. DO NOT include POV markers like "POV: Character"
6. Include a simple chapter description (2-5 sentences) for each chapter
7. Use plain text only - no bold, italic, or other formatting
8. Include an optional brief epilogue if appropriate for the story
9. Make each chapter description substantive enough to guide actual chapter writing
"""

if args.detailed:
    prompt += """
10. For each chapter, include more details such as:
   - Key plot developments
   - Important character moments or revelations
   - Setting details
   - Thematic elements being developed
   But still maintain plain text formatting with no POV markers or Markdown
"""

# create a version of the prompt without the example outline, characters, concept content:
prompt_for_logging = f"""You are a skilled novelist and story architect helping to create a detailed novel outline in fluent, authentic {args.lang}.
Draw upon your knowledge of worldwide literary traditions, narrative structure, and plot development approaches from across cultures,
while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Create a detailed novel outline with approximately {args.chapters} chapters organized into {args.sections} main parts or sections.
{title_suggestion}
{genre_suggestion}
Your outline should follow the general format and level of detail shown in the example (if provided), while being completely original.

Consider the following in your thinking:
- Refer to the included CHARACTERS, if provided
- Follow the structure of the EXAMPLE OUTLINE if provided
- Create a compelling narrative arc with rising tension, climax, and resolution
- Develop character arcs that show growth and change
- Include key plot points, conflicts, and important scenes
- Balance external plot with internal character development
- Ensure that each chapter has a clear purpose in advancing the story

IMPORTANT FORMATTING INSTRUCTIONS:
1. DO NOT use Markdown formatting (no #, ##, ###, *, **, etc.)
2. Start with "OUTLINE:" followed by the novel title on the next line
3. For parts/sections, use plain text like: "PART I: THE BEGINNING"
4. For chapters, use ONLY simple numbering like: "1. Chapter Title" (no "Chapter" word, just the number and title)
5. DO NOT include POV markers like "POV: Character"
6. Include a simple chapter description (2-5 sentences) for each chapter
7. Use plain text only - no bold, italic, or other formatting
8. Include an optional brief epilogue if appropriate for the story
9. Make each chapter description substantive enough to guide actual chapter writing
"""

if args.detailed:
    prompt_for_logging += """
10. For each chapter, include more details such as:
   - Key plot developments
   - Important character moments or revelations
   - Setting details
   - Thematic elements being developed
   But still maintain plain text formatting with no POV markers or Markdown
"""

prompt_for_logging += """
note: The actual prompt included any example outline, characters, and concept which are not logged here to save space.
"""

# calculate a safe max_tokens value
# estimate the input tokens based on a rough character count approximation
estimated_input_tokens = int(len(prompt) // 5.5)
max_safe_tokens = max(5000, args.context_window - estimated_input_tokens - 1000)  # 1000 token buffer for safety
# use the minimum of the requested max_tokens and what we calculated as safe:
max_tokens = int(min(args.max_tokens, max_safe_tokens))

absolute_path = os.path.abspath(args.save_dir)

print(f"Max request timeout: {args.request_timeout} seconds")
print(f"Max retries: 0 (anthropic's default was 2)")
print(f"Max AI model context window: {args.context_window} tokens")
print(f"AI model thinking budget: {args.thinking_budget} tokens")
print(f"Max output tokens: {args.max_tokens} tokens")
print(f"Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})")

# ensure max_tokens is always greater than thinking budget
if max_tokens <= args.thinking_budget:
    max_tokens = args.thinking_budget + args.max_tokens
    print(f"Adjusted max_tokens to {max_tokens} to exceed thinking budget of {args.thinking_budget} (room for thinking/writing)")

print(f"Estimated input/prompt tokens: {estimated_input_tokens}")

client = anthropic.Anthropic(
    timeout=1000, # 1000 seconds (default is 10 minutes = 600 seconds)
    max_retries=0 # default is 2
)

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
    print(f"Actual input/prompt tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)")
except Exception as e:
    print(f"Error:\n{e}\n")

full_response = ""
thinking_content = ""

start_time = time.time()

dt = datetime.fromtimestamp(start_time)
formatted_time = dt.strftime("%A %B %d, %Y %I:%M:%S %p").replace(" 0", " ").lower()
print(f"****************************************************************************")
print(f"*  sending to API at: {formatted_time}")
print(f"*  ... standby, as this usually takes a few minutes")
print(f"*  ")
print(f"*  It's recommended to keep the Terminal or command line the sole 'focus'")
print(f"*  and to avoid browsing online or running other apps, as these API")
print(f"*  network connections are often flakey, like delicate echoes of whispers.")
print(f"*  ")
print(f"*  So breathe, remove eye glasses, stretch, relax, and be like water 🥋 🧘🏽‍♀️")
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
    print(f"Error:\n{e}\n")

elapsed = time.time() - start_time
minutes = int(elapsed // 60)
seconds = elapsed % 60

# Remove markdown from the response
cleaned_response = remove_markdown_format(full_response)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
outline_filename = f"{args.save_dir}/outline_{timestamp}.txt"
with open(outline_filename, 'w', encoding='utf-8') as file:
    file.write(cleaned_response)

outline_word_count = count_words(cleaned_response)

print(f"\nelapsed time: {minutes} minutes, {seconds:.2f} seconds.")
print(f"\nOutline has {outline_word_count} words.")

outline_token_count = 0
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
    outline_token_count = response.input_tokens
    print(f"Outline text is {outline_token_count} tokens (via free client.beta.messages.count_tokens)")
except Exception as e:
    print(f"Error:\n{e}\n")

stats = f"""
Details:
Max request timeout: {args.request_timeout} seconds
Max retries: 0 (anthropic's default was 2)
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget} tokens
Max output tokens: {args.max_tokens} tokens

Estimated input/prompt tokens: {estimated_input_tokens} (includes: example outline, concept, characters, and prompt)
Actual    input/prompt tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)
Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})

elapsed time: {minutes} minutes, {seconds:.2f} seconds
Outline has {outline_word_count} words
Outline text is {outline_token_count} tokens (via free client.beta.messages.count_tokens)
Outline saved to: {outline_filename}
###
"""

if thinking_content:
    thinking_filename = f"{args.save_dir}/thinking_{timestamp}.txt"
    with open(thinking_filename, 'w', encoding='utf-8') as file:
        file.write("=== PROMPT USED (EXCLUDING REFERENCE CONTENT) ===\n")
        file.write(prompt_for_logging)
        file.write("\n\n=== AI'S THINKING PROCESS ===\n\n")
        file.write(thinking_content)
        file.write("\n=== END AI'S THINKING PROCESS ===\n")
        file.write(stats)
    print(f"Outline saved to: {outline_filename}")
    print(f"AI thinking saved to: {thinking_filename}\n")
    print(f"Files saved to: {absolute_path}")
else:
    print(f"Outline saved to: {outline_filename}")
    print("No AI thinking content was captured.\n")
    print(f"Files saved to: {absolute_path}")

print(f"###\n")

# empty garbage, helpful? nah, python's garbage collection is mobbed-up:
example_outline_content = None
characters_content = None
concept_content = None
full_response = None
thinking_content = None
cleaned_response = None
client = None
