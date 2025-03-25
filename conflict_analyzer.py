#!/usr/bin/env python
# conflict_analyzer.py
#
# Description: Analyzes a manuscript for conflict patterns at different structural levels 
#              using the Claude API. Identifies conflict nature, escalation, and resolution
#              at scene, chapter, and arc levels.
#
# Usage: 
# python -B conflict_analyzer.py --manuscript_file manuscript.txt [--outline_file outline.txt] [--analysis_level scene|chapter|arc|all]

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
        description='Analyze manuscript conflicts at different narrative levels using Claude thinking API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B conflict_analyzer.py --manuscript_file manuscript.txt --analysis_level all
  python -B conflict_analyzer.py --manuscript_file manuscript.txt --outline_file outline.txt --analysis_level scene
  python -B conflict_analyzer.py --manuscript_file manuscript.txt --analysis_level arc --save_dir reports
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    analysis_group = parser.add_argument_group('Conflict Analysis Options')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--manuscript_file', type=str, required=True,
                           help="File containing the manuscript to analyze (required)")
    input_group.add_argument('--outline_file', type=str, default=None,
                           help="File containing the story outline (optional)")

    # Add arguments to the Analysis Options group
    analysis_group.add_argument('--analysis_level', type=str, default="all",
                            choices=["scene", "chapter", "arc", "all"],
                            help="Level of conflict analysis to perform (default: all)")
    analysis_group.add_argument('--analysis_description', type=str, default="",
                            help="Optional description to include in output filenames")
    analysis_group.add_argument('--conflict_types', type=str, nargs='+', 
                            default=["internal", "interpersonal", "environmental", "societal", "cosmic"],
                            help="Specific conflict types to analyze (default: all main types)")

    # Add arguments to the Claude API Configuration group
    api_group.add_argument('--context_window',         type=int, default=200000, help='Context window for Claude 3.7 Sonnet (default: 200000)')
    api_group.add_argument('--betas_max_tokens',       type=int, default=128000, help='Maximum tokens for AI output (default: 128000)')
    api_group.add_argument('--thinking_budget_tokens', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
    api_group.add_argument('--desired_output_tokens',  type=int, default=8000, help='User desired number of tokens to generate before stopping output')
    api_group.add_argument('--request_timeout', type=int, default=300,
                         help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds)')

    # Add arguments to the Output Configuration group
    output_group.add_argument('--save_dir', type=str, default=".",
                            help='Directory to save conflict analysis reports (default: current directory)')
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


def create_prompt(analysis_level, outline_content, manuscript_content, conflict_types):
    no_markdown = "IMPORTANT: - NO Markdown formatting"
    
    conflict_types_list = ", ".join(conflict_types)
    
    prompts = {
        "scene": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in conflict analysis. Analyze the manuscript to identify and evaluate conflicts at the SCENE level. Focus on these conflict types: {conflict_types_list}.

For each scene in the manuscript:

1. CONFLICT IDENTIFICATION:
   - Identify the primary conflict driving the scene
   - Classify the conflict type (internal, interpersonal, environmental, societal, cosmic)
   - Identify any secondary or parallel conflicts

2. CONFLICT DYNAMICS:
   - Identify the specific opposing forces (character vs character, character vs self, etc.)
   - Analyze how the conflict is introduced
   - Track the escalation pattern within the scene
   - Identify the climax or turning point of the scene-level conflict
   - Analyze the resolution or non-resolution of the scene conflict

3. CONFLICT EFFECTIVENESS:
   - Evaluate how well the conflict creates tension and drives the scene
   - Identify if the conflict advances character development
   - Assess if the conflict contributes to the larger story arcs
   - Note if any scenes lack meaningful conflict

Organize your analysis by scene, using clear scene boundaries and key identifying text. For each scene, provide:
- Scene location in the manuscript (beginning and ending text)
- Main conflict identification and classification
- Analysis of conflict dynamics and progression
- Assessment of conflict effectiveness
- Specific recommendations for strengthening scene conflicts where needed

Use specific text examples from the manuscript to support your analysis.
""",

        "chapter": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in conflict analysis. Analyze the manuscript to identify and evaluate conflicts at the CHAPTER level. Focus on these conflict types: {conflict_types_list}.

For each chapter or major section in the manuscript:

1. CONFLICT PROGRESSION:
   - Identify the primary chapter-level conflict
   - Analyze how the conflict evolves across scenes within the chapter
   - Track rising and falling tension patterns
   - Identify how the chapter-level conflict connects to the overall story arcs

2. CONFLICT STRUCTURE:
   - Analyze the chapter's conflict structure (introduction, complications, climax)
   - Identify how scene-level conflicts contribute to the chapter's main conflict
   - Note any parallel conflict threads running through the chapter
   - Evaluate the chapter's conflict resolution or cliff-hanger

3. CONFLICT EFFECTIVENESS:
   - Assess if the chapter conflict is substantial enough to sustain reader interest
   - Evaluate if the conflict pacing is effective
   - Identify if the conflict advances the overall plot and character development
   - Note if the chapter conflict integrates well with preceding and following chapters

Organize your analysis by chapter/section, providing:
- Chapter identification (heading or beginning text)
- Main conflict analysis and classification
- Conflict progression through the chapter
- Assessment of conflict structure and effectiveness
- Specific recommendations for improving chapter-level conflict where needed

Use specific text examples from the manuscript to support your analysis.
""",

        "arc": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in conflict analysis. Analyze the manuscript to identify and evaluate conflicts at the ARC level. Focus on these conflict types: {conflict_types_list}.

Analyze the major conflict arcs that span multiple chapters or the entire manuscript:

1. CORE CONFLICT IDENTIFICATION:
   - Identify the primary conflict driving the overall narrative
   - Identify major secondary conflict arcs
   - Classify each conflict arc by type
   - Map the key characters or forces involved in each arc

2. ARC PROGRESSION:
   - For each major conflict arc, trace its development across the manuscript
   - Identify key escalation points and their manuscript locations
   - Track how the conflicts evolve, intensify, and interconnect
   - Map the climactic moments for each conflict arc
   - Analyze resolution patterns for each arc

3. CONFLICT ARCHITECTURE:
   - Analyze how the various conflict arcs interrelate
   - Identify how smaller conflicts feed into larger arcs
   - Evaluate the balance of different conflict types
   - Assess the structural integrity of the conflict arcs

4. NARRATIVE IMPACT:
   - Evaluate how effectively the conflict arcs drive the overall story
   - Assess if the conflict progression creates appropriate tension curves
   - Identify if the conflicts support the thematic elements
   - Evaluate if the resolutions are satisfying and consistent with setup

Provide a comprehensive analysis of the manuscript's conflict architecture:
- Map of major conflict arcs with their progression points
- Analysis of how conflicts interconnect and build upon each other
- Assessment of pacing and escalation effectiveness
- Specific recommendations for strengthening the conflict architecture

Use specific text examples from the manuscript to support your analysis.
"""
    }
    
    return prompts.get(analysis_level, "")


def run_conflict_analysis(analysis_level, outline_content, manuscript_content, conflict_types, args):
    """Run a single conflict analysis and return results."""
    prompt = create_prompt(analysis_level, outline_content, manuscript_content, conflict_types)

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

    print(f"Running {analysis_level} conflict analysis...")
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


def save_report(analysis_level, full_response, thinking_content, prompt_token_count, report_token_count, args, stats):
    """Save the conflict analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"conflict_analysis_{analysis_level}{desc}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== CONFLICT ANALYSIS LEVEL ===\n")
            file.write(f"{analysis_level}\n\n")
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
    print("\n=== Conflict Analyzer Configuration ===")
    print(f"Analysis level: {args.analysis_level}")
    print(f"Conflict types: {', '.join(args.conflict_types)}")
    print(f"Max request timeout: {args.request_timeout} seconds")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    # Handle "all" analysis level
    if args.analysis_level == "all":
        analysis_levels = ["scene", "chapter", "arc"]
        all_reports = []
        
        for level in analysis_levels:
            print(f"=== Running {level.upper()} Conflict Analysis ===")
            full_response, thinking_content, prompt_token_count, report_token_count = run_conflict_analysis(
                level, outline_content, manuscript_content, args.conflict_types, args
            )
            
            if full_response:
                stats = f"""
Details:
Analysis level: {level} conflict analysis
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
                
                report_file = save_report(level, full_response, thinking_content, 
                                        prompt_token_count, report_token_count, args, stats)
                all_reports.append(report_file)
            else:
                print(f"Failed to complete {level} conflict analysis.")
        
        print("\n=== All Conflict Analyses Completed ===")
        print("Reports saved:")
        for report in all_reports:
            print(f"- {report}")
    else:
        # Run a single analysis level
        full_response, thinking_content, prompt_token_count, report_token_count = run_conflict_analysis(
            args.analysis_level, outline_content, manuscript_content, args.conflict_types, args
        )
        
        if full_response:
            stats = f"""
Details:
Analysis level: {args.analysis_level} conflict analysis
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
            
            save_report(args.analysis_level, full_response, thinking_content, 
                      prompt_token_count, report_token_count, args, stats)
        else:
            print("Failed to complete conflict analysis.")


if __name__ == "__main__":
    main()
