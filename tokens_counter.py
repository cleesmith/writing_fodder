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

print(response)
print(response.model_dump_json())
print(f"input_tokens: {response.input_tokens}")

