#!/usr/bin/env python
# tokens_counter.py
#
# Description: A tool to count tokens and words in text files
#              using the Anthropic API and calculate thinking budgets.
#
# Usage: 
# python -B tokens_counter.py --text_file input.txt
# python -B tokens_counter.py --text_file input.txt --context_window 200000 --thinking_budget_tokens 32000

import anthropic
import argparse
import sys
import io
import os
import time
from datetime import datetime

# Make stdout line-buffered (effectively the same as flush=True for each print)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Count tokens and words in a text file using Claude API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B tokens_counter.py --text_file input.txt
  python -B tokens_counter.py --text_file input.txt --context_window 200000 --thinking_budget_tokens 32000
  python -B tokens_counter.py --text_file input.txt --desired_output_tokens 20000
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--text_file', type=str, required=True,
                           help="File containing the text to analyze (required)")

    # Add arguments to the Claude API Configuration group
    api_group.add_argument('--context_window', type=int, default=200000, 
                         help='Context window for Claude 3.7 Sonnet (default: 200000)')
    api_group.add_argument('--betas_max_tokens', type=int, default=128000, 
                         help='Maximum tokens for AI output (default: 128000)')
    api_group.add_argument('--thinking_budget_tokens', type=int, default=32000, 
                         help='Maximum tokens for AI thinking (default: 32000)')
    api_group.add_argument('--desired_output_tokens', type=int, default=12000, 
                         help='User desired number of tokens to generate before stopping output')
    api_group.add_argument('--request_timeout', type=int, default=300,
                         help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds)')

    # Add arguments to the Output Configuration group
    output_group.add_argument('--save_dir', type=str, default=".",
                            help='Directory to save output files (default: current directory)')
    # Add output tracking parameter for Writer's Toolkit integration
    output_group.add_argument('--output_tracking', type=str, default=None,
                            help='UUID-based file for tracking output files (used by Writer\'s Toolkit)')

    return parser.parse_args()

def read_text_file(file_path):
    """Read text file content with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if not content.strip():
            print(f"Error: text file '{file_path}' is empty.")
            sys.exit(1)
        return content
    except FileNotFoundError:
        print(f"Error: text file '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading text file '{file_path}': {e}")
        sys.exit(1)

def count_tokens(client, text):
    """Count tokens in text using Anthropic API."""
    time.sleep(3) # just for testing, coz it costs $0.00
    try:
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            thinking={
                "type": "enabled",
                "budget_tokens": 128000
            },
            messages=[{"role": "user", "content": text}],
            betas=["output-128k-2025-02-19"]
        )
        return response.input_tokens
    except Exception as e:
        print(f"Token counting error: {e}")
        sys.exit(1)

def count_words(text):
    """Count the number of words in a text string."""
    return len(text.split())

def write_output_file(args, word_count, prompt_tokens, words_per_token, available_tokens, thinking_budget):
    """Write token and word count results to an output file."""
    # Create output filename based on input filename
    input_base = os.path.basename(args.text_file)
    input_name = os.path.splitext(input_base)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(args.save_dir, f"count_{input_name}_{timestamp}.txt")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # Write results to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Token and Word Count Report\n")
        f.write(f"=========================\n\n")
        f.write(f"Analysis of file: {args.text_file}\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Word count: {word_count}\n")
        f.write(f"Token count: {prompt_tokens}\n")
        f.write(f"Words per token ratio: {words_per_token:.2f}\n\n")
        f.write(f"Context window: {args.context_window} tokens\n")
        f.write(f"Available tokens: {available_tokens} tokens\n")
        f.write(f"Thinking budget: {thinking_budget} tokens\n")
        f.write(f"Desired output tokens: {args.desired_output_tokens} tokens\n")
    
    print(f"Report saved to: {output_file}")
    return os.path.abspath(output_file)

def write_output_tracking(tracking_file, created_files):
    """Write a list of created files to the specified tracking file."""
    print(f">>> tracking_file={tracking_file}")
    print(f"*** created_files={created_files}")
    if tracking_file:
        # try:
        # Ensure directory exists
        # os.makedirs(os.path.dirname(os.path.abspath(tracking_file)), exist_ok=True)
        # Write each file path on a separate line
        with open(tracking_file, 'w', encoding='utf-8') as file:
            for file_path in created_files:
                print(f"### file_path={file_path}")
                file.write(f"{file_path}\n")
        # except Exception as e:
        #     print(f"Error writing output tracking file: {e}")

def main():
    args = parse_arguments()
    
    client = anthropic.Anthropic(
        timeout=args.request_timeout,
        max_retries=0
    )
    
    text = read_text_file(args.text_file)
    word_count = count_words(text)
    
    print(f"Counting tokens for text file: {args.text_file}")
    prompt_token_count = count_tokens(client, text)
    
    # Calculate available tokens after prompt
    prompt_tokens = prompt_token_count
    available_tokens = args.context_window - prompt_tokens
    
    # For API call, max_tokens must respect the API limit
    max_tokens = min(available_tokens, args.betas_max_tokens)
    
    # Thinking budget must be LESS than max_tokens to leave room for visible output
    thinking_budget = max_tokens - args.desired_output_tokens
    
    if thinking_budget > 32000:
        print(f"Warning: thinking budget is larger than 32K, reset to 32K. Use batch for larger thinking budgets.")
        thinking_budget = 32000
    
    # Display results
    print(f"\nToken stats:")
    print(f"Word count: {word_count}")
    print(f"Max AI model context window: [{args.context_window}] tokens")
    print(f"Input prompt tokens: [{prompt_tokens}]")
    print(f"Available tokens: [{available_tokens}] = {args.context_window} - {prompt_tokens}")
    print(f"Desired output tokens: [{args.desired_output_tokens}]")
    print(f"AI model thinking budget: [{thinking_budget}] tokens")
    print(f"Max output tokens (max_tokens): [{max_tokens}] tokens")
    
    if thinking_budget < args.thinking_budget_tokens:
        print(f"Error: prompt is too large to have a {args.thinking_budget_tokens} thinking budget!")
        sys.exit(1)
    else:
        print(f"✓ Thinking budget is sufficient!")
        print(f"✓ Text is ready for use with requested thinking budget of {args.thinking_budget_tokens} tokens")
        
    # words per token ratio
    words_per_token = word_count / prompt_tokens if prompt_tokens > 0 else 0
    print(f"Words per token ratio: {words_per_token:.2f}\n")
    
    print(f"\n***************************************************************************")
    print(f"Counts for text file: {args.text_file}")
    print(f"\n{word_count} words\n")
    print(f"\n{prompt_tokens} tokens using 'client.beta.messages.count_tokens'")
    print(f"\n***************************************************************************")

    # Write output file with the results
    created_files = []
    output_file = write_output_file(args, word_count, prompt_tokens, words_per_token, 
                                    available_tokens, thinking_budget)
    created_files.append(output_file)
    
    # Write output tracking file if requested
    if args.output_tracking:
        print(f"args.output_tracking={args.output_tracking}")
        write_output_tracking(args.output_tracking, created_files)

if __name__ == "__main__":
    main()

