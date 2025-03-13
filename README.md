# Writing Toolkit &nbsp;&nbsp;&nbsp;&nbsp;*AI powered writing tools*

> <h3>No more staring at blank pages or watching that cursor blink anxiously. This collection of tools helps you generate outlines, world-building details, and chapter drafts that may not be literary masterpieces, but they give you valuable starting material that follows your specific instructions.<br><br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Transform writer's block into writer's building blocks.</h3>

---

An AI-assisted writing system that leverages Anthropic's Claude 3.7 Sonnet API to take writers from initial concept through to a completed manuscript draft. This toolkit uses Claude's 32K thinking budget and 128K output capabilities to produce quality prose.

## Overview

This toolkit provides a complete end-to-end pipeline for creative writing projects, with each component building upon the outputs of previous steps:

1. **brainstorm.py** - Expands an initial premise into a foundational concept document and compendium
2. **outline_writer.py** - Creates a detailed chapter-by-chapter outline based on your concept
3. **chapters_from_outline.py** - Extracts and standardizes a list of chapters from the outline for easier processing
4. **world_writer.py** - Uses the outline to generate a detailed world compendium with settings, history, and character profiles
5. **chapter_writer.py** - Uses the outline, chapters list, world document, and existing manuscript to write rough draft chapters

## Key Features

- Uses Claude 3.7 Sonnet's API
- Takes advantage of Claude's 32K thinking budget for reasoning through the writing process
- Uses 128K output capacity for generation
- Maintains consistency across chapters through reference to previous content
- Provides token management, timeout handling, and organized file storage
- Supports continuing and expanding upon existing work

## Ideal For

- Fiction writers looking for AI assistance with longer works
- Non-fiction authors creating structured, research-based content
- Screenwriters and playwrights developing scripts with consistent characters
- Authors who want to maintain creative control while accelerating the drafting process
- Writing projects that benefit from consistent worldbuilding and character development
- Anyone interested in exploring the capabilities of AI in creative writing

Each script in this toolkit is designed to be used sequentially, though experienced users can also leverage individual components as needed for their specific writing workflow.

Think of them as ***creative partners*** that help you overcome writer's block or explore new directions for your story, while maintaining consistency with what you've already established.

## Tools Overview

### 1. Outline Writer

The `outline_writer.py` script helps you develop a detailed outline for your novel. It takes your high-level concept and generates a structured outline with chapter titles and key plot points.

```
python -B outline_writer.py --request "A sci-fi detective story where agent Havre disconnects from the collective consciousness to hunt thought manipulators" --sections 4 --chapters 24 --detailed --title "Dire Consequences" --genre "Science Fiction Noir"
```

### 2. World Builder

The `world_writer.py` script uses **outline.txt** to help you create detailed world-building elements for your story, including settings, cultures, technologies, and more.

```
python -B world_writer.py --outline_file outline.txt --detailed
```

### 3. Chapters From Outline

The `chapters_from_outline.py` script simply extracts the chapter numbers and names from your outline file. This utility helps prepare chapter information for use with the chapter writer.

```
python -B chapters_from_outline.py
```

### 4. Chapter Writer

The `chapter_writer.py` script is the main tool that generates individual chapters based on your outline, previous chapters, and character notes.

```
python -B chapter_writer.py --request "3. The First Contact"
```

## Features

- Creates chapters of approximately 1,800-2,500 words <br>&nbsp;&nbsp;&nbsp;*in lots of books the average is ~4,000 words, but AI isn't ready for that ... not yet*
- Maintains consistency with your existing storyline and characters <br>&nbsp;&nbsp;&nbsp;*AI's tend to add new characters, either your outline forgot them, or the AI is being overly creative*
- Follows natural dialogue patterns and narrative pacing
- Formats text according to standard writing conventions
- Saves both the **generated chapter** and the **AI's "thinking process"** <br>&nbsp;&nbsp;&nbsp;*<b>thinking</b> can provide insights into the AI's creative decisions often leading to* **prompt** *adjustments*
- Works in multiple languages &nbsp;&nbsp;&nbsp;*default is English, but I lightly tested: French, Spanish, Polish)*

## Requirements

Before you start:

1. You need **Python** 3.10 or higher installed on your computer
2. You need an **Anthropic API** key 
3. Your Anthropic account must have **Tier 2** or **Tier 3** API access level
4. You need to install the **Anthropic Python SDK** library (version 0.49.0 recommended)
5. This tool uses &nbsp;***Claude 3.7 Sonnet***&nbsp; with &nbsp;***"thinking" enabled***&nbsp; plus &nbsp;***beta***&nbsp; version of &nbsp;***128K output***&nbsp;<br> &nbsp;&nbsp;&nbsp;*these new capabilities have made a big improvement in its writing while staying in the story*

## Setup Instructions

1. Use the *green* **&nbsp;&nbsp;🟩 <> Code ⏷ 🟩&nbsp;&nbsp;** *button* to download the zip file to your computer, or clone this repository
2. Install the required **Anthropic Python SDK** library by running:
	```
	pip install anthropic==0.49.0
	```

3. Set up your **Anthropic API** key in your environment:
   - on Windows: **set ANTHROPIC_API_KEY=your_api_key_here**
   - on Mac/Linux: **export ANTHROPIC_API_KEY=your_api_key_here**

## Required Files

