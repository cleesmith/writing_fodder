# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
import json
from datetime import datetime

parser = argparse.ArgumentParser(description='Generate the next chapter based on the outline and any previous chapters.')
parser.add_argument('--request', type=str, required=True, help="must be: --request \"Chapter 9: Title\"  or  --request \"9: Title\"")
parser.add_argument('--request_timeout', type=int, default=3600, help='Maximum timeout for output (default: 3600 seconds or 1 hour)')
parser.add_argument('--manuscript', type=str, default="manuscript.txt")
parser.add_argument('--outline', type=str, default="outline.txt")
parser.add_argument('--characters', type=str, default="characters.txt")
parser.add_argument('--thinking_budget', type=int, default=64000, help='Maximum tokens for AI thinking (default: 64000)')
parser.add_argument('--max_tokens', type=int, default=9000, help='Maximum tokens for output (default: 9000)')
parser.add_argument('--context_window', type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir', type=str, default=".")
parser.add_argument('--lang', type=str, default="English", help='Language for writing (default: English)')
parser.add_argument('--polling_interval', type=int, default=30, help='Seconds between polling for results (default: 30)')
parser.add_argument('--no_wait', action='store_true', help='Start job and return message ID without waiting for completion')
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


def create_batch_request(client, prompt, max_tokens, thinking_budget):
    """Create a batch request and return the message ID"""
    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            thinking={
                "type": "enabled",
                "budget_tokens": thinking_budget
            },
            betas=["output-128k-2025-02-19", "batch-messages-2025-02-19"]
        )
        return response.id
    except Exception as e:
        print(f"Error creating batch request: {e}")
        sys.exit(1)


def retrieve_batch_result(client, message_id, polling_interval, max_attempts):
    """Poll for results until completion or timeout"""
    attempts = 0
    
    print("\nWaiting for Claude to complete writing your chapter...")
    print(f"This may take several minutes (polling every {polling_interval} seconds)")
    print("Progress: ", end="", flush=True)
    
    while attempts < max_attempts:
        try:
            message = client.messages.retrieve(message_id)
            
            if message.status == "completed":
                print("\nCompleted!")
                
                # Extract thinking and response content
                thinking_content = ""
                full_response = ""
                
                for content_block in message.content:
                    if content_block.type == "thinking":
                        thinking_content = content_block.thinking
                    elif content_block.type == "text":
                        full_response += content_block.text
                        
                return {
                    "thinking": thinking_content,
                    "response": full_response
                }
            elif message.status == "failed":
                print(f"\nBatch processing failed: {message.error}")
                sys.exit(1)
            
            # Show progress indicator
            progress_chars = "|/-\\"
            print(f"\rStatus: {message.status} {progress_chars[attempts % 4]}", end="", flush=True)
            
            time.sleep(polling_interval)
            attempts += 1
        except Exception as e:
            print(f"\nError retrieving batch result: {e}")
            sys.exit(1)
    
    print("\nTimeout waiting for batch completion. Your chapter is still being generated.")
    print(f"You can retrieve it later using the message ID: {message_id}")
    print("To retrieve the results later, run:")
    print(f"python retrieve_chapter.py {message_id}")
    
    # Create the retrieval script if it doesn't exist
    create_retrieval_script()
    
    sys.exit(0)


def create_retrieval_script():
    """Create a simple script to retrieve results later"""
    retrieval_script = """# retrieve_chapter.py
import anthropic
import json
import sys
import os
import time
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: python retrieve_chapter.py MESSAGE_ID")
    sys.exit(1)

message_id = sys.argv[1]
client = anthropic.Anthropic()

def clean_text_formatting(text):
    # Same cleaning function as in chapter_writer.py
    import re
    text = re.sub(r'^#+ .*$', '', text, flags=re.MULTILINE)
    # ... (include all the regex replacements from the original)
    return text

try:
    print(f"Retrieving results for message {message_id}...")
    message = client.messages.retrieve(message_id)
    
    if message.status == "completed":
        print("Job complete! Results retrieved.")
        
        # Extract thinking and response content
        thinking_content = ""
        full_response = ""
        
        for content_block in message.content:
            if content_block.type == "thinking":
                thinking_content = content_block.thinking
            elif content_block.type == "text":
                full_response += content_block.text
        
        # Clean the response
        cleaned_response = clean_text_formatting(full_response)
        
        # Save the files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chapter_filename = f"retrieved_chapter_{timestamp}.txt"
        thinking_filename = f"retrieved_thinking_{timestamp}.txt"
        
        with open(chapter_filename, 'w', encoding='utf-8') as f:
            f.write(cleaned_response)
            
        with open(thinking_filename, 'w', encoding='utf-8') as f:
            f.write(thinking_content)
            
        print(f"Chapter saved to: {chapter_filename}")
        print(f"Thinking saved to: {thinking_filename}")
        
    else:
        print(f"Job status: {message.status} - not yet complete")
        if message.status == "in_progress":
            print("The job is still processing. Try again later.")
        
except Exception as e:
    print(f"Error retrieving results: {e}")
    print("The results may no longer be available if it's been more than 30 days")
"""
    
    with open("retrieve_chapter.py", 'w', encoding='utf-8') as f:
        f.write(retrieval_script)


