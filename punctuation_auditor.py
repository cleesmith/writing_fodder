#!/usr/bin/env python
# punctuation_auditor.py
#
# Description: Analyzes manuscript for punctuation effectiveness using the Claude API.
#              Identifies issues like run-on sentences, missing commas, and odd punctuation patterns
#              that might hinder clarity and flow, following Ursula K. Le Guin's writing principles.
#
# Usage: 
# python -B punctuation_auditor.py --manuscript_file manuscript.txt [--save_dir reports]

import anthropic
import pypandoc
import os
import argparse
import sys
import time
from datetime import datetime


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Analyze manuscript for punctuation effectiveness using Claude AI.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B punctuation_auditor.py --manuscript_file manuscript.txt --analysis_level detailed --strictness high
  python -B punctuation_auditor.py --manuscript_file manuscript.txt
  python -B punctuation_auditor.py --manuscript_file manuscript.txt --save_dir reports
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    analysis_group = parser.add_argument_group('Analysis Options')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--manuscript_file', type=str, required=True,
                           help="File containing the manuscript to analyze (required)")

    # Add arguments to the Analysis Options group
    analysis_group.add_argument('--analysis_level', type=str, default="standard",
                              choices=["basic", "standard", "detailed"],
                              help="Level of analysis detail (default: standard)")
    analysis_group.add_argument('--elements', type=str, nargs='+',
                              default=["commas", "periods", "semicolons", "dashes", "parentheses", "colons", "run-ons"],
                              help="Specific punctuation elements to focus on (default: all elements)")
    analysis_group.add_argument('--strictness', type=str, default="medium",
                              choices=["low", "medium", "high"],
                              help="Strictness level for punctuation analysis (default: medium)")

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
                            help='Directory to save analysis reports (default: current directory)')
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
        print(f"Please provide a valid {file_type} file.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not read {file_type} file: {e}")
        sys.exit(1)


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


