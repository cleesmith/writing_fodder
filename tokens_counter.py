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

# # cls: yields a lower number:
# response2 = client.beta.messages.count_tokens(
#     model="claude-3-7-sonnet-20250219",
#     messages=[{"role": "user", "content": prompt}],
# )
# # print(response2)
# # print(response2.model_dump_json())
# print(f"input_tokens: {response2.input_tokens}")

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


# # Use actual token count from the API response
# input_tokens = response.input_tokens

# # Calculate available tokens for thinking
# # Here we account for the 128K output capacity from the beta
# context_total = 200000  # Total context window size
# output_capacity = 128000  # From the beta feature
# reserved_for_output = min(args.max_tokens, output_capacity)  # Your desired output size
# print(f"reserved_for_output={reserved_for_output}")

# # Maximum thinking budget (with safety buffer)
# buffer = 1000
# thinking_budget = context_total - input_tokens - reserved_for_output - buffer
# # Ensure it's a positive number
# thinking_budget = max(0, thinking_budget)
# print(f"thinking_budget={thinking_budget}")


