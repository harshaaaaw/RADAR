"""
Streamlit-based monitoring dashboard for the Enterprise Document Search System.
Displays live queue metrics, completion stats, and failure breakdowns for end users.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from opensearchpy.exceptions import RequestError

import pandas as pd
import streamlit as st

# Ensure the project src directory is importable when running "streamlit run"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config_manager import get_config  # noqa: E402
from core.queue_manager import get_queue_manager, reset_queue_manager  # noqa: E402
from indexing.opensearch_client import OpenSearchClient  # noqa: E402


# =============================================================================
# CACHING LAYER - Prevent expensive Redis/OpenSearch queries on every refresh
# =============================================================================

def invalidate_all_caches() -> None:
    """Invalidate all cached data - call after reset or major state changes"""
    get_cached_queue_stats.clear()
    get_cached_size_stats.clear()


@st.cache_data(ttl=2)  # Reduced to 2 seconds for more responsive updates
def get_cached_queue_stats() -> Dict[str, Any]:
    """Get queue statistics with caching to reduce Redis load"""
    try:
        qm = get_queue_manager()
        stats = qm.get_queue_statistics() or {}
        stats['_cached_at'] = time.time()  # Track cache age
        return stats
    except Exception:
        return {'_cached_at': time.time()}


@st.cache_data(ttl=5)  # Cache for 5 seconds (size stats are heavier)
def get_cached_size_stats() -> Dict[str, Any]:
    """Get size statistics with caching to reduce Redis load"""
    try:
        qm = get_queue_manager()
        return qm.get_size_statistics() or {}
    except Exception:
        return {
            'discovered': {'files': 0, 'size_bytes': 0},
            'in_pipeline': {'files': 0, 'size_bytes': 0},
            'searchable': {'files': 0, 'size_bytes': 0},
            'failed': {'files': 0, 'size_bytes': 0}
        }


@st.cache_data(ttl=10)  # Cache for 10 seconds
def get_cached_failed_files(limit: int = 50) -> List[Dict[str, Any]]:
    """Get failed files with caching"""
    try:
        qm = get_queue_manager()
        return qm.get_failed_files(limit=limit)
    except Exception:
        return []


@st.cache_data(ttl=10)  # Cache for 10 seconds
def get_cached_ocr_pending(limit: int = 30) -> List[Dict[str, Any]]:
    """Get OCR pending files with caching"""
    try:
        qm = get_queue_manager()
        return qm.get_ocr_pending_files(limit=limit)
    except Exception:
        return []


@st.cache_data(ttl=15)  # Cache for 15 seconds
def get_cached_largest_files(limit: int = 10) -> List[Dict[str, Any]]:
    """Get largest completed files with caching"""
    try:
        qm = get_queue_manager()
        return qm.get_largest_completed_files(limit=limit)
    except Exception:
        return []


def open_file_with_default_app(filepath: str) -> None:
    """Open a file with the default system application."""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(filepath)
        elif os.name == 'posix':  # Linux/Mac
            subprocess.run(['xdg-open', filepath], check=True)
    except Exception as e:
        raise Exception(f"Failed to open file: {e}")


def format_number(value: Any) -> str:
    """Format numeric values with thousands separators and fallbacks."""
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size (MB/GB/TB)."""
    if size_bytes is None or size_bytes == 0:
        return "0 MB"
    
    # Define size thresholds
    TB = 1024 ** 4
    GB = 1024 ** 3
    MB = 1024 ** 2
    
    if size_bytes >= TB:
        return f"{size_bytes / TB:.2f} TB"
    elif size_bytes >= GB:
        return f"{size_bytes / GB:.2f} GB"
    else:
        return f"{size_bytes / MB:.2f} MB"


def calculate_progress_percentage(completed: int, total: int) -> float:
    """Calculate progress percentage safely."""
    if total == 0:
        return 0.0
    return min((completed / total) * 100, 100.0)


def seconds_to_human(s: float) -> str:
    """Convert seconds to human-friendly H M S string."""
    try:
        s = int(max(0, math.floor(s)))
    except Exception:
        try:
            s = int(max(0, int(s)))
        except Exception:
            return "0s"

    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{sec}s")
    return ' '.join(parts)


