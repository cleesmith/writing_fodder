import anthropic

client = anthropic.Anthropic()

# Stream results file in memory-efficient chunks, processing one at a time
for result in client.beta.messages.batches.results(
    "msgbatch_014mbrA4mxSseAVE3N9vMwEF",
):
    match result.result.type:
        case "succeeded":
            print(f"Success! {result.custom_id}\n")
            print(result)
        case "errored":
            if result.result.error.type == "invalid_request":
                # Request body must be fixed before re-sending request
                print(f"Validation error {result.custom_id}")
            else:
                # Request can be retried directly
                print(f"Server error {result.custom_id}")
        case "expired":
            print(f"Request expired {result.custom_id}")
