#!/usr/bin/env python
# foreshadowing_tracker.py
#
# Description: Analyzes a manuscript to identify foreshadowing elements, planted clues, and their payoffs
#              using the Claude API. Tracks setup and resolution of story elements, ensuring narrative promises
#              are fulfilled.
#
# Usage: 
# python -B foreshadowing_tracker.py --manuscript_file manuscript.txt [--outline_file outline.txt] [--foreshadowing_type explicit|implicit|chekhov|all]

import pypandoc
import anthropic

import os
import argparse
import re
import sys
import time
from datetime import datetime


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Analyze manuscript for foreshadowing elements, planted clues, and their payoffs using Claude thinking API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B foreshadowing_tracker.py --manuscript_file manuscript.txt --foreshadowing_type all
  python -B foreshadowing_tracker.py --manuscript_file manuscript.txt --outline_file outline.txt --foreshadowing_type explicit
  python -B foreshadowing_tracker.py --manuscript_file manuscript.txt --foreshadowing_type chekhov --save_dir reports
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    analysis_group = parser.add_argument_group('Foreshadowing Analysis Options')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--manuscript_file', type=str, required=True,
                           help="File containing the manuscript to analyze (required)")
    input_group.add_argument('--outline_file', type=str, default=None,
                           help="File containing the story outline (optional)")

    # Add arguments to the Analysis Options group
    analysis_group.add_argument('--foreshadowing_type', type=str, default="all",
                            choices=["explicit", "implicit", "chekhov", "all"],
                            help="Type of foreshadowing to analyze (default: all)")
    analysis_group.add_argument('--analysis_description', type=str, default="",
                            help="Optional description to include in output filenames")

    # Add arguments to the Claude API Configuration group
    api_group.add_argument('--context_window',         type=int, default=200000, help='Context window for Claude 3.7 Sonnet (default: 200000)')
    api_group.add_argument('--betas_max_tokens',       type=int, default=128000, help='Maximum tokens for AI output (default: 128000)')
    api_group.add_argument('--thinking_budget_tokens', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
    api_group.add_argument('--desired_output_tokens',  type=int, default=8000, help='User desired number of tokens to generate before stopping output')
    api_group.add_argument('--request_timeout', type=int, default=300,
                         help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds)')

    # Add arguments to the Output Configuration group
    output_group.add_argument('--save_dir', type=str, default=".",
                            help='Directory to save foreshadowing analysis reports (default: current directory)')
    output_group.add_argument('--skip_thinking', action='store_true',
                            help='Skip saving the AI thinking process (smaller output files)')
    output_group.add_argument('--chronological', action='store_true',
                            help='Sort foreshadowing elements chronologically rather than by type')

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
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())


def strip_markdown(md_text):
    try:
        plain_text = pypandoc.convert_text(md_text, 'plain', format='markdown')
        plain_text = plain_text.replace("\u00A0", " ")
        return plain_text
    except Exception as e:
        print(f"Error converting markdown to plain text: {e}")
        print("Make sure pypandoc and pandoc are properly installed.")
        return md_text  # return original text if conversion fails


