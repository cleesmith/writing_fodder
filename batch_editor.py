# python -B batch_editor.py --thinking_budget 96000 --max_tokens 80000
# pip install anthropic
# tested with: anthropic 0.49.0 circa March 2025
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
import os
import argparse
import re
import sys
import json
from datetime import datetime

parser = argparse.ArgumentParser(description='Very thorough thinking about something.')
parser.add_argument('--prompt',             type=str, default="prompt.txt", help="Path to prompt file (default: prompt.txt)")
parser.add_argument('--thinking_budget',    type=int, default=64000, help='Maximum tokens for AI thinking (default: 64000)')
parser.add_argument('--max_tokens',         type=int, default=20000, help='Maximum tokens for output (default: 20000)')
parser.add_argument('--context_window',     type=int, default=204648, help='Context window for Claude 3.7 Sonnet (default: 204648)')
parser.add_argument('--save_dir',           type=str, default=".")
args = parser.parse_args()

def create_batch_request(client, prompt, max_tokens, thinking_budget):
    try:
        message_batch = client.beta.messages.batches.create(
            requests=[
                Request(
                    custom_id="cls-editor",
                    params=MessageCreateParamsNonStreaming(
                        model="claude-3-7-sonnet-20250219",
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": prompt}],
                    )
                )
            ]
        )
        print(message_batch)
        return message_batch.id

        # response = client.beta.messages.batches.create(
        #     model="claude-3-7-sonnet-20250219",
        #     max_tokens=max_tokens,
        #     messages=[{"role": "user", "content": prompt}],
        #     thinking={
        #         "type": "enabled",
        #         "budget_tokens": thinking_budget
        #     },
        #     betas=["output-128k-2025-02-19", "batch-messages-2025-02-19"]
        # )
        # return response.id
    except Exception as e:
        print(f"*** Error creating batch request:\n{e}\n")
        sys.exit(1)

def save_message_id(message_id, prompt):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    info = {
        "message_id": message_id,
        "timestamp": timestamp,
        "prompt_file": args.prompt,
        "prompt_summary": prompt[:100] + "..." if len(prompt) > 100 else prompt  # Save a summary of the prompt
    }
    filename = f"{args.save_dir}/message_id_{timestamp}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2)
    print(f"Message ID saved to: {filename}")
    print(f"To retrieve results later, run: python batch_retriever.py {message_id}")

# read prompt from specified file
try:
    with open(args.prompt, "r", encoding="utf-8") as f:
        prompt = f.read()
    if not prompt.strip():
        print(f"Error: prompt file '{args.prompt}' is empty.")
        sys.exit(1)
except FileNotFoundError:
    print(f"Error: prompt file '{args.prompt}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"Error reading prompt file '{args.prompt}': {e}")
    sys.exit(1)

# calculate a safe max_tokens value
estimated_input_tokens = int(len(prompt) // 5.5)
max_safe_tokens = max(5000, args.context_window - estimated_input_tokens - 1000)  # 1000 token buffer for safety
max_tokens = int(min(args.max_tokens, max_safe_tokens))

absolute_path = os.path.abspath(args.save_dir)
os.makedirs(args.save_dir, exist_ok=True)  # Create the save directory if it doesn't exist

print(f"Read prompt from '{args.prompt}' ({len(prompt)} characters)")
print(f"Max AI model context window: {args.context_window} tokens")
print(f"AI model thinking budget: {args.thinking_budget} tokens")
print(f"Max output tokens: {args.max_tokens} tokens")
print(f"Setting max_tokens to: {max_tokens} (requested: {args.max_tokens}, calculated safe maximum: {max_safe_tokens})")

# ensure max_tokens is always greater than thinking budget
if max_tokens <= args.thinking_budget:
    max_tokens = args.thinking_budget + args.max_tokens
    print(f"Adjusted max_tokens to {max_tokens} to exceed thinking budget of {args.thinking_budget} (room for thinking/writing)")

print(f"Estimated input/prompt tokens: {estimated_input_tokens}")

client = anthropic.Anthropic(max_retries=0)  # no retries = tokens = $'s

try:
    response = client.beta.messages.count_tokens(
        model="claude-3-7-sonnet-20250219",
        messages=[{"role": "user", "content": prompt}],
        thinking={
            "type": "enabled",
            "budget_tokens": args.thinking_budget
        },
        betas=["output-128k-2025-02-19"]
    )
    prompt_token_count = response.input_tokens
    print(f"Actual input/prompt tokens: {prompt_token_count} (via free client.beta.messages.count_tokens)")
except Exception as e:
    print(f"Error:\n{e}\n")

message_id = create_batch_request(client, prompt, max_tokens, args.thinking_budget)
print(f"\nBatch request created with message ID: {message_id}")

save_message_id(message_id, prompt)
print("\nBatch request submitted successfully.")
print(f"###\n")