def extract_summary(queue_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Compute top-level summary metrics for display with robust error handling."""
    try:
        discovery = queue_stats.get("discovery", {}) or {}
        extraction_by_size = queue_stats.get("extraction", {}) or {}
        extraction_total_stats = queue_stats.get("extraction_total", {}) or {}
        indexing = queue_stats.get("indexing", {}) or {}
        ocr = queue_stats.get("ocr", {}) or {}
        completed = queue_stats.get("completed", {}) or {}

        # Helper to safely get int value
        def safe_int(val):
            if val is None:
                return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        # Handle None values from SQLite/Redis aggregation
        extraction_pending = sum(safe_int((cat or {}).get("pending")) for cat in extraction_by_size.values() if isinstance(cat, dict))
        extraction_processing = sum(safe_int((cat or {}).get("processing")) for cat in extraction_by_size.values() if isinstance(cat, dict))
        # Use extraction_total.completed if available (new Redis format), otherwise sum categories
        extraction_completed = safe_int(extraction_total_stats.get("completed")) or sum(safe_int((cat or {}).get("completed")) for cat in extraction_by_size.values() if isinstance(cat, dict))
        extraction_total = sum(safe_int((cat or {}).get("total")) for cat in extraction_by_size.values() if isinstance(cat, dict))

        summary = {
            "discovered_total": safe_int(discovery.get("total")),
            "discovery_pending": safe_int(discovery.get("pending")),
            "discovery_completed": safe_int(discovery.get("completed")),
            "extraction_pending": extraction_pending,
            "extraction_processing": extraction_processing,
            "extraction_completed": extraction_completed,
            "extraction_total": extraction_total,
            "indexing_pending": safe_int(indexing.get("pending")),
            "indexing_processing": safe_int(indexing.get("processing")),
            "indexing_completed": safe_int(indexing.get("completed")),
            "indexing_total": safe_int(indexing.get("total")),
            "ocr_pending": safe_int(ocr.get("pending")),
            "ocr_processing": safe_int(ocr.get("processing")),
            "ocr_completed": safe_int(ocr.get("completed")),
            "ocr_total": safe_int(ocr.get("total")),
            "completed_total": safe_int(completed.get("total_completed") or completed.get("total")),
            "duplicates": safe_int(completed.get("duplicates")),
            "avg_extraction_ms": safe_int(completed.get("avg_extraction_ms") or completed.get("avg_extraction_time_ms")),
            "avg_indexing_ms": safe_int(completed.get("avg_indexing_ms") or completed.get("avg_indexing_time_ms")),
            "total_failures": safe_int(queue_stats.get("total_failures")),
        }

        return summary
    except Exception as e:
        # Return safe defaults if anything fails
        return {
            "discovered_total": 0, "discovery_pending": 0, "discovery_completed": 0,
            "extraction_pending": 0, "extraction_processing": 0, "extraction_completed": 0, "extraction_total": 0,
            "indexing_pending": 0, "indexing_processing": 0, "indexing_completed": 0, "indexing_total": 0,
            "ocr_pending": 0, "ocr_processing": 0, "ocr_completed": 0, "ocr_total": 0,
            "completed_total": 0, "duplicates": 0, "avg_extraction_ms": 0, "avg_indexing_ms": 0, "total_failures": 0,
        }


def render_pipeline_stage(stage_name: str, summary: Dict[str, Any], key_prefix: str) -> None:
    """Render a single pipeline stage with progress bar and metrics."""
    total = summary.get(f"{key_prefix}_total", 0)
    completed = summary.get(f"{key_prefix}_completed", 0)
    pending = summary.get(f"{key_prefix}_pending", 0)
    processing = summary.get(f"{key_prefix}_processing", 0)
    
    progress = calculate_progress_percentage(completed, total)
    
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"### {stage_name}")
            if total > 0:
                st.progress(progress / 100.0)
                st.caption(f"{format_number(completed)} / {format_number(total)} completed ({progress:.1f}%)")
            else:
                st.info("No items yet")
        
        with col2:
            if processing > 0:
                st.metric("Processing", format_number(processing), delta=None, delta_color="off")
            if pending > 0:
                st.metric("Pending", format_number(pending), delta=None, delta_color="off")


def render_failure_chart(queue_stats: Dict[str, Any]) -> None:
    """Render failure breakdown as a bar chart."""
    failures = queue_stats.get("failures", {})
    if not failures:
        st.success("No failures recorded")
        return
    
    df = pd.DataFrame([
        {"Error Type": error_type, "Count": count}
        for error_type, count in sorted(failures.items(), key=lambda x: x[1], reverse=True)
    ])
    
    st.bar_chart(df.set_index("Error Type"))


def render_extraction_detail(queue_stats: Dict[str, Any]) -> None:
    """Render extraction queue breakdown by size category."""
    extraction_data = queue_stats.get("extraction", {})
    if not extraction_data:
        st.info("No extraction data available")
        return
    
    df_data = []
    for size_category, data in extraction_data.items():
        df_data.append({
            "Category": size_category.title(),
            "Total": data.get("total", 0) or 0,
            "Completed": data.get("completed", 0) or 0,
            "Processing": data.get("processing", 0) or 0,
            "Pending": data.get("pending", 0) or 0,
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_dashboard() -> None:
    st.set_page_config(
        page_title="Document Search System",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for better styling
    st.markdown("""
        <style>
        .main > div {
            padding-top: 2rem;
        }
        .stMetric {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
        }
        h1 {
            color: #1f77b4;
            padding-bottom: 1rem;
        }
        h3 {
            color: #2c3e50;
            margin-top: 1rem;
        }
        .stProgress > div > div > div {
            background-color: #1f77b4;
        }
        .result-snippet { 
            font-size: 0.95rem; 
            color: #374151; 
            background: #f9fafb; 
            padding: 0.75rem; 
            border-radius: 6px; 
            line-height: 1.5; 
        }
        .highlight { 
            background-color: #fef08a; 
            padding: 0.1rem 0.2rem; 
            border-radius: 3px; 
            font-weight: 500; 
        }
        .doc-card {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            background: white;
        }
        .doc-filename {
            font-weight: 600;
            font-size: 1.1rem;
            color: #1f2937;
            margin-bottom: 0.5rem;
        }
        .doc-meta {
            font-size: 0.85rem;
            color: #6b7280;
            margin-bottom: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)

    config = get_config()
    queue_manager = get_queue_manager()

    # Initialize OpenSearch client for searching
    try:
        os_client = OpenSearchClient()
    except Exception as e:
        st.error(f"Failed to initialize OpenSearch client: {e}")
        os_client = None

    # Header
    st.title("Document Retrieval System")
    
    # Sidebar - different content based on selected tab
    render_sidebar(config, os_client, queue_manager)
    
    # Main tabs
    tab_search, tab_monitor = st.tabs(["🔍 Search", "📊 System Monitor"])
    
    # ============================================================================
    # SEARCH TAB
    # ============================================================================
    with tab_search:
        render_search_tab(config, os_client)
    
    # ============================================================================
    # MONITORING TAB
    # ============================================================================
    with tab_monitor:
        render_monitoring_tab(config, queue_manager)


def render_sidebar(config: Any, os_client: Optional[OpenSearchClient], queue_manager: Any) -> None:
    """Render sidebar with system stats."""
    with st.sidebar:
        st.markdown("## 📊 Data Progress")
        
        # Toggle between file count and data size view
        show_as_files = st.toggle(
            "📁 Show as file count", 
            value=st.session_state.get("show_as_files", False), 
            help="Toggle between data size and file count",
            key="show_as_files"
        )
        
        # Get size statistics with CACHING to prevent lag
        try:
            size_stats = get_cached_size_stats()
            queue_stats = get_cached_queue_stats()
            summary = extract_summary(queue_stats)
            
            # Safely get nested values with defaults
            def safe_get(d, *keys, default=0):
                """Safely traverse nested dict structure"""
                try:
                    result = d
                    for key in keys:
                        if result is None:
                            return default
                        result = result.get(key, default) if isinstance(result, dict) else default
                    return result if result is not None else default
                except Exception:
                    return default
            
            # Calculate values with safe access
            discovered = size_stats.get('discovered', {}) or {}
            in_pipeline = size_stats.get('in_pipeline', {}) or {}
            searchable = size_stats.get('searchable', {}) or {}
            failed = size_stats.get('failed', {}) or {}
            
            # Total progress with safe int conversion
            total_discovered = safe_get(discovered, 'files', default=0)
            total_searchable = safe_get(searchable, 'files', default=0)
            total_in_pipeline = safe_get(in_pipeline, 'files', default=0)
            total_failed = safe_get(failed, 'files', default=0)
            
            discovered_size = safe_get(discovered, 'size_bytes', default=0)
            searchable_size = safe_get(searchable, 'size_bytes', default=0)
            pipeline_size = safe_get(in_pipeline, 'size_bytes', default=0)
            
            if show_as_files:
                progress_pct = (total_searchable / max(total_discovered, 1)) * 100
            else:
                progress_pct = (searchable_size / max(discovered_size, 1)) * 100
            
            st.markdown("---")
            
            # Main progression display
            if show_as_files:
                # File count view
                st.markdown("### 📂 Total Discovered")
                st.markdown(f"**{total_discovered:,}** files")
                
                st.markdown("### 🔄 In Pipeline")
                st.markdown(f"**{total_in_pipeline:,}** files")
                
                st.markdown("### 🔍 Searchable")
                st.markdown(f"**{total_searchable:,}** files")
                
                if total_failed > 0:
                    st.markdown("### ❌ Failed")
                    st.markdown(f"**{total_failed:,}** files")
            else:
                # Data size view
                st.markdown("### 📂 Total Discovered")
                st.markdown(f"**{format_size(discovered_size)}**")
                st.caption(f"{total_discovered:,} files")
                
                st.markdown("### 🔄 In Pipeline")
                st.markdown(f"**{format_size(pipeline_size)}**")
                st.caption(f"{total_in_pipeline:,} files processing")
                
                st.markdown("### 🔍 Searchable")
                st.markdown(f"**{format_size(searchable_size)}**")
                st.caption(f"{total_searchable:,} files indexed")
                
                if total_failed > 0:
                    st.markdown("### ❌ Failed")
                    st.caption(f"{total_failed:,} files failed")
            
            st.markdown("---")
            
            # Overall progress bar
            st.markdown("### Overall Progress")
            st.progress(min(progress_pct / 100, 1.0), text=f"{progress_pct:.1f}% complete")
            
            st.markdown("---")
            
            # Pipeline status (compact)
            st.markdown("### ⚙️ Pipeline")
            
            # Discovery
            discovery_total = summary.get('discovered_total', 0) or 0
            discovery_completed = summary.get('discovery_completed', 0) or 0
            if discovery_total > 0:
                discovery_pct = (discovery_completed / discovery_total) * 100
                st.progress(min(discovery_pct / 100, 1.0), text=f"Discovery: {discovery_pct:.0f}%")
            
            # Extraction
            extraction_total = summary.get('extraction_total', 0) or 0
            extraction_completed = summary.get('extraction_completed', 0) or 0
            if extraction_total > 0:
                extraction_pct = (extraction_completed / extraction_total) * 100
                st.progress(min(extraction_pct / 100, 1.0), text=f"Extraction: {extraction_pct:.0f}%")
            
            # Indexing
            indexing_total = summary.get('indexing_total', 0) or 0
            indexing_completed = summary.get('indexing_completed', 0) or 0
            if indexing_total > 0:
                indexing_pct = (indexing_completed / indexing_total) * 100
                st.progress(min(indexing_pct / 100, 1.0), text=f"Indexing: {indexing_pct:.0f}%")
            
            # OCR
            ocr_total = summary.get('ocr_total', 0) or 0
            ocr_completed = summary.get('ocr_completed', 0) or 0
            if ocr_total > 0:
                ocr_pct = (ocr_completed / ocr_total) * 100
                st.progress(min(ocr_pct / 100, 1.0), text=f"OCR: {ocr_pct:.0f}%")
            
            if discovery_total == 0 and extraction_total == 0 and indexing_total == 0:
                st.info("System ready. No active processing.")
        
        except Exception as e:
            error_msg = str(e)
            if "no such table" in error_msg.lower() or "no such column" in error_msg.lower():
                # Database was reset - reset the singleton and try to re-create a fresh instance
                reset_queue_manager()
                queue_manager = get_queue_manager()
                try:
                    size_stats = queue_manager.get_size_statistics() or {}
                    queue_stats = queue_manager.get_queue_statistics() or {}
                    summary = extract_summary(queue_stats)
                except Exception:
                    # Still not available - show empty metrics and notify user
                    st.markdown("---")
                    st.markdown("### 📂 Total Discovered")
                    st.markdown("**0** files")
                    st.markdown("### 🔄 In Pipeline")
                    st.markdown("**0** files")
                    st.markdown("### 🔍 Searchable")
                    st.markdown("**0** files")
                    st.progress(0.0, text="0% complete")
                    st.info("🔄 System reset. Start the orchestrator to begin processing.")
            else:
                # Show fallback UI with error message
                st.markdown("---")
                st.markdown("### 📂 Total Discovered")
                st.markdown("**-** files")
                st.markdown("### 🔄 In Pipeline")
                st.markdown("**-** files")
                st.markdown("### 🔍 Searchable")
                st.markdown("**-** files")
                st.progress(0.0, text="Unable to load stats")
                st.warning(f"Stats unavailable: {str(e)[:100]}")


def render_search_tab(config: Any, os_client: Optional[OpenSearchClient]) -> None:
    """Render the search interface tab."""
    st.markdown("### Search Your Documents")
    
    # Search input
    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input(
            "Search documents", 
            placeholder="Enter keywords, filenames, or exact phrases in quotes...", 
            label_visibility="collapsed",
            key="search_input"
        )
    with col2:
        search_button = st.button("🔍 Search", use_container_width=True)
    
    st.markdown("---")
    
    if not os_client:
        st.error("OpenSearch is not available. Please check the system status.")
        return
    
    # Perform search
    if (query and len(query) >= 2) or search_button:
        if query and len(query) >= 2:
            with st.spinner("Searching..."):
                try:
                    results = perform_search(os_client, query)
                    if results:
                        render_search_results(results, query)
                    else:
                        st.info("💤 No documents indexed yet. Start the orchestrator to begin indexing.")
                        st.caption("Once documents are indexed, you'll be able to search through them here.")
                except Exception as e:
                    st.error(f"Search error: {e}")
        else:
            st.warning("Please enter at least 2 characters to search.")
    else:
        # Show recent documents
        render_recent_documents(os_client)


def extract_snippet_manually(text: str, query: str, max_length: int = 180) -> str:
    """Extract snippet around query match when highlights unavailable."""
    if not text:
        return ""
    
    # Normalize for searching
    text_lower = text.lower()
    query_lower = query.lower()
    query_terms = query_lower.split()
    
    # Find first occurrence of any query term
    best_pos = -1
    best_term = ""
    for term in query_terms:
        pos = text_lower.find(term)
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos
            best_term = term
    
    if best_pos == -1:
        # No match found, return beginning
        return text[:max_length] + "..." if len(text) > max_length else text
    
    # Extract context around match
    start = max(0, best_pos - max_length // 2)
    end = min(len(text), start + max_length)
    snippet = text[start:end]
    
    # Add ellipsis
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    # Highlight matching terms
    for term in query_terms:
        if len(term) >= 3:  # Only highlight meaningful terms
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            snippet = pattern.sub(lambda m: f"**{m.group()}**", snippet)
    
    return snippet


def _generate_ocr_variants(query: str) -> List[str]:
    """
    Generate query variants to handle common OCR character misrecognition.
    
    Common OCR errors:
    - 0 (zero) ↔ O (letter O)
    - 1 (one) ↔ l (lowercase L) ↔ I (uppercase i)
    - 5 ↔ S
    - 8 ↔ B
    - rn ↔ m
    - cl ↔ d
    - vv ↔ w
    """
    if not query:
        return [query]
    
    variants = set([query])
    query_lower = query.lower()
    
    # Character substitution mappings (source -> replacements)
    substitutions = [
        ('0', 'o'),
        ('o', '0'),
        ('1', 'l'),
        ('l', '1'),
        ('1', 'i'),
        ('i', '1'),
        ('5', 's'),
        ('s', '5'),
        ('8', 'b'),
        ('b', '8'),
        ('rn', 'm'),
        ('m', 'rn'),
        ('cl', 'd'),
        ('d', 'cl'),
        ('vv', 'w'),
        ('w', 'vv'),
    ]
    
    # Generate variants for each substitution
    for source, replacement in substitutions:
        if source in query_lower:
            # Replace first occurrence
            variant = query_lower.replace(source, replacement, 1)
            variants.add(variant)
            # Replace all occurrences
            variant_all = query_lower.replace(source, replacement)
            variants.add(variant_all)
    
    # Also generate variants without spaces (OCR sometimes drops spaces)
    no_space = query_lower.replace(' ', '')
    if len(no_space) > 3:
        variants.add(no_space)
    
    # Limit to prevent too many variants
    return list(variants)[:8]


def perform_search(os_client: OpenSearchClient, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Perform accurate search on OpenSearch optimized for audit/document discovery.
    
    Search Modes:
    1. EXACT PHRASE MODE (quotes): Only returns documents with exact phrase match
    2. MULTI-TERM MODE (no quotes): Balanced precision/recall with proper ranking
    
    Ranking Priority (highest to lowest):
    1. Exact phrase match in filename
    2. Exact phrase match in content
    3. All terms present (AND match)
    4. Most terms present (75%+ match)
    5. Fuzzy matches (for typos)
    """
    # Normalize user query: trim and collapse whitespace
    normalized_query = re.sub(r"\s+", " ", query.strip())
    
    if not normalized_query:
        return []

    # Check if query is in quotes for STRICT exact phrase search
    is_phrase = normalized_query.startswith('"') and normalized_query.endswith('"')
    if is_phrase:
        normalized_query = normalized_query.strip('"')
    
    # Highlight configuration
    highlight_block = {
        "fields": {
            "file_name": {"number_of_fragments": 0},
            "main_content": {"fragment_size": 200, "number_of_fragments": 3},
            "embedded_content": {"fragment_size": 200, "number_of_fragments": 2},
            "ocr_content": {"fragment_size": 200, "number_of_fragments": 3}
        },
        "pre_tags": ["**"],
        "post_tags": ["**"],
        "require_field_match": False,
        "type": "unified"
    }
    
    # Source fields to return
    source_fields = ["file_name", "file_path", "file_size", "mime_type", "indexed_at", 
                     "metadata", "main_content", "embedded_content", "ocr_content", 
                     "ocr_confidence", "ocr_completed"]

    if is_phrase:
        # =======================================================================
        # EXACT PHRASE SEARCH MODE - STRICT MATCHING ONLY
        # =======================================================================
        # When user uses quotes, they want ONLY exact phrase matches.
        # NO fuzzy matching, NO partial matching, NO synonym expansion.
        # This is critical for audit searches where precision matters.
        
        search_query = {
            "query": {
                "bool": {
                    "should": [
                        # Exact phrase in filename (highest priority)
                        {"match_phrase": {"file_name": {"query": normalized_query, "boost": 100, "slop": 0}}},
                        {"match_phrase": {"file_name.english": {"query": normalized_query, "boost": 80, "slop": 0}}},
                        # Exact phrase in file path
                        {"match_phrase": {"file_path": {"query": normalized_query, "boost": 50, "slop": 0}}},
                        # Exact phrase in main content (slop=0 means EXACT)
                        {"match_phrase": {"main_content": {"query": normalized_query, "boost": 40, "slop": 0}}},
                        {"match_phrase": {"main_content.standard": {"query": normalized_query, "boost": 35, "slop": 0}}},
                        # Exact phrase in OCR content (slop=1 for minor OCR spacing issues)
                        {"match_phrase": {"ocr_content": {"query": normalized_query, "boost": 40, "slop": 1}}},
                        {"match_phrase": {"ocr_content.standard": {"query": normalized_query, "boost": 35, "slop": 1}}},
                        # Exact phrase in embedded content
                        {"match_phrase": {"embedded_content": {"query": normalized_query, "boost": 30, "slop": 0}}}
                    ],
                    "minimum_should_match": 1
                }
            },
            "highlight": highlight_block,
            "size": limit,
            "_source": source_fields
        }
    else:
        # =======================================================================
        # MULTI-TERM SEARCH MODE - Balanced precision and recall
        # =======================================================================
        # Field configuration with strategic boosting
        content_fields = [
            "file_name^15",            # Highest: filename match most relevant
            "file_name.english^10",    # English-analyzed filename
            "file_path^8",             # High: path context important  
            "main_content^6",          # Medium-high: primary document content
            "main_content.standard^4", # Standard analyzer fallback
            "ocr_content^6",           # High priority for OCR (scanned docs important)
            "ocr_content.standard^4",  # Standard analyzer for OCR
            "embedded_content^3"       # Lower: reduces Excel data cell noise
        ]
        
        # Generate OCR-corrected variants for fuzzy tier
        ocr_variants = _generate_ocr_variants(normalized_query)
        
        bool_clauses = {
            "should": [
                # --- TIER 1: Exact Matches (Highest Priority - 100+ boost) ---
                {"term": {"file_name.keyword": {"value": normalized_query, "boost": 100}}},
                
                # --- TIER 2: Exact Phrase Matches (High Priority - 50-80 boost) ---
                {"match_phrase": {"file_name": {"query": normalized_query, "boost": 80, "slop": 0}}},
                {"match_phrase": {"file_path": {"query": normalized_query, "boost": 60, "slop": 0}}},
                {"match_phrase": {"main_content": {"query": normalized_query, "boost": 50, "slop": 0}}},
                {"match_phrase": {"ocr_content": {"query": normalized_query, "boost": 50, "slop": 1}}},
                {"match_phrase": {"embedded_content": {"query": normalized_query, "boost": 40, "slop": 0}}},
                
                # --- TIER 3: All Terms Present (AND match - 30-40 boost) ---
                {
                    "multi_match": {
                        "query": normalized_query,
                        "type": "cross_fields",
                        "fields": content_fields,
                        "operator": "and",
                        "boost": 35
                    }
                },
                
                # --- TIER 4: Most Terms Match (75%+ - 20 boost) ---
                {
                    "multi_match": {
                        "query": normalized_query,
                        "type": "best_fields",
                        "fields": content_fields,
                        "operator": "or",
                        "minimum_should_match": "75%",
                        "boost": 20
                    }
                },
                
                # --- TIER 5: Fuzzy Matching for Typos (10 boost) ---
                {
                    "multi_match": {
                        "query": normalized_query,
                        "fields": content_fields,
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                        "prefix_length": 3,
                        "max_expansions": 30,
                        "boost": 10
                    }
                }
            ],
            "minimum_should_match": 1
        }
        
        # Add OCR variant searches for common OCR misreads
        for variant in ocr_variants:
            if variant != normalized_query and variant != normalized_query.lower():
                bool_clauses["should"].append({
                    "match_phrase": {
                        "ocr_content": {
                            "query": variant,
                            "boost": 15,
                            "slop": 1
                        }
                    }
                })
        
        # Wrap with function_score for recency and quality boosting
        search_query = {
            "query": {
                "function_score": {
                    "query": {"bool": bool_clauses},
                    "functions": [
                        # Recency boost: prefer newer documents
                        {
                            "gauss": {
                                "indexed_at": {
                                    "scale": "90d",
                                    "offset": "7d",
                                    "decay": 0.5
                                }
                            },
                            "weight": 1.2
                        },
                        # Boost documents with high OCR confidence
                        {
                            "filter": {"range": {"ocr_confidence": {"gte": 80}}},
                            "weight": 1.3
                        },
                        # Slight penalty for low OCR confidence
                        {
                            "filter": {"range": {"ocr_confidence": {"lt": 50, "gte": 0}}},
                            "weight": 0.8
                        }
                    ],
                    "score_mode": "sum",
                    "boost_mode": "multiply"
                }
            },
            "highlight": highlight_block,
            "size": limit,
            "_source": source_fields
        }
    
    # Execute search with robust error handling
    use_manual_snippets = False
    try:
        # Check if index exists first
        if not os_client.client.indices.exists(index=os_client.index_name):
            return []  # Return empty results if index doesn't exist
        
        response = os_client.client.search(
            index=os_client.index_name,
            body=search_query
        )
    except RequestError as err:
        error_msg = str(err)
        # Handle index not found
        if "index_not_found" in error_msg.lower() or "no such index" in error_msg.lower():
            return []  # Return empty results
        # Fallback for highlight-size errors: retry without highlights, extract manually
        elif any(keyword in error_msg.lower() for keyword in ['highlight', 'analyzed_offset', 'analyzer offset']):
            # Remove highlights entirely, will extract snippets manually
            search_query.pop("highlight", None)
            use_manual_snippets = True
            try:
                response = os_client.client.search(
                    index=os_client.index_name,
                    body=search_query
                )
            except Exception as retry_err:
                # If still failing, something else is wrong
                raise Exception(f"Search failed even without highlights: {retry_err}")
        else:
            # Different error, re-raise
            raise
    
    results = []
    for hit in response['hits']['hits']:
        source = hit['_source']
        result = {
            'id': hit['_id'],
            'score': hit['_score'],
            'filename': source.get('file_name', 'Unknown'),
            'filepath': source.get('file_path', ''),
            'file_size': source.get('file_size', 0),
            'mime_type': source.get('mime_type', ''),
            'indexed_at': source.get('indexed_at', ''),
            'metadata': source.get('metadata', {}),
            'highlights': hit.get('highlight', {}),
            'snippet': '',
            'matched_field': 'unknown',
            'ocr_confidence': source.get('ocr_confidence'),
            'ocr_completed': source.get('ocr_completed', False),
            'has_ocr_content': bool(source.get('ocr_content'))
        }
        
        # Extract snippet from highlights or manually
        highlights = hit.get('highlight', {})
        
        if highlights and not use_manual_snippets:
            # Use OpenSearch highlights when available
            if 'main_content' in highlights:
                result['snippet'] = ' ... '.join(highlights['main_content'][:3])
                result['matched_field'] = 'main_content'
            elif 'embedded_content' in highlights:
                result['snippet'] = ' ... '.join(highlights['embedded_content'][:2])
                result['matched_field'] = 'embedded_content'
            elif 'ocr_content' in highlights:
                result['snippet'] = ' ... '.join(highlights['ocr_content'][:2])
                result['matched_field'] = 'ocr_content'
            elif 'file_name' in highlights:
                result['snippet'] = highlights['file_name'][0]
                result['matched_field'] = 'file_name'
        
        # Manual snippet extraction when highlights unavailable or failed
        if not result['snippet']:
            # Try manual extraction from content fields
            if source.get('main_content'):
                result['snippet'] = extract_snippet_manually(source['main_content'], normalized_query, 180)
                result['matched_field'] = 'main_content' if result['snippet'] else 'none'
            elif source.get('embedded_content'):
                result['snippet'] = extract_snippet_manually(source['embedded_content'], normalized_query, 180)
                result['matched_field'] = 'embedded_content' if result['snippet'] else 'none'
            elif source.get('ocr_content'):
                result['snippet'] = extract_snippet_manually(source['ocr_content'], normalized_query, 180)
                result['matched_field'] = 'ocr_content' if result['snippet'] else 'none'
        
        # Fallback: show metadata if still no snippet
        if not result['snippet']:
            metadata = source.get('metadata', {})
            if metadata:
                preview_parts = []
                for key, value in list(metadata.items())[:3]:
                    if isinstance(value, str) and len(value) < 100:
                        preview_parts.append(f"{key}: {value}")
                if preview_parts:
                    result['snippet'] = ' | '.join(preview_parts)
                    result['matched_field'] = 'metadata'
        
        # Final fallback: filename only
        if not result['snippet']:
            result['snippet'] = result['filename']
            result['matched_field'] = 'filename'
        
        results.append(result)
    
    return results


def render_search_results(results: List[Dict[str, Any]], query: str) -> None:
    """Render search results with highlighting and OCR indicators."""
    if not results:
        st.info(f"No documents found matching '{query}'")
        return
    
    st.markdown(f"### Found {len(results)} Result(s)")
    
    for i, result in enumerate(results):
        with st.container():
            st.markdown('<div class="doc-card">', unsafe_allow_html=True)
            
            col1, col2 = st.columns([5, 1])
            
            with col1:
                # Show OCR badge if content came from OCR
                ocr_badge = ""
                if result.get('has_ocr_content') or result.get('matched_field') == 'ocr_content':
                    ocr_conf = result.get('ocr_confidence')
                    if ocr_conf is not None:
                        if ocr_conf >= 80:
                            ocr_badge = f' <span style="background:#22c55e;color:white;padding:2px 6px;border-radius:4px;font-size:0.75em;">🔍 OCR {ocr_conf:.0f}%</span>'
                        elif ocr_conf >= 50:
                            ocr_badge = f' <span style="background:#f59e0b;color:white;padding:2px 6px;border-radius:4px;font-size:0.75em;">🔍 OCR {ocr_conf:.0f}%</span>'
                        else:
                            ocr_badge = f' <span style="background:#ef4444;color:white;padding:2px 6px;border-radius:4px;font-size:0.75em;">🔍 OCR {ocr_conf:.0f}%</span>'
                    else:
                        ocr_badge = ' <span style="background:#3b82f6;color:white;padding:2px 6px;border-radius:4px;font-size:0.75em;">🔍 OCR</span>'
                
                st.markdown(f'<div class="doc-filename">{result["filename"]}{ocr_badge}</div>', unsafe_allow_html=True)
                
                # Metadata
                file_size_mb = result.get('file_size', 0) / (1024 * 1024)
                meta_text = f"📁 {result['filepath']}"
                if file_size_mb > 0:
                    meta_text += f" | 📦 {file_size_mb:.2f} MB"
                if result.get('mime_type'):
                    meta_text += f" | 📋 {result['mime_type']}"
                
                # Show match source and score
                matched_field = result.get('matched_field', 'content')
                field_labels = {
                    'main_content': '📄 Document Text',
                    'ocr_content': '🔍 OCR Text',
                    'embedded_content': '📎 Embedded Content',
                    'file_name': '📝 Filename',
                    'file_path': '📂 Path',
                    'metadata': 'ℹ️ Metadata'
                }
                field_label = field_labels.get(matched_field, f'📌 {matched_field}')
                confidence = result.get('score', 0)
                meta_text += f" | ✨ {field_label} | Score: {confidence:.1f}"
                
                st.markdown(f'<div class="doc-meta">{meta_text}</div>', unsafe_allow_html=True)
            
            with col2:
                if st.button("📂 Open", key=f"open_{i}", use_container_width=True):
                    try:
                        open_file_with_default_app(result["filepath"])
                        st.success("Opened!")
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            # Snippet with highlighting
            snippet = result.get("snippet", "")
            if snippet:
                # Convert ** markers to HTML highlight
                snippet_html = re.sub(r'\*\*(.+?)\*\*', r'<span class="highlight">\1</span>', snippet)
                st.markdown(f'<div class="result-snippet">{snippet_html}</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("")  # Spacing


def render_recent_documents(os_client: OpenSearchClient, limit: int = 15) -> None:
    """Render recently indexed documents."""
    try:
        # Check if index exists first
        if not os_client.client.indices.exists(index=os_client.index_name):
            st.info("💤 No index found. System is ready to start indexing.")
            st.caption("Start the orchestrator to begin document discovery and indexing.")
            return
        
        query = {
            "query": {"match_all": {}},
            "sort": [{"indexed_at": {"order": "desc"}}],
            "size": limit,
            "_source": ["file_name", "file_path", "file_size", "mime_type", "indexed_at"]
        }
        
        response = os_client.client.search(
            index=os_client.index_name,
            body=query
        )
        
        docs = []
        for hit in response['hits']['hits']:
            docs.append({
                'id': hit['_id'],
                'filename': hit['_source'].get('file_name', 'Unknown'),
                'filepath': hit['_source'].get('file_path', ''),
                'file_size': hit['_source'].get('file_size', 0),
                'mime_type': hit['_source'].get('mime_type', ''),
                'indexed_at': hit['_source'].get('indexed_at', '')
            })
        
        if not docs:
            st.info("📄 No documents indexed yet. Index is ready for documents.")
            return
        
        st.markdown(f"### 📚 Recently Indexed Documents ({len(docs)})")
        
        for i, doc in enumerate(docs):
            with st.container():
                st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([4, 2, 1])
                
                with col1:
                    st.markdown(f'<div class="doc-filename">{doc["filename"]}</div>', unsafe_allow_html=True)
                    file_size_mb = doc.get('file_size', 0) / (1024 * 1024)
                    meta_text = f"📁 {doc['filepath']}"
                    if file_size_mb > 0:
                        meta_text += f" | {file_size_mb:.2f} MB"
                    st.markdown(f'<div class="doc-meta">{meta_text}</div>', unsafe_allow_html=True)
                
                with col2:
                    if doc.get('mime_type'):
                        st.caption(f"📋 {doc['mime_type']}")
                
                with col3:
                    if st.button("📂 Open", key=f"recent_{i}", use_container_width=True):
                        try:
                            open_file_with_default_app(doc["filepath"])
                            st.success("Opened!")
                        except Exception as e:
                            st.error(f"Error: {e}")
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("")  # Spacing
    
    except Exception as e:
        # Handle index not found gracefully
        if "index_not_found" in str(e).lower() or "no such index" in str(e).lower():
            st.info("💤 No index found. System is ready to start indexing.")
            st.caption("Start the orchestrator to begin document discovery and indexing.")
        else:
            st.error(f"Unable to load recent documents: {e}")


def render_monitoring_tab(config: Any, queue_manager: Any) -> None:
    """Render the system monitoring tab with comprehensive error handling."""
    try:
        source_path = getattr(config.paths, 'source_drive', 'N/A')
        working_root = getattr(config.paths, 'working_root', 'N/A')
        st.markdown(f"**Source:** `{source_path}` | **Working Root:** `{working_root}`")
    except Exception:
        st.markdown("**Source:** `N/A` | **Working Root:** `N/A`")
    st.markdown("---")
    
    # Monitoring controls in the main area
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=True, help="Automatically refresh data every few seconds")
    with col2:
        refresh_interval = st.slider("Refresh interval (seconds)", min_value=2, max_value=30, value=5, disabled=not auto_refresh)
    with col3:
        if st.button("Refresh Now", use_container_width=True):
            # Clear caches on manual refresh
            get_cached_queue_stats.clear()
            get_cached_size_stats.clear()
            st.rerun()

    # Initialize with empty defaults
    queue_stats = {}
    size_stats = {}
    
    # Load data using CACHED functions to prevent lag
    try:
        queue_stats = get_cached_queue_stats()
        size_stats = get_cached_size_stats()
    except Exception as exc:
        error_msg = str(exc)
        if "no such table" in error_msg.lower() or "no such column" in error_msg.lower():
            # Database was reset - reset the singleton and try to re-create a fresh instance
            try:
                reset_queue_manager()
                get_cached_queue_stats.clear()
                get_cached_size_stats.clear()
                queue_stats = get_cached_queue_stats()
                size_stats = get_cached_size_stats()
            except Exception:
                st.info("🔄 **System Reset Complete**")
                st.markdown("""
                The system has been reset and all data cleared. Ready for fresh indexing.
                
                **To start processing:**
                1. Open a terminal
                2. Run: `python src/main.py start`
                3. The system will begin discovering and indexing files
                4. Metrics will appear here once processing starts
                """)
                # Show empty metrics
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📁 Files Discovered", "0")
                with col2:
                    st.metric("✅ Fully Processed", "0")
                with col3:
                    st.metric("🔄 In Pipeline", "0")
                with col4:
                    st.metric("❌ Failed", "0")
                st.progress(0.0, text="Ready to start - 0% complete")
                
                # Auto-refresh logic
                if auto_refresh:
                    time.sleep(refresh_interval)
                    st.rerun()
                return
            else:
                st.warning(f"Unable to load queue metrics: {str(exc)[:200]}")
                queue_stats = {}
                size_stats = {'discovered': {'files': 0, 'size_bytes': 0}, 'in_pipeline': {'files': 0, 'size_bytes': 0}, 'searchable': {'files': 0, 'size_bytes': 0}, 'failed': {'files': 0, 'size_bytes': 0}}

    summary = extract_summary(queue_stats)
    show_as_files = st.session_state.get("show_as_files", False) # Default to False (Data Size view)

    # Calculate additional useful metrics
    total_discovered = summary["discovered_total"]
    total_completed = summary["completed_total"]
    total_failures = summary["total_failures"]
    total_duplicates = summary["duplicates"]
    
    # Overall progress
    total_to_process = total_discovered - total_duplicates
    overall_progress = (total_completed / total_to_process * 100) if total_to_process > 0 else 0
    
    # In-flight counts
    in_extraction = summary["extraction_pending"] + summary["extraction_processing"]
    in_indexing = summary["indexing_pending"] + summary["indexing_processing"]
    in_ocr = summary["ocr_pending"] + summary["ocr_processing"]
    total_in_flight = in_extraction + in_indexing + in_ocr
    
    # Success rate
    total_processed = total_completed + total_failures
    success_rate = (total_completed / total_processed * 100) if total_processed > 0 else 100

    # Row 1: Key Progress Metrics
    st.markdown("### 📊 Overall Progress")
    
    col1, col2, col3, col4 = st.columns(4)
    
    if show_as_files:
        with col1:
            st.metric(
                label="📁 Files Discovered",
                value=format_number(total_discovered),
                help="Total files found on source drive"
            )
        
        with col2:
            st.metric(
                label="✅ Fully Processed",
                value=format_number(total_completed),
                delta=f"{overall_progress:.1f}% of total" if total_to_process > 0 else None,
                help="Files that completed all pipeline stages successfully"
            )
        
        with col3:
            st.metric(
                label="🔄 In Pipeline",
                value=format_number(total_in_flight),
                help="Files currently being extracted, indexed, or OCR processed"
            )
        
        with col4:
            st.metric(
                label="❌ Failed",
                value=format_number(total_failures),
                delta=f"{success_rate:.1f}% success rate",
                delta_color="normal",
                help="Files that encountered errors during processing"
            )
        
        # Overall progress bar
        if total_to_process > 0:
            st.progress(min(overall_progress / 100, 1.0), text=f"Overall Progress: {overall_progress:.1f}% ({total_completed:,} / {total_to_process:,} files)")
    else:
        # Data size view - use safe access
        disc_size = (size_stats.get('discovered') or {}).get('size_bytes', 0) or 0
        comp_size = (size_stats.get('searchable') or {}).get('size_bytes', 0) or 0
        pipe_size = (size_stats.get('in_pipeline') or {}).get('size_bytes', 0) or 0
        fail_size = (size_stats.get('failed') or {}).get('size_bytes', 0) or 0
        
        size_progress = (comp_size / max(disc_size, 1)) * 100
        
        with col1:
            st.metric(
                label="📁 Data Discovered",
                value=format_size(disc_size),
                help="Total data volume found on source drive"
            )
        
        with col2:
            st.metric(
                label="✅ Data Indexed",
                value=format_size(comp_size),
                delta=f"{size_progress:.1f}% of total",
                help="Data volume fully indexed and searchable"
            )
            
        with col3:
            st.metric(
                label="🔄 In Pipeline",
                value=format_size(pipe_size),
                help="Data volume currently in processing"
            )
            
        with col4:
            st.metric(
                label="❌ Failed",
                value=format_number(total_failures),
                delta=f"{success_rate:.1f}% success rate",
                delta_color="normal",
                help="Number of files that encountered errors during processing"
            )

        # Overall progress bar
        if disc_size > 0:
            st.progress(min(size_progress / 100, 1.0), text=f"Overall Progress: {size_progress:.1f}% ({format_size(comp_size)} / {format_size(disc_size)} indexed)")

    st.markdown("---")
    
    # Row 2: Pipeline Breakdown
    st.markdown("### ⚙️ Pipeline Status")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**📂 Extraction**")
        st.metric("Pending", format_number(summary.get("extraction_pending", 0)))
        st.metric("Processing", format_number(summary.get("extraction_processing", 0)))
        st.metric("Done", format_number(summary.get("extraction_completed", 0)))
    
    with col2:
        st.markdown("**🗂️ Indexing**")
        st.metric("Pending", format_number(summary.get("indexing_pending", 0)))
        st.metric("Processing", format_number(summary.get("indexing_processing", 0)))
        st.metric("Done", format_number(summary.get("indexing_completed", 0)))
    
    with col3:
        st.markdown("**🔍 OCR Queue**")
        st.metric("Pending", format_number(summary.get("ocr_pending", 0)))
        st.metric("Processing", format_number(summary.get("ocr_processing", 0)))
        st.metric("Done", format_number(summary.get("ocr_completed", 0)))
    
    with col4:
        st.markdown("**📈 Performance**")
        avg_extract = summary.get("avg_extraction_ms", 0) or 0
        avg_index = summary.get("avg_indexing_ms", 0) or 0
        st.metric("Avg Extract", f"{avg_extract:.0f} ms")
        st.metric("Avg Index", f"{avg_index:.0f} ms")
        st.metric("Duplicates", format_number(total_duplicates))

    st.markdown("---")
    # ETA estimates per stage
    try:
        # Remaining counts per stage (use safe access)
        rem_extract = (summary.get('extraction_pending', 0) or 0) + (summary.get('extraction_processing', 0) or 0)
        rem_index = (summary.get('indexing_pending', 0) or 0) + (summary.get('indexing_processing', 0) or 0)
        rem_ocr = (summary.get('ocr_pending', 0) or 0) + (summary.get('ocr_processing', 0) or 0)

        # Average times (ms -> sec), fallbacks if unknown
        avg_extract_ms = summary.get('avg_extraction_ms') or 0
        avg_index_ms = summary.get('avg_indexing_ms') or 0
        avg_extract_sec = (avg_extract_ms / 1000.0) if avg_extract_ms > 0 else 10.0
        avg_index_sec = (avg_index_ms / 1000.0) if avg_index_ms > 0 else 1.0
        avg_ocr_sec = 5.0

        # Worker counts from config (with safe defaults)
        ext_workers = getattr(config.extraction, 'total_workers', 8) if hasattr(config, 'extraction') else 8
        idx_workers = getattr(config.indexing, 'num_workers', 4) if hasattr(config, 'indexing') else 4
        ocr_workers = getattr(config.ocr, 'initial_workers', 4) if hasattr(config, 'ocr') else 4

        eta_extract = (rem_extract * avg_extract_sec) / max(ext_workers, 1)
        eta_index = (rem_index * avg_index_sec) / max(idx_workers, 1)
        eta_ocr = (rem_ocr * avg_ocr_sec) / max(ocr_workers, 1)

        # Wall-clock ETA (parallel) and serial ETA
        wall_eta = max(eta_extract, eta_index, eta_ocr)
        serial_eta = eta_extract + eta_index + eta_ocr

        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        with col_e1:
            st.metric("Extraction Remaining", format_number(rem_extract), delta=seconds_to_human(eta_extract))
        with col_e2:
            st.metric("Indexing Remaining", format_number(rem_index), delta=seconds_to_human(eta_index))
        with col_e3:
            st.metric("OCR Remaining", format_number(rem_ocr), delta=seconds_to_human(eta_ocr))
        with col_e4:
            st.metric("Est. Time (wall)", seconds_to_human(wall_eta), help="Estimated wall-clock time to clear current pipeline")
    except Exception:
        pass
    # Extra: Indexed file metrics (average size + top largest files)
    try:
        comp_files = size_stats['searchable']['files']
        comp_bytes = size_stats['searchable']['size_bytes']
        avg_size = int(comp_bytes / comp_files) if comp_files > 0 else 0

        with st.expander("📦 Indexed File Metrics", expanded=False):
            col_a, col_b = st.columns([2, 3])
            with col_a:
                st.metric("Avg Indexed File", format_size(avg_size), help="Average size of indexed (searchable) files")
                st.caption(f"{comp_files:,} files indexed")

            with col_b:
                try:
                    top_files = get_cached_largest_files()
                    if top_files:
                        rows = []
                        for f in top_files:
                            rows.append({
                                "File": Path(f['file_path']).name,
                                "Size": format_size(f.get('file_size', 0)),
                                "Path": f.get('file_path', '')
                            })
                        df = pd.DataFrame(rows)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No indexed files available yet")
                except Exception as e:
                    st.error(f"Unable to load top indexed files: {e}")
    except Exception:
        # Defensive: if size_stats missing keys
        pass

    # Detailed sections
    tab1, tab2, tab3 = st.tabs(["📊 Extraction Details", "⚠️ Failure Analysis", "📋 Queue Status"])
    
    with tab1:
        st.subheader("Extraction by Size Category")
        render_extraction_detail(queue_stats)
    
    with tab2:
        st.subheader("Failure Breakdown")
        render_failure_chart(queue_stats)
        
        # Show detailed failure table
        failures = queue_stats.get("failures", {})
        if failures:
            total_failures = queue_stats.get("total_failures", 0)
            failure_df = pd.DataFrame([
                {
                    "Error Type": error_type,
                    "Count": count,
                    "Percentage": f"{(count / total_failures * 100):.1f}%" if total_failures else "0%"
                }
                for error_type, count in sorted(failures.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(failure_df, use_container_width=True, hide_index=True)
            
            # Show actual failed files
            st.markdown("---")
            st.subheader("📋 Failed Files Details")
            try:
                failed_files = get_cached_failed_files()
                if failed_files:
                    failed_df = pd.DataFrame([
                        {
                            "File": Path(f['file_path']).name if f.get('file_path') else 'Unknown',
                            "Stage": f.get('stage', ''),
                            "Error": f.get('error_type', ''),
                            "Message": (f.get('error_message', '') or '')[:100] + '...' if len(f.get('error_message', '') or '') > 100 else f.get('error_message', ''),
                            "Path": f.get('file_path', '')
                        }
                        for f in failed_files
                    ])
                    st.dataframe(failed_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No failed files to display")
            except Exception as e:
                st.warning(f"Could not load failed files: {e}")
        else:
            st.success("✓ No failures recorded. System running smoothly!")
    
    with tab3:
        st.subheader("Queue Status Overview")
        
        status_data = []
        # Main queues to monitor
        for q_key in ["discovery", "extraction", "indexing", "ocr"]:
            q_data = queue_stats.get(q_key, {})
            if q_key == "extraction":
                # Special handling for extraction size categories
                for size_cat, metrics in q_data.items():
                    if isinstance(metrics, dict):
                        for status, count in metrics.items():
                            if status in ["pending", "processing", "completed", "total"]:
                                status_data.append({
                                    "Queue": f"Extraction ({size_cat.title()})",
                                    "Status": status.title(),
                                    "Count": count or 0
                                })
            elif isinstance(q_data, dict):
                for status, count in q_data.items():
                    if status in ["pending", "processing", "completed", "failed", "total"]:
                        status_data.append({
                            "Queue": q_key.title(),
                            "Status": status.title(),
                            "Count": count or 0
                        })
        
        if status_data:
            status_df = pd.DataFrame(status_data)
            st.dataframe(status_df, use_container_width=True, hide_index=True)
        else:
            st.info("No queue status data available")
        
        # Show OCR pending files (flagged for OCR)
        st.markdown("---")
        st.subheader("🔍 Files Flagged for OCR")
        try:
            ocr_pending = get_cached_ocr_pending()
            if ocr_pending:
                ocr_df = pd.DataFrame([
                    {
                        "File": Path(f['file_path']).name if f.get('file_path') else 'Unknown',
                        "Status": f.get('status', '').title(),
                        "Priority": f.get('priority', 5),
                        "Path": f.get('file_path', '')
                    }
                    for f in ocr_pending
                ])
                st.dataframe(ocr_df, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(ocr_pending)} of pending OCR files")
            else:
                st.success("✓ No files pending OCR processing")
        except Exception as e:
            st.warning(f"Could not load OCR queue: {e}")

   
        # Auto-refresh logic - PREVENT INFINITE REFRESH CASCADE
    if "manual_refresh_triggered" not in st.session_state:
        st.session_state.manual_refresh_triggered = False
    
    if auto_refresh and not st.session_state.manual_refresh_triggered:
        time.sleep(refresh_interval)
        st.rerun()
    else:
        # Clear the flag after use to allow next auto-refresh cycle
        st.session_state.manual_refresh_triggered = False


def main() -> None:
    render_dashboard()


if __name__ == "__main__":
    main()
