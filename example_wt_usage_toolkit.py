#!/usr/bin/env python
# tokens_words_counter.py
#
# Description: A tool to count tokens and words in text files
#              using the Anthropic API and calculate thinking budgets.
#
# Usage: 
# python -B tokens_words_counter.py --text_file input.txt
# python -B tokens_words_counter.py --text_file input.txt --context_window 200000 --thinking_budget_tokens 32000

import anthropic
import argparse
import sys
import io
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
  python -B tokens_words_counter.py --text_file input.txt
  python -B tokens_words_counter.py --text_file input.txt --context_window 200000 --thinking_budget_tokens 32000
  python -B tokens_words_counter.py --text_file input.txt --desired_output_tokens 20000
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
    # cls: this is ignored, as the tool only outputs counts
    output_group.add_argument('--save_dir', type=str, default=".",
                            help='Directory to save character analysis reports (default: current directory)')

    return parser.parse_args()

def read_text_file(file_path):
    """Read text file content with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if not content.strip():
            print(f"Error: text file '{file_path}' is empty.")
            if __name__ == "__main__":
                sys.exit(1)
            else:
                return None
        return content
    except FileNotFoundError:
        print(f"Error: text file '{file_path}' not found.")
        if __name__ == "__main__":
            sys.exit(1)
        else:
            return None
    except Exception as e:
        print(f"Error reading text file '{file_path}': {e}")
        if __name__ == "__main__":
            sys.exit(1)
        else:
            return None

def count_tokens(client, text):
    """Count tokens in text using Anthropic API."""
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
        if __name__ == "__main__":
            sys.exit(1)
        else:
            return 0

def count_words(text):
    """Count the number of words in a text string."""
    return len(text.split())

def main(file_path=None, context_window=200000, betas_max_tokens=128000, 
         thinking_budget_tokens=32000, desired_output_tokens=12000, 
         request_timeout=300, return_results=False):
    """
    Main function that can be called directly or via command line.
    
    Args:
        file_path (str, optional): Path to the text file to analyze
        context_window (int): Context window size for Claude
        betas_max_tokens (int): Maximum tokens for AI output
        thinking_budget_tokens (int): Maximum tokens for AI thinking
        desired_output_tokens (int): User desired output tokens
        request_timeout (int): API request timeout in seconds
        return_results (bool): Whether to return results as a dictionary
        
    Returns:
        bool or dict: If return_results is False, returns True if thinking budget is sufficient
                      If return_results is True, returns a dictionary with analysis results
    """
    # Parse arguments from command line if file_path not provided
    if file_path is None:
        args = parse_arguments()
        file_path = args.text_file
        context_window = args.context_window
        betas_max_tokens = args.betas_max_tokens
        thinking_budget_tokens = args.thinking_budget_tokens
        desired_output_tokens = args.desired_output_tokens
        request_timeout = args.request_timeout
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(
        timeout=request_timeout,
        max_retries=0
    )
    
    # Read text file
    text = read_text_file(file_path)
    if text is None:
        return None if return_results else False
    
    # Count words
    word_count = count_words(text)
    
    # Count tokens
    print(f"Counting tokens for text file: {file_path}")
    prompt_token_count = count_tokens(client, text)
    if prompt_token_count == 0:
        return None if return_results else False
    
    # Calculate available tokens after prompt
    prompt_tokens = prompt_token_count
    available_tokens = context_window - prompt_tokens
    
    # For API call, max_tokens must respect the API limit
    max_tokens = min(available_tokens, betas_max_tokens)
    
    # Thinking budget must be LESS than max_tokens to leave room for visible output
    thinking_budget = max_tokens - desired_output_tokens
    
    if thinking_budget > 32000:
        print(f"Warning: thinking budget is larger than 32K, reset to 32K. Use batch for larger thinking budgets.")
        thinking_budget = 32000
    
    # Display results
    print(f"\nToken stats:")
    print(f"Word count: {word_count}")
    print(f"Max AI model context window: [{context_window}] tokens")
    print(f"Input prompt tokens: [{prompt_tokens}]")
    print(f"Available tokens: [{available_tokens}] = {context_window} - {prompt_tokens}")
    print(f"Desired output tokens: [{desired_output_tokens}]")
    print(f"AI model thinking budget: [{thinking_budget}] tokens")
    print(f"Max output tokens (max_tokens): [{max_tokens}] tokens")
    
    has_sufficient_budget = thinking_budget >= thinking_budget_tokens
    
    if not has_sufficient_budget:
        print(f"Error: prompt is too large to have a {thinking_budget_tokens} thinking budget!")
        if __name__ == "__main__" and not return_results:
            sys.exit(1)
    else:
        print(f"✓ Thinking budget is sufficient!")
        print(f"✓ Text is ready for use with requested thinking budget of {thinking_budget_tokens} tokens")
        
    # Words per token ratio
    words_per_token = word_count / prompt_tokens if prompt_tokens > 0 else 0
    print(f"Words per token ratio: {words_per_token:.2f}\n")
    
    # Simple summary output at the end
    print(f"\n***************************************************************************")
    print(f"Counts for text file: {file_path}")
    print(f"\n{word_count} words\n")
    print(f"\n{prompt_tokens} tokens using 'client.beta.messages.count_tokens'")
    print(f"\n***************************************************************************")
    
    if return_results:
        return {
            "word_count": word_count,
            "token_count": prompt_tokens,
            "available_tokens": available_tokens,
            "thinking_budget": thinking_budget,
            "max_tokens": max_tokens,
            "words_per_token": words_per_token,
            "has_sufficient_budget": has_sufficient_budget
        }
    
    return has_sufficient_budget

if __name__ == "__main__":
    main()
