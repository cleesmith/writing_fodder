// This defines our removeMarkdown function in the global scope for browser use
window.removeMarkdown = (function() {
  return function(md, options) {
    // Set default options if none provided
    options = options || {};
    options.listUnicodeChar = options.hasOwnProperty('listUnicodeChar') ? options.listUnicodeChar : false;
    options.stripListLeaders = options.hasOwnProperty('stripListLeaders') ? options.stripListLeaders : true;
    options.gfm = options.hasOwnProperty('gfm') ? options.gfm : true;
    options.useImgAltText = options.hasOwnProperty('useImgAltText') ? options.useImgAltText : true;
    options.preserveBlockSpacing = options.hasOwnProperty('preserveBlockSpacing') ? options.preserveBlockSpacing : true;

    var output = md || '';

    // Remove horizontal rules
    output = output.replace(/^(-\s*?|\*\s*?|_\s*?){3,}\s*$/gm, '');

    try {
      // Handle list markers
      if (options.stripListLeaders) {
        if (options.listUnicodeChar) {
          output = output.replace(/^([\s\t]*)([\*\-\+]|\d+\.)\s+/gm, options.listUnicodeChar + ' $1');
        } else {
          output = output.replace(/^([\s\t]*)([\*\-\+]|\d+\.)\s+/gm, '$1');
        }
      }

      // Handle GitHub Flavored Markdown features
      if (options.gfm) {
        output = output
          .replace(/\n={2,}/g, '\n')
          .replace(/~{3}.*\n/g, '')
          // Improved code block handling
          .replace(/(`{3,})([\s\S]*?)\1/gm, function(match, p1, p2) {
            return p2.trim() + '%%CODEBLOCK_END%%\n';
          })
          .replace(/~~/g, '');
      }

      // Process main markdown elements
      output = output
        // Remove HTML tags
        .replace(/<[^>]*>/g, '')
        // Remove setext headers
        .replace(/^[=\-]{2,}\s*$/g, '')
        // Remove footnotes
        .replace(/\[\^.+?\](\: .*?$)?/g, '')
        .replace(/\s{0,2}\[.*?\]: .*?$/g, '')
        // Handle images and links
        .replace(/\!\[(.*?)\][\[\(].*?[\]\)]/g, options.useImgAltText ? '$1' : '')
        .replace(/\[(.*?)\][\[\(].*?[\]\)]/g, '$1')
        // Better blockquote handling with spacing
        .replace(/^\s*>+\s?/gm, function(match) {
          return options.preserveBlockSpacing ? '\n' : '';
        })
        // Remove list markers again (thorough cleanup)
        .replace(/^([\s\t]*)([\*\-\+]|\d+\.)\s+/gm, '$1')
        // Remove reference links
        .replace(/^\s{1,2}\[(.*?)\]: (\S+)( ".*?")?\s*$/g, '')
        // Remove headers
        .replace(/^(\n)?\s{0,}#{1,6}\s+| {0,}(\n)?\s{0,}#{0,} {0,}(\n)?\s{0,}$/gm, '$1$2$3')
        // Remove emphasis
        .replace(/([\*_]{1,3})(\S.*?\S{0,1})\1/g, '$2')
        .replace(/([\*_]{1,3})(\S.*?\S{0,1})\1/g, '$2')
        // Remove code markers
        .replace(/`(.+?)`/g, '$1');

      // Final cleanup and spacing
      output = output
        // Replace code block markers with proper spacing
        .replace(/%%CODEBLOCK_END%%\n/g, '\n\n\n')
        // Normalize multiple newlines while preserving block spacing
        .replace(/\n{4,}/g, '\n\n\n')
        .replace(/\n{3}/g, '\n\n')
        // Clean up any trailing whitespace
        .trim();

    } catch(e) {
      console.error('Error processing markdown:', e);
      return md;
    }
    return output;
  };
})();