def save_message_id(message_id, chapter_num, formatted_chapter):
    """Save the message ID to a file for later retrieval"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    info = {
        "message_id": message_id,
        "chapter_num": chapter_num,
        "timestamp": timestamp,
        "request": args.request
    }
    
    filename = f"{args.save_dir}/{formatted_chapter}_message_id_{timestamp}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2)
    
    print(f"Message ID saved to: {filename}")
    print(f"To retrieve results later, run: python retrieve_chapter.py {message_id}")


# Main script execution starts here
chapter_num, formatted_chapter = extract_chapter_num(args.request)
print(f"Preparing for Chapter: {chapter_num}")

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
    print("The manuscript file is required to continue.")
    exit(1)

try:
    with open(args.characters, 'r', encoding='utf-8') as file:
        characters_content = file.read()
except FileNotFoundError:
    print(f"Note: Characters file not found: {args.characters}")
    print("Continuing without characters information.")
    characters_content = ""
except Exception as e:
    print(f"Warning: Could not read characters file: {e}")
    print("Continuing without characters information.")
    characters_content = ""

# Create prompt with explicit instructions for AI
prompt = f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== CHARACTERS ===
{characters_content}
=== END CHARACTERS ===

=== EXISTING MANUSCRIPT ===
{novel_content}
=== END EXISTING MANUSCRIPT ===

You are a skilled novelist writing Chapter {args.request} in fluent, authentic {args.lang}. 
Draw upon your knowledge of worldwide literary traditions, narrative techniques, and creative approaches from across cultures, while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Consider the following in your thinking:
- Refer to the included CHARACTERS, if provided
- IMPORTANT: always review the included OUTLINE
- How this chapter advances the overall narrative and character development
- Creating compelling opening and closing scenes
- Incorporating sensory details and vivid descriptions
- Maintaining consistent tone and style with previous chapters

IMPORTANT:
1. NO Markdown formatting
2. NO ellipsis  NO em dash  NO '.,-'  NO ',-'  NO '-,'  NO '--'  NO '*'
3. Use hyphens only for legitimate {args.lang} words
4. Begin with "Chapter {args.request}" and write in plain text only
5. Write 1,800-2,500 words
6. Do not repeat content from existing chapters
7. Do not start working on the next chapter
8. Maintain engaging narrative pacing through varied sentence structure, strategic scene transitions, and appropriate balance between action, description, and reflection
9. Prioritize natural, character-revealing dialogue as the primary narrative vehicle, ensuring each conversation serves multiple purposes (character development, plot advancement, conflict building). Include distinctive speech patterns for different characters, meaningful subtext, and strategic dialogue beats, while minimizing lengthy exposition and internal reflection.
10. Write all times in 12-hour numerical format with a space before lowercase am/pm (e.g., "10:30 am," "2:15 pm," "7:00 am") rather than spelling them out as words or using other formats
11. In your 'thinking' before writing always indicate and explain what you're using from: CHARACTERS, OUTLINE, and MANUSCRIPT (previous chapters)
"""

# Create a version of the prompt without the outline, characters, manuscript:
prompt_for_logging = f"""You are a skilled novelist writing Chapter {args.request} in fluent, authentic {args.lang}. 
Draw upon your knowledge of worldwide literary traditions, narrative techniques, and creative approaches from across cultures, while expressing everything in natural, idiomatic {args.lang} that honors its unique linguistic character.

Consider the following in your thinking:
- Refer to the included CHARACTERS, if provided
- IMPORTANT: always review the included OUTLINE thoroughly 
- How this chapter advances the overall narrative and character development
- Creating compelling opening and closing scenes
- Incorporating sensory details and vivid descriptions
- Maintaining consistent tone and style with previous chapters

IMPORTANT:
1. NO Markdown formatting
2. NO ellipsis  NO em dash  NO '.,-'  NO ',-'  NO '-,'  NO '--'  NO '*'
3. Use hyphens only for legitimate {args.lang} words
4. Begin with "Chapter {args.request}" and write in plain text only
5. Write 1,800-2,500 words
6. Do not repeat content from existing chapters
7. Do not start working on the next chapter
8. Maintain engaging narrative pacing through varied sentence structure, strategic scene transitions, and appropriate balance between action, description, and reflection
9. Prioritize natural, character-revealing dialogue as the primary narrative vehicle, ensuring each conversation serves multiple purposes (character development, plot advancement, conflict building). Include distinctive speech patterns for different characters, meaningful subtext, and strategic dialogue beats, while minimizing lengthy exposition and internal reflection.
10. Write all times in 12-hour numerical format with a space before lowercase am/pm (e.g., "10:30 am," "2:15 pm," "7:00 am") rather than spelling them out as words or using other formats
11. In your 'thinking' before writing always indicate and explain what you're using from: CHARACTERS, OUTLINE, and MANUSCRIPT (previous chapters)
note: The actual prompt included the outline, characters, manuscript which are not logged to save space.
"""