You need to prepare these files before running the chapter writer tool:

1. **outline.txt** - your story outline with chapter summaries (can be generated with outline_writer.py)
2. **manuscript.txt** - your current manuscript *(all previous chapters)*
3. **characters.txt** &nbsp;*(optional)* - information about your characters

> Examples of these 3 files are included, even though all 3 **must** exist they may be empty if desired.

## Writing Workflow

Here's a typical workflow using all tools in the toolkit:

1. **Generate an outline** using outline_writer.py
   ```
   python -B outline_writer.py --request "Your story concept" --sections 4 --chapters 20 --detailed
   ```

2. **Create world-building details** using world_writer.py (optional)
   ```
   python -B world_writer.py --outline outline.txt
   ```

3. **Extract chapter information** using chapters_from_outline.py (optional)
   ```
   python -B chapters_from_outline.py --outline outline.txt
   ```

4. **Write individual chapters** using chapter_writer.py
   ```
   python -B chapter_writer.py --request "1. Chapter Title"
   ```

5. **Generate multiple chapters** using chapter-writer-loop.py
   ```
   python -B chapter-writer-loop.py --start 3 --end 8
   ```

## How to Use Chapter Writer

The basic command to generate a new *(the next)* chapter is:

```
python -B chapter_writer.py --request "3. The First Contact"
```

---

### Watch a demo run:

[![Chapter ](https://img.youtube.com/vi/b-uAZVATJ3w/0.jpg)](https://youtube.com/live/b-uAZVATJ3w)

---

Ensure you have at least these two files: *outline.txt* and *manuscript.txt*, and 
that the **--request** matches the chapter title in *outline.txt* so in this case:
*"3. The First Contact"* must be a line with a number in your outline.

This will create a new Chapter 3 titled "The First Contact" based on your outline and previous chapters.

While *manuscript.txt* must exist, it is ok for it to be empty. Personally, I prefer to write chapter 1 myself, so the AI has a focused reference to follow for its writing. But if the *manuscript.txt* is empty, the AI *can* write chapter 1, if requested, based on *outline.txt*.

You can even have all 3 files empty and Claude will *riff off* of the **--request "whatever"**; a kind of *full-tilt-bozo* writing. But without at least a rough **outline.txt** the writing output is not very useful; then again, maybe you'll experience a *happy accident*.

## Common Options

You can customize how the tools work with these options:

- **--lang** - change the writing language (default: English)<br> example: --lang Spanish

- **--save_dir** - where to save the output files (default: current directory/folder)<br> example: --save_dir yet_another_great_novel

To see all command options for any tool:
```
python -B tool_name.py -h  
```

## Output Files

When you run the chapter writer tool, it creates two files in **--save_dir**, where **XXX** is the chapter number with leading zeros to help your dir/folder show chapters in numerical order:

1. **XXX_chapter_TIMESTAMP.txt** - the generated chapter text

2. **XXX_thinking_TIMESTAMP.txt** - what the AI was thinking

## Writing Tips When Using These Tools

- Make your outline detailed for better results and follow the layout in the example
- Include character descriptions that highlight personalities and motivations
- Review and edit the generated chapters - they're a starting point, not final drafts
- Use the AI's "thinking" file to understand its creative choices, may be useful to make **prompt** adjustments
- You can expect to wait a few minutes for the writing process to complete<br> &nbsp;&nbsp;&nbsp;*my average wait is about 1 minute 30 seconds; but elapsed time really depends on:*<br> &nbsp;&nbsp;&nbsp;*a calm fast computer, your network connection, your API Tier level, and the many moods that are Claude*

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

# Companion Browser Tools for Writers

### This repository also includes a collection of fast lightweight browser-based HTML/JavaScript tools that work locally in your browser. 

> There's no installation:
> ```
> cd more_writing_tools
> open all_tools.html
> ```
> Or just click <b>File</b> then <b>Open File...</b> in your browser, or bookmark it for later.<br>
> Or use them here in this repo: &nbsp;&nbsp;&nbsp;[More Writing Tools](https://cleesmith.github.io/writing_fodder/more_writing_tools/all_tools.html)

These tools complement the Writering Toolkit by helping you format, analyze, and convert text to other formats or prepare your text for publishing:

### File Conversion Tools
- DOCX to plain text (.txt)
- EPUB to plain text (.txt)
- EPUB to HTML (.html)
- Markdown to plain text (.txt)
- PDF to plain text (.txt)
- Text (.txt) to HTML (.html)
- Text to **Vellum**'s single-spaced paragraphs to DOCX (.docx)<br> &nbsp;&nbsp;&nbsp;***so you can "<b>Import Word File...</b>" into Vellum with proper chapters***

### Text Analysis Tools
- Word Frequency Counter - identifies commonly used words and potential overuse
- AI-isms Detector - helps spot common AI writing patterns and phrases
- DOCX HTML Block Viewer - assists with debugging .docx formatting

### Formatting Tools
- Paragraph Wrapper - formats text with line breaks at 70 characters *(ideal for reading)*
- Paragraph Unwrapper - removes line breaks *(useful for Vellum and TTS)*
- Text to Proper Chunks - formats text into 1000-5000 character segments for TextToSpeech (TTS)

All browser tools work directly in your web browser, if you prefer, without sending data to a server, ensuring your writing remains private and secure.

Best of luck with your writing!