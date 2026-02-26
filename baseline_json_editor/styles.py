"""
Custom CSS for the Baseline JSON Editor Streamlit app.
Premium dark theme with glassmorphism, color-coded block types, and smooth transitions.
"""

BLOCK_TYPE_COLORS = {
    "SectionHeader": "#6C5CE7",
    "Text": "#00B894",
    "Table": "#E17055",
    "ListItem": "#0984E3",
    "ListGroup": "#0984E3",
    "Code": "#F39C12",
    "Equation": "#E84393",
    "Figure": "#00CEC9",
    "Picture": "#00CEC9",
    "Caption": "#636E72",
    "Footnote": "#B2BEC3",
    "Form": "#A29BFE",
    "Handwriting": "#FD79A8",
    "TableOfContents": "#74B9FF",
    "Reference": "#DFE6E9",
    "Page": "#2D3436",
    "ComplexRegion": "#FDCB6E",
    "Default": "#636E72",
}


def get_block_color(block_type: str) -> str:
    """Return the hex color for a given block type."""
    return BLOCK_TYPE_COLORS.get(block_type, BLOCK_TYPE_COLORS["Default"])


CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* ─── Global Theme ─── */
    :root {
        --bg-primary: #0F0F1A;
        --bg-secondary: #1A1A2E;
        --bg-card: rgba(30, 30, 50, 0.7);
        --bg-glass: rgba(255, 255, 255, 0.04);
        --border-glass: rgba(255, 255, 255, 0.08);
        --text-primary: #E8E8F0;
        --text-secondary: #A0A0B8;
        --text-muted: #6C6C80;
        --accent-primary: #6C5CE7;
        --accent-secondary: #A29BFE;
        --accent-glow: rgba(108, 92, 231, 0.3);
        --success: #00B894;
        --warning: #FDCB6E;
        --danger: #E17055;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.4);
        --shadow-glow: 0 0 40px rgba(108, 92, 231, 0.15);
        --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ─── Base ─── */
    .stApp {
        background: var(--bg-primary) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-primary) !important;
    }

    .main .block-container {
        padding: 1.5rem 2rem 3rem 2rem !important;
        max-width: 100% !important;
    }

    /* ─── Sidebar ─── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #16162A 0%, #1A1A2E 100%) !important;
        border-right: 1px solid var(--border-glass) !important;
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
    }

    /* ─── Headers ─── */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em !important;
    }

    .hero-title {
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 40%, #00CEC9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem !important;
        line-height: 1.2 !important;
    }

    .hero-subtitle {
        font-size: 0.95rem;
        color: var(--text-secondary);
        font-weight: 400;
        margin-bottom: 1.5rem;
    }

    /* ─── Glassmorphism Cards ─── */
    .glass-card {
        background: var(--bg-glass);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border-glass);
        border-radius: var(--radius-lg);
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: var(--shadow-card);
        transition: var(--transition);
    }

    .glass-card:hover {
        border-color: rgba(108, 92, 231, 0.25);
        box-shadow: var(--shadow-card), var(--shadow-glow);
        transform: translateY(-1px);
    }

    /* ─── Block Type Badge ─── */
    .block-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        white-space: nowrap;
    }

    .block-badge-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
    }

    /* ─── Metric Cards ─── */
    .metric-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.25rem;
        flex-wrap: wrap;
    }

    .metric-card {
        flex: 1;
        min-width: 140px;
        background: var(--bg-glass);
        backdrop-filter: blur(16px);
        border: 1px solid var(--border-glass);
        border-radius: var(--radius-md);
        padding: 1rem 1.25rem;
        text-align: center;
        transition: var(--transition);
    }

    .metric-card:hover {
        border-color: rgba(108, 92, 231, 0.3);
        transform: translateY(-2px);
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: var(--accent-secondary);
        line-height: 1;
        margin-bottom: 4px;
    }

    .metric-label {
        font-size: 0.75rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }

    /* ─── Editor Block ─── */
    .editor-block {
        background: var(--bg-glass);
        backdrop-filter: blur(12px);
        border: 1px solid var(--border-glass);
        border-radius: var(--radius-md);
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        transition: var(--transition);
        border-left: 3px solid transparent;
    }

    .editor-block:hover {
        border-color: rgba(255, 255, 255, 0.1);
        background: rgba(255, 255, 255, 0.06);
    }

    .editor-block-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.6rem;
    }

    .block-id-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        color: var(--text-muted);
        opacity: 0.7;
    }

    .property-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        font-size: 0.68rem;
        color: var(--text-muted);
        font-family: 'JetBrains Mono', monospace;
        margin-right: 4px;
        margin-bottom: 4px;
    }

    /* ─── Tabs ─── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0 !important;
        background: var(--bg-glass) !important;
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-glass) !important;
        padding: 4px !important;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-sm) !important;
        padding: 0.5rem 1.25rem !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        color: var(--text-secondary) !important;
        transition: var(--transition) !important;
    }

    .stTabs [aria-selected="true"] {
        background: var(--accent-primary) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(108, 92, 231, 0.4) !important;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* ─── Buttons ─── */
    .stButton > button {
        background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.55rem 1.5rem !important;
        transition: var(--transition) !important;
        box-shadow: 0 4px 15px rgba(108, 92, 231, 0.3) !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(108, 92, 231, 0.5) !important;
    }

    .stButton > button:active {
        transform: translateY(0) !important;
    }

    /* Download button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #00B894 0%, #00CEC9 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        padding: 0.55rem 1.5rem !important;
        box-shadow: 0 4px 15px rgba(0, 184, 148, 0.3) !important;
        transition: var(--transition) !important;
    }

    .stDownloadButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(0, 184, 148, 0.5) !important;
    }

    /* ─── Inputs ─── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        transition: var(--transition) !important;
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px var(--accent-glow) !important;
    }

    /* ─── File Uploader ─── */
    section[data-testid="stFileUploader"] {
        background: var(--bg-glass) !important;
        border: 2px dashed rgba(108, 92, 231, 0.3) !important;
        border-radius: var(--radius-md) !important;
        padding: 1rem !important;
        transition: var(--transition) !important;
    }

    section[data-testid="stFileUploader"]:hover {
        border-color: var(--accent-primary) !important;
        background: rgba(108, 92, 231, 0.05) !important;
    }

    /* ─── Expander ─── */
    .streamlit-expanderHeader {
        background: var(--bg-glass) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }

    /* ─── JSON View ─── */
    .stJson {
        background: rgba(15, 15, 26, 0.9) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: var(--radius-md) !important;
    }

    /* ─── Scrollbar ─── */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: transparent;
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(108, 92, 231, 0.3);
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(108, 92, 231, 0.5);
    }

    /* ─── Status Indicator ─── */
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* ─── Divider ─── */
    .gradient-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--accent-primary), transparent);
        margin: 1.5rem 0;
        border: none;
    }

    /* ─── Toast / Success Banner ─── */
    .success-banner {
        background: linear-gradient(135deg, rgba(0, 184, 148, 0.1) 0%, rgba(0, 206, 201, 0.1) 100%);
        border: 1px solid rgba(0, 184, 148, 0.3);
        border-radius: var(--radius-md);
        padding: 0.75rem 1.25rem;
        color: #00B894;
        font-weight: 600;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 1rem;
    }

    /* ─── Spinner ─── */
    .stSpinner > div {
        border-top-color: var(--accent-primary) !important;
    }

    /* Hide default streamlit components we don't need */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
"""


def render_block_badge(block_type: str) -> str:
    """Generate HTML for a colored block-type badge."""
    color = get_block_color(block_type)
    return (
        f'<span class="block-badge" style="background: {color}15; color: {color}; border: 1px solid {color}30;">'
        f'<span class="block-badge-dot" style="background: {color};"></span>'
        f"{block_type}"
        f"</span>"
    )


def render_property_chips(properties: dict) -> str:
    """Generate HTML for property info chips."""
    if not properties:
        return ""
    chips = []
    for key, value in properties.items():
        if key in ("has_images", "image_keys"):
            continue
        chips.append(f'<span class="property-chip">🏷 {key}: {value}</span>')
    return " ".join(chips)


def render_metric_card(value: str, label: str, color: str = "#A29BFE") -> str:
    """Generate HTML for a single metric card."""
    return (
        f'<div class="metric-card">'
        f'<div class="metric-value" style="color: {color};">{value}</div>'
        f'<div class="metric-label">{label}</div>'
        f"</div>"
    )
