#!/usr/bin/env python
# dangling_modifier_checker.py
#
# Description: Analyzes manuscript for dangling and misplaced modifiers using the Claude API.
#              Identifies phrases that don't logically connect to the subject they're meant to modify,
#              which can create unintended humor or confusion, following Ursula K. Le Guin's 
#              writing guidance on clarity and precision.
#
# Usage: 
# python -B dangling_modifier_checker.py --manuscript_file manuscript.txt [--save_dir reports]

import anthropic
import pypandoc
import os
import argparse
import sys
import time
from datetime import datetime


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Analyze manuscript for dangling and misplaced modifiers using Claude AI.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B dangling_modifier_checker.py --manuscript_file manuscript.txt --analysis_level detailed --sensitivity high
  python -B dangling_modifier_checker.py --manuscript_file manuscript.txt
  python -B dangling_modifier_checker.py --manuscript_file manuscript.txt --save_dir reports
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
    analysis_group.add_argument('--modifier_types', type=str, nargs='+',
                              default=["dangling", "misplaced", "squinting", "limiting"],
                              help="Specific modifier types to focus on (default: all types)")
    analysis_group.add_argument('--sensitivity', type=str, default="medium",
                              choices=["low", "medium", "high"],
                              help="Sensitivity level for modifier detection (default: medium)")

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


def create_modifier_analysis_prompt(manuscript_content, analysis_level, modifier_types, sensitivity):
    """Create a prompt for the AI to analyze dangling and misplaced modifiers."""
    
    # Build instruction section based on analysis level
    basic_instructions = """
1. MODIFIER PROBLEM OVERVIEW:
   - Identify the most obvious dangling and misplaced modifiers in the manuscript
   - Highlight patterns of modifier usage that create confusion
   - Explain how these problems affect clarity and readability

2. DANGLING MODIFIER ANALYSIS:
   - Identify introductory phrases that don't logically connect to the subject that follows
   - Flag participial phrases (-ing, -ed) that appear to modify the wrong noun
   - Point out modifiers that create unintentional humor or confusion
   - Provide clear examples with correction suggestions

3. MISPLACED MODIFIER ANALYSIS:
   - Identify words, phrases, or clauses positioned where they modify the wrong element
   - Point out adverbs or adjectives that are placed too far from what they modify
   - Highlight restrictive modifiers (only, just, nearly, etc.) that modify the wrong element
   - Suggest proper placement for clarity
"""

    standard_instructions = basic_instructions + """
4. SQUINTING MODIFIER ANALYSIS:
   - Identify modifiers that could logically apply to either preceding or following elements
   - Flag ambiguous adverbs that create unclear meaning
   - Examine sentences where it's unclear what a modifier is intended to modify
   - Suggest restructuring for clarity

5. COORDINATION PROBLEMS:
   - Identify faulty parallelism in lists or series that creates modifier problems
   - Point out correlative conjunctions (not only/but also, either/or) with misaligned elements
   - Analyze comparisons that create logical inconsistencies
   - Suggest restructuring to maintain logical relationships
"""

    detailed_instructions = standard_instructions + """
6. CONTEXTUAL MODIFIER ISSUES:
   - Analyze how modifier problems affect character voice or narrative clarity
   - Identify patterns of modifier issues in different types of passages (dialogue, description, action)
   - Examine how modifier issues affect pacing or create reader confusion
   - Suggest revision strategies tailored to different passage types

7. LIMITING MODIFIER ANALYSIS:
   - Identify modifiers that create unintended restrictions or qualifications
   - Analyze how placement of limiting modifiers (only, just, even, etc.) affects meaning
   - Examine noun phrase modifiers that create ambiguity
   - Suggest precise placement to convey intended meaning

8. COMPLEX STRUCTURE ISSUES:
   - Identify problems in sentences with multiple clauses or nested modifiers
   - Analyze long sentences where modifier relationships become unclear
   - Examine complex descriptive passages for modifier clarity
   - Suggest simplification or restructuring strategies
"""

    # Choose the appropriate instruction level
    if analysis_level == "basic":
        instruction_set = basic_instructions
    elif analysis_level == "detailed":
        instruction_set = detailed_instructions
    else:  # standard
        instruction_set = standard_instructions

    # Construct the modifier types emphasis
    modifier_types_text = ", ".join(modifier_types)

    # Adjust instructions based on sensitivity level
    sensitivity_instructions = {
        "low": "Focus only on the most obvious and confusing modifier issues that significantly impact meaning.",
        "medium": "Identify moderate to major modifier issues, balancing technical correctness with stylistic considerations.",
        "high": "Perform a detailed analysis of all potential modifier issues, noting even subtle cases of ambiguity."
    }
    
    sensitivity_text = sensitivity_instructions.get(sensitivity, sensitivity_instructions["medium"])

    # Construct the full prompt
    instructions = f"""IMPORTANT: NO Markdown formatting

You are an expert literary editor specializing in grammatical clarity and precision. Your task is to analyze the provided manuscript for dangling and misplaced modifiers, focusing particularly on: {modifier_types_text}.

Follow Ursula K. Le Guin's guidance from "Steering the Craft" on the importance of clear, precise sentence construction. Dangling modifiers occur when a descriptive phrase doesn't connect logically to what it's supposed to modify, creating confusion or unintentional humor. In her words, "danglers can really wreck the scenery."

Sensitivity level: {sensitivity}. {sensitivity_text}

Pay special attention to:
1. Introductory phrases that don't logically connect to the subject that follows
   Example: "Walking down the street, the trees were beautiful." (Who is walking?)
   Corrected: "Walking down the street, I thought the trees were beautiful."

2. Participial phrases (-ing, -ed) that appear to modify the wrong noun
   Example: "Rushing to catch the train, my coffee spilled everywhere." (The coffee wasn't rushing)
   Corrected: "Rushing to catch the train, I spilled my coffee everywhere."

3. Modifiers placed too far from what they're modifying
   Example: "She served cake to the children on paper plates." (Were the children on paper plates?)
   Corrected: "She served cake on paper plates to the children."

4. Limiting modifiers (only, just, nearly, almost) that modify the wrong element
   Example: "He only eats vegetables on Tuesdays." (Does he do nothing else with vegetables on Tuesdays?)
   Corrected: "He eats vegetables only on Tuesdays."

5. Squinting modifiers that could apply to either what comes before or after
   Example: "Drinking coffee quickly improves alertness." (Does "quickly" modify drinking or improves?)
   Corrected: "Quickly drinking coffee improves alertness." OR "Drinking coffee improves alertness quickly."

For each issue you identify, provide:
- The original sentence with the modifier problem
- An explanation of why it's problematic
- A suggested revision that maintains the author's intended meaning

Create a comprehensive modifier analysis with these sections:
{instruction_set}

Format your analysis as a clear, organized report with sections and subsections. Use plain text formatting only (NO Markdown). Use numbered or bulleted lists where appropriate for clarity.

Be specific in your examples and suggestions, showing how modifier placement can be improved without changing the author's voice or intention. Focus on practical changes that will make the writing clearer and more effective.
"""

    # Combine all sections
    prompt = f"=== MANUSCRIPT ===\n{manuscript_content}\n=== END MANUSCRIPT ===\n\n{instructions}"
    
    return prompt


