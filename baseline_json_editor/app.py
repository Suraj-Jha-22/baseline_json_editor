"""
Baseline JSON Editor — Premium Streamlit Application
=====================================================
Upload a document (PDF, DOCX, PPTX, etc.) and convert it into a structured
baseline JSON schema. Edit content without altering the schema structure,
then export the modified JSON for downstream use.

Built on top of the Marker document conversion library.
"""

import json
import logging
import os
import sys
import tempfile

# Configure terminal logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["IN_STREAMLIT"] = "true"

import streamlit as st
from PIL import Image
from streamlit_ace import st_ace

from converter.schema import BaselineDocument
from styles import (
    CUSTOM_CSS,
    get_block_color,
    render_block_badge,
    render_metric_card,
    render_property_chips,
)
from utils import (
    build_export_json,
    count_editable_fields,
    flatten_blocks,
    get_block_icon,
    get_page_count,
    get_page_image,
)

# ────────────────────────────────────────────────────────────
# Page Config
# ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Baseline JSON Editor",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────
# Session State Initialization
# ────────────────────────────────────────────────────────────
if "synced_json_str" not in st.session_state:
    st.session_state.synced_json_str = None
if "original_pdf_bytes" not in st.session_state:
    st.session_state.original_pdf_bytes = None
if "conversion_done" not in st.session_state:
    st.session_state.conversion_done = False
if "uploaded_file_bytes" not in st.session_state:
    st.session_state.uploaded_file_bytes = None


