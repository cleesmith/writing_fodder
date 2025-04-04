# codechat.py - Code rewriting and analysis tool
# python -B codechat.py --file writers_toolkit.py --task "stop using tools_config.json directly, and replace with TinyDB"
# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
import os
import argparse
import re
import sys
import time
from datetime import datetime

parser = argparse.ArgumentParser(description='Analyze and rewrite code files.')
parser.add_argument('--file', type=str, required=True, help="Path to Python file to analyze or rewrite")
parser.add_argument('--task', type=str, required=True, help="Description of what to do with the code (optimize, explain, refactor, etc.)")
parser.add_argument('--output_file', type=str, help="File to write the modified code to (defaults to {original}_rewritten.py)")

parser.add_argument('--request_timeout', type=int, default=300, help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds = 5 minutes)')
parser.add_argument('--max_retries', type=int, default=0, help='Maximum times to retry request, may get expensive if too many')
parser.add_argument('--context_window', type=int, default=200000, help='Context window for Claude 3.7 Sonnet (default: 200000)')
parser.add_argument('--betas_max_tokens', type=int, default=128000, help='Maximum tokens for AI output (default: 128000)')
parser.add_argument('--thinking_budget_tokens', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
parser.add_argument('--desired_output_tokens', type=int, default=8000, help='User desired number of tokens to generate before stopping output')
parser.add_argument('--show_token_stats',       action='store_true', help='Show tokens stats but do not call API (default: False)')

parser.add_argument('--save_dir', type=str, default=".")
args = parser.parse_args()

def count_words(text):
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())

def read_file(filepath):
    """
    Read the code file and return its content as a string.
    Abort if the file doesn't exist.
    """
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return content.strip()

def save_output(filename, content):
    """
    Save the generated content to a file
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved output to: {filename}")

def calculate_max_tokens(prompt):
    try:
        # Get accurate token count for prompt
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": prompt}],
            thinking={
                "type": "enabled",
                "budget_tokens": args.thinking_budget_tokens
            },
            betas=["output-128k-2025-02-19"]
        )

        # calculate available tokens after prompt
        prompt_tokens = response.input_tokens
        available_tokens = args.context_window - prompt_tokens
        # for API call, max_tokens must respect the API limit
        max_tokens = min(available_tokens, args.betas_max_tokens)
        # thinking budget must be LESS than max_tokens to leave room for visible output
        thinking_budget = max_tokens - args.desired_output_tokens

        if thinking_budget > args.thinking_budget_tokens:
            thinking_budget = 32000

        # ensure max_tokens is always greater than thinking budget
        if max_tokens <= args.thinking_budget_tokens:
            max_tokens = args.thinking_budget_tokens + args.desired_output_tokens
            print(f"Adjusted max_tokens to {max_tokens} to exceed thinking budget of {args.thinking_budget_tokens}")

        return max_tokens, prompt_tokens, available_tokens, thinking_budget
    except Exception as e:
        print(f"Error: client.beta.messages.count_tokens:\n{e}\n")
        sys.exit(1)

def create_code_prompt(code_content, task):
    """
    Create a prompt for code rewriting/analysis based on the file content and task
    """
    prompt = f"""You are an expert software developer helping to analyze and rewrite Python code that uses NiceGUI and TinyDB.
    
=== ORIGINAL CODE ===
{code_content}
=== END ORIGINAL CODE ===

TASK: {task}

Provide the following in your response:

1. IMPROVED CODE
   - Complete rewritten version of the code
   - Include ALL necessary imports
   - Maintain the same functionality while addressing the task

2. EXPLANATION
   - Explain the key changes made
   - Why these changes improve the code as per the task

IMPORTANT INSTRUCTIONS:
1. Keep the same overall functionality unless the task specifically requires changes
2. Maintain compatibility with existing interfaces
3. The rewritten code should be complete and ready to run
4. Format your code neatly with proper indentation and spacing
5. Include helpful comments where appropriate

