#!/usr/bin/env python
# crowding_and_leaping_evaluator.py
#
# Description: Analyzes manuscript for pacing issues based on Ursula K. Le Guin's concepts of
#              "crowding" (intense detail) and "leaping" (jumping over time or events).
#              Identifies dense paragraphs, abrupt transitions, and visualizes pacing patterns.
#
# Usage: 
# python -B crowding_and_leaping_evaluator.py --manuscript_file manuscript.txt [--save_dir reports]

import anthropic
import pypandoc
import os
import argparse
import sys
import time
from datetime import datetime


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Analyze manuscript pacing using crowding and leaping concepts from Ursula K. Le Guin.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B crowding_leaping_evaluator.py --manuscript_file manuscript.txt --analysis_level detailed --sensitivity high --include_visualization
  python -B crowding_leaping_evaluator.py --manuscript_file manuscript.txt
  python -B crowding_leaping_evaluator.py --manuscript_file manuscript.txt --save_dir reports
        """
    )

    # create argument groups with section headers
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
    analysis_group.add_argument('--focus_areas', type=str, nargs='+',
                              default=["crowding", "leaping", "transitions", "pacing"],
                              help="Specific areas to focus on (default: all areas)")
    analysis_group.add_argument('--sensitivity', type=str, default="medium",
                              choices=["low", "medium", "high"],
                              help="Sensitivity level for pattern detection (default: medium)")

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
    output_group.add_argument('--include_visualization', action='store_true',
                            help='Include a text-based visualization of pacing patterns')

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


def create_crowding_leaping_prompt(manuscript_content, analysis_level, focus_areas, sensitivity, include_visualization):
    """Create a prompt for the AI to analyze crowding and leaping patterns."""
    
    # Build instruction section based on analysis level
    basic_instructions = """
1. PACING OVERVIEW:
   - Identify the overall pacing structure of the manuscript
   - Highlight patterns of crowding (dense detail) and leaping (time/event jumps)
   - Explain how these patterns affect readability and narrative flow

2. CROWDING ANALYSIS:
   - Identify paragraphs with intense detail or many events happening quickly
   - Flag sections where the narrative feels dense or overwhelming
   - Note effective use of crowding for emphasis or dramatic effect
   - Provide examples with suggestions for potential adjustment

3. LEAPING ANALYSIS:
   - Identify sections where significant time or events are skipped
   - Point out abrupt transitions that may confuse readers
   - Highlight effective uses of leaping to maintain narrative momentum
   - Suggest improvements for leaps that lack necessary context or bridges
"""

    standard_instructions = basic_instructions + """
4. TRANSITION ANALYSIS:
   - Evaluate the effectiveness of scene and chapter transitions
   - Identify transitions that are too abrupt or too drawn out
   - Analyze how transitions contribute to or detract from pacing
   - Suggest ways to improve problematic transitions

5. BALANCE ASSESSMENT:
   - Assess the balance between crowded and leaping sections
   - Identify narrative patterns that may create reading fatigue
   - Evaluate how well the pacing serves the content and genre expectations
   - Suggest adjustments to create more effective pacing rhythms
"""

    detailed_instructions = standard_instructions + """
6. SCENE DENSITY MAPPING:
   - Provide a structural map of the manuscript's pacing patterns
   - Analyze how scene density shifts throughout the manuscript
   - Identify potential pacing problems at the macro-structural level
   - Suggest strategic adjustments to improve overall narrative rhythm

7. WHITE SPACE ANALYSIS:
   - Examine how effectively "white space" is used between scenes and events
   - Analyze the presence and absence of reflective or transitional passages
   - Identify opportunities for adding or removing breathing room
   - Suggest techniques for modulating narrative density

8. GENRE-SPECIFIC CONSIDERATIONS:
   - Evaluate pacing against genre expectations and conventions
   - Analyze how crowding and leaping affect genre-specific elements
   - Identify pacing strategies that would enhance genre effectiveness
   - Suggest tailored approaches for improving genre alignment
"""

    # Choose the appropriate instruction level
    if analysis_level == "basic":
        instruction_set = basic_instructions
    elif analysis_level == "detailed":
        instruction_set = detailed_instructions
    else:  # standard
        instruction_set = standard_instructions

    # Add visualization instructions if requested
    visualization_instructions = """
9. PACING VISUALIZATION:
   - Create a text-based visualization that represents the pacing patterns
   - Use symbols to indicate dense/crowded sections (e.g., "###") and leaps/transitions (e.g., "->")
   - Map the pacing flow throughout the manuscript to identify rhythm patterns
   - Include a legend explaining the visualization symbols
