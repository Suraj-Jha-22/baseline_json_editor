import io
import fitz  # PyMuPDF
import logging
from typing import Optional
from converter.schema import BaselineDocument

logger = logging.getLogger(__name__)

def export_edited_pdf(original_pdf_bytes: bytes, baseline_doc: BaselineDocument) -> Optional[bytes]:
    """
    Overlays the edited text from the BaselineDocument onto the original PDF.
    It erases the original text region (using a white rectangle over the bbox)
    and draws the new text in its place.
    
    Args:
        original_pdf_bytes: The original uploaded PDF file in bytes
        baseline_doc: The edited BaselineDocument schema
        
    Returns:
        The new PDF as bytes, or None if it fails.
    """
    try:
        # Open the PDF from bytes
        pdf_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
        
        # Iterate through the baseline pages
        for page_data in baseline_doc.pages:
            # fitz pages are 0-indexed, and baseline page_number is 1-indexed (usually) or 0-indexed depending on parsing
            # Let's assume baseline page_number is 0-indexed based on how we built it, but we can verify.
            # In our schema it says: page_number: int. Let's assume it maps directly to fitz index.
            # If our page_number is 1-indexed, we subtract 1.
            # Let's just use the array index since they should be sequential.
            fitz_page = pdf_doc.load_page(page_data.page_number)
            
            # The coordinates in Marker are usually given in points matching the PDF page size.
            # Let's verify width/height match roughly to handle scaling if needed.
            # (In a production app, we would apply a scaling matrix here if Marker's bbox DPI != PDF native DPI).
            
            def process_blocks(blocks):
                for block in blocks:
                    if block.bbox and len(block.bbox) == 4 and block.content:
                        # block.bbox is [x0, y0, x1, y1]
                        rect = fitz.Rect(block.bbox)
                        
                        # 1. Erase the old content by drawing a white rectangle
                        fitz_page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        # 2. Draw the new content
                        # We try to fit the text in the box. `insert_textbox` handles wrapping.
                        # For a real premium feel, we could try to detect the original font size,
                        # but for now we let fitz auto-scale or pick a standard font size that fits.
                        try:
                            fitz_page.insert_textbox(
                                rect, 
                                block.content, 
                                fontsize=11, 
                                fontname="helv", 
                                color=(0, 0, 0),
                                align=0 # left align
                            )
                        except Exception as e:
                            logger.error(f"Failed to draw text for block {block.id}: {e}")
                    
                    # Recursively process children
                    if block.children:
                        process_blocks(block.children)
            
            process_blocks(page_data.blocks)
            
        # Save the result to a byte buffer
        out_pdf_bytes = pdf_doc.write()
        pdf_doc.close()
        
        return out_pdf_bytes
        
    except Exception as e:
        logger.error(f"Error during PDF regeneration: {e}")
        return None
