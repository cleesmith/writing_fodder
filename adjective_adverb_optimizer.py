#!/usr/bin/env python
# adjective_adverb_optimizer.py
#
# Description: Analyzes manuscript for adjective and adverb usage using the Claude API.
#              Identifies unnecessary modifiers, overused qualifiers, and suggests stronger verbs/nouns
#              to replace adjective-heavy descriptions, following Ursula K. Le Guin's writing advice.
#
# Usage: 
# python -B adjective_adverb_optimizer.py --manuscript_file manuscript.txt [--save_dir reports]

import anthropic
import pypandoc
import os
import argparse
import sys
import time
from datetime import datetime


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Analyze manuscript for adjective and adverb usage using Claude AI.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usages:
  python -B adjective_adverb_optimizer.py --manuscript_file manuscript.txt --analysis_level detailed
  python -B adjective_adverb_optimizer.py --manuscript_file manuscript.txt
  python -B adjective_adverb_optimizer.py --manuscript_file manuscript.txt --save_dir reports
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
    analysis_group.add_argument('--focus_areas', type=str, nargs='+',
                              default=["qualifiers", "adverbs", "adjectives", "imagery"],
                              help="Specific areas to focus analysis on (default: all areas)")

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


def create_modifier_analysis_prompt(manuscript_content, analysis_level, focus_areas):
    """Create a prompt for the AI to analyze adjective and adverb usage."""
    
    # Build instruction section based on analysis level
    basic_instructions = """
1. ADJECTIVE AND ADVERB OVERVIEW:
   - Identify patterns of adjective and adverb usage in the manuscript
   - Highlight the most common qualifiers (very, rather, just, quite, etc.)
   - Note any recurring descriptive patterns

2. MODIFIER OPTIMIZATION OPPORTUNITIES:
   - Identify passages with unnecessary or weak modifiers
   - Point out adverbs that could be replaced with stronger verbs
   - Highlight adjective clusters that could be simplified
   - Suggest specific improvements with examples

3. RECOMMENDATIONS:
   - Provide practical suggestions for strengthening descriptive language
   - Suggest specific verb replacements for adverb+verb combinations
   - Recommend stronger nouns to replace adjective+noun pairs where appropriate
"""

    standard_instructions = basic_instructions + """
4. QUALIFIER ANALYSIS:
   - List overused qualifiers and weakening words (e.g., very, just, quite, really, kind of, sort of)
   - Analyze frequency and impact of these qualifiers on prose strength
   - Identify dialogue vs. narrative patterns in qualifier usage
   - Suggest specific alternatives or eliminations

5. SENSORY LANGUAGE ASSESSMENT:
   - Evaluate balance between different sensory descriptors (visual, auditory, tactile, etc.)
   - Identify opportunities to replace abstract descriptions with concrete sensory details
   - Suggest ways to make descriptions more immediate and vivid
"""

    detailed_instructions = standard_instructions + """
6. CHARACTER-SPECIFIC MODIFIER PATTERNS:
   - For each major character, analyze distinctive modifier patterns in their dialogue or POV sections
   - Identify if modifier usage helps differentiate character voices
   - Suggest improvements to make character voices more distinct through modifier choices

7. STYLISTIC IMPACT ANALYSIS:
   - Assess how current modifier usage affects pace, tone, and atmosphere
   - Identify sections where modifier reduction could improve flow
   - Note sections where additional sensory detail might enrich the prose
   - Compare modifier patterns across different scene types (action, dialogue, description)

8. ADVANCED REPLACEMENT STRATEGIES:
   - Provide examples of metaphor or imagery that could replace adjective-heavy descriptions
   - Suggest specialized vocabulary or domain-specific terms that could replace generic descriptions
   - Offer alternative sentence structures to eliminate dependence on modifiers
"""

    # Choose the appropriate instruction level
    if analysis_level == "basic":
        instruction_set = basic_instructions
    elif analysis_level == "detailed":
        instruction_set = detailed_instructions
    else:  # standard
        instruction_set = standard_instructions

    # Construct the focus area emphasis
    focus_area_text = ", ".join(focus_areas)

    # Construct the full prompt
    instructions = f"""IMPORTANT: NO Markdown formatting

You are an expert literary editor specializing in prose improvement and optimization. Your task is to analyze the provided manuscript for adjective and adverb usage, focusing particularly on: {focus_area_text}.

Follow Ursula K. Le Guin's principle from "Steering the Craft" that "when the quality that the adverb indicates can be put in the verb itself... the prose will be cleaner, more intense, more vivid." Look for opportunities to replace weak verb+adverb combinations with strong verbs, and generic noun+adjective pairs with specific, evocative nouns.

Pay special attention to:
1. Overused qualifiers that weaken prose (very, rather, quite, just, really, somewhat, etc.)
2. Adverbs that could be eliminated by choosing stronger verbs
3. Generic adjectives that add little value (nice, good, bad, etc.)
4. Places where multiple adjectives could be replaced with one precise descriptor or a stronger noun
5. Abstract descriptions that could be made more concrete and sensory

For each issue you identify, provide:
- The original passage
- What makes it less effective
- A specific recommendation for improvement

Create a comprehensive modifier analysis with these sections:
{instruction_set}

Format your analysis as a clear, organized report with sections and subsections. Use plain text formatting only (NO Markdown). Use numbered or bulleted lists where appropriate for clarity.

Be specific in your examples and suggestions, showing how prose can be strengthened without changing the author's voice or intention. Focus on practical changes that will make the writing more vivid, clear, and powerful.
"""

    # Combine all sections
    prompt = f"=== MANUSCRIPT ===\n{manuscript_content}\n=== END MANUSCRIPT ===\n\n{instructions}"
    
    return prompt