"""

    if include_visualization:
        instruction_set += visualization_instructions

    # Construct the focus areas emphasis
    focus_areas_text = ", ".join(focus_areas)

    # Adjust instructions based on sensitivity level
    sensitivity_instructions = {
        "low": "Focus only on the most significant pacing issues that affect readability and engagement.",
        "medium": "Identify moderate to major pacing issues, balancing technical assessment with artistic considerations.",
        "high": "Perform a detailed analysis of all potential pacing patterns, noting even subtle variations in narrative density."
    }
    
    sensitivity_text = sensitivity_instructions.get(sensitivity, sensitivity_instructions["medium"])

    # Construct the full prompt
    instructions = f"""IMPORTANT: NO Markdown formatting

You are an expert literary editor specializing in narrative pacing and structure. Your task is to analyze the provided manuscript for crowding and leaping patterns, focusing particularly on: {focus_areas_text}.

Follow Ursula K. Le Guin's concepts from "Steering the Craft" on controlling scene density through "crowding" (adding intense detail) and "leaping" (jumping over time or events). According to Le Guin, mastering these techniques allows writers to control the reader's experience through the density and sparseness of the narrative.

Sensitivity level: {sensitivity}. {sensitivity_text}

Pay special attention to:
1. CROWDED SECTIONS
   - Paragraphs with intense sensory detail or many quick events
   - Sections where multiple significant actions occur in rapid succession
   - Dense descriptive passages that may overwhelm the reader
   Example: "She grabbed her keys, slammed the door, ran down three flights of stairs, hailed a cab, jumped in, gave the address, texted her boss, checked her makeup, and rehearsed her presentation all before the first stoplight."

2. LEAPING SECTIONS
   - Abrupt jumps in time, location, or perspective without sufficient transition
   - Places where significant events happen "off-screen" between scenes
   - Transitions that may leave readers disoriented or confused
   Example: "John left the party early. Three years later, he returned to find everything had changed."

3. TRANSITION EFFECTIVENESS
   - How smoothly the narrative moves between scenes, settings, and time periods
   - Whether transitions provide enough context for readers to follow leaps
   - If scene changes use appropriate pacing techniques for the content
   Example (effective): "As winter gave way to spring, so too did her grief begin to thaw." 
   Example (ineffective): "They argued bitterly. The wedding was beautiful."

4. PACING PATTERNS
   - Repetitive structures that may create monotony
   - Consistent density that doesn't vary with narrative importance
   - Opportunities to use crowding and leaping more strategically
   Example (problem): Five consecutive scenes that all use the same dense detail level regardless of importance
   Suggestion: Vary detail level to emphasize key moments and quicken pace for transitions

For each pacing issue you identify, provide:
- The relevant passage with the crowding or leaping pattern
- An analysis of its effect on reader experience and narrative flow
- A suggested revision approach that maintains the author's voice and intent

Create a comprehensive pacing analysis with these sections:
{instruction_set}

Format your analysis as a clear, organized report with sections and subsections. Use plain text formatting only (NO Markdown). Use numbered or bulleted lists where appropriate for clarity.

Be specific in your examples and suggestions, showing how crowding and leaping can be adjusted without changing the author's voice or intention. Focus on practical changes that will make the writing more engaging and effective.
"""

    # Combine all sections
    prompt = f"=== MANUSCRIPT ===\n{manuscript_content}\n=== END MANUSCRIPT ===\n\n{instructions}"
    
    return prompt


def run_crowding_leaping_analysis(manuscript_content, args):
    prompt = create_crowding_leaping_prompt(
        manuscript_content, 
        args.analysis_level, 
        args.focus_areas, 
        args.sensitivity,
        args.include_visualization
    )

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

    print(f"Running crowding and leaping analysis...")
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
    """Save the crowding and leaping analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    analysis_level = f"_{args.analysis_level}" if args.analysis_level != "standard" else ""
    visualization = "_with_viz" if args.include_visualization else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"crowding_leaping_evaluator{desc}{analysis_level}{visualization}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== CROWDING AND LEAPING ANALYSIS ===\n\n")
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
    print("\n=== Crowding and Leaping Evaluator Configuration ===")
    print(f"Input file: {args.manuscript_file}")
    print(f"Analysis level: {args.analysis_level}")
    print(f"Focus areas: {', '.join(args.focus_areas)}")
    print(f"Sensitivity level: {args.sensitivity}")
    print(f"Include visualization: {args.include_visualization}")
    print(f"Max request timeout: {args.request_timeout} seconds for each streamed chunk")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    full_response, thinking_content, prompt_token_count, report_token_count = run_crowding_leaping_analysis(
        manuscript_content, args
    )
    
    if full_response:
        stats = f"""
Details:
Analysis type: Crowding and leaping pacing analysis
Analysis level: {args.analysis_level}
Focus areas: {', '.join(args.focus_areas)}
Sensitivity level: {args.sensitivity}
Include visualization: {args.include_visualization}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
        
        save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats)
    else:
        print("Failed to complete crowding and leaping analysis.")


if __name__ == "__main__":
    main()
