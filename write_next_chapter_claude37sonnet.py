# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
from datetime import datetime

parser = argparse.ArgumentParser(description='Generate the next chapter based on the outline and any previous chapters.')
parser.add_argument('--request', type=str, required=True, help="like: --request \"Chapter 9: Title\"  or  --request \"9: Title\"")
parser.add_argument('--novel-file', type=str, default="sophie.txt")
parser.add_argument('--max-tokens', type=int, default=9000, help='Maximum tokens for output (default: 9000)')
parser.add_argument('--save-dir', type=str, default=".")
parser.add_argument('--lang', type=str, default="English", help='Language for writing (default: English)')
args = parser.parse_args()

def count_words(text):
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())

def clean_text_formatting(text):
    """
    clean text formatting by:
    - removing Markdown headers
    - converting em dashes, en dashes and spaced hyphens to commas
    - preserving legitimate hyphenated compound words
    - normalizing quotes
    - removing Markdown formatting (bold, italic, code)
    """
    # remove Markdown header before: Chapter #:
    text = re.sub(r'^#+ .*$', '', text, flags=re.MULTILINE)
    
    # replace em dashes with commas (ensuring proper spacing)
    text = re.sub(r'(\w+)—(\w+)', r'\1, \2', text)
    text = re.sub(r'(\w+)—\s+', r'\1, ', text)
    text = re.sub(r'\s+—(\w+)', r', \1', text)
    text = re.sub(r'—', ', ', text)
    
    # replace en dashes with commas (ensuring proper spacing)
    text = re.sub(r'(\w+)\s*–\s*(\w+)', r'\1, \2', text)
    text = re.sub(r'(\w+)\s*–\s*', r'\1, ', text)
    text = re.sub(r'\s*–\s*(\w+)', r', \1', text)
    text = re.sub(r'–', ', ', text)
    
    # replace hyphens with spaces around them (used as separators)
    text = re.sub(r'(\w+)\s+-\s+(\w+)', r'\1, \2', text)
    text = re.sub(r'(\w+)\s+-\s+', r'\1, ', text)
    text = re.sub(r'\s+-\s+(\w+)', r', \1', text)
    
    # replace double hyphens
    text = re.sub(r'--', ',', text)
    
    # replace special quotes with regular quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r"[''']", "'", text)
    
    # remove Markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # Code
    
    # clean up any double commas or extra spaces around commas
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r',\s+', ', ', text)
    
    return text


def extract_chapter_num(request):
    """
    Extract chapter number from request in format "Chapter X: Title" or "X: Title"
    Returns the chapter number as a string and the formatted 3-digit version.
    Aborts execution if the format is invalid.
    """
    # Check if the request is in one of the required formats
    chapter_pattern_full = r'^Chapter\s+(\d+)[:\.]?\s+(.+)$'  # "Chapter X: Title"
    chapter_pattern_short = r'^(\d+)[:\.]?\s+(.+)$'           # "X: Title"

    full_match = re.match(chapter_pattern_full, request, re.IGNORECASE)
    short_match = re.match(chapter_pattern_short, request, re.IGNORECASE)

    if full_match:
        chapter_num = full_match.group(1)
    elif short_match:
        chapter_num = short_match.group(1)
    else:
        print("\nERROR: it's best to copy your next chapter number and title from your outline, as")
        print("'-- request' must be like:\n\t--request \"Chapter X: Title\"\n...or\n\t--request \"X: Title\"\n... where X is a number.")
        print(f"But your request was: '{request}'\n")
        # Exit with error code 1
        sys.exit(1)
    
    formatted_chapter = f"{int(chapter_num):03d}"
    return chapter_num, formatted_chapter


chapter_num, formatted_chapter = extract_chapter_num(args.request)
print(f"preparing for Chapter: {chapter_num}")

with open(args.novel_file, 'r', encoding='utf-8') as file:
    novel_content = file.read()

# for writing with more dialogue use this instead:
# 8. Prioritize rich internal character thoughts as the primary narrative vehicle, while including natural dialogue selectively when it serves character development or plot advancement
# create prompt with explicit instructions for AI
prompt = f"""=== EXISTING MANUSCRIPT ===
{novel_content}
=== END EXISTING MANUSCRIPT ===

You are a skilled novelist writing Chapter {args.request} in fluent, authentic {args.lang}. 
Draw upon your knowledge of worldwide literary traditions, narrative techniques, and creative approaches from across cultures, while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Consider the following in your thinking:
- The included OUTLINE at the beginning of EXISTING MANUSCRIPT
- How this chapter advances the overall narrative and character development
- Creating compelling opening and closing scenes
- Incorporating sensory details and vivid descriptions
- Maintaining consistent tone and style with previous chapters

IMPORTANT:
1. NO Markdown formatting
2. Begin with "Chapter {args.request}" in plain text
3. Write 1,500-2,500 words
4. Do not repeat content from existing chapters
5. Do not start the next chapter
6. Use hyphens only for legitimate {args.lang} words
7. Maintain engaging narrative pacing through varied sentence structure, strategic scene transitions, and appropriate balance between action, description, and reflection
8. Prioritize natural, character-revealing dialogue as the primary narrative vehicle, ensuring each conversation serves multiple purposes (character development, plot advancement, conflict building). Include distinctive speech patterns for different characters, meaningful subtext, and strategic dialogue beats, while minimizing lengthy exposition and internal reflection.
9. Write all times in 12-hour numerical format with a space before lowercase am/pm (e.g., "10:30 am," "2:15 pm," "7:00 am") rather than spelling them out as words or using other formats
"""

