#!/usr/bin/env python
# consistency_checker.py
#
# Description: Checks a manuscript for consistency against a world document using the Claude API.
#              Supports different types of consistency checks: world, internal, development, unresolved.
#              Automatically strips Markdown formatting from Claude's responses.
#
# Usage: 
# python -B consistency_checker.py --world_file world.txt --manuscript_file manuscript.txt [--outline_file outline.txt] [--check_type world|internal|development|unresolved]

# pip install's:
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
        description='Check manuscript consistency against outline, world, and manuscript documents using Claude thinking API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B consistency_checker.py --world_file world.txt --manuscript_file manuscript.txt --outline_file outline.txt --check_type all
  python -B consistency_checker.py --world_file world.txt --manuscript_file manuscript.txt
  python -B consistency_checker.py --world_file world.txt --manuscript_file manuscript.txt --outline_file outline.txt --check_type internal
  python -B consistency_checker.py --world_file world.txt --manuscript_file manuscript.txt --check_type development --save_dir reports
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    check_group = parser.add_argument_group('Consistency Check Options')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--world_file', type=str, required=True, 
                           help="File containing the world details (required)")
    input_group.add_argument('--manuscript_file', type=str, required=True,
                           help="File containing the manuscript to check (required)")
    input_group.add_argument('--outline_file', type=str, default=None,
                           help="File containing the story outline (optional)")

    # Add arguments to the Consistency Check Options group
    check_group.add_argument('--check_type', type=str, default="world",
                            choices=["world", "internal", "development", "unresolved", "all"],
                            help="Type of consistency check to perform (default: world)")
    check_group.add_argument('--check_description', type=str, default="",
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
                            help='Directory to save consistency reports (default: current directory)')
    output_group.add_argument('--skip_thinking', action='store_true',
                            help='Skip saving the AI thinking process (smaller output files)')

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
        if file_type in ['world', 'manuscript']:  # Required files
            print(f"Please provide a valid {file_type} file.")
            sys.exit(1)
        else:  # Optional files
            print(f"Continuing without {file_type} information.")
            return ""
    except Exception as e:
        print(f"Error: Could not read {file_type} file: {e}")
        if file_type in ['world', 'manuscript']:  # Required files
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

