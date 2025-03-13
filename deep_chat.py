# python -B deep_chat.py --request "Explain quantum computing in simple terms" --thinking_budget 32000 --max_tokens 12000
# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
from datetime import datetime

parser = argparse.ArgumentParser(description='Have a deep chat with Claude with extended thinking time.')
parser.add_argument('--request', type=str, required=True, help="Your chat request or question")
parser.add_argument('--request_timeout', type=int, default=300, help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds or about 5 minutes)')
parser.add_argument('--thinking_budget', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
parser.add_argument('--max_tokens', type=int, default=12000, help='Maximum tokens for output (default: 12000)')
parser.add_argument('--context_window', type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir', type=str, default=".", help='Directory to save output files (default: current directory)')
parser.add_argument('--chat_history', type=str, default=None, help='Optional chat history text file to continue a conversation')
parser.add_argument('--chat_output', type=str, default=None, help='Filename to save the updated chat history (default: chat_history_TIMESTAMP.txt)')
args = parser.parse_args()

def count_words(text):
    """Count the number of words in a text."""
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())

def create_directory_if_not_exists(directory):
    """Create directory if it doesn't exist."""
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

# Create save directory if it doesn't exist
create_directory_if_not_exists(args.save_dir)

# Load chat history if provided
chat_history_text = ""
if args.chat_history:
    try:
        with open(args.chat_history, 'r', encoding='utf-8') as file:
            chat_history_text = file.read()
        print(f"Loaded chat history from: {args.chat_history}")
    except FileNotFoundError:
        print(f"Note: Chat history file not found: {args.chat_history}")
        print("Starting a new conversation.")
    except Exception as e:
        print(f"Warning: Could not load chat history file: {e}")
        print("Starting a new conversation.")

# Prepare the prompt with chat history and current request
prompt = ""
if chat_history_text:
    prompt = chat_history_text
    if not prompt.endswith("\n\n"):
        prompt += "\n\n"
    prompt += f"User: {args.request}"
else:
    prompt = f"User: {args.request}"

# Calculate a safe max_tokens value
estimated_input_tokens = int(len(prompt) // 4)  # Conservative estimate
total_estimated_input_tokens = estimated_input_tokens

max_safe_tokens = max(5000, args.context_window - total_estimated_input_tokens - 2000)  # 2000 token buffer for safety
# Use the minimum of the requested max_tokens and what we calculated as safe:
max_tokens = int(min(args.max_tokens, max_safe_tokens))

absolute_path = os.path.abspath(args.save_dir)

print(f"Deep Chat with Claude (Extended Thinking Mode)")
print(f"==============================================")
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

print(f"Estimated input tokens: {total_estimated_input_tokens}")
print(f"==============================================")

client = anthropic.Anthropic(
    timeout=args.request_timeout,
    max_retries=0  # default is 2
)

# Count tokens if possible
prompt_token_count = 0
try:
    # For accurate counting
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
    print(f"Actual input tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)")
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
                    # Display the response in real-time
                    print(event.delta.text, end='', flush=True)
except Exception as e:
    print(f"\nError during API call:\n{e}\n")

print("\n")  # Add a newline after the response for better formatting

elapsed = time.time() - start_time
minutes = int(elapsed // 60)
seconds = elapsed % 60

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
response_filename = f"{args.save_dir}/chat_response_{timestamp}.txt"
with open(response_filename, 'w', encoding='utf-8') as file:
    file.write(full_response)

response_word_count = count_words(full_response)

print(f"\nElapsed time: {minutes} minutes, {seconds:.2f} seconds.")
print(f"Response has {response_word_count} words.")

response_token_count = 0
try:
    count_response = client.beta.messages.count_tokens(
        model="claude-3-7-sonnet-20250219",
        messages=[{"role": "user", "content": full_response}],
        thinking={
            "type": "enabled",
            "budget_tokens": args.thinking_budget
        },
        betas=["output-128k-2025-02-19"]
    )
    response_token_count = count_response.input_tokens
    print(f"Response text is {response_token_count} tokens (via free client.beta.messages.count_tokens)")
except Exception as e:
    print(f"Error counting tokens:\n{e}\n")

stats = f"""
Details:
Max request timeout: {args.request_timeout} seconds
Max retries: 0 (anthropic's default was 2)
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget} tokens
Max output tokens: {args.max_tokens} tokens

Estimated input tokens: {total_estimated_input_tokens}
Actual input tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)
Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})

Elapsed time: {minutes} minutes, {seconds:.2f} seconds
Response has {response_word_count} words
Response text is {response_token_count} tokens (via free client.beta.messages.count_tokens)
Response saved to: {response_filename}
###
"""

if thinking_content:
    thinking_filename = f"{args.save_dir}/chat_thinking_{timestamp}.txt"
    with open(thinking_filename, 'w', encoding='utf-8') as file:
        file.write("=== REQUEST ===\n")
        file.write(args.request)
        file.write("\n\n=== AI'S THINKING PROCESS ===\n\n")
        file.write(thinking_content)
        file.write("\n=== END AI'S THINKING PROCESS ===\n")
        file.write(stats)
    print(f"Response saved to: {response_filename}")
    print(f"AI thinking saved to: {thinking_filename}\n")
    print(f"Files saved to: {absolute_path}")
else:
    print(f"Response saved to: {response_filename}")
    print("No AI thinking content was captured.\n")
    print(f"Files saved to: {absolute_path}")

# Save chat history
chat_output_filename = args.chat_output
if not chat_output_filename:
    chat_output_filename = f"{args.save_dir}/chat_history_{timestamp}.txt"

# Create updated chat history
updated_chat_history = chat_history_text
if updated_chat_history and not updated_chat_history.endswith("\n\n"):
    updated_chat_history += "\n\n"
if not updated_chat_history:
    updated_chat_history = f"User: {args.request}\n\nAssistant: {full_response}"
else:
    updated_chat_history += f"User: {args.request}\n\nAssistant: {full_response}"

with open(chat_output_filename, 'w', encoding='utf-8') as file:
    file.write(updated_chat_history)

print(f"Chat history saved to: {chat_output_filename}")
print(f"###\n")

# Print a simple help message for continuation
print(f"To continue this conversation, use:")
print(f"python deep_chat.py --request \"Your next question\" --chat_history \"{chat_output_filename}\" --chat_output \"{chat_output_filename}\"")