# create a version of the prompt without the novel content for logging
prompt_for_logging = f"""You are a skilled novelist writing Chapter {args.request} in fluent, authentic {args.lang}. 
Draw upon your knowledge of worldwide literary traditions, narrative techniques, and creative approaches from across cultures, while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Consider the following in your thinking:
- The included OUTLINE at the beginning of EXISTING MANUSCRIPT
- How this chapter advances the overall narrative and character development
- Creating compelling opening and closing scenes
- Incorporating sensory details and vivid descriptions
- Maintaining consistent tone and style with previous chapters

IMPORTANT:
1. NO Markdown formatting
2. Begin with "Chapter {args.request}" in plain text
3. Write 1,500-2,500 words
4. Do not repeat content from existing chapters
5. Do not start the next chapter
6. Use hyphens only for legitimate {args.lang} words
7. Maintain engaging narrative pacing through varied sentence structure, strategic scene transitions, and appropriate balance between action, description, and reflection
8. Prioritize natural, character-revealing dialogue as the primary narrative vehicle, ensuring each conversation serves multiple purposes (character development, plot advancement, conflict building). Include distinctive speech patterns for different characters, meaningful subtext, and strategic dialogue beats, while minimizing lengthy exposition and internal reflection.
9. Write all times in 12-hour numerical format with a space before lowercase am/pm (e.g., "10:30 am," "2:15 pm," "7:00 am") rather than spelling them out as words or using other formats
note: The actual prompt included the full novel manuscript that was not logged here to save space.
"""

# calculate a safe max_tokens value
# we'll estimate the input tokens based on a rough character count approximation
estimated_input_tokens = len(prompt) // 5.5
context_window = 204648  # Claude 3.7 Sonnet's context window
max_safe_tokens = max(5000, context_window - estimated_input_tokens - 1000)  # 1000 token buffer for safety
# use the minimum of the requested max_tokens and what we calculate as safe
max_tokens = int(min(args.max_tokens, max_safe_tokens))

print(f"Estimated input tokens: ~{estimated_input_tokens}")
print(f"Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})")

# ensure max_tokens is always greater than thinking budget
thinking_budget = 31000
if max_tokens <= thinking_budget:
    max_tokens = thinking_budget + 9000
    print(f"Adjusted max_tokens to {max_tokens} to exceed thinking budget of {thinking_budget} (make room for writing)")

# initialize client & response collector
client = anthropic.Anthropic(timeout=1000)
full_response = ""
thinking_content = ""

start_time = time.time()

dt = datetime.fromtimestamp(start_time)
formatted_time = dt.strftime("%A %B %d, %Y %I:%M:%S %p").replace(" 0", " ").lower()
print(f"************************************************************************")
print(f"sending to API at: {formatted_time}")
print(f"... standby, as this usually takes a few minutes\n")
print(f"It's recommended to keep the Terminal or command line the sole 'focus'")
print(f"and to avoid browsing online or running other apps, as these API")
print(f"network connections are often flakey, like delicate echoes of whispers.")
print(f"\nSo breathe, remove eye glasses, stretch, relax, and be like water 🥋 🧘🏽‍♀️")
print(f"************************************************************************")

with client.beta.messages.stream(
    model="claude-3-7-sonnet-20250219",
    max_tokens=max_tokens,
    messages=[{"role": "user", "content": prompt}],
    thinking={
        "type": "enabled",
        "budget_tokens": thinking_budget
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
                # maybe this was causing network issues = flakey:
                # print(event.delta.text, end="", flush=True)
                # show progress without heavy printing, show dot every 500 chars:
                # if len(full_response) % 500 == 0:
                #     print(".", end="", flush=True)

elapsed = time.time() - start_time
minutes = int(elapsed // 60)
seconds = elapsed % 60

cleaned_response = clean_text_formatting(full_response)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
chapter_filename = f"{args.save_dir}/{formatted_chapter}_chapter_{timestamp}.txt"
with open(chapter_filename, 'w', encoding='utf-8') as file:
    file.write(cleaned_response)

chapter_word_count = count_words(cleaned_response)

print(f"\nelapsed time: {minutes} minutes, {seconds:.2f} seconds.")
print(f"\nChapter: {chapter_num} has {chapter_word_count} words (includes chapter title).")

stats = f"""
Details:
Estimated input tokens: ~{estimated_input_tokens} (includes: outline, entire novel, and prompt)
Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})

elapsed time: {minutes} minutes, {seconds:.2f} seconds
Chapter: {chapter_num} has {chapter_word_count} words (includes chapter title)
###
"""

if thinking_content:
    thinking_filename = f"{args.save_dir}/{formatted_chapter}_thinking_{timestamp}.txt"
    with open(thinking_filename, 'w', encoding='utf-8') as file:
        file.write("=== PROMPT USED (EXCLUDING NOVEL CONTENT) ===\n")
        file.write(prompt_for_logging)
        file.write("\n\n=== AI'S THINKING PROCESS ===\n\n")
        file.write(thinking_content)
        file.write("\n=== END AI'S THINKING PROCESS ===\n")
        file.write(stats)
    print(f"New chapter saved to: {chapter_filename}")
    print(f"AI thinking saved to: {thinking_filename}\n###\n")
else:
    print(f"New chapter saved to: {chapter_filename}")
    print("No AI thinking content was captured.\n###\n")

# empty garbage, helpful? nah, python's garbage collection is mobbed-up:
full_response = None
thinking_content = None
cleaned_response = None
client = None

