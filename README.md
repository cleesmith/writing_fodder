# Next Chapter Writer - AI-powered chapter generation for writers

## What is Next Chapter Writer?

Next Chapter Writer is a tool that helps novelists, fiction writers, and storytellers generate new chapters for their books using Claude, an AI assistant. The tool reads your outline, previous chapters, and character notes, then creates a new chapter that fits naturally with your story and writing style.

Think of it as a creative partner that helps you overcome writer's block or explore new directions for your story - while maintaining consistency with what you've already written.

## Features

- Creates chapters of approximately 1,800-2,500 words
- Maintains consistency with your existing storyline and characters
- Follows natural dialogue patterns and narrative pacing
- Formats text according to standard writing conventions
- Works in multiple languages (default is English)
- Saves both the generated chapter and the AI's "thinking process" (which can provide insights into creative decisions)

## Requirements

Before you start:

1. You need Python 3.10 or higher installed on your computer
2. You need an Anthropic API key 
3. Your Anthropic account must have Tier 2 or Tier 3 API access level
4. The tool specifically uses Claude 3.7 Sonnet with "thinking" enabled and the beta version with 128K output capability
5. You need to install the Anthropic Python library (version 0.49.0 recommended)

## Setup Instructions

1. Clone or download this repository to your computer
2. Install the required Anthropic library by running:
   pip install anthropic==0.49.0

3. Set up your Anthropic API key in your environment:
   - On Windows: set ANTHROPIC_API_KEY=your_api_key_here
   - On Mac/Linux: export ANTHROPIC_API_KEY=your_api_key_here

## Required Files

You need to prepare these files before running the tool:

1. **outline.txt** - Your story outline with chapter summaries
2. **manuscript.txt** - Your current manuscript (all previous chapters)
3. **characters.txt** (optional) - Information about your characters

## How to Use

The basic command to generate a new chapter is:

```
python -B write_next_chapter_claude37sonnet.py --request "Chapter 9: The Dark Forest"
```

This will create a new Chapter 9 titled "The Dark Forest" based on your outline and previous chapters.

## Common Options

You can customize how the tool works with these options:

- **--lang** - Change the writing language (default: English)
  Example: --lang Spanish

- **--max_tokens** - Control the maximum length (default: 9000)
  Example: --max_tokens 12000

- **--save_dir** - Where to save the output files (default: current directory)
  Example: --save_dir my_novel

## Output Files

When you run the tool, it creates two files:

1. **XXX_chapter_TIMESTAMP.txt** - The generated chapter text
   (XXX is the chapter number with leading zeros)

2. **XXX_thinking_TIMESTAMP.txt** - What the AI was thinking
   (This can help you understand why certain narrative choices were made)

## Writing Tips When Using This Tool

- Make your outline detailed for better results
- Include character descriptions that highlight personalities and motivations
- Review and edit the generated chapters - they're a starting point, not final drafts
- Use the AI's "thinking" file to understand its creative choices

## Example Command

```
python -B write_next_chapter_claude37sonnet.py --request "Chapter 5: The Unexpected Visitor" --lang French --save_dir my_french_novel
```

This would generate Chapter 5 in French and save it to the "my_french_novel" directory.

## Need Help?

If you run into problems:

- Make sure your outline and manuscript files exist and are properly formatted
- Check that your API key is set correctly
- Verify that your Anthropic account has the required Tier 2 or Tier 3 access
- Try using shorter chapters if you're hitting token limits

---

## Companion Browser Tools for Writers

This repository also includes a collection of browser-based HTML/JavaScript tools that work locally in your browser without sending data to any server. 

See the folder: 

```more_writing_tools```

These tools complement the Next Chapter Writer by helping you format, analyze, and prepare your text for publishing or covert text to other formats:

### File Conversion Tools
- DOCX to plain text (.txt)
- EPUB to plain text (.txt)
- EPUB to HTML (.html)
- Markdown to plain text (.txt)
- PDF to plain text (.txt)
- Text (.txt) to HTML (.html)
- Text to Vellum to DOCX (.docx)

### Text Analysis Tools
- Word Frequency Counter - identifies commonly used words and potential overuse
- AI-isms Detector - helps spot common AI writing patterns and phrases
- DOCX HTML Block Viewer - assists with debugging document formatting

### Formatting Tools
- Paragraph Wrapper - formats text with line breaks at 70 characters (ideal for reading)
- Paragraph Unwrapper - removes line breaks (useful for Vellum and TTS)
- Text to Proper Chunks - formats text in 1000-5000 character segments for TextToSpeech

All browser tools work directly in your web browser without sending data to a server, ensuring your writing remains private and secure.

Happy writing!
