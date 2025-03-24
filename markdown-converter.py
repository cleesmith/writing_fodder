import pypandoc

def remove_markdown(md_text):
    try:
        return pypandoc.convert_text(md_text, 'plain', format='markdown')
    except Exception as e:
        print(f"Error converting markdown to plain text: {e}")
        print("Make sure pypandoc and pandoc are properly installed.")
        return md_text  # return original text if conversion fails

def main():
    # A more comprehensive set of Markdown syntax, with triple backticks escaped:
    markdown_examples = r"""
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6

Plain paragraph text, with **bold** and *italic* styles, plus ***both***.

> Single-line blockquote

> Multi-line blockquote
> spanning two paragraphs.

- Unordered list item 1
- Unordered list item 2
  - Nested sub-item

1. Ordered item 1
2. Ordered item 2
   1. Nested item A
   2. Nested item B
3. Ordered item 3

Inline `code` example.

\`\`\`python
# Fenced code block (escaped triple backticks)
def hello():
    print("Hello, extended markdown!")
\`\`\`

Horizontal rules:
---
***
___

[Link to example.com](https://example.com "Example Title")

![Tux Image](images/tux.png "Tux the Penguin")

**Table Example**:

| Syntax    | Description |
| --------- | ----------- |
| Header    | Title       |
| Paragraph | Text        |

~~Strikethrough~~ uses double tilde.

Footnotes[^1] can appear in some processors.
[^1]: Footnote explanation here.

Definition lists (in some processors):
Term 1
: Definition 1
Term 2
: Definition 2

- [x] Task list completed item
- [ ] Task list open item

Raw URL: http://www.example.org

That's it!
"""

    # Convert to plain text
    plain_output = remove_markdown(markdown_examples)
    print("CONVERTED OUTPUT:")
    print("-" * 40)
    print(plain_output)
    print("-" * 40)

if __name__ == "__main__":
    main()