def create_prompt(check_type, outline_content, world_content, manuscript_content):
    no_markdown = "IMPORTANT: - NO Markdown formatting"
    
    prompts = {
        "world": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== WORLD ===
{world_content}
=== END WORLD ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor with exceptional attention to detail.
Using the WORLD document as the established source of truth, analyze
the MANUSCRIPT for any inconsistencies or contradictions with the
established facts. Focus on:

1. CHARACTER CONSISTENCY:
   - Are characters acting in ways that match their established
     personality traits?
   - Does dialogue reflect their documented speech patterns and
     knowledge level?
   - Are relationships developing consistently with established
     dynamics?
   - Are physical descriptions matching those in the WORLD document?

2. SETTING & WORLD CONSISTENCY:
   - Are locations described consistently with their established
     features?
   - Does the manuscript respect the established rules of the world?

3. TIMELINE COHERENCE:
   - Does the manuscript respect the established historical events and
     their sequence?
   - Are there any temporal contradictions with established dates?
   - Is character knowledge appropriate for their place in the
     timeline?
   - Are seasonal elements consistent with the story's temporal
     placement?

4. THEMATIC INTEGRITY:
   - Are the established themes being consistently developed?
   - Are symbolic elements used consistently with their established meanings?

For each inconsistency, provide:
- The specific element in the manuscript that contradicts the WORLD
- The established fact in the WORLD it contradicts
- The location in the manuscript where this occurs using verbatim text
- A suggested correction that would maintain narrative integrity

Use the extensive thinking space to thoroughly cross-reference the
manuscript against the story's world before identifying issues.
""",

        "internal": f"""=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor focusing on internal narrative
consistency. Analyze the MANUSCRIPT to identify elements that are
internally inconsistent or contradictory, regardless of the
established story world. Focus on:

1. NARRATIVE CONTINUITY:
   - Events that contradict earlier established facts within the
     manuscript itself
   - Description inconsistencies (characters, objects, settings
     changing without explanation)
   - Dialogue that contradicts earlier statements by the same
     character
   - Emotional arcs that show sudden shifts without sufficient
     development

2. SCENE-TO-SCENE COHERENCE:
   - Physical positioning and transitions between locations
   - Time of day and lighting inconsistencies
   - Character presence/absence in scenes without explanation
   - Weather or environmental conditions that change illogically

3. PLOT LOGIC:
   - Character motivations that seem inconsistent with their actions
   - Convenient coincidences that strain credibility
   - Information that characters possess without logical means of
     acquisition
   - Plot developments that contradict earlier established rules or
     limitations

4. POV CONSISTENCY:
   - Shifts in viewpoint that break established narrative patterns
   - Knowledge revealed that the POV character couldn't logically
     possess
   - Tone or voice inconsistencies within the same POV sections

For each issue found, provide:
- The specific inconsistency with exact manuscript locations
- Why it creates a continuity problem
- A suggested revision approach
""",

        "development": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== WORLD ===
{world_content}
=== END WORLD ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor analyzing character and plot
development. Track how key elements evolve throughout the manuscript
and identify any development issues:

1. CHARACTER ARC TRACKING:
   - For each major character, trace their development through the manuscript
   - Identify key transformation moments and their emotional progression
   - Highlight any character development that feels rushed, stalled,
     or inconsistent
   - Note if their arc is following the trajectory established in the
     WORLD document

2. MYSTERY DEVELOPMENT:
   - Track the progression of the central mystery
   - Ensure clues are being revealed at an appropriate pace
   - Identify any critical information that's missing or presented out
     of logical sequence
   - Check if red herrings and misdirections are properly balanced
     with genuine progress

3. RELATIONSHIP EVOLUTION:
   - Track how key relationships develop
   - Ensure relationship changes are properly motivated and paced
   - Identify any significant jumps in relationship dynamics that need
     development

4. THEME DEVELOPMENT:
   - Track how the core themes from the WORLD document are being
     developed
   - Identify opportunities to strengthen thematic elements
   - Note if any established themes are being neglected

Provide a structured analysis showing the progression points for each
tracked element, identifying any gaps, pacing issues, or development
opportunities.
""",

        "unresolved": f"""=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative
completeness. Analyze the MANUSCRIPT to identify elements that have
been set up but not resolved:

1. UNRESOLVED PLOT ELEMENTS:
   - Mysteries or questions raised but not answered
   - Conflicts introduced but not addressed
   - Promises made to the reader (through foreshadowing or explicit
     setup) without payoff
   - Character goals established but not pursued

2. CHEKHOV'S GUNS:
   - Significant objects introduced but not used
   - Skills or abilities established but never employed
   - Locations described in detail but not utilized in the plot
   - Information revealed but not made relevant

3. CHARACTER THREADS:
   - Side character arcs that begin but don't complete
   - Character-specific conflicts that don't reach resolution
   - Backstory elements introduced but not integrated into the main
     narrative
   - Relationship dynamics that are established but not developed

For each unresolved element, provide:
- What was introduced and where in the manuscript
- Why it creates an expectation of resolution
- Suggested approaches for resolution or intentional non-resolution
"""
    }
    
    return prompts.get(check_type, "")


