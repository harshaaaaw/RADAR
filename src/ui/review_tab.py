"""
Production-Grade Snippet Review Portal — Human-in-the-Loop Visual Verification.

This module renders the "Snippet Review" tab in the Streamlit dashboard.
It provides:
  1. Document selector with per-document dynamic KPI metrics
  2. Role-based snippet filtering (signatures, stamps, logos)
  3. Clean vertical card layout with snippet images, impact %, and reviewer roles
  4. Mandatory acceptance reason system with audit trail
  5. Activity log panel showing chronological review history
  6. Storage management for snippet crop files
"""
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageOps
import streamlit as st
import streamlit.components.v1 as components

from core.config_manager import get_config
from core.reporting_manager import (
    get_all_reviews_for_doc,
    get_docs_with_reviews,
    get_pending_reviews,
    get_review_activity_log,
    get_snippet_storage_stats,
    purge_old_snippets,
    update_snippet_review_status,
    get_page_segmentation_breakdown,
    get_snippet_suppressions,
    revert_snippet_review,
    add_opensearch_retry,
    get_pending_opensearch_retries,
    update_opensearch_retry,
)
from indexing.opensearch_client import OpenSearchClient
from ocr.visual_memory import VisualMemoryEngine
from ocr.tesseract_wrapper import TesseractWrapper

# ── Standard acceptance reasons for each snippet type ────────────────────────
ACCEPTANCE_REASONS = {
    "signature": [
        "Authorized signatory — verified signer identity",
        "Known employee signature — HR verified",
        "Client signature — contractually approved",
        "Witness signature — standard legal requirement",
        "Digital signature — system-generated",
    ],
    "stamp": [
        "Official company stamp/seal — known template",
        "Notary public seal — standard legal element",
        "Government department stamp — regulatory requirement",
        "Quality assurance stamp — internal process",
        "Received/filed date stamp — administrative",
    ],
    "logo": [
        "Registered company logo — brand asset",
        "Partner/client logo — business relationship",
        "Regulatory body logo — compliance requirement",
        "Certification mark — industry standard",
        "Decorative header/footer — no content impact",
    ],
    "text_anomaly": [
        "OCR extracted correctly — no visual review required",
        "Machine-readable text region — routed to OCR flow",
        "Reference number/identifier — expected text token",
        "Printed text artifact — not a signature",
        "No manual visual validation needed",
    ],
    "handwritten": [
        "Legible handwritten annotation — verified content",
        "Handwritten numbers/date — standard document field",
        "Margin notes/comments — administrative record",
        "Form fill-in — manual entry verified",
        "Correction/amendment — approved handwriting",
    ],
    "faded_text": [
        "Faded printed text recovered — verified transcription",
        "Faint watermark/background text — readable content",
        "Carbon copy text restored — administrative record",
        "Low contrast text region — manually corrected",
        "Partially legible text segment — transcription verified",
    ],
}
GENERIC_REASONS = [
    "Verified element — no accuracy concern",
    "Standard document formatting — expected element",
    "Custom reason...",
]

# ── Snippet type display configuration ───────────────────────────────────────
SNIPPET_TYPE_CONFIG = {
    "signature": {
        "icon": "✒️",
        "label": "Signature",
        "color": "#3B82F6",
        "bg": "#EFF6FF",
        "border": "#93C5FD",
    },
    "stamp": {
        "icon": "🔏",
        "label": "Stamp & Seal",
        "color": "#EA580C",
        "bg": "#FFF7ED",
        "border": "#FDBA74",
    },
    "logo": {
        "icon": "🖼️",
        "label": "Logo & Image",
        "color": "#7C3AED",
        "bg": "#F5F3FF",
        "border": "#C4B5FD",
    },
    "text_anomaly": {
        "icon": "🔤",
        "label": "OCR Text Region",
        "color": "#0F766E",
        "bg": "#ECFEFF",
        "border": "#67E8F9",
    },
    "handwritten": {
        "icon": "✍️",
        "label": "Handwritten",
        "color": "#DB2777",
        "bg": "#FDF2F8",
        "border": "#FBCFE8",
    },
    "faded_text": {
        "icon": "░",
        "label": "Faded Text",
        "color": "#1D4ED8",
        "bg": "#EFF6FF",
        "border": "#BFDBFE",
    },
}

STATUS_BADGES = {
    "pending": {"color": "#D97706", "bg": "#FFF6E5", "label": "Pending Review"},
    "accepted": {"color": "#047857", "bg": "#ECFDF5", "label": "Accepted"},
    "rejected": {"color": "#B91C1C", "bg": "#FEF2F2", "label": "Rejected"},
}