Start with "1. IMPROVED CODE:" with a full rewrite of the code, and finally "2. EXPLANATION:" with your explanation.
"""
    return prompt


# Print initial setup information
print(f"Starting code analysis/rewriting for file: '{args.file}'")
file_path = os.path.abspath(args.file)
print(f"Absolute file path: {file_path}")
print(f"Task: {args.task}")
print(f"Save directory: {os.path.abspath(args.save_dir)}")
print(f"Max request timeout: {args.request_timeout} seconds")
print(f"Max retries: {args.max_retries}")
print(f"Context window: {args.context_window} tokens")
print(f"Betas max tokens: {args.betas_max_tokens} tokens")
print(f"Thinking budget tokens: {args.thinking_budget_tokens} tokens")
print(f"Desired output tokens: {args.desired_output_tokens} tokens")

code_content = read_file(args.file)

if code_content:
    code_lines = code_content.count('\n') + 1
    print(f"Code file contains {code_lines} lines")
else:
    print("Code file is empty")
    sys.exit(1)

client = anthropic.Anthropic(
    timeout=args.request_timeout,
    max_retries=args.max_retries
)

def process_code():
    prompt = create_code_prompt(code_content, args.task)
    
    max_tokens, prompt_tokens, available_tokens, thinking_budget = calculate_max_tokens(prompt)

    print(f"\nToken stats:")
    print(f"Max retries: {args.max_retries}")
    print(f"Max AI model context window: [{args.context_window}] tokens")
    print(f"Input prompt tokens: [{prompt_tokens}] ...")
    print(f"Available tokens: [{available_tokens}]  = {args.context_window} - {prompt_tokens} = context_window - prompt")
    print(f"Desired output tokens: [{args.desired_output_tokens}]")
    print(f"\nMax output tokens (max_tokens): [{max_tokens}] tokens  = min({available_tokens}, {args.betas_max_tokens})")
    print(f"                                   = can not exceed: 'betas=[\"output-128k-2025-02-19\"]'")
    print(f"AI model thinking budget: [{thinking_budget}] tokens  = {max_tokens} - {args.desired_output_tokens}")
    print(f"                           = can not exceed: 32K")
    if thinking_budget < args.thinking_budget_tokens:
        print(f"Error: prompt is too large to have a {args.thinking_budget_tokens} thinking budget!")
        sys.exit(1)

    if args.show_token_stats:
        print(f"FYI: token stats shown without sending to API, to aid in making adjustments.")
        sys.exit(1)
    
    print(f"\n--- Processing Code ---")
    
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
    except Exception as e:
        print(f"\nError during API call:\n{e}\n")
    
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Determine output filenames
    if args.output_file:
        output_filename = args.output_file
    else:
        base_name, ext = os.path.splitext(args.file)
        output_filename = f"{base_name}_rewritten{ext}"
    
    # Create analysis and results files
    results_filename = f"{args.save_dir}/code_results_{timestamp}.txt"
    
    # Extract the improved code section from the response
    improved_code_match = re.search(r'IMPROVED CODE:(.*?)(?:EXPLANATION:|$)', full_response, re.DOTALL)
    if improved_code_match:
        improved_code = improved_code_match.group(1).strip()
        # Remove any markdown code block formatting
        improved_code = re.sub(r'^```python\s*', '', improved_code, flags=re.MULTILINE)
        improved_code = re.sub(r'^```\s*$', '', improved_code, flags=re.MULTILINE)
        save_output(output_filename, improved_code)
    
    # Save the full analysis and results
    save_output(results_filename, full_response)
    
    output_word_count = count_words(full_response)
    
    print(f"\nElapsed time: {minutes} minutes, {seconds:.2f} seconds.")
    print(f"Generated response has {output_word_count} words.")
    
    output_token_count = 0
    try:
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": full_response}],
            thinking={
                "type": "enabled",
                "budget_tokens": args.thinking_budget_tokens
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
Max retries: {args.max_retries}
Max AI model context window: {args.context_window} tokens
Betas max tokens: {args.betas_max_tokens} tokens
Thinking budget tokens: {args.thinking_budget_tokens} tokens
Desired output tokens: {args.desired_output_tokens} tokens

Prompt tokens: {prompt_tokens}
Available tokens after prompt: {available_tokens}
Dynamic thinking budget: {thinking_budget} tokens
Setting max_tokens to: {max_tokens} (requested: {args.betas_max_tokens})

Elapsed time: {minutes} minutes, {seconds:.2f} seconds
Output has {output_word_count} words
Output is {output_token_count} tokens (via client.beta.messages.count_tokens)
Full response saved to: {results_filename}
"""
    
    if thinking_content:
        thinking_filename = f"{args.save_dir}/code_thinking_{timestamp}.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== PROMPT USED ===\n")
            file.write(prompt)
            file.write("\n\n=== AI'S THINKING PROCESS ===\n\n")
            file.write(thinking_content)
            file.write("\n=== END AI'S THINKING PROCESS ===\n")
            file.write(stats)
        print(f"AI thinking saved to: {thinking_filename}\n")
    else:
        print("No AI thinking content was captured.\n")
    
    return results_filename

try:
    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)
        print(f"Created directory: {args.save_dir}")
    
    results_file = process_code()
    
    print("\nCode processing complete!")
    print(f"Full analysis saved to: {results_file}")
    if args.output_file:
        print(f"Rewritten code saved to: {args.output_file}")
    else:
        base_name, ext = os.path.splitext(args.file)
        output_filename = f"{base_name}_rewritten{ext}"
        print(f"Rewritten code saved to: {output_filename}")
    
except Exception as e:
    print(f"\nAn error occurred: {e}")
    sys.exit(1)
finally:
    # clean up resources
    client = None