# ────────────────────────────────────────────────────────────
# Sidebar
# ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="hero-title">🔬 Baseline JSON</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Document → Structured Schema Editor</div>', unsafe_allow_html=True)
    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    st.markdown("### 📂 Upload Document")
    in_file = st.file_uploader(
        "Drop your document here",
        type=["pdf", "png", "jpg", "jpeg", "gif", "pptx", "docx", "xlsx", "html", "htm", "epub"],
        label_visibility="collapsed",
    )

    if in_file is not None:
        st.session_state.uploaded_file_bytes = in_file.getvalue()

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    st.markdown("### ⚙️ Conversion Settings")
    engine_choice = st.radio(
        "Conversion Engine",
        options=["Fast Vision API (GPT-4o/Gemini)", "Local Marker (Slow but Free)"],
        index=0,
        help="Fast API takes ~2s per page but requires API keys. Local Marker runs free on your machine but takes ~30s per page."
    )
    
    page_range = st.text_input(
        "Page range",
        value="",
        help="Comma-separated page ranges, e.g. 0,2-5,10. Leave empty for all pages.",
        placeholder="All pages",
    )
    
    if "Local" in engine_choice:
        force_ocr = st.checkbox("🔍 Force OCR", value=False, help="Force OCR on all pages even if text is embedded")
        use_llm = st.checkbox("🤖 Use LLM Enhancement", value=False, help="Use LLM for higher quality extraction")
    else:
        # API takes over, these settings aren't relevant
        force_ocr = False
        use_llm = False

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    convert_btn = st.button("⚡ Convert Document", use_container_width=True, disabled=in_file is None)

    # Preload models button (only useful for Local Marker)
    if "Local" in engine_choice:
        if st.button("🔥 Preload Local AI Models", use_container_width=True, help="Load local models into memory now so conversion is fast"):
            with st.spinner("Loading AI models into cache..."):
                from converter.pdf_to_baseline import get_cached_models
                get_cached_models()
            st.success("✅ Models loaded! Conversions will be fast now.")

    # Export section
    if st.session_state.synced_json_str is not None:
        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
        st.markdown("### 📥 Export")

        # Parse to get filename safely
        temp_doc = BaselineDocument.model_validate_json(st.session_state.synced_json_str)

        st.download_button(
            label="⬇️ Download Baseline JSON",
            data=st.session_state.synced_json_str,
            file_name=f"{temp_doc.filename.rsplit('.', 1)[0]}_baseline.json",
            mime="application/json",
            use_container_width=True,
        )

        from utils import clear_document_content
        empty_doc = clear_document_content(temp_doc)
        
        st.download_button(
            label="🈳 Download Empty Schema",
            data=empty_doc.model_dump_json(indent=2),
            file_name=f"{temp_doc.filename.rsplit('.', 1)[0]}_template.json",
            mime="application/json",
            use_container_width=True,
        )

        # Also offer the Edited PDF if the original file was a PDF
        if st.session_state.original_pdf_bytes is not None:
            # Rebuild the edited PDF on the fly using PyMuPDF
            from converter.pdf_exporter import export_edited_pdf
            
            with st.spinner("Generating Edited PDF overlay..."):
                edited_pdf_bytes = export_edited_pdf(
                    st.session_state.original_pdf_bytes, 
                    temp_doc
                )
                
            if edited_pdf_bytes:
                st.download_button(
                    label="📄 Download Edited PDF",
                    data=edited_pdf_bytes,
                    file_name=f"{temp_doc.filename.rsplit('.', 1)[0]}_edited.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.error("❌ Failed to generate edited PDF.")
                
        # Optional HTML Export
        from converter.html_exporter import export_edited_html
        with st.spinner("Generating HTML..."):
            edited_html_str = export_edited_html(temp_doc)
        if edited_html_str:
            st.download_button(
                label="🌐 Download Edited HTML",
                data=edited_html_str,
                file_name=f"{temp_doc.filename.rsplit('.', 1)[0]}_edited.html",
                mime="text/html",
                use_container_width=True,
            )
            
        # Optional DOCX Export
        from converter.docx_exporter import export_edited_docx
        with st.spinner("Generating DOCX..."):
            edited_docx_bytes = export_edited_docx(temp_doc)
        if edited_docx_bytes:
            st.download_button(
                label="📘 Download Edited DOCX",
                data=edited_docx_bytes,
                file_name=f"{temp_doc.filename.rsplit('.', 1)[0]}_edited.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center; font-size:0.7rem; color:#6C6C80; margin-top:1rem;">'
        "Powered by <b>Marker</b> · Schema v1.0.0"
        "</div>",
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────
# Conversion Logic
# ────────────────────────────────────────────────────────────
if convert_btn and in_file is not None:
    progress_bar = st.progress(0, text="Starting conversion...")
    status_text = st.empty()

    def _update_progress(pct, msg):
        progress_bar.progress(pct, text=msg)
        status_text.markdown(
            f'<div style="font-size:0.82rem; color:var(--text-secondary);">⏳ {msg}</div>',
            unsafe_allow_html=True,
        )

    try:
        logger.info(f"Starting {engine_choice} conversion for uploaded file: {in_file.name} (Size: {in_file.size} bytes)")
        
        if in_file.type == "application/pdf":
            file_bytes = in_file.read()
            st.session_state.original_pdf_bytes = file_bytes
            # reset pointer for downstream readers
            in_file.seek(0)
        else:
            st.session_state.original_pdf_bytes = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            ext = os.path.splitext(in_file.name)[1]
            temp_path = os.path.join(tmp_dir, f"input{ext}")
            with open(temp_path, "wb") as f:
                f.write(in_file.getvalue())

            logger.info(f"Saved temp file to {temp_path}. Routing to selected converter...")
            
            file_ext = os.path.splitext(in_file.name)[1].lower()
            
            if file_ext == ".docx":
                # DOCX: always use the instant direct converter (no API needed)
                from converter.docx_to_baseline import convert_docx_direct
                baseline_doc = convert_docx_direct(
                    filepath=temp_path,
                    progress_callback=_update_progress,
                )
            elif "Fast Vision API" in engine_choice:
                from converter.fast_api_converter import convert_document_fast_api
                baseline_doc = convert_document_fast_api(
                    filepath=temp_path,
                    page_range=page_range if page_range.strip() else None,
                    progress_callback=_update_progress,
                )
            else:
                from converter.pdf_to_baseline import convert_document_to_baseline
                baseline_doc = convert_document_to_baseline(
                    filepath=temp_path,
                    page_range=page_range if page_range.strip() else None,
                    force_ocr=force_ocr,
                    use_llm=use_llm,
                    progress_callback=_update_progress,
                )

        logger.info(f"Conversion complete! Processed {len(baseline_doc.pages)} pages.")
        
        # Single Source of Truth
        st.session_state.synced_json_str = baseline_doc.model_dump_json(indent=2, exclude_none=True)
        st.session_state.conversion_done = True
        progress_bar.empty()
        status_text.empty()
        st.rerun()

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Conversion failed: {str(e)}")
        st.exception(e)


# ────────────────────────────────────────────────────────────
# Main Content
# ────────────────────────────────────────────────────────────

# Hero header
st.markdown('<div class="hero-title">Baseline JSON Schema Editor</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">'
    "Convert documents into structured, editable JSON schemas. "
    "Edit content freely — the schema structure stays locked."
    "</div>",
    unsafe_allow_html=True,
)

if st.session_state.synced_json_str is None:
    # Landing state
    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            '<div class="glass-card" style="text-align:center;">'
            '<div style="font-size:2.5rem; margin-bottom:0.5rem;">📄</div>'
            '<div style="font-weight:700; margin-bottom:0.4rem;">Upload</div>'
            '<div style="font-size:0.82rem; color:var(--text-secondary);">Drop a PDF, DOCX, PPTX, or image file in the sidebar</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '<div class="glass-card" style="text-align:center;">'
            '<div style="font-size:2.5rem; margin-bottom:0.5rem;">🔬</div>'
            '<div style="font-weight:700; margin-bottom:0.4rem;">Convert</div>'
            '<div style="font-size:0.82rem; color:var(--text-secondary);">Marker extracts structure, text, tables, equations & more</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            '<div class="glass-card" style="text-align:center;">'
            '<div style="font-size:2.5rem; margin-bottom:0.5rem;">✏️</div>'
            '<div style="font-weight:700; margin-bottom:0.4rem;">Edit & Export</div>'
            '<div style="font-size:0.82rem; color:var(--text-secondary);">Modify content while preserving schema structure, then export JSON</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Supported formats
    st.markdown("#### Supported Formats")
    format_cols = st.columns(5)
    formats = [
        ("📕", "PDF"),
        ("📘", "DOCX"),
        ("📙", "PPTX"),
        ("📗", "XLSX"),
        ("🖼️", "Images"),
    ]
    for col, (icon, fmt) in zip(format_cols, formats):
        with col:
            st.markdown(
                f'<div class="glass-card" style="text-align:center; padding:0.75rem;">'
                f'<div style="font-size:1.5rem;">{icon}</div>'
                f'<div style="font-size:0.8rem; font-weight:600; margin-top:0.25rem;">{fmt}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.stop()

# ────────────────────────────────────────────────────────────
# Document loaded — show success + metrics
# ────────────────────────────────────────────────────────────
try:
    doc = BaselineDocument.model_validate_json(st.session_state.synced_json_str)
except Exception as e:
    st.error(f"Internal Error: Failed to parse SSOT JSON state: {e}")
    st.stop()

if st.session_state.conversion_done:
    st.markdown(
        '<div class="success-banner">'
        '<span class="status-dot" style="background:#00B894;"></span>'
        f"✅ Document converted successfully — {doc.metadata.total_pages} page(s) processed"
        "</div>",
        unsafe_allow_html=True,
    )
    st.session_state.conversion_done = False

# Metrics row
total_blocks = sum(doc.metadata.block_type_counts.values())
editable_fields = count_editable_fields(doc)

metrics_html = '<div class="metric-row">'
metrics_html += render_metric_card(str(doc.metadata.total_pages), "Pages", "#6C5CE7")
metrics_html += render_metric_card(str(total_blocks), "Blocks", "#00B894")
metrics_html += render_metric_card(str(editable_fields), "Editable Fields", "#0984E3")
metrics_html += render_metric_card(str(len(doc.metadata.block_type_counts)), "Block Types", "#F39C12")
metrics_html += "</div>"
st.markdown(metrics_html, unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────
# Callbacks for SSOT Sync
# ────────────────────────────────────────────────────────────
def update_doc_state(block_id: str, widget_key: str):
    """Callback to update the centralized JSON string when a text input changes."""
    new_val = st.session_state[widget_key]
    current_doc = BaselineDocument.model_validate_json(st.session_state.synced_json_str)
    
    if block_id == "__title__":
        current_doc.title = new_val
    else:
        for page in current_doc.pages:
            def update_blocks(blocks):
                for b in blocks:
                    if b.id == block_id:
                        b.content = new_val
                        return True
                    if b.children and update_blocks(b.children):
                        return True
                return False
            if update_blocks(page.blocks):
                break
                
    # Save back to Single Source of Truth
    st.session_state.synced_json_str = current_doc.model_dump_json(indent=2, exclude_none=True)


# ────────────────────────────────────────────────────────────
# Tabs
# ────────────────────────────────────────────────────────────
tab_preview, tab_editor, tab_json = st.tabs(["📄 Document Preview", "🔧 Schema Editor", "📋 JSON View / Code Editor"])


# ─── Tab 1: Document Preview ───
with tab_preview:
    file_ext = os.path.splitext(in_file.name)[1].lower() if in_file is not None else ""
    is_renderable = file_ext in [".pdf", ".jpg", ".jpeg", ".png"]

    if in_file is not None and is_renderable:
        total_pages = get_page_count(in_file)
        col_nav, col_img = st.columns([0.25, 0.75])

        with col_nav:
            st.markdown("#### Navigation")
            page_num = st.number_input(
                "Page",
                min_value=0,
                max_value=max(0, total_pages - 1),
                value=0,
                help="Select a page to preview",
            )
            st.markdown(f"**Page {page_num + 1}** of {total_pages}")

            # Show blocks on this page
            if page_num < len(doc.pages):
                page_data = doc.pages[page_num]
                st.markdown("##### Blocks on this page")
                for block in page_data.blocks:
                    badge_html = render_block_badge(block.block_type)
                    preview = block.content[:50] + "..." if len(block.content) > 50 else block.content
                    st.markdown(
                        f'{badge_html} <span style="font-size:0.78rem; color:#A0A0B8; margin-left:6px;">{preview}</span>',
                        unsafe_allow_html=True,
                    )

        with col_img:
            try:
                pil_image = get_page_image(in_file, page_num)
                if pil_image:
                    st.image(pil_image, use_container_width=True, caption=f"Page {page_num + 1}")
                else:
                    st.warning("Could not render page preview.")
            except Exception as e:
                st.warning(f"Could not render page preview: {e}")
    else:
        st.info("📄 Image previews are available for PDF and Image files. Your document structure is shown below and in the Schema Editor tab.")

        # Show a text-based summary for non-PDF files
        for page in doc.pages:
            st.markdown(f"#### Page {page.page_number}")
            for block in page.blocks:
                icon = get_block_icon(block.block_type)
                preview = block.content[:120] + "..." if len(block.content) > 120 else block.content
                st.markdown(f"{icon} **{block.block_type}**: {preview}")


# ─── Tab 2: Schema Editor ───
with tab_editor:
    st.markdown("#### ✏️ Edit Document Content")
    st.markdown(
        '<div style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:1rem;">'
        "Edit the <b>content</b> fields below. Changes are instantly synchronized with the JSON code view! Block types and hierarchy are <b>locked</b> (read-only)."
        "</div>",
        unsafe_allow_html=True,
    )

    # Editable document title
    st.markdown("##### 📌 Document Title")
    st.text_input(
        "Document Title",
        value=doc.title,
        key="input_title",
        on_change=update_doc_state,
        args=("__title__", "input_title"),
        label_visibility="collapsed",
    )

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Page-by-page block editor
    for page in doc.pages:
        with st.expander(f"📄 Page {page.page_number}  —  {len(page.blocks)} blocks", expanded=(page.page_number == 1)):
            for block_idx, block in enumerate(page.blocks):
                color = get_block_color(block.block_type)
                icon = get_block_icon(block.block_type)

                # Block card header
                header_html = (
                    f'<div class="editor-block" style="border-left-color: {color};">'
                    f'<div class="editor-block-header">'
                    f"<div>{render_block_badge(block.block_type)}</div>"
                    f'<div class="block-id-label">{block.id}</div>'
                    f"</div>"
                )

                # Properties chips
                if block.properties:
                    props_dict = block.properties.model_dump(exclude_none=True)
                    if props_dict:
                        header_html += f"<div>{render_property_chips(props_dict)}</div>"

                # Section hierarchy
                if block.section_hierarchy:
                    hierarchy_str = " → ".join(block.section_hierarchy.values())
                    header_html += (
                        f'<div style="font-size:0.72rem; color:#A29BFE; margin-top:4px; margin-bottom:4px;">'
                        f"📂 {hierarchy_str}</div>"
                    )

                # Bbox info
                if block.bbox:
                    bbox_str = ", ".join(f"{v:.1f}" for v in block.bbox[:4])
                    header_html += f'<div class="block-id-label">📐 bbox: [{bbox_str}]</div>'

                header_html += "</div>"
                st.markdown(header_html, unsafe_allow_html=True)

                # Editable content field
                if block.content:
                    use_textarea = len(block.content) > 100
                    edit_key = f"edit_{page.page_number}_{block_idx}"

                    if use_textarea:
                        st.text_area(
                            f"{icon} Content",
                            value=block.content,
                            key=edit_key,
                            on_change=update_doc_state,
                            args=(block.id, edit_key),
                            height=min(200, max(80, len(block.content) // 2)),
                            label_visibility="collapsed",
                        )
                    else:
                        st.text_input(
                            f"{icon} Content",
                            value=block.content,
                            key=edit_key,
                            on_change=update_doc_state,
                            args=(block.id, edit_key),
                            label_visibility="collapsed",
                        )

                # Render children recursively (read-only structure overview)
                if block.children:
                    with st.container():
                        st.markdown(
                            f'<div style="margin-left:1.5rem; padding-left:1rem; border-left:2px solid {color}30;">'
                            f'<div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:0.4rem;">↳ {len(block.children)} nested block(s)</div>'
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        for child_idx, child in enumerate(block.children):
                            child_color = get_block_color(child.block_type)
                            child_icon = get_block_icon(child.block_type)

                            child_html = (
                                f'<div style="margin-left:1.5rem; padding:0.5rem 0.75rem; '
                                f"background:rgba(255,255,255,0.02); border-left:2px solid {child_color}40; "
                                f'border-radius:0 6px 6px 0; margin-bottom:0.3rem;">'
                                f"{render_block_badge(child.block_type)} "
                                f'<span class="block-id-label" style="margin-left:8px;">{child.id}</span>'
                                f"</div>"
                            )
                            st.markdown(child_html, unsafe_allow_html=True)

                            if child.content:
                                child_key = f"edit_{page.page_number}_{block_idx}_child_{child_idx}"
                                st.text_input(
                                    f"{child_icon} {child.block_type}",
                                    value=child.content,
                                    key=child_key,
                                    on_change=update_doc_state,
                                    args=(child.id, child_key),
                                    label_visibility="collapsed",
                                )

# ─── Tab 3: JSON View / Code Editor ───
with tab_json:
    st.markdown("#### 💻 Live JSON Editor")
    st.markdown(
        '<div style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:1rem;">'
        "This is the raw Baseline JSON representation. You can freely edit the <code>content</code> values here. "
        "Any valid changes will automatically sync to the Schema Editor. <b>Do not alter block_type or ids.</b>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Render streamlit-ace editor
    new_json_val = st_ace(
        value=st.session_state.synced_json_str,
        language="json",
        theme="monokai",
        key="ace_editor",
        font_size=13,
        tab_size=2,
        wrap=True,
        show_gutter=True,
        show_print_margin=False,
        height=600,
        auto_update=False, # Wait for the user to lift hands or press Cmd+S
    )

    # Perform bi-directional sync if code editor fired an update
    if new_json_val and new_json_val != st.session_state.synced_json_str:
        try:
            # First, check if valid JSON AND valid BaselineDocument schema
            validate_doc = BaselineDocument.model_validate_json(new_json_val)
            
            # If successful, establish the new Single Source of Truth
            # Re-serialize to enforce formatting
            clean_str = validate_doc.model_dump_json(indent=2, exclude_none=True)
            st.session_state.synced_json_str = clean_str
            
            st.success("✅ JSON synced successfully!")
            st.rerun() # Force UI elements to update with new state
            
        except Exception as e:
            st.error(f"❌ Invalid JSON or Schema violation. Changes discarded. \n\nError details: `{str(e)}`")


def main():
    """Entry point for the script console command."""
    import subprocess
    subprocess.run(
        ["streamlit", "run", os.path.abspath(__file__)],
        check=True,
    )


if __name__ == "__main__":
    pass
