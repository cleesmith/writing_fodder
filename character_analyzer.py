#!/usr/bin/env python
# character_analyzer.py
#
# Description: Analyzes manuscript, outline, and world files to identify and compare
#              character appearances across different story documents using the Claude API.
#
# Usage: 
# python -B character_analyzer.py --manuscript_file manuscript.txt --outline_file outline.txt --world_file world.txt

import anthropic
import pypandoc
import os
import argparse
import sys
import time
from datetime import datetime


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Analyze characters across story files using Claude AI.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B character_analyzer.py --manuscript_file manuscript.txt --outline_file outline.txt --world_file world.txt
  python -B character_analyzer.py --manuscript_file manuscript.txt --outline_file outline.txt
  python -B character_analyzer.py --manuscript_file manuscript.txt --world_file world.txt
  python -B character_analyzer.py --manuscript_file manuscript.txt --save_dir reports
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--manuscript_file', type=str, required=True,
                           help="File containing the manuscript to analyze (required)")
    input_group.add_argument('--outline_file', type=str, default=None,
                           help="File containing the story outline (optional)")
    input_group.add_argument('--world_file', type=str, default=None,
                           help="File containing the story world/lore information (optional)")

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
                            help='Directory to save character analysis reports (default: current directory)')
    output_group.add_argument('--skip_thinking', action='store_true',
                            help='Skip saving the AI thinking process (smaller output files)')
    output_group.add_argument('--analysis_description', type=str, default="",
                            help="Optional description to include in output filenames")

    return parser.parse_args()


def read_file(file_path, file_type):
    """Read file content with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        print(f"Loaded {file_type} from: {file_path}")
        return content
    except FileNotFoundError:
        print(f"Error: {file_type.capitalize()} file not found: {file_path}")
        if file_type == 'manuscript':  # Required file
            print(f"Please provide a valid {file_type} file.")
            sys.exit(1)
        else:  # Optional files
            print(f"Continuing without {file_type} information.")
            return ""
    except Exception as e:
        print(f"Error: Could not read {file_type} file: {e}")
        if file_type == 'manuscript':  # Required file
            sys.exit(1)
        else:  # Optional files
            print(f"Continuing without {file_type} information.")
            return ""

def count_words(text):
    """Count the number of words in a text string."""
    return len(text.split())

def strip_markdown(md_text):
    try:
        plain_text = pypandoc.convert_text(md_text, 'plain', format='markdown')
        plain_text = plain_text.replace("\u00A0", " ")
        return plain_text
    except Exception as e:
        print(f"Error converting markdown to plain text: {e}")
        print("Make sure pypandoc and pandoc are properly installed.")
        return md_text  # return original text if conversion fails

def create_character_analysis_prompt(manuscript_content, outline_content="", world_content=""):
    """Create a prompt for the AI to analyze characters across files."""
    
    # Determine which files we have
    has_outline = bool(outline_content.strip())
    has_world = bool(world_content.strip())
    
    # Construct file sections
    file_sections = "=== MANUSCRIPT ===\n{}\n=== END MANUSCRIPT ===\n".format(manuscript_content)
    
    if has_outline:
        file_sections = "=== OUTLINE ===\n{}\n=== END OUTLINE ===\n\n".format(outline_content) + file_sections
    
    if has_world:
        file_sections = "=== WORLD ===\n{}\n=== END WORLD ===\n\n".format(world_content) + file_sections
    
    # Build instruction section
    instructions = """IMPORTANT: NO Markdown formatting

You are an expert literary analyst specializing in character identification and analysis. Analyze the provided story files to identify all characters that appear in each file.

Your task is to create a comprehensive character analysis with these sections:

1. MASTER CHARACTER LIST:
   - Create a master list of ALL characters found across all provided files
   - For each character, specify in which file(s) they appear: manuscript, outline, and/or world
   - Include character names, aliases, titles, and roles where identifiable
   - Group related characters if appropriate (e.g., family members, teams)

2. CHARACTER PRESENCE ANALYSIS:
   - List characters that appear in the manuscript but NOT in the outline or world files
   - For each such character, provide:
     a) Brief description based on manuscript context
     b) An assessment of whether the character appears to be a deliberate addition or a potential inconsistency

3. CHARACTER CONSISTENCY ANALYSIS:
   - Identify any notable differences in how characters are portrayed across files
   - Note changes in names, titles, roles, or relationships
   - Highlight any potential continuity issues or contradictions