def run_modifier_analysis(manuscript_content, args):
    """Run dangling modifier analysis using Claude API and return results."""
    prompt = create_modifier_analysis_prompt(manuscript_content, args.analysis_level, args.modifier_types, args.sensitivity)

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

    print(f"Running dangling and misplaced modifier analysis...")
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
    """Save the dangling modifier analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    analysis_level = f"_{args.analysis_level}" if args.analysis_level != "standard" else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"dangling_modifier_check{desc}{analysis_level}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== DANGLING MODIFIER ANALYSIS ===\n\n")
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
    print("\n=== Dangling Modifier Checker Configuration ===")
    print(f"Input file: {args.manuscript_file}")
    print(f"Analysis level: {args.analysis_level}")
    print(f"Modifier types: {', '.join(args.modifier_types)}")
    print(f"Sensitivity level: {args.sensitivity}")
    print(f"Max request timeout: {args.request_timeout} seconds for each streamed chunk")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    full_response, thinking_content, prompt_token_count, report_token_count = run_modifier_analysis(
        manuscript_content, args
    )
    
    if full_response:
        stats = f"""
Details:
Analysis type: Dangling and misplaced modifier analysis
Analysis level: {args.analysis_level}
Modifier types: {', '.join(args.modifier_types)}
Sensitivity level: {args.sensitivity}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
        
        save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats)
    else:
        print("Failed to complete dangling modifier analysis.")


if __name__ == "__main__":
    main()
