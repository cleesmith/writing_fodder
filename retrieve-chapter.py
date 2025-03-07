#!/usr/bin/env python3
"""
retrieve_chapter.py - Retrieves a novel chapter generated using the batch API

This script retrieves both the generated chapter text and the AI's thinking
process from a previously started batch job using the message ID.

Usage:
    python retrieve_chapter.py MESSAGE_ID [--save_dir DIR] [--format_chapter]

Arguments:
    MESSAGE_ID       The message ID from a previously started batch job
    --save_dir       Directory to save the retrieved files (default: current directory)
    --format_chapter Whether to apply text formatting cleanup to the chapter (default: True)
"""

import anthropic
import argparse
import os
import re
import sys
import time
from datetime import datetime


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Retrieve a novel chapter from a batch job")
    parser.add_argument("message_id", help="Message ID from the batch job")
    parser.add_argument("--save_dir", default=".", help="Directory to save the retrieved files")
    parser.add_argument("--format_chapter", action="store_true", default=True, 
                        help="Apply text formatting cleanup to the chapter")
    return parser.parse_args()


def clean_text_formatting(text):
    """
    Clean text formatting by:
    - removing Markdown headers
    - converting em dashes, en dashes and spaced hyphens to commas
    - preserving legitimate hyphenated compound words
    - normalizing quotes
    - removing Markdown formatting (bold, italic, code)
    """
    # remove Markdown header before: Chapter #:
    text = re.sub(r'^#+ .*$', '', text, flags=re.MULTILINE)
    
    # replace em dashes with commas (ensuring proper spacing)
    text = re.sub(r'(\w+)—(\w+)', r'\1, \2', text)
    text = re.sub(r'(\w+)—\s+', r'\1, ', text)
    text = re.sub(r'\s+—(\w+)', r', \1', text)
    text = re.sub(r'—', ', ', text)
    
    # replace en dashes with commas (ensuring proper spacing)
    text = re.sub(r'(\w+)\s*–\s*(\w+)', r'\1, \2', text)
    text = re.sub(r'(\w+)\s*–\s*', r'\1, ', text)
    text = re.sub(r'\s*–\s*(\w+)', r', \1', text)
    text = re.sub(r'–', ', ', text)
    
    # replace hyphens with spaces around them (used as separators)
    text = re.sub(r'(\w+)\s+-\s+(\w+)', r'\1, \2', text)
    text = re.sub(r'(\w+)\s+-\s+', r'\1, ', text)
    text = re.sub(r'\s+-\s+(\w+)', r', \1', text)
    
    # replace double hyphens
    text = re.sub(r'--', ',', text)
    
    # replace special quotes with regular quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r"[''']", "'", text)
    
    # remove Markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # Code
    
    # clean up any double commas or extra spaces around commas
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r',\s+', ', ', text)
    
    return text


def count_words(text):
    """Count the number of words in a text"""
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())


def extract_chapter_number(text):
    """Try to extract chapter number from the text"""
    # Look for patterns like "Chapter 9: Title" or just "Chapter 9"
    chapter_pattern = r'Chapter\s+(\d+)'
    match = re.search(chapter_pattern, text)
    
    if match:
        return match.group(1)
    return "unknown"


def retrieve_batch_result(client, message_id):
    """Retrieve results from a batch job"""
    try:
        print(f"Retrieving results for message ID: {message_id}...")
        message = client.messages.retrieve(message_id)
        
        if message.status == "completed":
            print("✓ Job completed successfully!")
            
            # Extract thinking and response content
            thinking_content = ""
            full_response = ""
            
            for content_block in message.content:
                if content_block.type == "thinking":
                    thinking_content = content_block.thinking
                elif content_block.type == "text":
                    full_response += content_block.text
            
            return {
                "status": "completed",
                "thinking": thinking_content,
                "response": full_response
            }
            
        elif message.status == "in_progress":
            print("⟳ Job is still in progress. Please try again later.")
            return {"status": "in_progress"}
            
        elif message.status == "failed":
            print(f"⨯ Job failed: {message.error}")
            return {"status": "failed", "error": message.error}
            
        else:
            print(f"? Unknown status: {message.status}")
            return {"status": message.status}
            
    except Exception as e:
        error_message = str(e)
        print(f"⨯ Error retrieving results: {error_message}")
        
        if "404" in error_message:
            print("The message ID may be invalid or the results may no longer be available.")
            print("Note: Results typically remain available for up to 30 days.")
        
        return {"status": "error", "error": error_message}


def save_results(results, args):
    """Save the retrieved results to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Extract chapter number if possible
    chapter_num = extract_chapter_number(results["response"])
    formatted_chapter = f"{int(chapter_num):03d}" if chapter_num.isdigit() else "unknown"
    
    # Clean the response if requested
    chapter_text = clean_text_formatting(results["response"]) if args.format_chapter else results["response"]
    
    # Create filenames
    chapter_filename = f"{args.save_dir}/{formatted_chapter}_chapter_{timestamp}.txt"
    thinking_filename = f"{args.save_dir}/{formatted_chapter}_thinking_{timestamp}.txt"
    
    # Save chapter
    with open(chapter_filename, 'w', encoding='utf-8') as file:
        file.write(chapter_text)
    
    # Save thinking if available
    thinking_saved = False
    if results["thinking"]:
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== AI'S THINKING PROCESS ===\n\n")
            file.write(results["thinking"])
            file.write("\n\n=== END AI'S THINKING PROCESS ===\n")
        thinking_saved = True
    
    # Calculate statistics
    word_count = count_words(chapter_text)
    
    # Report results
    print(f"\nChapter saved to: {chapter_filename}")
    if thinking_saved:
        print(f"Thinking process saved to: {thinking_filename}")
    else:
        print("No thinking content was available.")
    
    print(f"\nChapter contains approximately {word_count} words.")
    
    return {
        "chapter_file": chapter_filename,
        "thinking_file": thinking_filename if thinking_saved else None,
        "word_count": word_count
    }


def main():
    args = parse_arguments()
    
    os.makedirs(args.save_dir, exist_ok=True)
    
    try:
        client = anthropic.Anthropic()
    except Exception as e:
        print(f"Error initializing Anthropic client: {e}")
        print("Make sure your API key is properly set in the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    results = retrieve_batch_result(client, args.message_id)
    
    if results["status"] != "completed":
        # Not completed, just exit
        sys.exit(1 if results["status"] in ["failed", "error"] else 0)
    
    save_info = save_results(results, args)
    
    print("\nRetrieval complete.")


if __name__ == "__main__":
    main()