def run_modifier_analysis(manuscript_content, args):
    """Run adjective/adverb analysis using Claude API and return results."""
    prompt = create_modifier_analysis_prompt(manuscript_content, args.analysis_level, args.focus_areas)

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

    print(f"Running adjective and adverb optimization analysis...")
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
    """Save the adjective/adverb analysis report and thinking content to files."""
    # Create save directory if it doesn't exist
    os.makedirs(args.save_dir, exist_ok=True)
    
    # Create descriptive filename
    desc = f"_{args.analysis_description}" if args.analysis_description else ""
    analysis_level = f"_{args.analysis_level}" if args.analysis_level != "standard" else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"adjective_adverb_optimizer{desc}{analysis_level}_{timestamp}"
    
    # Save full response
    report_filename = f"{args.save_dir}/{base_filename}.txt"
    with open(report_filename, 'w', encoding='utf-8') as file:
        file.write(full_response)
    
    # Save thinking content if available and not skipped
    if thinking_content and not args.skip_thinking:
        thinking_filename = f"{args.save_dir}/{base_filename}_thinking.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== ADJECTIVE AND ADVERB OPTIMIZATION ANALYSIS ===\n\n")
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
    print("\n=== Adjective Adverb Optimizer Configuration ===")
    print(f"Input file: {args.manuscript_file}")
    print(f"Analysis level: {args.analysis_level}")
    print(f"Focus areas: {', '.join(args.focus_areas)}")
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
Analysis type: Adjective and adverb optimization
Analysis level: {args.analysis_level}
Focus areas: {', '.join(args.focus_areas)}
Max request timeout: {args.request_timeout} seconds
Max AI model context window: {args.context_window} tokens
AI model thinking budget: {args.thinking_budget_tokens} tokens
Max output tokens: {args.betas_max_tokens} tokens

Input tokens: {prompt_token_count}
Output tokens: {report_token_count}
"""
        
        save_report(full_response, thinking_content, prompt_token_count, report_token_count, args, stats)
    else:
        print("Failed to complete adjective and adverb optimization analysis.")


if __name__ == "__main__":
    main()
