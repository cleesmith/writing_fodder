#!/usr/bin/env python3
import anthropic
import argparse
import os
import re
import sys
from datetime import datetime


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Retrieve a batch job")
    parser.add_argument("message_id", help="Message ID from the batch job")
    parser.add_argument("--save_dir", default=".", help="Directory to save the retrieved files")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    return parser.parse_args()


def count_words(text):
    """Count the number of words in a text"""
    return len(re.sub(r'(\r\n|\r|\n)', ' ', text).split())


def retrieve_batch_result(client, message_id, debug=False):
    """Retrieve batch results using the streaming API"""
    try:
        print(f"Retrieving results for message ID: {message_id}...")
        
        # Results containers
        results = {
            "status": "completed",
            "thinking": "",
            "response": "",
            "errors": []
        }
        
        success_count = 0
        error_count = 0
        expired_count = 0
        
        # stream results using the beta endpoint:
        # https://docs.anthropic.com/en/docs/build-with-claude/batch-processing
        for result in client.beta.messages.batches.results(message_id):
            if debug:
                print(f"\n--- Debug: Result Object ---")
                print(result)
                print("---------------------------\n")
            
            # Process based on result type
            match result.result.type:
                case "succeeded":
                    success_count += 1
                    custom_id = result.custom_id if hasattr(result, 'custom_id') else f"#{success_count}"
                    print(f"✓ Successfully processed item {custom_id}")
                    
                    # Extract content directly from the result structure
                    # Based on the debug output, we can see that message is in result.result.message
                    try:
                        if hasattr(result.result, 'message'):
                            message = result.result.message
                            if debug:
                                print(f"  Found message with ID: {message.id}")
                            
                            for content_block in message.content:
                                if content_block.type == "text":
                                    results["response"] += content_block.text
                                    if debug:
                                        print(f"  Added {len(content_block.text)} characters of text content")
                                elif content_block.type == "thinking":
                                    results["thinking"] += content_block.thinking
                                    if debug:
                                        print(f"  Added {len(content_block.thinking)} characters of thinking content")
                        else:
                            print(f"  ⚠ No message found in result structure for {custom_id}")
                    except Exception as e:
                        print(f"  ⚠ Error extracting content: {e}")
                        if debug:
                            import traceback
                            traceback.print_exc()
                
                case "errored":
                    error_count += 1
                    custom_id = result.custom_id if hasattr(result, 'custom_id') else f"item_{error_count}"
                    
                    try:
                        error_info = {
                            "custom_id": custom_id,
                            "type": result.result.error.type if hasattr(result.result, 'error') and hasattr(result.result.error, 'type') else "unknown",
                            "message": result.result.error.message if hasattr(result.result, 'error') and hasattr(result.result.error, 'message') else "Unknown error"
                        }
                        results["errors"].append(error_info)
                        
                        error_type = error_info["type"]
                        if error_type == "invalid_request":
                            print(f"⨯ Validation error for {custom_id}: {error_info['message']}")
                        else:
                            print(f"⨯ Server error for {custom_id}: {error_info['message']}")
                    except Exception as e:
                        print(f"⨯ Error processing error information: {e}")
                
                case "expired":
                    expired_count += 1
                    custom_id = result.custom_id if hasattr(result, 'custom_id') else f"item_{expired_count}"
                    print(f"⨯ Request expired for {custom_id}")
                    results["errors"].append({
                        "custom_id": custom_id,
                        "type": "expired",
                        "message": "Request processing time exceeded the limit"
                    })
                
                case _:
                    print(f"? Unknown result type: {result.result.type}")
        
        # Determine overall status based on counts
        if error_count > 0 or expired_count > 0:
            if success_count == 0:
                results["status"] = "failed"
                print("⨯ Job failed: All batch items encountered errors or expired")
            else:
                results["status"] = "partial"
                print(f"⚠ Job partially completed: {success_count} succeeded, {error_count} failed, {expired_count} expired")
        else:
            if success_count > 0:
                print(f"✓ Job completed successfully with {success_count} item{'s' if success_count > 1 else ''}!")
            else:
                results["status"] = "empty"
                print("⚠ No results found for this batch job.")
        
        return results
            
    except Exception as e:
        error_message = str(e)
        print(f"⨯ Error retrieving results: {error_message}")
        
        if "404" in error_message:
            print("The message ID may be invalid or the results may no longer be available.")
            print("Note: Results typically remain available for up to 30 days.")
        
        if debug:
            import traceback
            traceback.print_exc()
        
        return {"status": "error", "error": error_message, "thinking": "", "response": ""}


def save_results(results, args):
    """Save the retrieved results to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save main output if there's any response content
    output_filename = f"{args.save_dir}/output_{timestamp}.txt"
    if results["response"]:
        with open(output_filename, 'w', encoding='utf-8') as file:
            file.write(results["response"])
        word_count = count_words(results["response"])
        print(f"\nOutput saved to: {output_filename}")
        print(f"Output contains approximately {word_count} words.")
    else:
        output_filename = None
        word_count = 0
        print("\nNo response content was generated.")
    
    # Save thinking content if available
    thinking_filename = None
    if results["thinking"]:
        thinking_filename = f"{args.save_dir}/thinking_{timestamp}.txt"
        with open(thinking_filename, 'w', encoding='utf-8') as file:
            file.write("=== AI'S THINKING PROCESS ===\n\n")
            file.write(results["thinking"])
            file.write("\n\n=== END AI'S THINKING PROCESS ===\n")
        print(f"Thinking process saved to: {thinking_filename}")
    else:
        print("No thinking content was available.")
    
    # Save errors if any occurred
    if results.get("errors") and len(results["errors"]) > 0:
        errors_filename = f"{args.save_dir}/errors_{timestamp}.txt"
        with open(errors_filename, 'w', encoding='utf-8') as file:
            file.write("=== BATCH PROCESSING ERRORS ===\n\n")
            for i, error in enumerate(results["errors"], 1):
                file.write(f"Error {i}:\n")
                file.write(f"  Custom ID: {error.get('custom_id', 'N/A')}\n")
                file.write(f"  Type: {error.get('type', 'unknown')}\n")
                file.write(f"  Message: {error.get('message', 'No message')}\n\n")
        print(f"Errors saved to: {errors_filename}")
    
    return {
        "output_file": output_filename,
        "thinking_file": thinking_filename,
        "word_count": word_count
    }


def main():
    """Main function to retrieve and save batch results"""
    args = parse_arguments()
    
    os.makedirs(args.save_dir, exist_ok=True)
    
    try:
        client = anthropic.Anthropic(
            # timeout=args.request_timeout,
            max_retries=0
        )
    except Exception as e:
        print(f"Error initializing Anthropic client: {e}")
        print("Make sure your API key is properly set in the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    results = retrieve_batch_result(client, args.message_id, debug=args.debug)
    
    if results["status"] in ["failed", "error"]:
        # Complete failure, exit with error
        sys.exit(1)
    
    save_info = save_results(results, args)
    
    if results["status"] == "partial":
        # Partial success, exit with warning code
        print("\nRetrieval partially complete with some errors.")
        sys.exit(2)
    elif results["status"] == "empty":
        # No results, exit with a different code
        print("\nNo results were found for this batch job.")
        sys.exit(3)
    else:
        print("\nRetrieval complete.")
        sys.exit(0)


if __name__ == "__main__":
    main()
