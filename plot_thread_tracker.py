#!/usr/bin/env python
# plot_thread_tracker.py
#
# Description: Analyzes a manuscript to identify and track distinct plot threads,
#              showing how they interconnect, converge, and diverge throughout the
#              narrative. Uses textual representation rather than graphics.
#
# Usage: 
# python -B plot_thread_tracker.py --manuscript_file manuscript.txt [--outline_file outline.txt] [--analysis_depth basic|detailed|comprehensive]

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
        description='Analyze manuscript for plot threads and their interconnections using Claude thinking API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B plot_thread_tracker.py --manuscript_file manuscript.txt --analysis_depth comprehensive
  python -B plot_thread_tracker.py --manuscript_file manuscript.txt --outline_file outline.txt --analysis_depth basic
  python -B plot_thread_tracker.py --manuscript_file manuscript.txt --analysis_depth detailed --save_dir reports
        """
    )

    # Create argument groups with section headers
    input_group = parser.add_argument_group('Input Files')
    analysis_group = parser.add_argument_group('Plot Thread Analysis Options')
    api_group = parser.add_argument_group('Claude API Configuration')
    output_group = parser.add_argument_group('Output Configuration')

    # Add arguments to the Input Files group
    input_group.add_argument('--manuscript_file', type=str, required=True,
                           help="File containing the manuscript to analyze (required)")
    input_group.add_argument('--outline_file', type=str, default=None,
                           help="File containing the story outline (optional)")

    # Add arguments to the Analysis Options group
    analysis_group.add_argument('--analysis_depth', type=str, default="comprehensive",
                            choices=["basic", "detailed", "comprehensive"],
                            help="Depth of plot thread analysis to perform (default: comprehensive)")
    analysis_group.add_argument('--analysis_description', type=str, default="",
                            help="Optional description to include in output filenames")
    analysis_group.add_argument('--thread_focus', type=str, nargs='+', default=None,
                            help="Optional list of specific plot threads to focus on (e.g., 'romance' 'mystery')")

    # Add arguments to the Claude API Configuration group
    api_group.add_argument('--context_window',         type=int, default=200000, help='Context window for Claude 3.7 Sonnet (default: 200000)')
    api_group.add_argument('--betas_max_tokens',       type=int, default=128000, help='Maximum tokens for AI output (default: 128000)')
    api_group.add_argument('--thinking_budget_tokens', type=int, default=32000, help='Maximum tokens for AI thinking (default: 32000)')
    api_group.add_argument('--desired_output_tokens',  type=int, default=8000, help='User desired number of tokens to generate before stopping output')
    api_group.add_argument('--request_timeout', type=int, default=300,
                         help='Maximum timeout for each *streamed chunk* of output (default: 300 seconds)')

    # Add arguments to the Output Configuration group
    output_group.add_argument('--save_dir', type=str, default=".",
                            help='Directory to save plot thread analysis reports (default: current directory)')
    output_group.add_argument('--skip_thinking', action='store_true',
                            help='Skip saving the AI thinking process (smaller output files)')
    output_group.add_argument('--ascii_art', action='store_true',
                            help='Include simple ASCII art visualization in the output')

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


def create_prompt(analysis_depth, outline_content, manuscript_content, thread_focus=None, use_ascii=False):
    no_markdown = "IMPORTANT: - NO Markdown formatting"
    
    thread_focus_str = ""
    if thread_focus:
        thread_focus_str = f"Pay special attention to these specific plot threads: {', '.join(thread_focus)}."
    
    ascii_instruction = ""
    if use_ascii:
        ascii_instruction = """
Include simple ASCII art visualizations to represent:
- Thread progressions using horizontal timelines (e.g., Thread A: ----*----*------>)
- Thread connections using branching symbols (e.g., +-- for connections)
- Thread intensity using symbols like | (low), || (medium), ||| (high)
"""
    
    prompts = {
        "basic": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative structure and plot analysis. Conduct a BASIC plot thread analysis of the manuscript, focusing on the main storylines and how they progress. {thread_focus_str}

Focus on identifying:

1. MAIN PLOT THREADS:
   - Identify 3-5 major plot threads running through the manuscript
   - Provide a clear name and short description for each thread
   - Note the primary characters involved in each thread

2. THREAD PROGRESSION:
   - For each identified thread, track where it appears in the manuscript
   - Note key progression points (beginning, major developments, resolution)
   - Provide manuscript locations (using exact text excerpts) for each point

3. BASIC THREAD CONNECTIONS:
   - Identify where major plot threads intersect or influence each other
   - Note convergence points where multiple threads come together
   - Highlight any threads that remain isolated from others

{ascii_instruction}

Organize your analysis by thread, showing each thread's progression and key connection points with other threads. For each thread, include:
- Thread name and description
- Key progression points with manuscript locations
- Major connections to other threads

Present the information in a clear, structured format that makes the plot architecture easy to understand without requiring graphics.
""",

        "detailed": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative structure and plot analysis. Conduct a DETAILED plot thread analysis of the manuscript, tracking how multiple storylines develop and interconnect. {thread_focus_str}

Focus on identifying:

1. PLOT THREAD IDENTIFICATION:
   - Identify all significant plot threads running through the manuscript
   - Classify threads as main plot, subplot, character arc, thematic thread, etc.
   - Provide a clear name and description for each thread
   - Note the primary and secondary characters involved in each thread