def create_prompt(foreshadowing_type, outline_content, manuscript_content, chronological=False):
    no_markdown = "IMPORTANT: - NO Markdown formatting"
    
    org_instruction = ""
    if chronological:
        org_instruction = "Organize your analysis chronologically, following the manuscript's progression."
    else:
        org_instruction = "Organize your analysis by foreshadowing type, grouping similar elements together."
    
    prompts = {
        "explicit": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative structure and foreshadowing. Analyze the manuscript to identify EXPLICIT foreshadowing elements - direct hints, statements, or events that point to future developments.

Focus on identifying:

1. DIRECT FORESHADOWING:
   - Clear statements or hints that explicitly point to future events
   - Prophecies, predictions, or warnings made by characters
   - Narrative statements that directly hint at what's to come
   - Character statements that foreshadow future developments

2. SETUP AND PAYOFF TRACKING:
   - For each foreshadowing element, locate where it is set up (the hint/clue)
   - Identify where/if each setup is paid off later in the manuscript
   - Note any explicit foreshadowing that remains unresolved
   - Analyze the effectiveness of the setup-payoff connections

3. TIMING AND DISTANCE ASSESSMENT:
   - Evaluate the distance between setup and payoff (immediate, mid-range, long-range)
   - Assess if the timing between setup and payoff is appropriate
   - Note if foreshadowed events occur too quickly or are delayed too long

4. NARRATIVE IMPACT:
   - Analyze how the foreshadowing enhances tension and anticipation
   - Assess if the foreshadowing is too obvious or too subtle
   - Evaluate if the payoff satisfies the expectations created by the setup

{org_instruction}

For each foreshadowing element, provide:
- The exact text and location where the foreshadowing occurs
- The exact text and location where the payoff occurs (if present)
- An assessment of the effectiveness of the setup-payoff connection
- Recommendations for improvement where relevant

For unresolved foreshadowing, note:
- The setup that lacks a payoff
- Where a payoff could naturally occur
- Specific suggestions for resolving the planted clue

Use the extensive thinking space to thoroughly catalog and cross-reference all foreshadowing elements before finalizing your analysis.
""",

        "implicit": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative structure and foreshadowing. Analyze the manuscript to identify IMPLICIT foreshadowing elements - subtle clues, symbolic imagery, and thematic elements that hint at future developments.

Focus on identifying:

1. SYMBOLIC FORESHADOWING:
   - Recurring symbols, motifs, or imagery that hint at future events
   - Visual descriptions that subtly indicate coming developments
   - Metaphors or similes that suggest future outcomes
   - Environmental details (weather, setting) that subtly presage events

2. DIALOGUE FORESHADOWING:
   - Casual remarks by characters that gain significance later
   - Seemingly unimportant information revealed in dialogue
   - Character observations that subtly hint at future revelations
   - Patterns in dialogue that create expectations

3. BACKGROUND DETAILS:
   - Seemingly minor world-building elements that become important
   - Casual mentions of places, objects, or people that later become significant
   - Incidental actions or habits that foreshadow character choices

4. PATTERN RECOGNITION:
   - Track recurring themes or ideas that create expectations
   - Identify narrative patterns that implicitly suggest outcomes
   - Note subtle character behaviors that foreshadow major decisions

{org_instruction}

For each implicit foreshadowing element, provide:
- The exact text and location where the subtle clue appears
- The exact text and location of the corresponding payoff (if present)
- An analysis of how the subtle connection works (or doesn't)
- Recommendations for strengthening subtle connections where relevant

For potential missed opportunities, identify:
- Events that would benefit from earlier foreshadowing
- Suggestions for subtle clues that could be planted earlier
- Ways to enhance thematic coherence through implicit connections

Use the extensive thinking space to thoroughly catalog and cross-reference all implicit elements before finalizing your analysis.
""",

        "chekhov": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative structure and "Chekhov's Gun" analysis - the principle that significant elements introduced in a story must be used in a meaningful way. Analyze the manuscript to identify introduced elements that create expectations for later use.

Focus on identifying:

1. INTRODUCED BUT UNUSED ELEMENTS:
   - Significant objects that are prominently described but not used
   - Special abilities, skills, or knowledge mentioned but never employed
   - Locations described in detail but not utilized in the plot
   - Character traits or backgrounds emphasized but not made relevant

2. PROPERLY UTILIZED ELEMENTS:
   - Significant objects, places, or abilities that are introduced and later used
   - The setup of these elements and their subsequent payoff
   - How effectively the payoff fulfills the expectation created by the setup

3. SETUP-PAYOFF EVALUATION:
   - Whether the payoff is proportional to the emphasis placed on the setup
   - If the payoff occurs at an appropriate time after the setup
   - Whether the use of the element is satisfying given how it was introduced

4. NARRATIVE PROMISE ASSESSMENT:
   - Identify what narrative promises are made to readers through introduced elements
   - Evaluate whether these promises are fulfilled
   - Assess the impact of unfulfilled narrative promises on reader satisfaction

{org_instruction}

For each Chekhov's Gun element, provide:
- The exact text and location where the element is introduced
- The exact text and location where the element is used (if it is)
- An assessment of the effectiveness of the setup-payoff
- Specific recommendations for elements that need resolution

For unfired Chekhov's Guns, suggest:
- How the introduced element could be meaningfully incorporated
- Where in the narrative the payoff could naturally occur
- How to revise the introduction if the element won't be used

Use the extensive thinking space to thoroughly catalog all introduced significant elements and their resolution status before finalizing your analysis.
"""
    }
    
    return prompts.get(foreshadowing_type, "")


def run_foreshadowing_analysis(foreshadowing_type, outline_content, manuscript_content, args):
    """Run a single foreshadowing analysis and return results."""
    prompt = create_prompt(foreshadowing_type, outline_content, manuscript_content, args.chronological)

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
        print(f"Warning: thinking budget is larger than 32K, set to 32K. Use batch for larger thinking budgets.")
        thinking_budget = 32000

    print(f"Running {foreshadowing_type} foreshadowing analysis...")
    print(f"\nToken stats:")
    print(f"Max AI model context window: [{args.context_window}] tokens")
    print(f"Input prompt tokens: [{prompt_tokens}] ...")
    print(f"                     = outline.txt + manuscript.txt")
    print(f"                       + prompt instructions")
    print(f"Available tokens: [{available_tokens}]  = {args.context_window} - {prompt_tokens} = context_window - prompt")
    print(f"Desired output tokens: [{args.desired_output_tokens}]")
    print(f"AI model thinking budget: [{thinking_budget}] tokens  = {max_tokens} - {args.desired_output_tokens}")
    print(f"Max output tokens (max_tokens): [{max_tokens}] tokens  = min({thinking_budget}, {available_tokens})")
    print(f"                                = can not exceed: 'betas=[\"output-128k-2025-02-19\"]'")
    if thinking_budget < args.thinking_budget_tokens:
        print(f"Error: prompt is too large to have a {args.thinking_budget_tokens} thinking budget!")
        sys.exit(1)
    
    full_response = ""
    thinking_content = ""
    
    system_prompt = "NO Markdown! Never respond with Markdown formatting, plain text only."
    
    start_time = time.time()
    print(f"Sending request to Claude API...")
    
    try:
        with client.beta.messages.stream(
            model="claude-3-7-sonnet-20250219",
            system=system_prompt,
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
                        # Print progress indicator
                        if len(full_response) % 1000 == 0:
                            print(".", end="", flush=True)
    except Exception as e:
        print(f"\nAPI Error: {e}")
        return "", "", 0, 0
    
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    
    report_word_count = count_words(full_response)
    print(f"\nCompleted in {minutes}m {seconds:.2f}s. Report has {report_word_count} words.")
    
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
        print(f"Response token counting error: {e}")
    
    plain_text_response = strip_markdown(full_response)
    
    return plain_text_response, thinking_content, prompt_token_count, report_token_count


def save_report(foreshadowing_type, full_response, thinking_content, prompt_token_count, report_token_count, args, stats):
    """Save the foreshadowing analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"foreshadowing_analysis_{foreshadowing_type}{desc}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== FORESHADOWING ANALYSIS TYPE ===\n")
            file.write(f"{foreshadowing_type}\n\n")
            file.write("=== AI'S THINKING PROCESS ===\n\n")
            file.write(strip_markdown(thinking_content)) # Remove Markdown
            file.write("\n=== END AI'S THINKING PROCESS ===\n")
            file.write(stats)
        print(f"AI thinking saved to: {thinking_filename}")
    
    print(f"Report saved to: {report_filename}")
    return report_filename


