# Chapter Writer - AI-powered chapter generation

> <h3>No more staring at blank pages or watching that cursor blink anxiously. This tool generates chapter drafts that may not be literary masterpieces, but they give you valuable starting material that follows your specific instructions.<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Transform writer's block into writer's building blocks.</h3>

---

## What is Chapter Writer?

Chapter Writer is a tool that helps novelists, fiction writers, and storytellers generate new chapters for their books using Claude, an AI assistant. The tool reads your outline, previous chapters, and character notes, then creates a new chapter that fits naturally with your story and writing style *(as best it can)*.

Think of it as a creative partner that helps you overcome writer's block or explore new directions for your story - while maintaining consistency with what you've already written.

## Features

- Creates chapters of approximately 1,800-2,500 words <br>&nbsp;&nbsp;&nbsp;*in lots of books the average is ~4,000 words, but AI isn't ready for that ... not yet*
- Maintains consistency with your existing storyline and characters <br>&nbsp;&nbsp;&nbsp;*AI's tend to add new characters, either your outline forgot them, or the AI is being overly creative*
- Follows natural dialogue patterns and narrative pacing
- Formats text according to standard writing conventions
- Saves both the **generated chapter** and the **AI's "thinking process"** <br>&nbsp;&nbsp;&nbsp;*<b>thinking</b> can provide insights into the AI's creative decisions often leading to* **prompt** *adjustments*
- Works in multiple languages &nbsp;&nbsp;&nbsp;*default is English, but I lightly tested: French, Spanish, Polish)*

## Requirements

Before you start:

1. You need Python 3.10 or higher installed on your computer
2. You need an Anthropic API key 
3. Your Anthropic account must have Tier 2 or Tier 3 API access level
4. This tool uses Claude 3.7 Sonnet with "thinking" enabled plus beta version of 128K output<br> &nbsp;&nbsp;&nbsp;*these new capabilities have made a big improvement in its writing and staying in the story*
5. You need to install the Anthropic Python library (version 0.49.0 recommended)

## Setup Instructions

1. Clone or download this repository to your computer
2. Install the required Anthropic library by running:
	```
   	pip install anthropic==0.49.0
   	```

3. Set up your Anthropic API key in your environment:
   - on Windows: **set ANTHROPIC_API_KEY=your_api_key_here**
   - on Mac/Linux: **export ANTHROPIC_API_KEY=your_api_key_here**

## Required Files

You need to prepare these files before running the tool:

1. **outline.txt** - your story outline with chapter summaries
2. **manuscript.txt** - your current manuscript *(all previous chapters)*
3. **characters.txt** &nbsp;*(optional)* - information about your characters

> Examples of these 3 files are included.

## How to Use

This tool is a single python *.py* file with only one dependency: **anthropic's sdk** installed using pip.

The basic command to generate a new *(the next)* chapter is:

```
python -B chapter_writer.py --request "3. The First Contact"
```

Ensure you have at least these two files: *outline.txt* and *manuscript.txt*, and 
that the **--request** matches the chapter title in *outline.txt* so in this case:
*"3. The First Contact"* must be a line with a number in your outline.

This will create a new Chapter 3 titled "The First Contact" based on your outline and previous chapters.

## Common Options

You can customize how the tool works with these options:

- **--lang** - change the writing language (default: English)<br> example: --lang Spanish

- **--save_dir** - where to save the output files (default: current directory/folder)<br> example: --save_dir yet_another_great_novel

To see all command options:
```
python -B chapter_writer.py -h  
```

## Output Files

When you run the tool, it creates two files in **--save_dir**, where **XXX** is the chapter number with leading zeros to help your dir/folder show chapters in numerical order:

1. **XXX_chapter_TIMESTAMP.txt** - the generated chapter text

2. **XXX_thinking_TIMESTAMP.txt** - what the AI was thinking

## Writing Tips When Using This Tool

- Make your outline detailed for better results and follow they layout in the example
- Include character descriptions that highlight personalities and motivations
- Review and edit the generated chapters - they're a starting point, not final drafts
- Use the AI's "thinking" file to understand its creative choices, may be useful to make **prompt** adjustments
- You can expect to wait a few minutes for the writing process to complete<br> &nbsp;&nbsp;&nbsp;*my average wait is about 1 minute 30 seconds; it also depends:*<br> &nbsp;&nbsp;&nbsp;*on your network connection, your API Tier level, and the many moods that are Claude*

## Example Command

```
python -B chapter_writer.py --request "3. The First Contact" --lang French --save_dir mon_roman_français
```

This would generate Chapter 3 in French and save it to the "mon_roman_français" directory.

## Need Help?

If you run into problems:

- Make sure your outline and manuscript files exist and are properly formatted
- Check that your API key is set correctly
- Verify that your Anthropic account has the required Tier 2 or Tier 3 access

---

---

## Companion Browser Tools for Writers

This repository also includes a collection of fast lightweight browser-based HTML/JavaScript tools that work locally in your browser. 

> There's no installation:
> ```
> cd more_writing_tools
> open all_tools.html
> ```
> Or just click <b>File</b> then <b>Open File...</b> in your browser, or bookmark it for later.
> &nbsp;<br>
> Or use them here in this repo:
> &nbsp;<br>
> [More Writing Tools](https://cleesmith.github.io/writing_fodder/more_writing_tools/all_tools.html)

These tools complement the Chapter Writer by helping you format, analyze, and convert text to other formats or prepare your text for publishing:

### File Conversion Tools
- DOCX to plain text (.txt)
- EPUB to plain text (.txt)
- EPUB to HTML (.html)
- Markdown to plain text (.txt)
- PDF to plain text (.txt)
- Text (.txt) to HTML (.html)
- Text to Vellum to DOCX (.docx) ***... so you can "<b>Import Word File...</b>" into Vellum with proper chapters***

### Text Analysis Tools
- Word Frequency Counter - identifies commonly used words and potential overuse
- AI-isms Detector - helps spot common AI writing patterns and phrases
- DOCX HTML Block Viewer - assists with debugging .docx formatting

### Formatting Tools
- Paragraph Wrapper - formats text with line breaks at 70 characters (ideal for reading)
- Paragraph Unwrapper - removes line breaks (useful for Vellum and TTS)
- Text to Proper Chunks - formats text in 1000-5000 character segments for TextToSpeech

All browser tools work directly in your web browser without sending data to a server, ensuring your writing remains private and secure.

Best of luck with your writing!
