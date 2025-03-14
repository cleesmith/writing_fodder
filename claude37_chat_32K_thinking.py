# python -B claude37_chat_32K_thinking.py --no_markdown
# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
from datetime import datetime

# Create argument parser
parser = argparse.ArgumentParser(description='Chat with Claude 3.7 Sonnet and 32K tokens of thinking.')

# Add all arguments - ensuring --request is NOT required
parser.add_argument('--request',         type=str, help="Your chat request or question (optional in chat mode)", default=None)
parser.add_argument('--request_timeout', type=int, default=300,    help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds or about 5 minutes)')
parser.add_argument('--thinking_budget', type=int, default=32000,  help='Maximum tokens for AI thinking (default: 32000)')
parser.add_argument('--max_tokens',      type=int, default=12000,  help='Maximum tokens for output (default: 12000)')
parser.add_argument('--context_window',  type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir',        type=str, default=".",    help='Directory to save output files (default: current directory)')
parser.add_argument('--chat_history',    type=str, default=None,   help='Optional chat history text file to continue a conversation')
parser.add_argument('--chat_output',     type=str, default=None,   help='Filename to save the updated chat history (default: chat_history_TIMESTAMP.txt)')
parser.add_argument('--no_markdown',     action='store_true',      help='Tell Claude not to respond with Markdown formatting')

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

# Initialize client
client = anthropic.Anthropic(
    timeout=args.request_timeout,
    max_retries=0  # default is 2
)

def process_chat_request(user_input, current_chat_history=""):
    """Process a single chat exchange with Claude"""
    
    # Prepare the prompt with chat history and current request
    prompt = ""
    
    # FIX: Prefix the no-markdown instruction directly to the user prompt if needed
    if args.no_markdown:
        prompt = "Never respond with Markdown formatting, plain text only.\n\n"
        
    if current_chat_history:
        prompt += current_chat_history
        if not prompt.endswith("\n\n"):
            prompt += "\n\n"
    
    # Add the current input to the prompt
    prompt += f"ME: {user_input}"

    # Calculate a safe max_tokens value
    estimated_input_tokens = int(len(prompt) // 4)  # Conservative estimate
    total_estimated_input_tokens = estimated_input_tokens

    max_safe_tokens = max(5000, args.context_window - total_estimated_input_tokens - 2000)  # 2000 token buffer for safety
    # Use the minimum of the requested max_tokens and what we calculated as safe:
    max_tokens = int(min(args.max_tokens, max_safe_tokens))

    # Ensure max_tokens is always greater than thinking budget
    if max_tokens <= args.thinking_budget:
        max_tokens = args.thinking_budget + args.max_tokens

    # Prepare messages list - simple user message with prefixed instruction
    messages = [{"role": "user", "content": prompt}]

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
            messages=messages,
            # No system parameter used - instruction is already in the prompt
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

    if thinking_content:
        thinking_filename = f"{args.save_dir}/chat_thinking_{timestamp}.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== REQUEST ===\n")
            file.write(user_input)
            file.write("\n\n=== AI THINKING PROCESS ===\n\n")
            file.write(thinking_content)
            file.write("\n=== END AI THINKING PROCESS ===\n")

    # Return both the response and updated chat history
    updated_history = current_chat_history
    if updated_history and not updated_history.endswith("\n\n"):
        updated_history += "\n\n"
    updated_history += f"ME: \n{user_input}\n\nAI: \n{full_response}\n"
    
    return full_response, updated_history

def run_interactive_chat():
    """Run an interactive chat loop with Claude"""
    print(f"Chat with Claude 3.7 Sonnet and 32K tokens of thinking")
    print(f"=======================================================")
    print(f"Type your messages and press Enter to send.")
    print(f"Type 'exit', 'quit', or 'bye' to end the conversation.")
    print(f"=======================================================")
    
    current_history = chat_history_text
    
    # Process initial request if provided
    if args.request:
        print(f"ME: \n{args.request}")
        _, current_history = process_chat_request(args.request, current_history)
    
    # Enter the chat loop
    while True:
        try:
            user_input = input("\nME: ")
            
            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Exiting chat. Goodbye!")
                break
            
            print()  # Add a blank line
            print("AI: \n", end='', flush=True)
            
            # Process the request
            _, current_history = process_chat_request(user_input, current_history)
            
        except KeyboardInterrupt:
            print("\nChat interrupted. Exiting.")
            break
        except EOFError:
            print("\nInput ended. Exiting.")
            break
    
    # Save the final chat history
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chat_output_filename = args.chat_output
    if not chat_output_filename:
        chat_output_filename = f"{args.save_dir}/chat_history_{timestamp}.txt"
    
    with open(chat_output_filename, 'w', encoding='utf-8') as file:
        file.write(current_history)
    
    print(f"Chat history saved to: {chat_output_filename}")

def run_single_request():
    """Process a single request and exit, as in the original script"""
    absolute_path = os.path.abspath(args.save_dir)

    print(f"Chat with Claude 3.7 Sonnet and 32K tokens of thinking.")
    print(f"=======================================================")
    print(f"Max request timeout: {args.request_timeout} seconds")
    print(f"Max retries: 0 (anthropic default was 2)")
    print(f"Max AI model context window: {args.context_window} tokens")
    print(f"AI model thinking budget: {args.thinking_budget} tokens")
    print(f"Max output tokens: {args.max_tokens} tokens")
    print(f"Markdown formatting: {'Disabled' if args.no_markdown else 'Enabled'}")
    print(f"==============================================")

    # Process the request
    _, updated_history = process_chat_request(args.request, chat_history_text)
    
    # Save chat history
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chat_output_filename = args.chat_output
    if not chat_output_filename:
        chat_output_filename = f"{args.save_dir}/chat_history_{timestamp}.txt"
    
    with open(chat_output_filename, 'w', encoding='utf-8') as file:
        file.write(updated_history)
    
    print(f"Chat history saved to: {chat_output_filename}")
    print(f"Files saved to: {absolute_path}")
    print(f"###\n")

    # Print a simple help message for continuation
    print(f"To continue this conversation, use:")
    print(f"python claude37_chat_32K_thinking.py --chat_history \"{chat_output_filename}\"")

# Main execution flow
if __name__ == "__main__":
    # Check if request is provided
    if args.request is not None:
        # Run in single request mode
        run_single_request()
    else:
        # Run in interactive mode
        run_interactive_chat()
