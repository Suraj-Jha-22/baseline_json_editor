"""
Fast Vision API Document Conversion.

Replaces the local, heavy `marker-pdf` models with a direct call to 
OpenAI (GPT-4o-mini) or Google Gemini (1.5 Flash) Vision APIs.
This guarantees <2s extraction per page while adhering exactly 
to the Baseline JSON schema via Structured Outputs.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import List, Optional

import pypdfium2
from dotenv import load_dotenv
from PIL import Image

from converter.schema import (
    BaselineBlock,
    BaselineDocument,
    BaselineMetadata,
    BaselinePage,
)

logger = logging.getLogger(__name__)

# Load API keys from .env
load_dotenv()


def encode_image_base64(image: Image.Image) -> str:
    """Convert a PIL Image to base64 JPEG."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def get_page_image_from_path(filepath: str, page_num: int, dpi: int = 150) -> Image.Image:
    """Render a page from a local PDF file as a PIL Image."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        doc = pypdfium2.PdfDocument(filepath)
        page = doc[page_num]
        img = page.render(scale=dpi / 72).to_pil().convert("RGB")
        return img
    else:
        # If it's already an image
        return Image.open(filepath).convert("RGB")


def get_total_pages(filepath: str) -> int:
    """Get the total number of pages in the document."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        doc = pypdfium2.PdfDocument(filepath)
        return len(doc)
    return 1


SYSTEM_PROMPT = """You are a perfect data extraction system.
Your job is to look at the provided document (image or HTML chunk) and extract its FULL structure and ALL content into the required JSON schema.
- Identify all distinct blocks: SectionHeaders, Text paragraphs, Tables, Lists, Code, Equations, etc.
- Extract the exact text content for every block.
- **CRITICAL FORMATTING INSTRUCTION**: If inline `style="..."` attributes exist in the HTML (e.g. `color`, `background-color`, `font-family`, `font-size`), you MUST extract these values and populate the corresponding fields inside the block's `properties` object. Do not ignore them.
- For SectionHeaders, carefully set the heading_level property.
- Preserve the document structure as best as possible.
Return the exact JSON structure defined by the schema. Do not skip any text.
"""


def extract_page_openai(image_b64: str, page_num: int) -> BaselinePage:
    """Extract page structure using GPT-4o-mini via Structured Outputs."""
    import openai

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": f"Extract all content from this page (Page {page_num + 1}). Make sure every block_type is accurate (SectionHeader, Text, Table, ListItem, etc). Give each block an ID like 'page_{page_num}/Type/Index'."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                    }
                ]
            }
        ],
        response_format=BaselinePage,
        temperature=0.0,
    )
    
    return response.choices[0].message.parsed


