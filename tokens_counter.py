import anthropic
import json

client = anthropic.Anthropic()

prompt_file = "prompt.txt"
try:
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()
    if not prompt.strip():
        print(f"Error: prompt file '{prompt_file}' is empty.")
        sys.exit(1)
except FileNotFoundError:
    print(f"Error: prompt file '{prompt_file}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"Error reading prompt file '{prompt_file}': {e}")
    sys.exit(1)

response = client.beta.messages.count_tokens(
    model="claude-3-7-sonnet-20250219",
    thinking={
        "type": "enabled",
        "budget_tokens": 128000
    },
    messages=[{"role": "user", "content": prompt}],
    betas=["output-128k-2025-02-19"]
)
# print(response)
# print(response.model_dump_json())
print(f"input_tokens: {response.input_tokens}")

context_window = 200000   # total context window size
output_capacity = 128000  # via the beta feature
thinking_tokens = context_window - response.input_tokens
print(f"thinking_tokens: {thinking_tokens}")
if thinking_tokens < 32000:
    print(f"Error: prompt is too large to have a proper thinking budget!")
    sys.exit(1)
max_tokens = thinking_tokens + response.input_tokens
print(f"max_tokens: {max_tokens}")


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

print(f"Running character analysis...")
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