4. RECOMMENDATIONS:
   - Suggest which characters from the manuscript might need to be added to the outline/world files
   - Identify characters that might benefit from consolidation or clarification
   - Highlight any character-related issues that might impact story coherence

Format your analysis as a clear, organized report with sections and subsections. Use plain text formatting only (NO Markdown). Use numbered or bulleted lists where appropriate for clarity.

Be comprehensive in your character identification, capturing not just main characters but also secondary and minor characters that appear in any file."""

    # Combine all sections
    prompt = file_sections + "\n" + instructions
    
    return prompt

def run_character_analysis(manuscript_content, outline_content, world_content, args):
    """Run character analysis using Claude API and return results."""
    prompt = create_character_analysis_prompt(manuscript_content, outline_content, world_content)

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
                "budget_tokens": args.thinking_budget_tokens
            },
            betas=["output-128k-2025-02-19"]
        )
        prompt_token_count = response.input_tokens
        print(f"Actual input/prompt tokens: {prompt_token_count}")
    except Exception as e:
        print(f"Token counting error: {e}")

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

    print(f"Running character analysis...")
    print(f"\nToken stats:")
    print(f"Max AI model context window: [{args.context_window}] tokens")
    print(f"Input prompt tokens: [{prompt_tokens}]")
    print(f"Available tokens: [{available_tokens}]  = {args.context_window} - {prompt_tokens}")
    print(f"Desired output tokens: [{args.desired_output_tokens}]")
    print(f"AI model thinking budget: [{thinking_budget}] tokens")
    print(f"Max output tokens (max_tokens): [{max_tokens}] tokens")
    
    if thinking_budget < args.thinking_budget_tokens:
        print(f"Error: prompt is too large to have a {args.thinking_budget_tokens} thinking budget!")
        sys.exit(1)
    
    full_response = ""
    thinking_content = ""
    
    start_time = time.time()
    print(f"Sending request to Claude API...")
    
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
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "thinking_delta":
                        thinking_content += event.delta.thinking
                    elif event.delta.type == "text_delta":
                        full_response += event.delta.text
    except Exception as e:
        print(f"\nAPI Error:\n{e}\n")
        return "", "", 0, 0
    
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    
    report_word_count = count_words(full_response)
    print(f"\nCompleted in {minutes}m {seconds:.2f}s.\nReport has {report_word_count} words.")
    
    # Get token count for response
    report_token_count = 0
    try:
        response = client.beta.messages.count_tokens(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": full_response}],
            thinking={
                "type": "enabled",
                "budget_tokens": thinking_budget
            },
            betas=["output-128k-2025-02-19"]
        )
        report_token_count = response.input_tokens
    except Exception as e:
        print(f"Response token counting error:\n{e}\n")
    
    # convert any Markdown formatting to plain text
    plain_text_response = strip_markdown(full_response)
    
    return plain_text_response, thinking_content, prompt_token_count, report_token_count

def save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats):
    """Save the character analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"character_analysis{desc}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== CHARACTER ANALYSIS ===\n\n")
            file.write("=== AI'S THINKING PROCESS ===\n\n")
            file.write(strip_markdown(thinking_content))  # Also strip markdown from thinking content
            file.write("\n=== END AI'S THINKING PROCESS ===\n")
            file.write(stats)
        print(f"AI thinking saved to: {thinking_filename}")
    
    print(f"Report saved to: {report_filename}")
    return report_filename

def main():
    args = parse_arguments()
    
    manuscript_content = read_file(args.manuscript_file, "manuscript")
    outline_content = read_file(args.outline_file, "outline") if args.outline_file else ""
    world_content = read_file(args.world_file, "world") if args.world_file else ""
    
    current_time = datetime.now().strftime("%I:%M:%S %p").lower().lstrip("0")
    print("\n=== Character Analyzer Configuration ===")
    print(f"Input files:")
    print(f"  - Manuscript: {args.manuscript_file}")
    print(f"  - Outline: {args.outline_file if args.outline_file else 'Not provided'}")
    print(f"  - World: {args.world_file if args.world_file else 'Not provided'}")
    print(f"Max request timeout: {args.request_timeout} seconds for each streamed chunk")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    full_response, thinking_content, prompt_token_count, report_token_count = run_character_analysis(
        manuscript_content, outline_content, world_content, args
    )
    
    if full_response:
        stats = f"""
Details:
Analysis type: Character analysis
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
        
        save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats)
    else:
        print("Failed to complete character analysis.")

if __name__ == "__main__":
    main()