def extract_page_gemini(image: Image.Image, page_num: int) -> BaselinePage:
    """Extract page structure using Gemini 1.5 Flash via Structured Outputs."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    prompt = f"{SYSTEM_PROMPT}\n\nExtract all content from this page (Page {page_num + 1}). Make sure every block_type is accurate (SectionHeader, Text, Table, ListItem, etc). Give each block an ID like 'page_{page_num}/Type/Index'."
    
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=[image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BaselinePage,
            temperature=0.0,
        ),
    )
    
    # Needs to be parsed since Gemini returns the JSON string
    return BaselinePage.model_validate_json(response.text)


def convert_document_fast_api(
    filepath: str,
    page_range: Optional[str] = None,
    progress_callback=None,
) -> BaselineDocument:
    """
    Convert a document to Baseline JSON using Vision APIs.
    Prioritizes OpenAI API KEY, falls back to Gemini API KEY.
    """
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    
    if not has_openai and not has_gemini:
        raise ValueError("Neither OPENAI_API_KEY nor GEMINI_API_KEY found in environment or .env file.")

    engine = "OpenAI (GPT-4o-mini)" if has_openai else "Gemini (1.5 Flash)"
    logger.info(f"Using Fast Vision API engine: {engine}")
    
    if progress_callback:
        progress_callback(0.05, f"Initializing {engine} API extraction...")

    original_filepath = filepath

    # Pre-process DOCX files natively into HTML for the Vision API
    orig_ext = os.path.splitext(filepath)[1].lower()
    if orig_ext == ".docx":
        logger.info("DOCX detected. Converting to HTML using mammoth for Vision API processing...")
        if progress_callback:
            progress_callback(0.08, "Converting DOCX to HTML for Fast Vision API...")
        try:
            import mammoth
            import tempfile
            with open(filepath, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
                html_str = result.value
            
            temp_html_path = os.path.join(os.path.dirname(filepath), "converted_docx.html")
            with open(temp_html_path, "w", encoding="utf-8") as f:
                f.write(html_str)
                
            filepath = temp_html_path
        except ImportError:
            raise ValueError("The 'mammoth' library is required to process DOCX files with Fast Vision API.")
        except Exception as e:
            raise ValueError(f"Failed to convert DOCX to HTML: {e}")

    total_pages = get_total_pages(filepath)
    pages: List[BaselinePage] = []
    block_type_counts = {}

    pages_to_process = list(range(total_pages))
    if page_range and page_range.strip():
        parsed_pages = set()
        parts = [p.strip() for p in page_range.split(",") if p.strip()]
        for part in parts:
            if "-" in part:
                try:
                    start_str, end_str = part.split("-", 1)
                    start = int(start_str) - 1 # 0-indexed internally
                    end = int(end_str) - 1 
                    if start >= 0 and end < total_pages and start <= end:
                        for p in range(start, end + 1):
                            parsed_pages.add(p)
                except ValueError:
                    logger.warning(f"Invalid page range part: {part}")
            else:
                try:
                    p = int(part) - 1 # 0-indexed internally
                    if 0 <= p < total_pages:
                        parsed_pages.add(p)
                except ValueError:
                    logger.warning(f"Invalid page number: {part}")
        
        if parsed_pages:
            pages_to_process = sorted(list(parsed_pages))
            logger.info(f"Parsed page range to process: {[p+1 for p in pages_to_process]}")
        else:
            logger.warning(f"Could not parse valid pages from '{page_range}', defaulting to all limit 5.")
            pages_to_process = list(range(total_pages))[:5]

    # 1. Check if it's HTML, handle entire file at once
    ext = os.path.splitext(filepath)[1].lower()
    is_html = ext in [".html", ".htm"]
    
    if is_html:
        logger.info("Processing as raw HTML file to bypass image rendering.")
        try:
            from bs4 import BeautifulSoup
            with open(filepath, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                
            # Strip out noisy tags that waste tokens
            for tag in soup(["script", "style", "svg", "nav", "footer", "meta", "noscript", "link"]):
                tag.extract()
                
            # Strip all attributes from tags except basic ones to save tokens
            allowed_attrs = ['id', 'class', 'colspan', 'rowspan', 'style']
            for tag in soup.find_all(True):
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in allowed_attrs:
                        del tag[attr]
                
            body = soup.body if soup.body else soup
            
            # Element-aware chunking
            html_chunks = []
            current_chunk = ""
            children = getattr(body, 'children', [body])
            
            # Use smaller chunks since we are keeping styles now
            for child in children:
                child_str = str(child).strip()
                if not child_str:
                    continue
                
                if len(current_chunk) + len(child_str) > 8000:
                    if current_chunk:
                        html_chunks.append(current_chunk)
                    current_chunk = child_str
                else:
                    current_chunk += child_str
                    
            if current_chunk:
                html_chunks.append(current_chunk)
            
            import concurrent.futures

            def process_html_chunk(chunk_idx, chunk):
                if has_openai:
                    import openai
                    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                    response = client.beta.chat.completions.parse(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": f"Extract all content from this raw HTML chunk into the required JSON schema. Treat this chunk as a single page.\n\n```html\n{chunk}\n```"
                            }
                        ],
                        response_format=BaselinePage,
                        temperature=0.0,
                    )
                    page_data = response.choices[0].message.parsed
                else:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
                    prompt = f"{SYSTEM_PROMPT}\n\nExtract all content from this raw HTML chunk into the required JSON schema. Treat this chunk as a single page.\n\n```html\n{chunk}\n```"
                    response = client.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=[prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=BaselinePage,
                            temperature=0.0,
                        ),
                    )
                    page_data = BaselinePage.model_validate_json(response.text)
                
                # Assign sequential page number based on chunks
                page_data.page_number = chunk_idx + 1
                return page_data

            results = []
            if progress_callback:
                progress_callback(0.08, f"Submitting {len(html_chunks)} HTML chunks to Vision API concurrently...")

            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = {executor.submit(process_html_chunk, idx, chunk): idx for idx, chunk in enumerate(html_chunks)}
                
                if progress_callback:
                    progress_callback(0.1, "Waiting for AI extraction to complete... (This may take 15-45 seconds)")

                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    idx = futures[future]
                    if progress_callback:
                        progress_callback(0.1 + (0.8 * (completed / len(html_chunks))), 
                                          f"Extracting HTML chunk {completed} of {len(html_chunks)}...")
                    try:
                        page_data = future.result()
                        results.append((idx, page_data))
                    except Exception as e:
                        logger.error(f"Failed to extract HTML chunk {idx} via API: {e}")
                        results.append((idx, BaselinePage(
                            page_number=idx + 1,
                            blocks=[BaselineBlock(
                                id=f"page_{idx}/Error/0",
                                block_type="Error",
                                content=f"API Extraction failed for HTML: {str(e)}"
                            )]
                        )))

            results.sort(key=lambda x: x[0])
            for idx, page_data in results:
                pages.append(page_data)
                for block in page_data.blocks:
                    bt = block.block_type
                    block_type_counts[bt] = block_type_counts.get(bt, 0) + 1
        except Exception as e:
            logger.error(f"Failed to extract HTML via API: {e}")
            pages.append(BaselinePage(
                page_number=1,
                blocks=[BaselineBlock(
                    id="page_0/Error/0",
                    block_type="Error",
                    content=f"API Extraction failed for HTML: {str(e)}"
                )]
            ))
    else:
        # 2. STANDARD IMAGE/PDF PIPELINE
        import concurrent.futures

        def process_page(page_num):
            try:
                img = get_page_image_from_path(filepath, page_num)
                if has_openai:
                    img_b64 = encode_image_base64(img)
                    page_data = extract_page_openai(img_b64, page_num)
                else:
                    page_data = extract_page_gemini(img, page_num)
                    
                # Guarantee page number matches
                page_data.page_number = page_num + 1
                return page_data
            except Exception as e:
                logger.error(f"Failed to extract page {page_num+1} via API: {e}")
                return BaselinePage(
                    page_number=page_num + 1,
                    blocks=[BaselineBlock(
                        id=f"page_{page_num}/Error/0",
                        block_type="Error",
                        content=f"API Extraction failed for this page: {str(e)}"
                    )]
                )

        results = []
        if progress_callback:
            progress_callback(0.1, f"Submitting {len(pages_to_process)} pages to Vision API concurrently...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(process_page, page_num): page_num for page_num in pages_to_process}
            
            if progress_callback:
                progress_callback(0.15, "Waiting for AI extraction to complete... (This may take 15-45 seconds)")

            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                page_num = futures[future]
                if progress_callback:
                    progress_pct = 0.15 + (0.8 * (completed / len(pages_to_process)))
                    progress_callback(progress_pct, f"Extracting page {completed} of {len(pages_to_process)} via API...")
                page_data = future.result()
                results.append((page_num, page_data))

        results.sort(key=lambda x: x[0])
        for page_num, page_data in results:
            pages.append(page_data)
            for block in page_data.blocks:
                bt = block.block_type
                block_type_counts[bt] = block_type_counts.get(bt, 0) + 1

    if progress_callback:
        progress_callback(0.95, "Assembling Baseline Document schema...")

    filename = os.path.basename(original_filepath)
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

    if progress_callback:
        progress_callback(1.0, "Done!")

    return BaselineDocument(
        title=title,
        filename=filename,
        pages=pages,
        metadata=BaselineMetadata(
            total_pages=len(pages),
            block_type_counts=block_type_counts,
            converter_info=f"Vision API ({engine})",
        ),
    )