def main():
    args = parse_arguments()
    
    manuscript_content = read_file(args.manuscript_file, "manuscript")
    outline_content = read_file(args.outline_file, "outline") if args.outline_file else ""
    
    current_time = datetime.now().strftime("%I:%M:%S %p").lower().lstrip("0")
    print("\n=== Foreshadowing Tracker Configuration ===")
    print(f"Foreshadowing type: {args.foreshadowing_type}")
    print(f"Organization mode: {'Chronological' if args.chronological else 'By foreshadowing type'}")
    print(f"Max request timeout: {args.request_timeout} seconds")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    # Handle "all" foreshadowing type
    if args.foreshadowing_type == "all":
        foreshadowing_types = ["explicit", "implicit", "chekhov"]
        all_reports = []
        
        for f_type in foreshadowing_types:
            print(f"\n=== Running {f_type.upper()} Foreshadowing Analysis ===")
            full_response, thinking_content, prompt_token_count, report_token_count = run_foreshadowing_analysis(
                f_type, outline_content, manuscript_content, args
            )
            
            if full_response:
                stats = f"""
Details:
Foreshadowing type: {f_type} analysis
Organization mode: {'Chronological' if args.chronological else 'By foreshadowing type'}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
                
                report_file = save_report(f_type, full_response, thinking_content, 
                                        prompt_token_count, report_token_count, args, stats)
                all_reports.append(report_file)
            else:
                print(f"Failed to complete {f_type} foreshadowing analysis.")
        
        print("\n=== All Foreshadowing Analyses Completed ===")
        print("Reports saved:")
        for report in all_reports:
            print(f"- {report}")
    else:
        # Run a single foreshadowing type
        full_response, thinking_content, prompt_token_count, report_token_count = run_foreshadowing_analysis(
            args.foreshadowing_type, outline_content, manuscript_content, args
        )
        
        if full_response:
            stats = f"""
Details:
Foreshadowing type: {args.foreshadowing_type} analysis
Organization mode: {'Chronological' if args.chronological else 'By foreshadowing type'}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
            
            save_report(args.foreshadowing_type, full_response, thinking_content, 
                      prompt_token_count, report_token_count, args, stats)
        else:
            print("Failed to complete foreshadowing analysis.")


if __name__ == "__main__":
    main()
