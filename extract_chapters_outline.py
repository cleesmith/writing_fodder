import re

def extract_chapters_from_outline(outline_text):
    """
    Extract chapter numbers and titles from an outline text.
    Handles three common formats:
    - 'Chapter X: Title' or 'Chapter X. Title'
    - 'chapter X: Title' or 'chapter X. Title' (lowercase)
    - 'X. Title' or 'X: Title' (just number)
    
    Returns a list of formatted chapters in "Chapter X: Title" format.
    Double quotes around titles are removed if present.
    """
    # Define regex pattern to match all three chapter formats
    pattern = r'^(?:(?:[Cc]hapter\s+)?(\d+)[\.:]?\s+(.+))$'
    
    chapters = []
    
    for line in outline_text.strip().split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if match:
            chapter_num = match.group(1)
            title = match.group(2)
            title = title.strip('"')
            formatted_chapter = f"{chapter_num}. {title}"
            chapters.append(formatted_chapter)
    
    return chapters

def extract_chapters_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            outline_text = file.read()
        return extract_chapters_from_outline(outline_text)
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

if __name__ == "__main__":
    chapters = extract_chapters_from_file("outline.txt")
    
    print("Extracted chapters:")
    for chapter in chapters:
        print(chapter)
