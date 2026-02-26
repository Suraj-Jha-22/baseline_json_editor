import html
import logging
from typing import Optional
from converter.schema import BaselineDocument

logger = logging.getLogger(__name__)

def export_edited_html(baseline_doc: BaselineDocument) -> Optional[str]:
    """
    Converts a BaselineDocument schema into clean, semantic HTML.
    
    Args:
        baseline_doc: The edited BaselineDocument schema
        
    Returns:
        A string containing a full HTML document.
    """
    try:
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"  <title>{html.escape(baseline_doc.title or 'Document')}</title>",
            "  <style>",
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; color: #333; }",
            "    h1, h2, h3, h4, h5, h6 { margin-top: 1.5em; margin-bottom: 0.5em; color: #111; }",
            "    p { margin-bottom: 1em; }",
            "    table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }",
            "    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "    th { background-color: #f5f5f5; }",
            "    blockquote { border-left: 4px solid #ddd; padding-left: 1rem; color: #666; margin-left: 0; }",
            "    pre { background: #f4f4f4; padding: 1rem; overflow-x: auto; border-radius: 4px; }",
            "    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #f4f4f4; padding: 0.2em 0.4em; border-radius: 3px; }",
            "  </style>",
            "</head>",
            "<body>",
        ]

        def process_blocks(blocks):
            for block in blocks:
                if not block.content and not block.children:
                    continue
                    
                content = html.escape(block.content or "")
                
                # Check properties first
                is_blockquote = block.properties and block.properties.blockquote
                
                if block.block_type == "SectionHeader":
                    level = 2 # default
                    if block.properties and block.properties.heading_level:
                        level = min(6, max(1, block.properties.heading_level))
                    html_parts.append(f"<h{level}>{content}</h{level}>")
                
                elif block.block_type == "Text":
                    if is_blockquote:
                        html_parts.append(f"<blockquote><p>{content}</p></blockquote>")
                    else:
                        html_parts.append(f"<p>{content}</p>")
                
                elif block.block_type == "List":
                    # We render the text part, then process children inside a list tag
                    list_tag = "ol" if (block.properties and block.properties.list_type == "ordered") else "ul"
                    if content:
                        html_parts.append(f"<p>{content}</p>")
                    html_parts.append(f"<{list_tag}>")
                    if block.children:
                        for child in block.children:
                            child_content = html.escape(child.content or "")
                            html_parts.append(f"<li>{child_content}</li>")
                            # Simple 1-level child logic for now
                    html_parts.append(f"</{list_tag}>")
                    continue # handled children
                
                elif block.block_type == "Table":
                    # For Tables, we generate a simple HTML table structure.
                    # This assumes children might be rows/cells, or content is pre-formatted.
                    # Since Marker/Vision APIs sometimes dump table content as markdown or raw text in `content`
                    # we will wrap it in a pre block if it's not structured children
                    if block.children:
                        html_parts.append("<table>")
                        # Basic assumption of a list of list rows
                        for row in block.children:
                            html_parts.append("<tr>")
                            for cell in row.children:
                                cell_content = html.escape(cell.content or "")
                                html_parts.append(f"<td>{cell_content}</td>")
                            html_parts.append("</tr>")
                        html_parts.append("</table>")
                    else:
                        # Fallback if the whole table is just a string (markdown representation)
                        html_parts.append(f"<pre><code>{content}</code></pre>")
                
                elif block.block_type == "Code":
                    html_parts.append(f"<pre><code>{content}</code></pre>")
                
                elif block.block_type == "Equation":
                    # Wrap in simple div, LaTeX rendering requires MathJax/KaTeX
                    html_parts.append(f"<div class='equation'>\\[ {content} \\]</div>")
                
                else:
                    # Fallback for Generic or unknown types
                    html_parts.append(f"<div>{content}</div>")
                
                # Process children specifically if not already handled
                if block.children and block.block_type not in ["List", "Table"]:
                    html_parts.append("<div class='children' style='margin-left: 1rem;'>")
                    process_blocks(block.children)
                    html_parts.append("</div>")

        for page in baseline_doc.pages:
            html_parts.append(f"<div class='page' id='page-{page.page_number}'>")
            process_blocks(page.blocks)
            html_parts.append("</div>")
            if page != baseline_doc.pages[-1]:
                html_parts.append("<hr style='border: 0; border-top: 1px dashed #ccc; margin: 2rem 0;' />")

        html_parts.append("</body>")
        html_parts.append("</html>")
        
        return "\n".join(html_parts)
    except Exception as e:
        logger.error(f"Error during HTML export: {e}")
        return None