def run_consistency_check(check_type, outline_content, world_content, manuscript_content, max_tokens, thinking_budget, args):
    """Run a single consistency check and return results."""
    prompt = create_prompt(check_type, outline_content, world_content, manuscript_content)

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

    # calculate available tokens after prompt
    prompt_tokens = prompt_token_count
    available_tokens = args.context_window - prompt_tokens
    # for API call, max_tokens must respect the API limit
    max_tokens = min(available_tokens, available_tokens)
    # thinking budget must be LESS than max_tokens to leave room for visible output
    thinking_budget = max_tokens - args.desired_output_tokens
    if thinking_budget > 32000:
        print(f"Warning: thinking budget is larger than 32K, set to 32K. Use batch for larger thinking budgets.")
        thinking_budget = 32000

    print(f"Running {check_type} consistency check...")
    print(f"\nToken stats:")
    print(f"Max AI model context window: [{args.context_window}] tokens")
    print(f"Input prompt tokens: [{prompt_tokens}] ...")
    print(f"                     = outline.txt + world.txt + manuscript.txt")
    print(f"                       + prompt instructions")
    print(f"Available tokens: [{available_tokens}]  = {args.context_window} - {prompt_tokens} = context_window - prompt")
    print(f"Desired output tokens: [{args.desired_output_tokens}]")
    print(f"AI model thinking budget: [{thinking_budget}] tokens  = {max_tokens} - {args.desired_output_tokens}")
    print(f"Max output tokens (max_tokens): [{max_tokens}] tokens  = min({thinking_budget}, {available_tokens})")
    print(f"                                = can not exceed: 'betas=[\"output-128k-2025-02-19\"]'")
    if thinking_budget < args.thinking_budget_tokens:
        print(f"Error: prompt is too large to have a {args.thinking_budget_tokens} thinking budget!")
        sys.exit(1)

    print(f"\nprompt:\n{prompt}\n")
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


def save_report(check_type, full_response, thinking_content, prompt_token_count, report_token_count, args, stats):
    """Save the consistency report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.check_description}" if args.check_description else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"consistency_{check_type}{desc}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== CONSISTENCY CHECK TYPE ===\n")
            file.write(f"{check_type}\n\n")
            file.write("=== AI'S THINKING PROCESS ===\n\n")
            file.write(strip_markdown(thinking_content)) # remove Markdown
            file.write("\n=== END AI'S THINKING PROCESS ===\n")
            file.write(stats)
        print(f"AI thinking saved to: {thinking_filename}")
    
    print(f"Report saved to: {report_filename}")
    return report_filename


def main():
    args = parse_arguments()
    
    world_content = read_file(args.world_file, "world")
    manuscript_content = read_file(args.manuscript_file, "manuscript")
    outline_content = read_file(args.outline_file, "outline") if args.outline_file else ""
    
    current_time = datetime.now().strftime("%I:%M:%S %p").lower().lstrip("0")
    print("\n=== Consistency Checker Configuration ===")
    print(f"Check type: {args.check_type}")
    print(f"Max request timeout: {args.request_timeout} seconds")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    # Handle "all" check type
    if args.check_type == "all":
        check_types = ["world", "internal", "development", "unresolved"]
        all_reports = []
        
        for check in check_types:
            max_tokens = 0
            thinking_budget = 0
            print(f"\n=== Running {check.upper()} Consistency Check ===")
            full_response, thinking_content, prompt_token_count, report_token_count = run_consistency_check(
                check, outline_content, world_content, manuscript_content, max_tokens, thinking_budget, args
            )
            
            if full_response:
                stats = f"""
Details:
Check type: {check} consistency check
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {thinking_budget} tokens
Max output tokens: {max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
                
                report_file = save_report(check, full_response, thinking_content, 
                                        prompt_token_count, report_token_count, args, stats)
                all_reports.append(report_file)
            else:
                print(f"Failed to complete {check} consistency check.")
        
        print("\n=== All Consistency Checks Completed ===")
        print("Reports saved:")
        for report in all_reports:
            print(f"- {report}")
    else:
        # Run a single check type
        full_response, thinking_content, prompt_token_count, report_token_count = run_consistency_check(
            args.check_type, outline_content, world_content, manuscript_content, args
        )
        
        if full_response:
            stats = f"""
Details:
Check type: {args.check_type} consistency check
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {thinking_budget} tokens
Max output tokens: {args.max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
            
            save_report(args.check_type, full_response, thinking_content, 
                      prompt_token_count, report_token_count, args, stats)
        else:
            print("Failed to complete consistency check.")


if __name__ == "__main__":
    main()
