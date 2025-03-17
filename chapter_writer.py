# chapter_writer
# python -B chapter_writer.py --chapters chapters.txt --chapter_delay 20 --backup
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
parser.add_argument('--request', type=str, help="Single chapter format: --request \"Chapter 9: Title\", \"9: Title\", or \"9. Title\"")
parser.add_argument('--request_timeout', type=int, default=240, help='Maximum timeout for each *streamed chunk* of output (default: 240 seconds = 4 minutes)')
parser.add_argument('--chapter_delay', type=int, default=20, help='Delay in seconds between processing multiple chapters (default: 20 seconds)')
parser.add_argument('--chapters', type=str, default="chapters.txt", help="Path to a file containing a list of chapters to process sequentially (format: \"9. Title\" per line)")
parser.add_argument('--manuscript', type=str, default="manuscript.txt", help='Path to manuscript file (default: manuscript.txt)')
parser.add_argument('--outline', type=str, default="outline.txt", help='Path to outline file (default: outline.txt)')
parser.add_argument('--world', type=str, default="world.txt", help='Path to world-characters file (default: world.txt)')
parser.add_argument('--thinking_budget', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
parser.add_argument('--max_tokens', type=int, default=9000, help='Maximum tokens for output (default: 9000)')
parser.add_argument('--context_window', type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir', type=str, default=".", help='Directory to save chapter files (default: current directory)')
parser.add_argument('--lang', type=str, default="English", help='Language for writing (default: English)')
parser.add_argument('--verbose', action='store_true', help='Enable verbose output during chapter generation')
parser.add_argument('--no_append', action='store_true', help='Disable auto-appending new chapters to manuscript file')
parser.add_argument('--backup', action='store_true', help='Create backup of manuscript file before appending (default: False)')
args = parser.parse_args()

# Validate that either --request or --chapters is provided
if args.request is None and args.chapters is None:
    print("ERROR: You must provide either --request for a single chapter or --chapters for multiple chapters")
    sys.exit(1)

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
    Extract chapter number from request in formats:
    - "Chapter X: Title" 
    - "X: Title"
    - "X. Title"
    
    Returns the chapter number as a string and the formatted 3-digit version.
    Aborts execution if the format is invalid.
    """
    # Check if the request is in one of the required formats
    chapter_pattern_full = r'^Chapter\s+(\d+)[:\.]?\s+(.+)$'  # "Chapter X: Title"
    chapter_pattern_with_colon = r'^(\d+):\s+(.+)$'           # "X: Title"
    chapter_pattern_with_period = r'^(\d+)\.\s+(.+)$'         # "X. Title"

    full_match = re.match(chapter_pattern_full, request, re.IGNORECASE)
    colon_match = re.match(chapter_pattern_with_colon, request)
    period_match = re.match(chapter_pattern_with_period, request)

    if full_match:
        chapter_num = full_match.group(1)
    elif colon_match:
        chapter_num = colon_match.group(1)
    elif period_match:
        chapter_num = period_match.group(1)
    else:
        print("\nERROR: it's best to copy your next chapter number and title from your outline, as")
        print("'--request' must be like:\n\t--request \"Chapter X: Title\"\n...or\n\t--request \"X: Title\"\n...or\n\t--request \"X. Title\"\n... where X is a number.")
        print(f"But your request was: '{request}'\n")
        # Exit with error code 1
        sys.exit(1)
    
    formatted_chapter = f"{int(chapter_num):03d}"
    return chapter_num, formatted_chapter


def append_to_manuscript(chapter_text, manuscript_path, backup=False):
    """
    Append the new chapter to the manuscript file with proper formatting.
    Creates a backup of the manuscript first if requested.
    
    Returns True on success, False on failure.
    """
    try:
        # Read the existing manuscript
        with open(manuscript_path, 'r', encoding='utf-8') as file:
            manuscript_content = file.read()
        
        # Create backup if requested
        if backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{manuscript_path}_{timestamp}.bak"
            with open(backup_path, 'w', encoding='utf-8') as file:
                file.write(manuscript_content)
        
        # Ensure manuscript ends with exactly one newline
        manuscript_content = manuscript_content.rstrip('\n') + '\n'
        
        # Append chapter with proper formatting (two blank lines)
        with open(manuscript_path, 'w', encoding='utf-8') as file:
            file.write(manuscript_content)
            file.write('\n\n')  # Add two newlines between chapters
            file.write(chapter_text)
        
        return True
    except Exception as e:
        print(f"Error appending to manuscript: {e}")
        return False


def process_chapter(chapter_request, current_idx=None, total_chapters=None):
    """Process a single chapter with the given request string"""
    chapter_num, formatted_chapter = extract_chapter_num(chapter_request)

    current_time = datetime.now().strftime("%I:%M:%S %p").lower().lstrip("0")
    if current_idx is not None and total_chapters is not None:
        print(f"{current_time} - Processing chapter {current_idx} of {total_chapters}: Chapter {chapter_num}")
    else:
        print(f"{current_time} - Processing: Chapter {chapter_num}")

    try:
        with open(args.outline, 'r', encoding='utf-8') as file:
            outline_content = file.read()
    except FileNotFoundError:
        print(f"Error: Required outline file not found: {args.outline}")
        print("The outline file is required to continue.")
        exit(1)

    try:
        with open(args.manuscript, 'r', encoding='utf-8') as file:
            novel_content = file.read()
    except FileNotFoundError:
        print(f"Error: Required manuscript file not found: {args.manuscript}")
        print("Creating a new manuscript file.")
        novel_content = ""
        with open(args.manuscript, 'w', encoding='utf-8') as file:
            file.write("")

    try:
        with open(args.world, 'r', encoding='utf-8') as file:
            world_content = file.read()
    except FileNotFoundError:
        if args.verbose:
            print(f"Note: World file not found: {args.world}")
            print("Continuing without world information.")
        world_content = ""
    except Exception as e:
        if args.verbose:
            print(f"Warning: Could not read world file: {e}")
            print("Continuing without world information.")
        world_content = ""

    # Format the chapter request to ensure it's in "Chapter X: Title" format for Claude
    # This ensures consistency in the prompt regardless of input format
    if re.match(r'^Chapter\s+\d+', chapter_request, re.IGNORECASE):
        formatted_request = chapter_request  # Already in "Chapter X: Title" format
    else:
        # Extract number and title
        match = re.match(r'^(\d+)[:\.]?\s+(.+)$', chapter_request)
        if match:
            num, title = match.groups()
            formatted_request = f"Chapter {num}: {title}"
        else:
            # Fallback, should never happen due to extract_chapter_num validation
            formatted_request = chapter_request

    # Convert outline format to dot format for consistency with output format
    formatted_outline_request = chapter_request
    if not re.match(r'^Chapter\s+\d+', chapter_request, re.IGNORECASE):
        match = re.match(r'^(\d+)[:\.]?\s+(.+)$', chapter_request)
        if match:
            num, title = match.groups()
            formatted_outline_request = f"Chapter {num}. {title}"

    # create prompt with explicit instructions for AI
    # note: the weird indentation keeps the text of the prompt properly aligned
    prompt = f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== WORLD ===
{world_content}
=== END WORLD ===

=== EXISTING MANUSCRIPT ===
{novel_content}
=== END EXISTING MANUSCRIPT ===

You are a skilled novelist writing {formatted_request} in fluent, authentic {args.lang}. 
Draw upon your knowledge of worldwide literary traditions, narrative techniques, and creative approaches from across cultures, while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Consider the following in your thinking:
- IMPORTANT: always review the included OUTLINE
- Refer to the included WORLD of characters and settings, if provided
- How this chapter advances the overall narrative and character development
- Creating compelling opening and closing scenes
- Incorporating sensory details and vivid descriptions
- Maintaining consistent tone and style with previous chapters

IMPORTANT:
1. NO Markdown formatting
2. NO ellipsis  NO em dash  NO '.,-'  NO ',-'  NO '-,'  NO '--'  NO '*'
3. Use hyphens only for legitimate {args.lang} words
4. Begin with: {formatted_outline_request} and write in plain text only
5. Write 1,800-2,500 words
6. Do not repeat content from existing chapters
7. Do not start working on the next chapter
8. Maintain engaging narrative pacing through varied sentence structure, strategic scene transitions, and appropriate balance between action, description, and reflection
9. Prioritize natural, character-revealing dialogue as the primary narrative vehicle, ensuring each conversation serves multiple purposes (character development, plot advancement, conflict building). Include distinctive speech patterns for different characters, meaningful subtext, and strategic dialogue beats, while minimizing lengthy exposition and internal reflection.
10. Write all times in 12-hour numerical format with a space before lowercase am/pm (e.g., "10:30 am," "2:15 pm," "7:00 am") rather than spelling them out as words or using other formats
11. In your 'thinking' before writing always indicate and explain what you're using from: WORLD, OUTLINE, and MANUSCRIPT (previous chapters)
"""

    # create a version of the prompt without the outline, world, manuscript:
    prompt_for_logging = f"""You are a skilled novelist writing {formatted_outline_request} in fluent, authentic {args.lang}. 
Draw upon your knowledge of worldwide literary traditions, narrative techniques, and creative approaches from across cultures, while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Consider the following in your thinking:
- IMPORTANT: always review the included OUTLINE thoroughly 
- Refer to the included WORLD of characters and settings, if provided
- How this chapter advances the overall narrative and character development
- Creating compelling opening and closing scenes
- Incorporating sensory details and vivid descriptions
- Maintaining consistent tone and style with previous chapters

IMPORTANT:
1. NO Markdown formatting
2. NO ellipsis  NO em dash  NO '.,-'  NO ',-'  NO '-,'  NO '--'  NO '*'
3. Use hyphens only for legitimate {args.lang} words
4. Begin with: {formatted_outline_request} and write in plain text only
5. Write 1,800-2,500 words
6. Do not repeat content from existing chapters
7. Do not start working on the next chapter
8. Maintain engaging narrative pacing through varied sentence structure, strategic scene transitions, and appropriate balance between action, description, and reflection
9. Prioritize natural, character-revealing dialogue as the primary narrative vehicle, ensuring each conversation serves multiple purposes (character development, plot advancement, conflict building). Include distinctive speech patterns for different characters, meaningful subtext, and strategic dialogue beats, while minimizing lengthy exposition and internal reflection.
10. Write all times in 12-hour numerical format with a space before lowercase am/pm (e.g., "10:30 am," "2:15 pm," "7:00 am") rather than spelling them out as words or using other formats
11. In your 'thinking' before writing always indicate and explain what you're using from: WORLD, OUTLINE, and MANUSCRIPT (previous chapters)
note: The actual prompt included the outline, world, manuscript which are not logged to save space.
"""

    # calculate a safe max_tokens value
    estimated_input_tokens = int(len(prompt) // 5.5)
    max_safe_tokens = max(5000, args.context_window - estimated_input_tokens - 1000)  # 1000 token buffer for safety
    max_tokens = int(min(args.max_tokens, max_safe_tokens))

    # ensure max_tokens is always greater than thinking budget
    if max_tokens <= args.thinking_budget:
        max_tokens = args.thinking_budget + args.max_tokens

    client = anthropic.Anthropic(
        timeout=args.request_timeout,
        max_retries=0
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
    except Exception as e:
        if args.verbose:
            print(f"Error counting tokens: {e}")

    full_response = ""
    thinking_content = ""

    start_time = time.time()

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
        print(f"Error during generation: {e}")
        return None

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60

    cleaned_response = clean_text_formatting(full_response)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chapter_filename = f"{args.save_dir}/{formatted_chapter}_chapter_{timestamp}.txt"
    
    # Create directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    with open(chapter_filename, 'w', encoding='utf-8') as file:
        file.write(cleaned_response)

    chapter_word_count = count_words(cleaned_response)

    # Optional count of tokens in the chapter
    chapter_token_count = 0
    try:
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": cleaned_response}]
        )
        chapter_token_count = response.input_tokens
    except Exception:
        pass  # Silently ignore token counting errors

    # Append the new chapter to the manuscript file
    if not args.no_append:
        append_success = append_to_manuscript(cleaned_response, args.manuscript, args.backup)
        if append_success:
            print(f"Chapter {chapter_num} appended to manuscript file: {args.manuscript}")
        else:
            print(f"Warning: Failed to append chapter to manuscript file")

    stats = f"""
Details:
Max request timeout: {args.request_timeout} seconds
Max retries: 0
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget} tokens
Max output tokens: {args.max_tokens} tokens
Estimated input/prompt tokens: {estimated_input_tokens}
Actual input/prompt tokens: {prompt_token_count}
Max tokens set to: {max_tokens}
Elapsed time: {minutes}m {seconds:.2f}s
Chapter {chapter_num}: {chapter_word_count} words
Chapter {chapter_num} token count: {chapter_token_count}
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
        
        if args.verbose:
            print(f"AI thinking saved to: {thinking_filename}")
    
    print(f"Completed Chapter {chapter_num}: {chapter_word_count} words ({minutes}m {seconds:.2f}s) - saved to: {os.path.basename(chapter_filename)}")
    
    # Clean up references
    outline_content = None
    world_content = None
    novel_content = None
    full_response = None
    thinking_content = None
    cleaned_response = None
    
    return {
        "chapter_num": chapter_num,
        "word_count": chapter_word_count,
        "token_count": chapter_token_count,
        "elapsed_time": elapsed,
        "chapter_file": chapter_filename
    }


# Main execution logic
if args.chapters:
    # Load chapter list from file
    try:
        with open(args.chapters, 'r', encoding='utf-8') as file:
            chapter_list = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"Error: Chapters file not found: {args.chapters}")
        sys.exit(1)
    
    if not chapter_list:
        print(f"Error: Chapters file is empty: {args.chapters}")
        sys.exit(1)
    
    print(f"Found {len(chapter_list)} chapters to process:")
    for i, chapter in enumerate(chapter_list, 1):
        print(f"  {i}. {chapter}")
    
    # Process each chapter with a delay between them
    summary = []
    for i, chapter_request in enumerate(chapter_list, 1):
        result = process_chapter(chapter_request, i, len(chapter_list))
        if result:
            summary.append(result)
        
        # If this isn't the last chapter, wait before processing the next one
        if i < len(chapter_list):
            print(f"Waiting {args.chapter_delay} seconds before next chapter...")
            time.sleep(args.chapter_delay)
    
    # Print summary of all chapters
    print("\n" + "="*80)
    print("SUMMARY OF ALL CHAPTERS PROCESSED")
    print("="*80)
    total_words = 0
    total_time = 0
    
    for result in summary:
        total_words += result["word_count"]
        total_time += result["elapsed_time"]
        minutes = int(result["elapsed_time"] // 60)
        seconds = result["elapsed_time"] % 60
        print(f"Chapter {result['chapter_num']}: {result['word_count']} words, {minutes}m {seconds:.1f}s, saved to: {os.path.basename(result['chapter_file'])}")
    
    # Calculate averages and totals
    avg_words = total_words / len(summary) if summary else 0
    total_minutes = int(total_time // 60)
    total_seconds = total_time % 60
    
    print(f"\nTotal chapters: {len(summary)}")
    print(f"Total words: {total_words}")
    print(f"Average words per chapter: {avg_words:.1f}")
    print(f"Total time: {total_minutes}m {total_seconds:.1f}s")
    print("="*80)
    
else:
    # Process single chapter using the --request parameter
    process_chapter(args.request)

# Clean up
client = None
