import re

def clean_forbidden_punctuation(text):
    """
    Removes or replaces forbidden punctuation patterns from AI-generated text.
    
    This function systematically processes text to remove all forbidden punctuation
    patterns specified in the AI instructions: ellipsis, em dashes, specific punctuation
    sequences (.,-  ,-  -,  --), and asterisks.
    
    Args:
        text (str): The input text to be cleaned
        
    Returns:
        str: The cleaned text with all forbidden punctuation patterns removed or replaced
    """
    # Dictionary of patterns and their replacements
    replacements = {
        r'-,': ',',              # Replace -, with just a comma
        # r'\.\.\. ': ' ',         # Replace ellipsis with a space
        # r'\.\.\.': ' ',          # Replace ellipsis with a space
        # r'… ': ' ',              # Unicode ellipsis character
        # r'…': '',                # Unicode ellipsis character
        r'—': ', ',              # Replace em dash with a space
        r'–': ' ',               # En dash as well (often confused with em dash)
        r'\.,-': '.',            # Replace .,- with just a period
        r'\.-': '.',             # Replace ., with just a period
        r'\.,': '.',             # Replace ., with just a period
        r',-': ',',              # Replace ,- with just a comma
        # r'-,': '-',              # Replace -, with just a hyphen
        r'--': ' ',              # Replace double hyphen with a space
        r'\*': '',               # Remove asterisks completely
    }
    
    # Process each pattern in turn
    cleaned_text = text
    for pattern, replacement in replacements.items():
        cleaned_text = re.sub(pattern, replacement, cleaned_text)
    
    # Additional safety checks for multi-character sequences
    # This catches any remaining multi-asterisk patterns
    cleaned_text = re.sub(r'\*+', '', cleaned_text)
    
    # This catches any attempt to create ellipsis with 4+ periods
    cleaned_text = re.sub(r'\.{4,}', '.', cleaned_text)
    
    return cleaned_text

# Example usage in a post-processing pipeline
def post_process_ai_text(ai_response_text):
    """
    Performs post-processing on AI-generated text to ensure it follows formatting rules.
    
    Args:
        ai_response_text (str): The raw text received from the AI
        
    Returns:
        str: The processed text ready for use
    """
    # Clean forbidden punctuation
    cleaned_text = clean_forbidden_punctuation(ai_response_text)
    
    # You could add additional post-processing steps here:
    # - Remove excess whitespace
    # - Fix formatting of times (ensure proper space before am/pm)
    # - Other custom processing requirements
    
    return cleaned_text

# Example of how to use this in your workflow
if __name__ == "__main__":
    # NO ellipsis  NO em dash  NO '.,-'  NO ',-'  NO '-,'  NO '--'  NO '*'
    # This would be the text from your AI API response
    sample_text = """
    She closed the book., The story had--moved her deeply... It was—without a doubt—the 
    best novel... she'd read in years. The character's...journey from poverty-, to success 
    made her,- reflect on-, her own life.,- She thought: * What if I had made different choices? *
    The ending was unexpected-- but satisfying.
    """
    
    # Process the text
    processed_text = post_process_ai_text(sample_text)
    
    # Show the before and after
    print("BEFORE PROCESSING:")
    print(sample_text)
    print("\nAFTER PROCESSING:")
    print(processed_text)