2. THREAD PROGRESSION MAPPING:
   - For each thread, track its complete progression through the manuscript
   - Map the initiation, development stages, climax, and resolution
   - Note the intensity/prominence of the thread at different points
   - Identify when threads go dormant and reactivate

3. INTERCONNECTION ANALYSIS:
   - Map where and how plot threads connect to each other
   - Identify causal relationships between thread developments
   - Note where threads converge, diverge, or conflict
   - Analyze how threads support or undermine each other

4. NARRATIVE STRUCTURE ASSESSMENT:
   - Identify how threads align with overall narrative structure
   - Note how multiple threads build toward key story moments
   - Assess thread balance and pacing across the manuscript

{ascii_instruction}

Present your analysis as:
1. A thread directory listing all identified threads with descriptions
2. A progression map for each thread showing its development points
3. An interconnection analysis showing how threads relate to each other
4. A narrative assessment of the overall plot architecture

For each thread entry, include:
- Thread name, type, and key characters
- Detailed progression points with manuscript locations
- Connection points with other threads
- Assessment of thread effectiveness

Use text formatting to create a clear visual structure that shows the relationships between threads without requiring graphics.
""",

        "comprehensive": f"""=== OUTLINE ===
{outline_content}
=== END OUTLINE ===

=== MANUSCRIPT ===
{manuscript_content}
=== END MANUSCRIPT ===

{no_markdown}

You are an expert fiction editor specializing in narrative structure and plot architecture. Conduct a COMPREHENSIVE plot thread analysis of the manuscript, creating a detailed visualization of how all narrative elements interconnect. {thread_focus_str}

Focus on identifying:

1. COMPLETE THREAD IDENTIFICATION:
   - Identify ALL plot threads: main plot, subplots, character arcs, thematic threads, mystery threads, etc.
   - Provide a clear name, type classification, and detailed description for each thread
   - Note all characters involved in each thread with their roles
   - Identify the narrative purpose of each thread

2. DETAILED PROGRESSION TRACKING:
   - For each thread, map its complete journey through the manuscript
   - Track the setup, development stages, complications, climax, resolution
   - Measure thread intensity/prominence at each appearance (minor mention vs. focal point)
   - Note when threads transform or evolve in purpose
   - Track emotional tone shifts within threads

3. COMPLEX INTERCONNECTION MAPPING:
   - Create a detailed map of all thread connections and relationships
   - Identify direct and indirect influences between threads
   - Note where threads support, undermine, mirror, or contrast each other
   - Map causal chains that span multiple threads
   - Identify connection hubs where multiple threads converge

4. STRUCTURAL ARCHITECTURE ANALYSIS:
   - Analyze how threads combine to create the overall narrative structure
   - Identify patterns in how threads are arranged and interwoven
   - Note rhythm and pacing across multiple threads
   - Identify structural strengths and weaknesses in the thread architecture

{ascii_instruction}

Present your analysis in four main sections:
1. THREAD DIRECTORY - Comprehensive listing of all threads with detailed descriptions
2. PROGRESSION MAPS - Detailed development tracking for each thread
3. INTERCONNECTION ATLAS - Mapping of how all threads relate to and influence each other
4. ARCHITECTURAL ASSESSMENT - Analysis of the overall narrative structure created by the threads

For the Interconnection Atlas, create a text-based visualization that shows:
- Direct connections between threads (with connection types)
- Hub points where multiple threads converge
- Patterns of thread interaction throughout the manuscript

Use precise manuscript locations (with exact quotes) to anchor your analysis throughout.
"""
    }
    
    return prompts.get(analysis_depth, "")


def run_plot_thread_analysis(analysis_depth, outline_content, manuscript_content, args):
    """Run a plot thread analysis and return results."""
    prompt = create_prompt(analysis_depth, outline_content, manuscript_content, args.thread_focus, args.ascii_art)

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

    print(f"Running {analysis_depth} plot thread analysis...")
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


def save_report(analysis_depth, full_response, thinking_content, prompt_token_count, report_token_count, args, stats):
    """Save the plot thread analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"plot_thread_analysis_{analysis_depth}{desc}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== PLOT THREAD ANALYSIS DEPTH ===\n")
            file.write(f"{analysis_depth}\n\n")
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
    
    thread_focus_str = ", ".join(args.thread_focus) if args.thread_focus else "All threads"
    
    current_time = datetime.now().strftime("%I:%M:%S %p").lower().lstrip("0")
    print("\n=== Plot Thread Tracker Configuration ===")
    print(f"Analysis depth: {args.analysis_depth}")
    print(f"Thread focus: {thread_focus_str}")
    print(f"ASCII art: {'Enabled' if args.ascii_art else 'Disabled'}")
    print(f"Max request timeout: {args.request_timeout} seconds")
    print(f"Save directory: {os.path.abspath(args.save_dir)}")
    print(f"Started at: {current_time}")
    print("=" * 40 + "\n")
    
    full_response, thinking_content, prompt_token_count, report_token_count = run_plot_thread_analysis(
        args.analysis_depth, outline_content, manuscript_content, args
    )
    
    if full_response:
        stats = f"""
Details:
Analysis depth: {args.analysis_depth} plot thread analysis
Thread focus: {thread_focus_str}
ASCII art: {'Enabled' if args.ascii_art else 'Disabled'}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
        
        save_report(args.analysis_depth, full_response, thinking_content, 
                  prompt_token_count, report_token_count, args, stats)
    else:
        print("Failed to complete plot thread analysis.")


if __name__ == "__main__":
    main()