def create_punctuation_analysis_prompt(manuscript_content, analysis_level, elements, strictness):
    """Create a prompt for the AI to analyze punctuation effectiveness."""
    
    # Build instruction section based on analysis level
    basic_instructions = """
1. PUNCTUATION OVERVIEW:
   - Analyze overall patterns of punctuation usage in the manuscript
   - Identify common punctuation habits
   - Note any immediate issues with basic punctuation (missing periods, etc.)

2. RUN-ON SENTENCE IDENTIFICATION:
   - Identify overly long sentences with inadequate punctuation
   - Flag sentences that may cause confusion due to length or structure
   - Suggest natural breaking points and punctuation improvements

3. COMMA USAGE ANALYSIS:
   - Highlight missing commas in compound sentences
   - Identify comma splices (two complete sentences joined only by a comma)
   - Point out necessary commas missing after introductory phrases
   - Note any patterns of comma overuse
"""

    standard_instructions = basic_instructions + """
4. SPECIALIZED PUNCTUATION ANALYSIS:
   - Evaluate semicolon and colon usage for correctness and effectiveness
   - Assess dash usage (em dashes, en dashes, hyphens) for consistency and clarity
   - Review parenthetical expressions and their impact on readability
   - Examine quotation mark and dialogue punctuation conventions

5. READABILITY IMPACT ASSESSMENT:
   - Analyze how punctuation patterns affect the flow and rhythm of sentences
   - Identify passages where punctuation hinders natural reading cadence
   - Suggest punctuation changes to improve overall readability
   - Note patterns where punctuation style might be adjusted to match content
"""

    detailed_instructions = standard_instructions + """
6. SENTENCE STRUCTURE AND PUNCTUATION:
   - Analyze how punctuation interacts with sentence structure
   - Identify complex sentences that might benefit from restructuring
   - Suggest alternative punctuation strategies for particularly challenging passages
   - Examine nested clauses and their punctuation

7. DIALOGUE AND QUOTATION ANALYSIS:
   - Review dialogue punctuation conventions and consistency
   - Assess quotation mark usage, including nested quotations
   - Examine speaker attribution and its punctuation
   - Suggest improvements for unclear dialogue punctuation

8. ADVANCED PUNCTUATION STRATEGIES:
   - Recommend stylistic punctuation techniques from master prose writers
   - Suggest intentional punctuation variations to create emphasis or effect
   - Analyze how punctuation might be used to establish or enhance voice
   - Provide examples of innovative punctuation approaches that maintain clarity
"""

    # Choose the appropriate instruction level
    if analysis_level == "basic":
        instruction_set = basic_instructions
    elif analysis_level == "detailed":
        instruction_set = detailed_instructions
    else:  # standard
        instruction_set = standard_instructions

    # Construct the punctuation elements emphasis
    elements_text = ", ".join(elements)

    # Adjust instructions based on strictness level
    strictness_instructions = {
        "low": "Focus only on major punctuation issues that significantly impact readability or clarity.",
        "medium": "Identify moderate to major punctuation issues, balancing mechanical correctness with stylistic considerations.",
        "high": "Perform a detailed analysis of punctuation usage, noting even minor or stylistic issues."
    }
    
    strictness_text = strictness_instructions.get(strictness, strictness_instructions["medium"])

    # Construct the full prompt
    instructions = f"""IMPORTANT: NO Markdown formatting

You are an expert literary editor specializing in punctuation and its impact on prose clarity and flow. Your task is to analyze the provided manuscript for punctuation effectiveness, focusing particularly on: {elements_text}.

Follow Ursula K. Le Guin's principle from "Steering the Craft" that punctuation should guide how the text "sounds" to a reader. Analyze how punctuation either supports or hinders the clarity, rhythm, and natural flow of the prose.

Strictness level: {strictness}. {strictness_text}

Pay special attention to:
1. Overly long sentences that lack adequate punctuation (run-ons)
2. Missing commas that would clarify meaning or improve readability
3. Unusual or inconsistent punctuation patterns
4. Places where reading aloud would reveal awkward punctuation
5. Sentences where alternative punctuation would improve flow or clarity

For each issue you identify, provide:
- The original passage
- What makes the punctuation problematic
- A specific recommendation for improvement

Create a comprehensive punctuation analysis with these sections:
{instruction_set}

Format your analysis as a clear, organized report with sections and subsections. Use plain text formatting only (NO Markdown). Use numbered or bulleted lists where appropriate for clarity.

Be specific in your examples and suggestions, showing how punctuation can be improved without changing the author's voice or intention. Focus on practical changes that will make the writing more readable and effective.
"""

    # Combine all sections
    prompt = f"=== MANUSCRIPT ===\n{manuscript_content}\n=== END MANUSCRIPT ===\n\n{instructions}"
    
    return prompt


def run_punctuation_analysis(manuscript_content, args):
    """Run punctuation analysis using Claude API and return results."""
    prompt = create_punctuation_analysis_prompt(manuscript_content, args.analysis_level, args.elements, args.strictness)

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

    print(f"Running punctuation effectiveness analysis...")
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
    
    # Convert any Markdown formatting to plain text
    plain_text_response = strip_markdown(full_response)
    
    return plain_text_response, thinking_content, prompt_token_count, report_token_count


def save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats):
    """Save the punctuation analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    analysis_level = f"_{args.analysis_level}" if args.analysis_level != "standard" else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"punctuation_audit{desc}{analysis_level}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== PUNCTUATION EFFECTIVENESS ANALYSIS ===\n\n")
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
    
    current_time = datetime.now().strftime("%I:%M:%S %p").lower().lstrip("0")
    print("\n=== Punctuation Auditor Configuration ===")
    print(f"Input file: {args.manuscript_file}")
    print(f"Analysis level: {args.analysis_level}")
    print(f"Punctuation elements: {', '.join(args.elements)}")
    print(f"Strictness level: {args.strictness}")
    print(f"Max request timeout: {args.request_timeout} seconds for each streamed chunk")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    full_response, thinking_content, prompt_token_count, report_token_count = run_punctuation_analysis(
        manuscript_content, args
    )
    
    if full_response:
        stats = f"""
Details:
Analysis type: Punctuation effectiveness analysis
Analysis level: {args.analysis_level}
Punctuation elements: {', '.join(args.elements)}
Strictness level: {args.strictness}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
        
        save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats)
    else:
        print("Failed to complete punctuation analysis.")


if __name__ == "__main__":
    main()
