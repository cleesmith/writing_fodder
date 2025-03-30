#!/usr/bin/env python
"""
Example script that imports tokens_words_counter.py as a module
and demonstrates how to use it programmatically.
"""

import tokens_words_counter
import os

def main():
    # Example file path - replace with your actual file
    input_file = "sample_text.txt"
    
    print(f"===== EXAMPLE 1: Basic usage with default parameters =====")
    # This returns True if budget is sufficient, False otherwise
    has_sufficient_budget = tokens_words_counter.main(input_file)
    
    if has_sufficient_budget:
        print(f"\nFile '{input_file}' has sufficient thinking budget")
    else:
        print(f"\nFile '{input_file}' does NOT have sufficient thinking budget")
    
    print("\n" + "="*60 + "\n")
    
    print(f"===== EXAMPLE 2: Using explicit parameters =====")
    # Using the same original hardcoded values explicitly
    custom_results = tokens_words_counter.main(
        file_path=input_file,
        context_window=200000,
        betas_max_tokens=128000,
        thinking_budget_tokens=32000,
        desired_output_tokens=12000,
        request_timeout=300,
        return_results=True
    )
    
    if custom_results:
        print("\nResults with explicit parameters:")
        print(f"- Word count: {custom_results['word_count']}")
        print(f"- Token count: {custom_results['token_count']}")
        print(f"- Thinking budget: {custom_results['thinking_budget']}")
        print(f"- Has sufficient budget: {custom_results['has_sufficient_budget']}")

if __name__ == "__main__":
    main()