# Calculate a safe max_tokens value
estimated_input_tokens = int(len(prompt) // 5.5)
max_safe_tokens = max(5000, args.context_window - estimated_input_tokens - 1000)  # 1000 token buffer for safety
max_tokens = int(min(args.max_tokens, max_safe_tokens))

absolute_path = os.path.abspath(args.save_dir)

print(f"Max request timeout: {args.request_timeout} seconds")
print(f"Max retries: 0 (anthropic's default was 2)")
print(f"Max AI model context window: {args.context_window} tokens")
print(f"AI model thinking budget: {args.thinking_budget} tokens")
print(f"Max output tokens: {args.max_tokens} tokens")
print(f"Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})")

# Ensure max_tokens is always greater than thinking budget
if max_tokens <= args.thinking_budget:
    max_tokens = args.thinking_budget + args.max_tokens
    print(f"Adjusted max_tokens to {max_tokens} to exceed thinking budget of {args.thinking_budget} (room for thinking/writing)")

print(f"Estimated input/prompt tokens: {estimated_input_tokens}")

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
    print(f"Actual input/prompt tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)")
except Exception as e:
    print(f"Error:\n{e}\n")

start_time = time.time()

dt = datetime.fromtimestamp(start_time)
formatted_time = dt.strftime("%A %B %d, %Y %I:%M:%S %p").replace(" 0", " ").lower()
print(f"****************************************************************************")
print(f"*  sending to API at: {formatted_time}")
print(f"*  ... standby, as this usually takes several minutes")
print(f"*  Using BATCH API with thinking budget: {args.thinking_budget} tokens")
print(f"*  ")
if args.no_wait:
    print(f"*  You've selected 'no_wait' mode. The script will start the job")
    print(f"*  and provide a message ID for you to retrieve results later.")
else:
    print(f"*  The script will poll for results every {args.polling_interval} seconds")
    print(f"*  until completion or until the timeout ({args.request_timeout} seconds).")
print(f"****************************************************************************")

# Create the batch request
message_id = create_batch_request(client, prompt, max_tokens, args.thinking_budget)
print(f"\nBatch request created with message ID: {message_id}")

# Save the message ID to a file
save_message_id(message_id, chapter_num, formatted_chapter)

# If no_wait flag is set, exit now
if args.no_wait:
    print("\nYou chose not to wait for completion. Your chapter is being generated.")
    print("You can retrieve it later using the message ID.")
    print("To retrieve the results later, run:")
    print(f"python retrieve_chapter.py {message_id}")
    
    # Create the retrieval script
    create_retrieval_script()
    
    sys.exit(0)

# Calculate maximum polling attempts based on timeout
max_attempts = args.request_timeout // args.polling_interval
results = retrieve_batch_result(client, message_id, args.polling_interval, max_attempts)

# Processing results
full_response = results["response"]
thinking_content = results["thinking"]

elapsed = time.time() - start_time
minutes = int(elapsed // 60)
seconds = elapsed % 60

cleaned_response = clean_text_formatting(full_response)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
chapter_filename = f"{args.save_dir}/{formatted_chapter}_chapter_{timestamp}.txt"
with open(chapter_filename, 'w', encoding='utf-8') as file:
    file.write(cleaned_response)

chapter_word_count = count_words(cleaned_response)

print(f"\nElapsed time: {minutes} minutes, {seconds:.2f} seconds.")
print(f"Chapter: {chapter_num} has {chapter_word_count} words (includes chapter title).")

chapter_token_count = 0
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
    chapter_token_count = response.input_tokens
    print(f"Chapter: {chapter_num}'s text is {chapter_token_count} tokens (via free client.beta.messages.count_tokens)")
except Exception as e:
    print(f"Error:\n{e}\n")

stats = f"""
Details:
Max request timeout: {args.request_timeout} seconds
Max retries: 0 (anthropic's default was 2)
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget} tokens
Max output tokens: {args.max_tokens} tokens

Estimated input/prompt tokens: {estimated_input_tokens} (includes: outline, entire novel, and prompt)
Actual input/prompt tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)
Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})

Elapsed time: {minutes} minutes, {seconds:.2f} seconds
Chapter: {chapter_num} has {chapter_word_count} words (includes chapter title)
Chapter: {chapter_num}'s text is {chapter_token_count} tokens (via free client.beta.messages.count_tokens)
New chapter saved to: {chapter_filename}
Message ID: {message_id}
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
    print(f"AI thinking saved to: {thinking_filename}\n")
    print(f"Files saved to: {absolute_path}")
else:
    print(f"New chapter saved to: {chapter_filename}")
    print("No AI thinking content was captured.\n")
    print(f"Files saved to: {absolute_path}")

print(f"###\n")