def _format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _render_metric_card(
    title: str,
    value: str,
    subtitle: str,
    border_color: str,
    bg_color: str,
    text_color: str,
    icon: str = "",
) -> None:
    """Render a styled metric card using HTML."""
    st.markdown(
        f"""
        <div style="
            background: {bg_color};
            padding: 1rem 1.2rem;
            border-radius: 10px;
            border-left: 4px solid {border_color};
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            margin-bottom: 0.5rem;
        ">
            <p style="margin:0; font-size:0.78rem; font-weight:600; color:{text_color};
                       text-transform:uppercase; letter-spacing:0.5px;">
                {icon} {title}
            </p>
            <h3 style="margin:0.25rem 0 0 0; color:{border_color}; font-size:1.6rem;
                        font-weight:700; line-height:1.2;">
                {value}
            </h3>
            <p style="margin:0.15rem 0 0 0; font-size:0.72rem; color:{text_color}; opacity:0.85;">
                {subtitle}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _resolve_snippet_path(snippet_path, working_root) -> Optional[str]:
    """Resolve legacy snippet paths into current workspace data path.

    Args:
        snippet_path: Path to the snippet file (str or Path).
        working_root: Root directory of the working space (str or Path).

    Returns:
        Resolved path string if the file exists, or None if not found.
    """
    if snippet_path is None:
        return None

    path = Path(str(snippet_path))
    working = Path(str(working_root))

    if path.exists():
        return str(path)

    # Try normalized path remapping for legacy paths
    normalized = str(path).replace("\\", "/")
    marker = "/data/review_snippets/"
    if marker in normalized:
        relative_part = normalized.split(marker, 1)[1]
        mapped = working.parent / "data" / "review_snippets" / Path(relative_part)
        if mapped.exists():
            return str(mapped)

    # File not found
    return None


def _build_uniform_thumbnail(img: Image.Image, width: int = 480, height: int = 160) -> Image.Image:
    """Build a fixed-size thumbnail canvas for consistent tile height."""
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Keep aspect ratio while fitting into a fixed canvas for stable grid layout.
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    fitted = ImageOps.contain(img, (width - 16, height - 16), method=resample)
    canvas = Image.new("RGB", (width, height), color=(248, 250, 252))
    x = (width - fitted.width) // 2
    y = (height - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def _resolve_document_path(file_path: Any) -> Optional[str]:
    """Resolve legacy document file paths using current environment settings."""
    if not file_path:
        return None
    p = Path(file_path)
    if p.exists():
        return str(p)
    
    try:
        config = get_config()
        # config is a dataclass — access via attribute, not .get()
        source_drive = getattr(getattr(config, "paths", None), "source_drive", None)
        if source_drive:
            mapped = Path(source_drive) / p.name
            if mapped.exists():
                return str(mapped)
    except Exception:
        pass
        
    # Try relative data directory
    try:
        mapped = Path("data") / p.name
        if mapped.exists():
            return str(mapped)
    except Exception:
        pass
        
    return None



def _build_document_page_link(file_path: str, page_num: int) -> Optional[str]:
    """Build file:// URL with page hint for local PDF files."""
    if not file_path:
        return None
    try:
        resolved = _resolve_document_path(file_path)
        if not resolved:
            return None
        p = Path(resolved)
        uri = p.resolve().as_uri()
        if p.suffix.lower() == ".pdf":
            return f"{uri}#page={max(1, int(page_num or 1))}"
        return uri
    except Exception:
        return None


def _open_source_document(file_path: Any, page_num: Any) -> None:
    """Open file with system default application to specific page."""
    try:
        import webbrowser
        page_num_int = int(page_num or 1)
        file_path_str = str(file_path)
        
        # Build file URL using the existing helper which correctly adds the page anchor
        uri = _build_document_page_link(file_path_str, page_num_int)
        if uri:
            try:
                if webbrowser.open(uri):
                    return
            except Exception:
                pass
        
        if os.name == 'nt':  # Windows
            # Final fallback: Use default app (won't open to page, but will work)
            os.startfile(file_path_str)
        elif os.uname().sysname == 'Darwin':  # macOS
            # macOS: use open with -a for app and page parameter via URL scheme
            file_uri = Path(file_path_str).resolve().as_uri()
            if page_num_int > 1:
                file_uri += f'#page={page_num_int}'
            subprocess.run(['open', file_uri], check=True)
        else:  # Linux
            # Linux: xdg-open respects file:// URLs with #page anchor
            file_uri = Path(file_path_str).resolve().as_uri()
            if page_num_int > 1:
                file_uri += f'#page={page_num_int}'
            subprocess.run(['xdg-open', file_uri], check=True)
    except Exception as e:
        st.error(f"Failed to open file: {e}")


def _render_accuracy_waterfall_chart(snippets: List[Dict[str, Any]], selected_doc: Dict[str, Any]) -> None:
    """Render accuracy waterfall chart.

    Layout order:
      1. Current Accuracy (green, solid) — first bar
      2. Category error bars (signatures, stamps, etc.) — stacked starting from
         current accuracy upward toward 100%
      3. Total Accuracy (blue, dotted outline, light fill) — last bar
    """
    category_meta = {
        "stamp": ("Stamp", "#F59E0B"),
        "signature": ("Signature", "#EF4444"),
        "logo": ("Logo/Image", "#8B5CF6"),
        "text_anomaly": ("Text", "#14B8A6"),
        "handwritten": ("Handwritten", "#EC4899"),
        "faded_text": ("Faded Text", "#3B82F6"),
    }

    pending = [s for s in snippets if s.get("status") == "pending"]
    by_type: Dict[str, Dict[str, float]] = {}
    for s in pending:
        t = str(s.get("snippet_type") or "other")
        impact = max(0.0, float(s.get("accuracy_impact") or 0.0))
        by_type.setdefault(t, {"impact": 0.0, "count": 0.0})
        by_type[t]["impact"] += impact
        by_type[t]["count"] += 1

    raw_fault_total = sum(v["impact"] for v in by_type.values())
    fault_total = min(100.0, raw_fault_total)
    current_accuracy = max(0.0, 100.0 - fault_total)

    # Build bars: Current first, then categories stacking upward, Total last
    bars = []

    # 1. Current Accuracy — solid green bar
    bars.append({
        "label": "Current",
        "value": current_accuracy,
        "bottom": 0.0,
        "color": "#16A34A",
        "fill_color": "#16A34A",
        "text": f"{current_accuracy:.2f}%",
        "style": "solid",
    })

    # 2. Category error bars — each starts where the previous ended above current accuracy
    sorted_types = sorted(by_type.items(), key=lambda kv: kv[1]["impact"], reverse=True)
    running_bottom = current_accuracy
    for t, data in sorted_types:
        raw = data["impact"]
        scaled = (raw / raw_fault_total * fault_total) if raw_fault_total > 0 else 0.0
        label, color = category_meta.get(t, (t.title(), "#64748B"))
        bars.append({
            "label": f"{label} ({int(data['count'])})",
            "value": scaled,
            "bottom": running_bottom,
            "color": color,
            "fill_color": color,
            "text": f"{raw:.2f}%",
            "style": "solid",
        })
        running_bottom = min(100.0, running_bottom + scaled)

    # 3. Total Accuracy — blue, dotted outline, light fill (last)
    bars.append({
        "label": "Total",
        "value": 100.0,
        "bottom": 0.0,
        "color": "#2563EB",
        "fill_color": "#DBEAFE",
        "text": "100%",
        "style": "dotted",
    })

    chart_width = max(800, 120 * len(bars))
    bar_slot = max(90, int(chart_width / max(1, len(bars))))
    bar_width = int(bar_slot * 0.35)
    left_pad = 30
    chart_h = 240
    plot_top = 20
    plot_h = chart_h - 80

    bar_rects: List[str] = []
    pct_labels: List[str] = []
    x_labels: List[str] = []
    legend_items: List[str] = []
    for i, bar in enumerate(bars):
        x = left_pad + i * bar_slot + (bar_slot - bar_width) // 2
        h = max(0.0, min(100.0, bar["value"]))
        b = max(0.0, min(100.0, bar["bottom"]))
        px_h = (h / 100.0) * plot_h
        px_b = (b / 100.0) * plot_h
        y = plot_top + (plot_h - px_b - px_h)

        if bar["style"] == "dotted":
            bar_rects.append(
                f"<rect x='{x}' y='{y:.1f}' width='{bar_width}' height='{px_h:.1f}' rx='6' "
                f"fill='{bar['fill_color']}' stroke='{bar['color']}' stroke-width='2' "
                f"stroke-dasharray='5,3'></rect>"
            )
        else:
            bar_rects.append(
                f"<rect x='{x}' y='{y:.1f}' width='{bar_width}' height='{px_h:.1f}' rx='6' "
                f"fill='{bar['fill_color']}'></rect>"
            )

        pct_labels.append(
            f"<text x='{x + bar_width/2:.1f}' y='{max(12, y - 8):.1f}' text-anchor='middle' font-size='12' font-weight='700' fill='#0F172A'>{bar['text']}</text>"
        )
        x_labels.append(
            f"<text x='{x + bar_width/2:.1f}' y='{chart_h - 28}' text-anchor='middle' font-size='12' font-weight='700' fill='#111827'>{bar['label']}</text>"
        )
        legend_items.append(
            f"<span style='display:inline-flex; align-items:center; gap:6px; margin-right:14px; font-size:12px; color:#334155;'>"
            f"<span style='display:inline-block; width:10px; height:10px; border-radius:2px; background:{bar['color']};{' border:1px dashed #2563EB;' if bar['style'] == 'dotted' else ''}'></span>"
            f"{bar['label']}</span>"
        )

    svg = f"""
    <div style='border:1px solid #E5E7EB; border-radius:10px; background:#FFFFFF; padding:8px 10px 10px 10px;'>
      <svg width='{left_pad + bar_slot * len(bars) + 20}' height='{chart_h}' viewBox='0 0 {left_pad + bar_slot * len(bars) + 20} {chart_h}'>
        <line x1='{left_pad-6}' y1='{plot_top + plot_h}' x2='{left_pad + bar_slot * len(bars)}' y2='{plot_top + plot_h}' stroke='#CBD5E1' stroke-width='1.2'></line>
        {''.join(bar_rects)}
        {''.join(pct_labels)}
        {''.join(x_labels)}
      </svg>
      <div style='margin-top:6px; padding-top:6px; border-top:1px dashed #E2E8F0; white-space:nowrap; overflow-x:auto;'>
        {''.join(legend_items)}
      </div>
    </div>
    """
    components.html(svg, height=chart_h + 70, width=chart_width, scrolling=False)


def _render_page_composition_bar(selected_doc: Dict[str, Any]) -> None:
    smart_id = selected_doc.get("smart_id")
    if not smart_id:
        st.warning("No document selected.")
        return

    breakdown = get_page_segmentation_breakdown(smart_id)
    if not breakdown:
        st.info("No page segmentation breakdown available for this document.")
        return

    st.markdown("""<div style="border: 1px solid #E5E7EB; border-radius: 10px; padding: 16px; background: #FFFFFF; font-family: sans-serif; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 15px;">
  <div style="font-weight: 700; color: #1E293B; margin-bottom: 12px; font-size: 15px;">Page-by-Page Composition Breakdown</div>
  <!-- Legend -->
  <div style="display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: #475569;">
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #10B981; border-radius: 3px;"></span>Clean Text</span>
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #3B82F6; border-radius: 3px;"></span>Faded Text</span>
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #8B5CF6; border-radius: 3px;"></span>Logo/Image</span>
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #F59E0B; border-radius: 3px;"></span>Stamp</span>
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #EC4899; border-radius: 3px;"></span>Handwritten</span>
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 3px;"></span>Whitespace</span>
    <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="display: inline-block; width: 12px; height: 12px; background: #6B7280; border-radius: 3px;"></span>Noise</span>
  </div>
</div>""", unsafe_allow_html=True)

    file_path = _resolve_document_path(selected_doc.get("file_path"))

    for row in breakdown:
        page_num = row.get("page_num", 1)
        clean = float(row.get("clean_text_pct") or 0.0)
        faded = float(row.get("faded_text_pct") or 0.0)
        logo = float(row.get("logo_pct") or 0.0)
        stamp = float(row.get("stamp_pct") or 0.0)
        handwritten = float(row.get("handwritten_pct") or 0.0)
        whitespace = float(row.get("whitespace_pct") or 0.0)
        noise = float(row.get("noise_pct") or 0.0)

        # Normalize to 100%
        total = clean + faded + logo + stamp + handwritten + whitespace + noise
        if total > 0:
            scale = 100.0 / total
            clean *= scale
            faded *= scale
            logo *= scale
            stamp *= scale
            handwritten *= scale
            whitespace *= scale
            noise *= scale
        else:
            whitespace = 100.0

        col_btn, col_bar = st.columns([1.5, 8.5])
        with col_btn:
            if file_path:
                st.button(
                    f"🔗 P. {page_num}",
                    key=f"open_comp_page_{smart_id}_{page_num}",
                    on_click=_open_source_document,
                    args=(file_path, page_num),
                    help=f"Open document to page {page_num}"
                )
            else:
                st.markdown(f"**Page {page_num}**")

        with col_bar:
            page_html_parts = []
            page_html_parts.append(f"""<div style="font-family: sans-serif; margin-bottom: 14px; padding: 8px; border: 1px solid #E2E8F0; border-radius: 8px; background: #F8FAFC;">
  <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; color: #64748B; margin-bottom: 4px;">
    <span>Page {page_num} Breakdown</span>
    <span>Width: {row.get('page_width_px', 0)}px | Height: {row.get('page_height_px', 0)}px</span>
  </div>
  <div style="display: flex; width: 100%; height: 20px; border-radius: 4px; overflow: hidden; background: #E2E8F0;">""")

            if clean > 0:
                page_html_parts.append(f'<div style="width: {clean:.2f}%; background: #10B981; height: 100%;" title="Clean Text: {clean:.1f}%"></div>')
            if faded > 0:
                page_html_parts.append(f'<div style="width: {faded:.2f}%; background: #3B82F6; height: 100%;" title="Faded Text: {faded:.1f}%"></div>')
            if logo > 0:
                page_html_parts.append(f'<div style="width: {logo:.2f}%; background: #8B5CF6; height: 100%;" title="Logo: {logo:.1f}%"></div>')
            if stamp > 0:
                page_html_parts.append(f'<div style="width: {stamp:.2f}%; background: #F59E0B; height: 100%;" title="Stamp: {stamp:.1f}%"></div>')
            if handwritten > 0:
                page_html_parts.append(f'<div style="width: {handwritten:.2f}%; background: #EC4899; height: 100%;" title="Handwritten: {handwritten:.1f}%"></div>')
            if whitespace > 0:
                page_html_parts.append(f'<div style="width: {whitespace:.2f}%; background: #F3F4F6; border-left: 1px solid #D1D5DB; border-right: 1px solid #D1D5DB; height: 100%;" title="Whitespace: {whitespace:.1f}%"></div>')
            if noise > 0:
                page_html_parts.append(f'<div style="width: {noise:.2f}%; background: #6B7280; height: 100%;" title="Noise: {noise:.1f}%"></div>')

            page_html_parts.append("""</div>
  <!-- Numeric breakdown tooltip inline -->
  <div style="display: flex; gap: 8px; font-size: 10px; color: #64748B; margin-top: 4px; flex-wrap: wrap;">""")
            if clean > 0: page_html_parts.append(f'<span>🟢 Text: {clean:.1f}%</span>')
            if faded > 0: page_html_parts.append(f'<span>🔵 Faded: {faded:.1f}%</span>')
            if logo > 0: page_html_parts.append(f'<span>🟣 Logo: {logo:.1f}%</span>')
            if stamp > 0: page_html_parts.append(f'<span>🟡 Stamp: {stamp:.1f}%</span>')
            if handwritten > 0: page_html_parts.append(f'<span>💗 Hand: {handwritten:.1f}%</span>')
            if whitespace > 0: page_html_parts.append(f'<span>⚪ WS: {whitespace:.1f}%</span>')
            if noise > 0: page_html_parts.append(f'<span>⚫ Noise: {noise:.1f}%</span>')
            page_html_parts.append("</div></div>")

            st.markdown("".join(page_html_parts), unsafe_allow_html=True)


def _run_auto_tagging(
    accepted_review_id: str,
    smart_id: str,
    visual_memory: Any,
    working_root: str,
    db_conn=None,
) -> int:
    """Run auto-tagging: after accepting one snippet, auto-accept similar pending siblings.

    Args:
        accepted_review_id: The review_id that was just accepted.
        smart_id: The document ID.
        visual_memory: VisualMemoryEngine instance.
        working_root: Path to the working root directory (for vector resolution).
        db_conn: Optional SQLite connection for testing.

    Returns:
        Number of snippets auto-tagged.
    """
    if visual_memory is None:
        return 0

    try:
        if db_conn is not None:
            rows = db_conn.execute(
                """SELECT review_id, snippet_type, snippet_path, extracted_text
                   FROM snippet_reviews
                   WHERE smart_id=? AND status='pending' AND review_id!=?""",
                (smart_id, accepted_review_id)
            ).fetchall()
            all_reviews = [dict(r) for r in rows]
        else:
            all_reviews = get_all_reviews_for_doc(smart_id)
            all_reviews = [r for r in all_reviews
                           if r.get("status") == "pending"
                           and r.get("review_id") != accepted_review_id]

        vector_dir = Path(working_root) / "data" / "visual_memory" / smart_id
        auto_count = 0

        for sibling in all_reviews:
            sib_id = sibling.get("review_id") or sibling[0]
            sib_path = sibling.get("snippet_path") or sibling[2]
            sib_type = sibling.get("snippet_type") or sibling[1]
            sib_text = sibling.get("extracted_text") or (sibling[3] if isinstance(sibling, tuple) and len(sibling) > 3 else None)

            ELIGIBLE_AUTO_TAG_TYPES = {"signature", "stamp", "logo"}
            if sib_type not in ELIGIBLE_AUTO_TAG_TYPES:
                continue

            resolved = _resolve_snippet_path(str(sib_path), working_root)
            if not resolved or not Path(resolved).exists():
                continue
            try:
                is_match, _ = visual_memory.match_snippet(
                    candidate_image_path=resolved,
                    approved_vectors_dir=str(vector_dir),
                    threshold=0.90,
                    candidate_text=sib_text,
                )
                if is_match:
                    update_snippet_review_status(
                        sib_id,
                        status="accepted",
                        review_reason=f"Auto-tagged from {accepted_review_id}",
                        db_conn=db_conn,
                    )
                    auto_count += 1
            except Exception:
                pass

        return auto_count
    except Exception:
        return 0


def _update_opensearch_with_retry(
    os_client: Any,
    smart_id: str,
    updates: Dict[str, Any],
    max_retries: int = 3,
    delay_s: float = 0.5,
) -> Optional[Any]:
    """Update OpenSearch document with automatic retry on version conflicts.

    Args:
        os_client: OpenSearch client instance with update_document method.
        smart_id: Document ID to update.
        updates: Dict of field updates to apply.
        max_retries: Maximum number of retry attempts.
        delay_s: Initial delay between retries (doubles each attempt).

    Returns:
        The result of the successful update, or None if all retries failed.
    """
    import time
    last_exc = None
    for attempt in range(max_retries):
        try:
            return os_client.update_document(smart_id, updates)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(delay_s * (2 ** attempt))
    if last_exc:
        raise last_exc
    return None



def _is_obvious_noise_review_snippet(snippet: Dict[str, Any], working_root: Path) -> bool:
    """Identify sparse dot/blob snippets that should not appear in visual review queue."""
    if snippet.get("status") != "pending":
        return False

    # Hard suppression only for extremely tiny impact — real cursive signatures
    # can have low area ratios on large pages so the threshold is kept very low.
    if snippet.get("snippet_type") == "signature":
        try:
            if float(snippet.get("accuracy_impact") or 0.0) <= 0.03:
                return True
        except Exception:
            pass

    snippet_path = _resolve_snippet_path(Path(snippet.get("snippet_path", "")), working_root)
    if not snippet_path:
        return False

    try:
        arr = np.array(Image.open(str(snippet_path)).convert("L"))
        if arr.ndim != 2:
            return False

        h, w = arr.shape
        area = max(1, h * w)
        ink_mask = arr < 200
        ink_px = int(np.count_nonzero(ink_mask))
        if ink_px == 0:
            return True

        ink_ratio = ink_px / area
        row_coverage = float(np.count_nonzero(np.any(ink_mask, axis=1)) / max(1, h))
        col_coverage = float(np.count_nonzero(np.any(ink_mask, axis=0)) / max(1, w))

        return (
            ink_ratio < 0.004
            or (ink_ratio < 0.010 and row_coverage < 0.35 and col_coverage < 0.35)
            or (area > 1500 and ink_px < 60)
        )
    except Exception:
        return False


def _is_printed_font_review_snippet(snippet: Dict[str, Any], working_root: Path) -> bool:
    """Return True when the saved crop looks like printed/digital text, not handwriting.

    Uses numpy-only stroke-width uniformity check (no cv2 dependency in UI layer).
    Printed fonts: very uniform stroke widths → low coefficient of variation on the
    distance-field proxy (run-length distribution per row).
    Handwriting: highly variable stroke widths → high CV.
    """
    if snippet.get("snippet_type") != "signature":
        return False
    if snippet.get("status") != "pending":
        return False

    snippet_path = _resolve_snippet_path(Path(snippet.get("snippet_path", "")), working_root)
    if not snippet_path:
        return False

    try:
        arr = np.array(Image.open(str(snippet_path)).convert("L"))
        if arr.ndim != 2:
            return False

        h, w = arr.shape
        if h < 8 or w < 8:
            return False

        # Binarize: ink = True
        ink = arr < 128

        ink_px = int(np.count_nonzero(ink))
        if ink_px < 20:
            return False

        # ── Stroke-width proxy: horizontal run lengths of ink pixels ──────
        # For each row collect the lengths of consecutive ink runs.
        # Printed fonts produce very consistent run lengths across all rows;
        # cursive handwriting has wildly variable run lengths.
        run_lengths = []
        for row in ink:
            in_run = False
            run_len = 0
            for px in row:
                if px:
                    in_run = True
                    run_len += 1
                else:
                    if in_run and run_len > 0:
                        run_lengths.append(run_len)
                    in_run = False
                    run_len = 0
            if in_run and run_len > 0:
                run_lengths.append(run_len)

        if len(run_lengths) < 10:
            return False

        rl = np.array(run_lengths, dtype=np.float32)
        cv_val = float(np.std(rl) / max(np.mean(rl), 0.001))

        # Printed text: uniform runs → CV < 0.55 (raised to tolerate scan noise)
        # Handwriting: irregular runs → CV > 0.65
        is_uniform_stroke = cv_val < 0.55

        # ── Edge regularity: row-wise ink fraction variance ───────────────
        # Printed glyphs have very consistent ink density per row within a letter;
        # cursive letters taper and swell → higher variance.
        row_densities = np.sum(ink, axis=1) / max(w, 1)
        nonzero_rows = row_densities[row_densities > 0]
        if len(nonzero_rows) < 3:
            return False
        density_cv = float(np.std(nonzero_rows) / max(np.mean(nonzero_rows), 0.001))

        # Suppress when both uniformity signals agree (2-of-2).
        is_uniform_density = density_cv < 0.65

        return is_uniform_stroke and is_uniform_density

    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _get_review_tesseract() -> Optional[TesseractWrapper]:
    """Initialize one reusable Tesseract wrapper for queue-side snippet suppression."""
    try:
        return TesseractWrapper()
    except Exception:
        return None


def _is_text_like_review_snippet(snippet: Dict[str, Any], working_root: Path) -> bool:
    """Hide queued snippets that are actually machine-readable text tokens."""
    if snippet.get("status") != "pending":
        return False

    snippet_path = _resolve_snippet_path(Path(snippet.get("snippet_path", "")), working_root)
    if not snippet_path:
        return False

    tesseract = _get_review_tesseract()
    if not tesseract:
        return False

    try:
        ocr_result = tesseract.extract_text(str(snippet_path))
        if not ocr_result:
            return False

        text, confidence = ocr_result
        cleaned = re.sub(r"\s+", "", text or "")
        alnum = re.sub(r"[^A-Za-z0-9]", "", cleaned)
        alpha_only = re.sub(r"[^A-Za-z]", "", cleaned)
        conf = float(confidence or 0.0)

        # Cursive handwriting → Tesseract <10% confidence + garbled chars.
        # Printed/typewriter words → 18-60% confidence even on degraded scans.
        base_text_like = (len(alnum) >= 4 and conf >= 18.0) or (len(alnum) >= 7 and conf >= 12.0)

        # Signature false-positive guard for existing queue items:
        # hide alphabetic typed words that are often misdetected as signatures.
        snippet_type = str(snippet.get("snippet_type") or "")
        alpha_ratio = (len(alpha_only) / max(1, len(alnum))) if alnum else 0.0
        printed_signature_word = (
            snippet_type == "signature"
            and len(alpha_only) >= 6
            and alpha_ratio >= 0.85
            and conf >= 8.0
        )

        return base_text_like or printed_signature_word
    except Exception:
        return False


def _render_snippet_card(
    snippet: Dict[str, Any],
    working_root: Path,
    idx: int,
    compact: bool = False,
) -> None:
    """Render a single snippet review card with image, details, and action buttons."""
    review_id = snippet["review_id"]
    snippet_type = snippet["snippet_type"]
    snippet_path = Path(snippet["snippet_path"])
    snippet_path = _resolve_snippet_path(snippet_path, working_root)
    page_num = snippet["page_num"]
    accuracy_impact = snippet["accuracy_impact"]
    reviewer_role = snippet["reviewer_role"]
    status = snippet.get("status", "pending")
    extracted_text = snippet.get("extracted_text", "")

    type_cfg = SNIPPET_TYPE_CONFIG.get(snippet_type, SNIPPET_TYPE_CONFIG["signature"])
    status_cfg = STATUS_BADGES.get(status, STATUS_BADGES["pending"])
    file_path = _resolve_document_path(snippet.get("file_path"))
    doc_link = _build_document_page_link(file_path=file_path, page_num=int(page_num or 1))

    # Wrap the entire card in a container with a border
    with st.container(border=True):
        # Anchor div for CSS selectors to target container and apply premium hovers and shadows
        st.markdown(f'<div class="snippet-card-anchor {status}"></div>', unsafe_allow_html=True)
        
        # ── Row 1: Header (Type tag, Page Number / Link) ──
        # Render type badge and page link in a single HTML flexbox row to ensure perfect vertical alignment
        page_link_html = (
            f'<a href="{doc_link}" target="_blank" style="text-decoration:none; background:#F1F5F9; color:#475569; font-size:0.71rem; font-weight:500; padding:0.2rem 0.5rem; border-radius:4px; border:1px solid #E2E8F0; white-space:nowrap; display:inline-flex; align-items:center; gap:0.2rem;">'
            f'📄 P. {page_num} 🔗</a>'
            if doc_link and file_path else
            f'<span style="background:#F1F5F9; color:#94A3B8; font-size:0.71rem; padding:0.2rem 0.5rem; border-radius:4px; border:1px solid #E2E8F0;">📄 P. {page_num}</span>'
        )
        st.markdown(f"""
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem; margin-top:2px;">
                <span style="
                    background: {type_cfg['bg']};
                    color: {type_cfg['color']};
                    font-size: 0.72rem;
                    font-weight: 600;
                    padding: 0.2rem 0.55rem;
                    border-radius: 4px;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.25rem;
                    white-space: nowrap;
                ">{type_cfg['icon']} {type_cfg['label']}</span>
                {page_link_html}
            </div>
        """, unsafe_allow_html=True)

        # ── Row 2: Render Snippet Image ──
        if snippet_path:
            try:
                img = Image.open(str(snippet_path))
                if compact:
                    thumb = _build_uniform_thumbnail(img, width=480, height=160)
                    st.image(thumb, use_column_width=True)
                else:
                    st.image(img, use_column_width=True)
            except Exception as img_err:
                st.error(f"Could not load snippet image: {img_err}")
        else:
            orig_name = Path(snippet.get("snippet_path", "")).name
            st.warning(f"Snippet file not found: `{orig_name}`")

        # ── Row 3: Metadata Details (Notion-style property grid) ──
        st.markdown(f"""
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #E2E8F0; border-radius: 6px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 0.75rem; margin-top: 0.5rem; margin-bottom: 0.5rem;">
                <tbody>
                    <tr style="border-bottom: 1px solid #E2E8F0;">
                        <td style="padding: 0.4rem 0.6rem; color: #64748B; font-weight: 500; background: #FAFAFB; width: 45%; border-right: 1px solid #E2E8F0;">Status</td>
                        <td style="padding: 0.4rem 0.6rem; text-align: right;">
                            <span style="background: {status_cfg['bg']}; color: {status_cfg['color']}; padding: 0.15rem 0.4rem; border-radius: 4px; font-weight: 500; font-size: 0.7rem;">{status_cfg['label']}</span>
                        </td>
                    </tr>
                    <tr style="border-bottom: 1px solid #E2E8F0;">
                        <td style="padding: 0.4rem 0.6rem; color: #64748B; font-weight: 500; background: #FAFAFB; border-right: 1px solid #E2E8F0;">Role</td>
                        <td style="padding: 0.4rem 0.6rem; color: #1E293B; font-weight: 500; text-align: right;">{reviewer_role}</td>
                    </tr>
                    <tr>
                        <td style="padding: 0.4rem 0.6rem; color: #64748B; font-weight: 500; background: #FAFAFB; border-right: 1px solid #E2E8F0;">Accuracy Impact</td>
                        <td style="padding: 0.4rem 0.6rem; color: #DC2626; font-weight: 600; text-align: right;">-{accuracy_impact:.2f}%</td>
                    </tr>
                </tbody>
            </table>
        """, unsafe_allow_html=True)

        with st.expander("Tesseract Extracted", expanded=False):
            st.code(
                extracted_text if extracted_text.strip() else "(empty)",
                language=None,
            )

        # ── Row 4: Review reason + review metadata for already-reviewed items ──
        if status in ("accepted", "rejected"):
            reason = snippet.get("review_reason", "")
            reviewed_by = snippet.get("reviewed_by", "")
            reviewed_at = snippet.get("reviewed_at", "")
            action_label = "Accepted" if status == "accepted" else "Rejected"
            st.markdown(
                f"""
                <div style="
                    background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px;
                    padding:0.6rem 0.8rem; margin-top:0.3rem; font-size:0.75rem; color:#334155;
                ">
                    <b>{action_label}</b> by <i>{reviewed_by or 'Unknown'}</i>
                    {f'on {reviewed_at[:19]}' if reviewed_at else ''}<br/>
                    {f'<b>Reason:</b> {reason}' if reason else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        # ── Row 5: Action buttons for pending items ──
        type_reasons = ACCEPTANCE_REASONS.get(snippet_type, []) + GENERIC_REASONS
        reason_key = f"reason_{review_id}"
        custom_key = f"custom_reason_{review_id}"

        selected_reason = st.selectbox(
            "Acceptance Reason",
            options=type_reasons,
            key=reason_key,
            label_visibility="collapsed",
            help="Select or type a reason for accepting this visual element",
        )

        # Show custom text field if "Custom reason..." is selected
        custom_reason_text = ""
        if selected_reason == "Custom reason...":
            custom_reason_text = st.text_input(
                "Enter custom reason:",
                key=custom_key,
                placeholder="Describe why this element should be accepted...",
            )

        final_reason = custom_reason_text if selected_reason == "Custom reason..." else selected_reason

        # Action buttons
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            st.markdown('<div class="accept-btn-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if st.button(
                "Accept & Learn",
                key=f"btn_acc_{review_id}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state["active_review_editor"] = review_id
                st.rerun()

        with btn_col2:
            st.markdown('<div class="reject-btn-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if st.button(
                "Reject",
                key=f"btn_rej_{review_id}",
                use_container_width=True,
            ):
                try:
                    update_snippet_review_status(
                        review_id=review_id,
                        status="rejected",
                        review_reason="Rejected — baseline accuracy maintained",
                        reviewed_by="Dashboard User",
                    )
                    st.toast("❌ Rejected — baseline accuracy maintained.", icon="🚫")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to reject snippet: {e}")

        # ── Verification window (rendered inside the card) ──
        if st.session_state.get("active_review_editor") == review_id:
            st.markdown(
                f"""
                <div style="
                    margin-top:0.6rem; border:1px solid #BFDBFE; border-radius:10px;
                    background:#EFF6FF; padding:0.7rem;
                ">
                    <div style="font-size:0.82rem; font-weight:700; color:#1E3A8A; margin-bottom:0.15rem;">
                        📝 Verification Window
                    </div>
                    <div style="font-size:0.74rem; color:#334155;">Verify OCR transcription below, then submit:</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            text_key = f"typed_content_{review_id}"
            default_val = extracted_text if extracted_text else ""
            typed_content = st.text_area(
                "Content in this snippet",
                value=default_val,
                key=text_key,
                placeholder=f"{reviewer_role} types here...",
                height=90,
                label_visibility="collapsed",
            )

            submit_col, cancel_col = st.columns(2)
            with submit_col:
                st.markdown('<div class="submit-accept-btn-marker" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Submit & Accept", key=f"submit_accept_{review_id}", type="primary", use_container_width=True):
                    if not final_reason or final_reason == "Custom reason...":
                        st.warning("⚠️ Please select or enter an acceptance reason before approving.")
                        return
                    typed = (typed_content or "").strip()
                    if not typed:
                        st.warning("⚠️ Please enter the visible content before accepting.")
                        return

                    matched_vector_path = None
                    vector_dir = working_root / "data" / "visual_memory" / snippet["smart_id"]
                    global_vector_dir = working_root / "data" / "visual_memory" / "global"
                    if "visual_memory" in st.session_state and st.session_state.visual_memory and snippet_path:
                        try:
                            candidate_vector = st.session_state.visual_memory.extract_vector(str(snippet_path))
                            if candidate_vector is not None:
                                # Save locally
                                vector_dir.mkdir(parents=True, exist_ok=True)
                                vector_path = vector_dir / f"{review_id}.npy"
                                np.save(str(vector_path), candidate_vector)
                                matched_vector_path = str(vector_path)
                                
                                # Save globally
                                global_vector_dir.mkdir(parents=True, exist_ok=True)
                                global_vector_path = global_vector_dir / f"{review_id}.npy"
                                np.save(str(global_vector_path), candidate_vector)
                        except Exception:
                            pass

                    reason_with_text = f"{final_reason} | Role={reviewer_role} | Verified Content: {typed}"
                    try:
                        update_snippet_review_status(
                            review_id=review_id,
                            status="accepted",
                            feature_vector_path=matched_vector_path,
                            review_reason=reason_with_text,
                            reviewed_by=reviewer_role,
                            transcription_text=typed,
                        )

                        # ── Index reviewed snippet to OpenSearch for searchability ──
                        try:
                            doc_id = snippet.get("file_key") or _get_file_key(snippet["smart_id"])
                            page_num_val = int(page_num or 1)
                            
                            # Create reviewed snippet entry
                            reviewed_entry = {
                                "page": page_num_val,
                                "snippet_type": snippet_type,
                                "verified_content": typed,
                                "reviewer_role": reviewer_role,
                                "acceptance_reason": final_reason,
                                "reviewed_at": datetime.now().isoformat()
                            }
                            
                            # Initialize OpenSearch client and append to reviewed_snippets
                            try:
                                os_client = OpenSearchClient()
                                
                                # Get current document to check for existing reviewed_snippets
                                try:
                                    doc_response = os_client.client.get(index=os_client.index_name, id=doc_id)
                                    existing_reviewed = doc_response['_source'].get('reviewed_snippets', [])
                                except Exception:
                                    # Document doesn't exist yet or can't be retrieved, start fresh
                                    existing_reviewed = []
                                
                                # Append new reviewed snippet
                                reviewed_snippets = existing_reviewed + [reviewed_entry]
                                
                                # Update document with reviewed snippets and combined searchable content
                                combined_content = " ".join([entry["verified_content"] for entry in reviewed_snippets])
                                
                                update_payload = {
                                    "reviewed_snippets": reviewed_snippets,
                                    "reviewed_content": combined_content
                                }
                                
                                os_client.update_document(doc_id=doc_id, updates=update_payload)
                            except Exception as index_error:
                                add_opensearch_retry(
                                    smart_id=snippet["smart_id"],
                                    review_id=review_id,
                                    payload={
                                        "reviewed_snippets": [reviewed_entry],
                                        "reviewed_content": typed
                                    }
                                )
                        except Exception as review_index_error:
                            try:
                                add_opensearch_retry(
                                    smart_id=snippet["smart_id"],
                                    review_id=review_id,
                                    payload={
                                        "reviewed_snippets": [{
                                            "page": int(page_num or 1),
                                            "snippet_type": snippet_type,
                                            "verified_content": typed,
                                            "reviewer_role": reviewer_role,
                                            "acceptance_reason": final_reason,
                                            "reviewed_at": datetime.now().isoformat()
                                        }],
                                        "reviewed_content": typed
                                    }
                                )
                            except Exception:
                                pass

                        auto_count = 0
                        ELIGIBLE_AUTO_TAG_TYPES = {"signature", "stamp", "logo"}
                        if snippet_type in ELIGIBLE_AUTO_TAG_TYPES and "visual_memory" in st.session_state and st.session_state.visual_memory and vector_dir.exists():
                            siblings = get_all_reviews_for_doc(snippet["smart_id"])
                            for sib in siblings:
                                if sib.get("status") != "pending":
                                    continue
                                if sib.get("review_id") == review_id:
                                    continue
                                if str(sib.get("snippet_type") or "") != str(snippet_type):
                                    continue

                                sib_path = _resolve_snippet_path(Path(str(sib.get("snippet_path") or "")), working_root)
                                if not sib_path:
                                    continue

                                try:
                                    is_match, matched_path = st.session_state.visual_memory.match_snippet(
                                        candidate_image_path=str(sib_path),
                                        approved_vectors_dir=str(vector_dir),
                                        threshold=0.90,
                                        candidate_text=sib.get("transcription_text") or sib.get("extracted_text"),
                                    )
                                    if not is_match:
                                        continue

                                    update_snippet_review_status(
                                        review_id=str(sib.get("review_id")),
                                        status="accepted",
                                        feature_vector_path=matched_path,
                                        review_reason=f"Auto-tagged from {review_id} | Role={reviewer_role} | Verified Content: {typed}",
                                        reviewed_by=reviewer_role,
                                        transcription_text=typed,
                                    )
                                    auto_count += 1
                                except Exception:
                                    continue

                        st.session_state.pop("active_review_editor", None)
                        st.toast(f"✅ Accepted by {reviewer_role}. Auto-tagged {auto_count} similar snippet(s).", icon="✨")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to accept snippet: {e}")
            with cancel_col:
                if st.button("Close", key=f"cancel_accept_{review_id}", use_container_width=True):
                    st.session_state.pop("active_review_editor", None)
                    st.rerun()

def _get_file_key(smart_id: str) -> str:
    """Resolve smart_id to file_key by querying file_state in audit.db.
    If not found, fallback to smart_id.
    """
    try:
        from core.config_manager import get_config
        config = get_config()
        db_path = Path(config.paths.working_root) / "audit" / "audit.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT file_key FROM file_state WHERE smart_id = ?", (smart_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
    except Exception:
        pass
    return smart_id

def process_opensearch_retry_queue() -> None:
    """Attempt to flush pending entries in the OpenSearch retry queue."""
    try:
        retries = get_pending_opensearch_retries()
    except Exception:
        return
    if not retries:
        return

    try:
        os_client = OpenSearchClient()
    except Exception:
        return

    for entry in retries:
        entry_id = entry["id"]
        smart_id = entry["smart_id"]
        doc_id = _get_file_key(smart_id)
        attempt_count = entry.get("attempt_count", 0) + 1
        
        try:
            payload = json.loads(entry["payload_json"])
            try:
                doc_response = os_client.client.get(index=os_client.index_name, id=doc_id)
                existing_reviewed = doc_response['_source'].get('reviewed_snippets', [])
            except Exception:
                existing_reviewed = []

            new_snippets = payload.get("reviewed_snippets", [])
            merged_snippets = list(existing_reviewed)
            for ns in new_snippets:
                if not any(es.get("page") == ns.get("page") and es.get("snippet_type") == ns.get("snippet_type") and es.get("verified_content") == ns.get("verified_content") for es in merged_snippets):
                    merged_snippets.append(ns)
            
            combined_content = " ".join([e.get("verified_content", "") for e in merged_snippets])
            
            update_payload = {
                "reviewed_snippets": merged_snippets,
                "reviewed_content": combined_content
            }
            
            os_client.update_document(doc_id=doc_id, updates=update_payload)
            update_opensearch_retry(entry_id, status="completed", attempt_count=attempt_count)
        except Exception:
            new_status = "failed" if attempt_count >= 5 else "pending"
            update_opensearch_retry(entry_id, status=new_status, attempt_count=attempt_count)


def render_snippet_review_tab(config: Any) -> None:
    """Render the production-grade HITL Visual Verification Portal."""
    process_opensearch_retry_queue()

    # ── Page Header & Custom CSS Stylesheet ──
    st.markdown(
        """
        <style>
        /* CSS to style standard Streamlit container with border for premium snippet card */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) {
            border: 1px solid #E2E8F0 !important;
            border-radius: 14px !important;
            background: #FFFFFF !important;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            padding: 1rem !important;
            margin-bottom: 0.5rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor):hover {
            transform: translateY(-3px) !important;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.07) !important;
            border-color: #CBD5E1 !important;
        }

        /* Dim and color-code accepted cards */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor.accepted) {
            border: 1px solid #A7F3D0 !important;
            background-color: #FAFAF9 !important;
            opacity: 0.65 !important;
            box-shadow: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor.accepted):hover {
            opacity: 1.0 !important;
            border-color: #34D399 !important;
        }

        /* Dim and color-code rejected cards */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor.rejected) {
            border: 1px solid #FECACA !important;
            background-color: #FAFAF9 !important;
            opacity: 0.65 !important;
            box-shadow: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor.rejected):hover {
            opacity: 1.0 !important;
            border-color: #F87171 !important;
        }

        /* Crop image framed preview */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) div[data-testid="stImage"] {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px !important;
            overflow: hidden !important;
            padding: 0 !important;
            margin: 0.35rem 0 !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) div[data-testid="stImage"] img {
            width: 100% !important;
            height: auto !important;
            object-fit: contain !important;
            transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        /* Hover zoom micro-animation */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) div[data-testid="stImage"]:hover img {
            transform: scale(1.05) !important;
        }

        /* Hide fullscreen expand button inside card images to prevent Streamlit layout engine crashing/flickering */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) button[title*="fullscreen"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) button[data-testid="stImageFullscreenButton"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) div[data-testid="stImage"] button {
            display: none !important;
        }

        /* Style selectbox input */
        div[data-testid="stSelectbox"] {
            margin-top: 0.25rem !important;
        }

        /* Style the buttons in card columns */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.snippet-card-anchor) button {
            border-radius: 6px !important;
            font-size: 0.75rem !important;
            font-weight: 500 !important;
            padding: 0.3rem 0.6rem !important;
            transition: all 0.2s ease !important;
            box-shadow: none !important;
        }

        /* Notion-style Accept button */
        div[data-testid="column"]:has(div.accept-btn-marker) button,
        div[data-testid="column"]:has(div.submit-accept-btn-marker) button {
            background-color: #e3f2e7 !important;
            border: 1px solid rgba(43, 89, 63, 0.15) !important;
            color: #1e5230 !important;
        }
        div[data-testid="column"]:has(div.accept-btn-marker) button:hover,
        div[data-testid="column"]:has(div.submit-accept-btn-marker) button:hover {
            background-color: #d2ebd9 !important;
            border-color: rgba(43, 89, 63, 0.3) !important;
        }

        /* Notion-style Reject button */
        div[data-testid="column"]:has(div.reject-btn-marker) button {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            color: #dc2626 !important;
        }
        div[data-testid="column"]:has(div.reject-btn-marker) button:hover {
            background-color: #fdebeb !important;
            border-color: #f8cdcd !important;
            color: #b32b2b !important;
        }
        </style>
        
        <div style="margin-bottom:0.5rem;">
            <h3 style="margin:0; color:#1E293B;">🔍 Visual Verification Portal</h3>
            <p style="margin:0.2rem 0 0 0; font-size:0.85rem; color:#64748B;">
                Review extracted visual elements (signatures, stamps, logos) to improve document accuracy.
                Accepted elements are memorized by the CNN engine and auto-approved in future scans.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Paths & initialization ──
    working_root = Path(config.paths.working_root)

    # Clear any stale viewer state from older builds to avoid unintended document auto-open.
    st.session_state.pop("review_viewer_target", None)

    if "visual_memory" not in st.session_state:
        try:
            st.session_state.visual_memory = VisualMemoryEngine()
        except Exception:
            st.session_state.visual_memory = None

    # ── Fetch documents with reviews ──
    docs = get_docs_with_reviews()
    if not docs:
        st.info("📭 No documents with visual review elements found. Process documents first to generate snippet reviews.")
        return

    # ── Document Selector ──
    st.markdown("---")
    doc_options = {}
    smart_id_to_label = {}
    for doc in docs:
        fname = doc.get("file_name", "Unknown")
        sid = doc.get("smart_id", "")
        pending = doc.get("pending_count", 0)
        label = f"{'🔴 ' if pending > 0 else '🟢 '}{fname}  —  {pending} pending | {doc.get('accepted_count', 0)} accepted | {doc.get('rejected_count', 0)} rejected"
        doc_options[label] = doc
        smart_id_to_label[sid] = label

    option_keys = list(doc_options.keys())

    # Restore selection from session state so reruns don't jump to index 0
    saved_smart_id = st.session_state.get("review_selected_smart_id", "")
    saved_label = smart_id_to_label.get(saved_smart_id, "")
    default_index = option_keys.index(saved_label) if saved_label in option_keys else 0

    selected_label = st.selectbox(
        "📂 Select Document to Review",
        options=option_keys,
        index=default_index,
        help="Documents with pending reviews are marked with 🔴",
    )
    selected_doc = doc_options[selected_label]
    selected_smart_id = selected_doc["smart_id"]

    # Reset sticky filters when switching documents so old role/status filters
    # do not silently hide valid snippets (common cause of seeing only logos/stamps).
    prev_doc = st.session_state.get("review_prev_selected_smart_id")
    if prev_doc != selected_smart_id:
        st.session_state["snippet_status_filter"] = "All Statuses"
        st.session_state["snippet_role_filter"] = "All Roles"
        st.session_state["review_prev_selected_smart_id"] = selected_smart_id

    st.session_state["review_selected_smart_id"] = selected_smart_id

    # ── Per-Document Dynamic KPI Metrics ──
    baseline_acc = selected_doc.get("extraction_accuracy") or 0.0
    enhanced_acc = selected_doc.get("enhanced_accuracy") or baseline_acc
    pending_count = selected_doc.get("pending_count", 0)
    accepted_count = selected_doc.get("accepted_count", 0)
    rejected_count = selected_doc.get("rejected_count", 0)
    total_snippets = selected_doc.get("total_snippets", 0)
    pending_impact = selected_doc.get("pending_impact") or 0.0
    uplift = max(0, enhanced_acc - baseline_acc)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        _render_metric_card(
            "Baseline Accuracy", f"{baseline_acc:.1f}%",
            "Raw OCR extraction", "#6366F1", "#EEF2FF", "#4338CA", "📊",
        )
    with m2:
        _render_metric_card(
            "Enhanced Accuracy", f"{enhanced_acc:.1f}%",
            f"+{uplift:.1f}% uplift" if uplift > 0 else "No uplift yet",
            "#059669", "#ECFDF5", "#047857", "📈",
        )
    with m3:
        _render_metric_card(
            "Pending Review", f"{pending_count}",
            f"−{pending_impact:.1f}% potential impact",
            "#F59E0B", "#FFFBEB", "#B45309", "⏳",
        )
    with m4:
        _render_metric_card(
            "Accepted", f"{accepted_count}",
            "Templates memorized",
            "#059669", "#ECFDF5", "#047857", "✅",
        )
    with m5:
        _render_metric_card(
            "Rejected", f"{rejected_count}",
            "Accuracy penalty kept",
            "#DC2626", "#FEF2F2", "#991B1B", "❌",
        )

    # ── Document info bar ──
    st.markdown(
        f"""
        <div style="
            background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;
            padding:0.6rem 1rem; margin:0.75rem 0; font-size:0.78rem; color:#475569;
        ">
            <b>File:</b> {selected_doc.get('file_name', 'Unknown')} &nbsp;|&nbsp;
            <b>Smart ID:</b> <code>{selected_smart_id}</code> &nbsp;|&nbsp;
            <b>Pipeline:</b> {selected_doc.get('pipeline_type', 'N/A')} &nbsp;|&nbsp;
            <b>Status:</b> {selected_doc.get('approval_status', 'N/A')}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sub-tabs: Review Queue | Activity Log | Storage ──
    review_subtab, log_subtab, storage_subtab = st.tabs([
        "📋 Review Queue", "📜 Activity Log", "💾 Storage Management"
    ])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1: Review Queue
    # ════════════════════════════════════════════════════════════════════════
    with review_subtab:
        all_snippets = get_all_reviews_for_doc(selected_smart_id)
        if not all_snippets:
            st.info("No visual elements found for this document.")
            return

        # ── Status & Role filters ──
        # Dynamically build role options from config + actual DB roles so the
        # filter never silently hides snippets with unrecognised roles.
        reviewer_roles_cfg = dict(getattr(config.ocr, "reviewer_roles", {}) or {})
        known_roles = set(reviewer_roles_cfg.values())
        actual_roles = {s.get("reviewer_role", "") for s in all_snippets if s.get("reviewer_role")}
        all_roles = sorted(known_roles | actual_roles)

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All Statuses", "Pending", "Accepted", "Rejected"],
                index=0,
                key="snippet_status_filter",
            )
        with filter_col2:
            role_filter = st.selectbox(
                "Filter by Reviewer Role",
                ["All Roles"] + all_roles,
                index=0,
                key="snippet_role_filter",
                help="Roles are loaded dynamically from your config and the document's snippets.",
            )

        # Apply filters
        filtered = all_snippets
        if status_filter != "All Statuses":
            status_map = {"Pending": "pending", "Accepted": "accepted", "Rejected": "rejected"}
            filtered = [s for s in filtered if s.get("status") == status_map.get(status_filter, "")]
        if role_filter != "All Roles":
            filtered = [s for s in filtered if s.get("reviewer_role") == role_filter]

        # Config-driven strict visual policy (same semantics as OCR worker).
        preprocessing_cfg = dict(getattr(config.ocr, "preprocessing", {}) or {})

        # Optional static per-file overrides for known PDFs.
        selected_file_path = str(selected_doc.get("file_path") or "")
        normalized_path = selected_file_path.replace("\\", "/").lower()
        overrides = preprocessing_cfg.get("visual_pdf_overrides") or []
        if isinstance(overrides, list) and normalized_path:
            for item in overrides:
                if not isinstance(item, dict):
                    continue
                match_sub = str(item.get("match_substring", "") or "").strip().lower()
                if match_sub and match_sub in normalized_path:
                    for key in (
                        "visual_allowed_types",
                        "signature_min_impact",
                        "logo_min_impact",
                        "stamp_min_impact",
                        "text_anomaly_min_impact",
                        "max_per_page_per_type",
                        "review_keep_signatures",
                    ):
                        if key in item:
                            preprocessing_cfg[key] = item[key]
                    break

        # For matched static overrides, keep signature snippets visible in review
        # even if OCR/text heuristics think they are text-like.
        keep_signatures_visible = bool(preprocessing_cfg.get("review_keep_signatures", False))
        allowed_types = {
            str(t).strip().lower()
            for t in (preprocessing_cfg.get("visual_allowed_types") or [])
            if str(t).strip()
        }
        if keep_signatures_visible and allowed_types:
            # Legacy/manual signature boxes may have been saved as text_anomaly
            # before force-keep type pinning. Include them in review visibility.
            allowed_types.add("text_anomaly")
        if allowed_types:
            filtered = [
                s for s in filtered
                if str((s or {}).get("snippet_type", "")).lower() in allowed_types
                or str((s or {}).get("snippet_type", "")).lower() == "faded_text"
            ]

        min_impact_by_type = {
            "signature": float(preprocessing_cfg.get("signature_min_impact", 0.0) or 0.0),
            "logo": float(preprocessing_cfg.get("logo_min_impact", 0.0) or 0.0),
            "stamp": float(preprocessing_cfg.get("stamp_min_impact", 0.0) or 0.0),
            "handwritten": float(preprocessing_cfg.get("handwritten_min_impact", 0.0) or 0.0),
            "text_anomaly": float(preprocessing_cfg.get("text_anomaly_min_impact", 0.0) or 0.0),
            "faded_text": float(preprocessing_cfg.get("faded_text_min_impact", 0.0) or 0.0),
        }
        filtered = [
            s for s in filtered
            if float((s or {}).get("accuracy_impact", 0.0) or 0.0)
            >= min_impact_by_type.get(str((s or {}).get("snippet_type", "")).lower(), 0.0)
        ]

        max_per_type_cfg = preprocessing_cfg.get("max_per_page_per_type") or {}
        if isinstance(max_per_type_cfg, dict) and filtered:
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for s in filtered:
                t = str((s or {}).get("snippet_type", "")).lower()
                page = int((s or {}).get("page_num", 0) or 0)
                key = f"{t}:{page}"
                grouped.setdefault(key, []).append(s)

            topk: List[Dict[str, Any]] = []
            for key, items in grouped.items():
                s_type = key.split(":", 1)[0]
                sorted_items = sorted(
                    items,
                    key=lambda it: float((it or {}).get("accuracy_impact", 0.0) or 0.0),
                    reverse=True,
                )
                try:
                    limit = int(max_per_type_cfg.get(s_type, 0) or 0)
                except Exception:
                    limit = 0
                if limit > 0:
                    sorted_items = sorted_items[:limit]
                topk.extend(sorted_items)
            filtered = topk

        # Auto-hide ONLY truly blank/zero-ink noise snippets.
        # Do NOT suppress based on printed-font or text-like heuristics — those
        # were causing legitimate stamps, handwriting, and signatures to disappear.
        hidden_noise_count = 0
        visible_snippets = []
        for snippet in filtered:
            snippet_type = str((snippet or {}).get("snippet_type") or "").lower()

            # Always keep non-pending snippets (accepted/rejected) in full view
            if snippet.get("status") != "pending":
                visible_snippets.append(snippet)
                continue

            # Force-keep signatures when the override flag is set
            if keep_signatures_visible and snippet_type == "signature":
                visible_snippets.append(snippet)
                continue

            # Only suppress truly blank/zero-ink blobs
            if _is_obvious_noise_review_snippet(snippet, working_root):
                hidden_noise_count += 1
                continue

            visible_snippets.append(snippet)
        filtered = visible_snippets

        # Sort: pending first (urgent), then by page number for readability
        def sort_priority(s):
            status_order = {"pending": 0, "accepted": 1, "rejected": 2}
            return (status_order.get(s.get("status"), 3), s.get("page_num", 0))
        filtered = sorted(filtered, key=sort_priority)

        if hidden_noise_count > 0:
            st.caption(f"Auto-hidden {hidden_noise_count} blank/zero-ink noise snippets from review queue.")

        view_tabs = st.tabs(["Waterfall Analysis", "Page Composition"])
        with view_tabs[0]:
            st.markdown("<div style='margin:0.35rem 0 0.5rem 0;'><b>Accuracy Impact Waterfall</b></div>", unsafe_allow_html=True)
            _render_accuracy_waterfall_chart(filtered, selected_doc)
        with view_tabs[1]:
            _render_page_composition_bar(selected_doc)

        if not filtered:
            st.info(f"No snippets matching filters: Status={status_filter}, Role={role_filter} ({len(all_snippets)} total available)")
        else:
            st.markdown(
                f"<p style='font-size:0.82rem; color:#64748B; margin:0.5rem 0;'>"
                f"Showing <b>{len(filtered)}</b> of <b>{len(all_snippets)}</b> elements</p>",
                unsafe_allow_html=True,
            )

            # ── Render snippet cards in compact 3-column tile layout ──
            tiles_per_row = 3
            for row_start in range(0, len(filtered), tiles_per_row):
                cols = st.columns(tiles_per_row)
                for col_idx in range(tiles_per_row):
                    snippet_idx = row_start + col_idx
                    if snippet_idx >= len(filtered):
                        continue
                    with cols[col_idx]:
                        _render_snippet_card(filtered[snippet_idx], working_root, snippet_idx, compact=True)

        # Render Suppressed Items panel
        suppressions = get_snippet_suppressions(selected_doc.get("smart_id"))
        st.markdown("<div style='margin:1.0rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)
        with st.expander(f"🔇 Suppressed Items ({len(suppressions)})", expanded=False):
            if not suppressions:
                st.write("No items were suppressed for this document.")
            else:
                st.markdown(
                    """
                    <div style="font-size:0.82rem; color:#64748B; margin-bottom:0.75rem;">
                        These items were automatically filtered out during processing based on configured heuristics.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                suppressed_data = []
                for s in suppressions:
                    suppressed_data.append({
                        "Page": f"Page {s.get('page_num')}",
                        "Type": str(s.get("snippet_type")).title(),
                        "Reason": str(s.get("suppressed_by")).replace("_", " ").title(),
                        "Impact": f"{s.get('accuracy_impact', 0.0):.2f}%",
                        "Bbox": s.get("bbox_json"),
                        "Time": s.get("suppressed_at")[:19].replace("T", " "),
                    })
                st.table(suppressed_data)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2: Activity Log
    # ════════════════════════════════════════════════════════════════════════
    with log_subtab:
        st.markdown(
            """
            <div style="margin-bottom:0.5rem;">
                <h4 style="margin:0; color:#1E293B;">📜 Review Activity History</h4>
                <p style="margin:0.2rem 0; font-size:0.78rem; color:#64748B;">
                    Chronological audit trail of all review decisions for this document.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        activity_log = get_review_activity_log(smart_id=selected_smart_id, limit=50)

        if not activity_log:
            st.info("No review activity recorded yet for this document. Accept or reject snippets to create entries.")
        else:
            for entry in activity_log:
                action = entry.get("action", "")
                action_icon = "✅" if action == "accepted" else ("❌" if action == "rejected" else "🔄")
                action_color = "#059669" if action == "accepted" else ("#DC2626" if action == "rejected" else "#6B7280")
                ts = entry.get("timestamp", "")[:19].replace("T", " ")
                acc_before = entry.get("accuracy_before", 0) or 0
                acc_after = entry.get("accuracy_after", 0) or 0
                delta = acc_after - acc_before

                st.markdown(
                    f"""
                    <div style="
                        border-left: 3px solid {action_color};
                        padding: 0.6rem 0.8rem;
                        margin-bottom: 0.5rem;
                        background: #FAFAFA;
                        border-radius: 0 6px 6px 0;
                        font-size: 0.78rem;
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span>
                                <b style="color:{action_color};">{action_icon} {action.title()}</b>
                                — <i>{entry.get('snippet_type', '')}</i>
                                by <b>{entry.get('actor', 'Unknown')}</b>
                            </span>
                            <span style="color:#9CA3AF; font-size:0.72rem;">{ts}</span>
                        </div>
                        <div style="margin-top:0.25rem; color:#4B5563;">
                            {f'<b>Reason:</b> {entry.get("reason", "")}' if entry.get("reason") else ''}
                        </div>
                        <div style="margin-top:0.15rem; color:#6B7280; font-size:0.72rem;">
                            Accuracy: {acc_before:.1f}% → {acc_after:.1f}%
                            <span style="color:{'#059669' if delta >= 0 else '#DC2626'}; font-weight:600;">
                                ({'+' if delta >= 0 else ''}{delta:.1f}%)
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if action in ("accepted", "rejected"):
                    btn_key = f"revert_btn_{entry.get('id')}_{entry.get('review_id')}"
                    if st.button("↩ Revert Decision", key=btn_key, use_container_width=False):
                        try:
                            revert_snippet_review(entry.get("review_id"))
                            
                            # ── Sync Revert to OpenSearch ──
                            try:
                                doc_id = entry.get("smart_id")
                                if doc_id:
                                    os_doc_id = _get_file_key(doc_id)
                                    os_client = OpenSearchClient()
                                    remaining_snippets = get_all_reviews_for_doc(doc_id)
                                    accepted_list = []
                                    for r in remaining_snippets:
                                        if r.get("status") == "accepted":
                                            accepted_list.append({
                                                "page": int(r.get("page_num") or 1),
                                                "snippet_type": r.get("snippet_type"),
                                                "verified_content": r.get("transcription_text") or "",
                                                "reviewer_role": r.get("reviewed_by") or "Dashboard User",
                                                "acceptance_reason": r.get("review_reason") or "",
                                                "reviewed_at": r.get("reviewed_at") or datetime.now().isoformat()
                                            })
                                    combined_content = " ".join([item["verified_content"] for item in accepted_list])
                                    update_payload = {
                                        "reviewed_snippets": accepted_list,
                                        "reviewed_content": combined_content
                                    }
                                    os_client.update_document(doc_id=os_doc_id, updates=update_payload)
                            except Exception as os_revert_err:
                                try:
                                    doc_id = entry.get("smart_id")
                                    if doc_id:
                                        add_opensearch_retry(
                                            smart_id=doc_id,
                                            review_id=entry.get("review_id"),
                                            payload={
                                                "reviewed_snippets": [],
                                                "reviewed_content": ""
                                            }
                                        )
                                except Exception:
                                    pass
                            
                            st.toast(f"Successfully reverted decision for {entry.get('review_id')}.", icon="↩")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to revert decision: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3: Storage Management
    # ════════════════════════════════════════════════════════════════════════
    with storage_subtab:
        st.markdown(
            """
            <div style="margin-bottom:0.5rem;">
                <h4 style="margin:0; color:#1E293B;">💾 Snippet Storage Management</h4>
                <p style="margin:0.2rem 0; font-size:0.78rem; color:#64748B;">
                    Monitor and manage disk usage from cropped visual snippet files.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        try:
            stats = get_snippet_storage_stats()
            total_mb = stats.get("total_size_mb", 0)
            per_doc = stats.get("per_doc", {})

            # Summary metrics
            s1, s2, s3 = st.columns(3)
            with s1:
                _render_metric_card(
                    "Total Disk Usage",
                    f"{total_mb:.2f} MB",
                    f"{sum(d.get('file_count', 0) for d in per_doc.values())} files on disk",
                    "#6366F1", "#EEF2FF", "#4338CA", "💿",
                )
            with s2:
                _render_metric_card(
                    "Documents Tracked",
                    str(len(per_doc)),
                    "With visual snippets",
                    "#0891B2", "#ECFEFF", "#155E75", "📁",
                )
            with s3:
                total_accepted = sum(d.get("accepted", 0) for d in per_doc.values())
                _render_metric_card(
                    "CNN Templates Saved",
                    str(total_accepted),
                    "Feature vectors (.npy) preserved",
                    "#059669", "#ECFDF5", "#047857", "🧠",
                )

            # Per-document breakdown table
            if per_doc:
                st.markdown("#### Per-Document Breakdown")
                rows = []
                for sid, info in per_doc.items():
                    rows.append({
                        "Document": info.get("file_name", sid),
                        "Files": info.get("file_count", 0),
                        "Size": _format_file_size(info.get("total_size", 0)),
                        "Pending": info.get("pending", 0),
                        "Accepted": info.get("accepted", 0),
                        "Rejected": info.get("rejected", 0),
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)

            # Purge controls
            st.markdown("---")
            st.markdown("#### 🗑️ Purge Old Snippet Files")
            st.caption(
                "Remove crop image files from disk for snippets that have been accepted or rejected. "
                "CNN feature vectors (.npy) are always preserved — only the large PNG crop files are deleted."
            )
            purge_days = st.number_input(
                "Delete snippets older than (days):",
                min_value=1,
                max_value=365,
                value=30,
                key="purge_days_input",
            )
            if st.button("🗑️ Purge Old Snippets", key="btn_purge_snippets", type="secondary"):
                result = purge_old_snippets(older_than_days=purge_days)
                freed = result.get("bytes_freed", 0)
                count = result.get("purged_count", 0)
                if count > 0:
                    st.success(f"✅ Purged {count} files, freed {_format_file_size(freed)}")
                else:
                    st.info("No snippet files older than the specified threshold found.")

        except Exception as e:
            st.warning(f"Could not load storage statistics: {e}")
