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
import mimetypes
mimetypes.add_type('application/pdf', '.pdf')
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
}

STATUS_BADGES = {
    "pending": {"color": "#F59E0B", "bg": "#FFFBEB", "label": "⏳ Pending Review"},
    "accepted": {"color": "#059669", "bg": "#ECFDF5", "label": "✅ Accepted"},
    "rejected": {"color": "#DC2626", "bg": "#FEF2F2", "label": "❌ Rejected"},
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


def _resolve_snippet_path(snippet_path: Path, working_root: Path) -> Path:
    """Resolve legacy snippet paths into current workspace data path."""
    if snippet_path.exists():
        return snippet_path

    normalized = str(snippet_path).replace("\\", "/")
    marker = "/data/review_snippets/"
    if marker in normalized:
        relative_part = normalized.split(marker, 1)[1]
        mapped = working_root.parent / "data" / "review_snippets" / Path(relative_part)
        if mapped.exists():
            return mapped

    return snippet_path


def _build_uniform_thumbnail(img: Image.Image, width: int = 520, height: int = 280) -> Image.Image:
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


def _build_document_page_link(file_path: str, page_num: int) -> Optional[str]:
    """Build file:// URL with page hint for local PDF files."""
    if not file_path:
        return None
    try:
        p = Path(file_path)
        if not p.exists():
            return None
        uri = p.resolve().as_uri()
        if p.suffix.lower() == ".pdf":
            return f"{uri}#page={max(1, int(page_num or 1))}"
        return uri
    except Exception:
        return None


def _prepare_static_document(resolved_path: str) -> Optional[str]:
    """Copy resolved document path to Streamlit's static directory so it can be opened via browser URL.
    
    Returns the relative URL path to be opened by the browser.
    """
    if not resolved_path:
        return None
    try:
        p = Path(resolved_path)
        if not p.exists():
            return None
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(exist_ok=True)
        dest = static_dir / p.name
        # Copy file if it doesn't exist or is outdated
        if not dest.exists() or dest.stat().st_mtime < p.stat().st_mtime:
            import shutil
            shutil.copy(resolved_path, dest)
            print(f"[DEBUG] Copied {resolved_path} to static/ directory.")
        # Return the Streamlit static URL (relative)
        return f"/app/static/{p.name}"
    except Exception as e:
        print(f"[DEBUG] Error preparing static document: {e}")
        return None


def _open_source_document(file_path: Any, page_num: Any) -> None:
    """Open file with system default application to specific page."""
    import logging
    logger = logging.getLogger("review_tab")
    
    page_num_int = int(page_num or 1)
    file_path_str = str(file_path) if file_path else ""
    
    msg = f"Request to open document: file_path='{file_path_str}', page_num={page_num_int}"
    print(f"[DEBUG] {msg}")
    logger.info(msg)
    st.toast(f"Opening Page {page_num_int}...")
    
    if not file_path_str:
        st.error("Cannot open document: No file path provided.")
        return
        
    resolved_path = _resolve_document_path(file_path_str)
    if not resolved_path or not os.path.exists(resolved_path):
        err_msg = f"Resolved file path does not exist on disk: '{resolved_path}'"
        print(f"[DEBUG] {err_msg}")
        logger.error(err_msg)
        st.error(f"Cannot open document: File not found on host disk. Resolved path: '{resolved_path}'")
        return
        
    uri = _build_document_page_link(resolved_path, page_num_int)
    print(f"[DEBUG] Resolved path: {resolved_path}, URI: {uri}")
    
    try:
        if os.name == 'nt':  # Windows
            # os.startfile silently fails when Streamlit runs in a non-interactive session.
            # Use a temporary Scheduled Task to launch the file in the user's interactive desktop.
            import tempfile
            import time

            temp_dir = tempfile.gettempdir()
            ts = int(time.time() * 1000)
            bat_name = f"open_pdf_{ts}.bat"
            bat_path = os.path.join(temp_dir, bat_name)
            task_name = f"OpenPDFTask_{ts}"

            # Always open the resolved local file path with the default app.
            # Windows PDF readers jump to the correct page when opened; we pass the
            # raw file path so it opens in the native desktop application, not a browser.
            with open(bat_path, "w") as _bf:
                _bf.write("@echo off\n")
                _bf.write(f'start "" "{resolved_path}"\n')

            print(f"[DEBUG] Created temporary batch file: {bat_path}")

            try:
                # 1. Create scheduled task
                subprocess.run(
                    ["schtasks", "/create", "/tn", task_name, "/tr",
                     f'"{bat_path}"', "/sc", "once", "/st", "12:00", "/f"],
                    capture_output=True, text=True, check=True
                )
                print(f"[DEBUG] Created task: {task_name}")

                # 2. Run task immediately
                subprocess.run(
                    ["schtasks", "/run", "/tn", task_name],
                    capture_output=True, text=True, check=True
                )
                print(f"[DEBUG] Executed task: {task_name}")

                time.sleep(0.5)
            except Exception as task_err:
                print(f"[DEBUG] Scheduled task execution failed: {task_err}")
                try:
                    subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True)
                except Exception:
                    pass
            else:
                # 3. Cleanup task only if creation+run succeeded
                try:
                    subprocess.run(
                        ["schtasks", "/delete", "/tn", task_name, "/f"],
                        capture_output=True, text=True
                    )
                    print(f"[DEBUG] Deleted task: {task_name}")
                except Exception:
                    pass
            finally:
                try:
                    if os.path.exists(bat_path):
                        os.remove(bat_path)
                        print(f"[DEBUG] Cleaned up batch file: {bat_path}")
                except Exception:
                    pass
        else:
            # macOS / Linux
            import webbrowser
            if uri:
                try:
                    print(f"[DEBUG] Attempting launch via webbrowser.open: {uri}")
                    if webbrowser.open(uri):
                        print("[DEBUG] webbrowser.open succeeded.")
                        return
                except Exception as e:
                    print(f"[DEBUG] webbrowser.open exception: {e}")
                    
            try:
                system_name = os.uname().sysname
            except Exception:
                system_name = ""
                
            if system_name == 'Darwin':  # macOS
                file_uri = Path(resolved_path).resolve().as_uri()
                if page_num_int > 1:
                    file_uri += f'#page={page_num_int}'
                print(f"[DEBUG] Attempting launch via mac open: {file_uri}")
                subprocess.run(['open', file_uri], check=True)
                return
            else:  # Linux
                file_uri = Path(resolved_path).resolve().as_uri()
                if page_num_int > 1:
                    file_uri += f'#page={page_num_int}'
                print(f"[DEBUG] Attempting launch via xdg-open: {file_uri}")
                subprocess.run(['xdg-open', file_uri], check=True)
                return
    except Exception as e:
        print(f"[DEBUG] Failure during document open process: {e}")
        logger.exception("Failed to open source document")
        st.error(f"Failed to open file: {e}")



def _render_accuracy_waterfall_chart(snippets: List[Dict[str, Any]], selected_doc: Dict[str, Any]) -> None:
    """Render accuracy waterfall chart showing true page composition corrected by reviews."""
    smart_id = selected_doc.get("smart_id")
    breakdown = get_page_segmentation_breakdown(smart_id)
    
    # Calculate average page composition percentages from database
    avg_clean = 0.0
    avg_whitespace = 0.0
    avg_faded = 0.0
    avg_logo = 0.0
    avg_stamp = 0.0
    avg_handwritten = 0.0
    avg_noise = 0.0
    
    if breakdown:
        num_pages = len(breakdown)
        avg_clean = sum(float(p.get("clean_text_pct") or 0.0) for p in breakdown) / num_pages
        avg_whitespace = sum(float(p.get("whitespace_pct") or 0.0) for p in breakdown) / num_pages
        avg_faded = sum(float(p.get("faded_text_pct") or 0.0) for p in breakdown) / num_pages
        avg_logo = sum(float(p.get("logo_pct") or 0.0) for p in breakdown) / num_pages
        avg_stamp = sum(float(p.get("stamp_pct") or 0.0) for p in breakdown) / num_pages
        avg_handwritten = sum(float(p.get("handwritten_pct") or 0.0) for p in breakdown) / num_pages
        avg_noise = sum(float(p.get("noise_pct") or 0.0) for p in breakdown) / num_pages
    else:
        # Fallback to general baseline if database records are empty
        baseline_acc = float(selected_doc.get("extraction_accuracy") or 0.0)
        avg_clean = max(1.0, baseline_acc)
        avg_whitespace = max(1.0, 100.0 - avg_clean)
        
    # Calculate counts and impact sums dynamically from snippets (all reviews for the doc)
    pending_counts = {}
    pending_impacts = {}
    accepted_impact_total = 0.0
    doc_snippet_types = set()
    
    for s in snippets:
        t = str(s.get("snippet_type") or "").strip().lower()
        doc_snippet_types.add(t)
        status = s.get("status", "pending")
        impact = max(0.0, float(s.get("accuracy_impact") or 0.0))
        
        if status == "pending":
            pending_counts[t] = pending_counts.get(t, 0) + 1
            pending_impacts[t] = pending_impacts.get(t, 0.0) + impact
        elif status == "accepted":
            accepted_impact_total += impact

    # Mapping display configuration for segments
    segment_cfg = {
        "clean": {"label": "Extractable Text", "value": avg_clean, "color": "#10B981"},
        "whitespace": {"label": "Whitespace", "value": avg_whitespace, "color": "#F1F5F9", "border": "#CBD5E1"},
        "faded": {"label": "Faded Text", "value": avg_faded, "color": "#3B82F6", "snippet_key": "faded_text"},
        "logo": {"label": "Logo/Image", "value": avg_logo, "color": "#8B5CF6", "snippet_key": "logo"},
        "stamp": {"label": "Stamp", "value": avg_stamp, "color": "#F59E0B", "snippet_key": "stamp"},
        "handwritten": {
            "label": "Handwritten",
            "value": avg_handwritten,
            "color": "#EC4899",
            "snippet_key": "handwritten",
            "extra_snippet_key": "signature"
        },
        "noise": {"label": "Noise", "value": avg_noise, "color": "#64748B", "snippet_key": "text_anomaly"}, 
    }

    # Add verified (accepted) snippet impacts to the baseline Extractable Text bar
    segment_cfg["clean"]["value"] += accepted_impact_total

    # For categories present as snippets in the document, use their pending snippet impact sum.
    # For categories not in the snippet queue, keep the database composition averages.
    for key, cfg in segment_cfg.items():
        if key == "clean" or key == "whitespace":
            continue
            
        has_snippets = False
        if "snippet_key" in cfg and cfg["snippet_key"] in doc_snippet_types:
            has_snippets = True
        if "extra_snippet_key" in cfg and cfg["extra_snippet_key"] in doc_snippet_types:
            has_snippets = True
            
        if has_snippets:
            # Value is exactly the sum of impacts of remaining pending elements in this category
            snippet_pending_sum = 0.0
            if "snippet_key" in cfg:
                snippet_pending_sum += pending_impacts.get(cfg["snippet_key"], 0.0)
            if "extra_snippet_key" in cfg:
                snippet_pending_sum += pending_impacts.get(cfg["extra_snippet_key"], 0.0)
            cfg["value"] = snippet_pending_sum

    # Normalize all segments to sum to exactly 100.0% dynamically
    total_val_sum = sum(cfg["value"] for cfg in segment_cfg.values())
    if total_val_sum > 0:
        scale = 100.0 / total_val_sum
        for cfg in segment_cfg.values():
            cfg["value"] *= scale
    else:
        segment_cfg["whitespace"]["value"] = 100.0

    # Order of presentation in waterfall
    order = ["clean", "whitespace", "faded", "logo", "stamp", "handwritten", "noise"]
    
    bars = []
    running_bottom = 0.0
    
    for key in order:
        cfg = segment_cfg[key]
        val = cfg["value"]
        if val <= 0.001:
            continue
            
        # Determine displaying label with snippet counts
        lbl = cfg["label"]
        count = 0
        if "snippet_key" in cfg:
            count += pending_counts.get(cfg["snippet_key"], 0)
        if "extra_snippet_key" in cfg:
            count += pending_counts.get(cfg["extra_snippet_key"], 0)
            
        if count > 0:
            lbl = f"{lbl} ({count})"
            
        border_color = cfg["color"]
        fill_color = cfg["color"]
        
        bars.append({
            "label": lbl,
            "value": val,
            "bottom": running_bottom,
            "color": border_color,
            "fill_color": fill_color,
            "text": f"{val:.2f}%",
            "style": "solid" if key != "whitespace" else "whitespace"
        })
        running_bottom = min(100.0, running_bottom + val)
        
    # Final Total bar representing 100% composition
    bars.append({
        "label": "Total",
        "value": 100.0,
        "bottom": 0.0,
        "color": "#2563EB",
        "fill_color": "#DBEAFE",
        "text": "100%",
        "style": "dotted"
    })

    left_pad = 40
    right_pad = 40
    chart_h = 240
    plot_top = 20
    plot_h = chart_h - 80

    # Ensure dynamic slots fit screen space and don't overflow
    bar_slot = max(120, int(800 / max(1, len(bars))))
    bar_width = int(bar_slot * 0.35)
    svg_width = left_pad + bar_slot * len(bars) + right_pad

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
        elif bar["style"] == "whitespace":
            bar_rects.append(
                f"<rect x='{x}' y='{y:.1f}' width='{bar_width}' height='{px_h:.1f}' rx='6' "
                f"fill='{bar['fill_color']}' stroke='#CBD5E1' stroke-width='1'></rect>"
            )
        else:
            bar_rects.append(
                f"<rect x='{x}' y='{y:.1f}' width='{bar_width}' height='{px_h:.1f}' rx='6' "
                f"fill='{bar['fill_color']}'></rect>"
            )

        pct_labels.append(
            f"<text x='{x + bar_width/2:.1f}' y='{max(12, y - 8):.1f}' text-anchor='middle' font-size='11' font-weight='700' fill='#0F172A'>{bar['text']}</text>"
        )
        x_labels.append(
            f"<text x='{x + bar_width/2:.1f}' y='{chart_h - 28}' text-anchor='middle' font-size='11' font-weight='700' fill='#111827'>{bar['label']}</text>"
        )
        
        border_dashed = " border:1px dashed #2563EB;" if bar["style"] == "dotted" else ""
        border_solid = " border:1px solid #CBD5E1;" if bar["style"] == "whitespace" else ""
        legend_items.append(
            f"<span style='display:inline-flex; align-items:center; gap:6px; margin-right:14px; font-size:12px; color:#334155;'>"
            f"<span style='display:inline-block; width:10px; height:10px; border-radius:2px; background:{bar['color']};{border_dashed}{border_solid}'></span>"
            f"{bar['label']}</span>"
        )

    svg = f"""
    <div style='border:1px solid #E5E7EB; border-radius:10px; background:#FFFFFF; padding:8px 10px 10px 10px;'>
      <svg width='{svg_width}' height='{chart_h}' viewBox='0 0 {svg_width} {chart_h}'>
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
    components.html(svg, height=chart_h + 75, width=svg_width + 10, scrolling=False)


def _render_page_composition_bar(selected_doc: Dict[str, Any]) -> None:
    smart_id = selected_doc.get("smart_id")
    if not smart_id:
        st.warning("No document selected.")
        return

    breakdown = get_page_segmentation_breakdown(smart_id)
    if not breakdown:
        st.info("No page segmentation breakdown available for this document.")
        return

    segment_cfg = {
        "clean": {"label": "Clean Text", "color": "#10B981"},
        "faded": {"label": "Faded Text", "color": "#3B82F6"},
        "logo": {"label": "Logo/Image", "color": "#8B5CF6"},
        "stamp": {"label": "Stamp", "color": "#F59E0B"},
        "handwritten": {"label": "Handwritten", "color": "#EC4899"},
        "whitespace": {"label": "Whitespace", "color": "#F1F5F9", "border": "#CBD5E1"},
        "noise": {"label": "Noise", "color": "#64748B"},
    }

    legend_html_parts = []
    for key, cfg in segment_cfg.items():
        border_style = f" border: 1px solid {cfg['border']};" if "border" in cfg else ""
        legend_html_parts.append(
            f'<span style="display: inline-flex; align-items: center; gap: 6px;">'
            f'<span style="display: inline-block; width: 12px; height: 12px; background: {cfg["color"]}; border-radius: 3px;{border_style}"></span>'
            f'{cfg["label"]}</span>'
        )
    legend_html = "".join(legend_html_parts)

    st.markdown(f"""<div style="border: 1px solid #E5E7EB; border-radius: 10px; padding: 16px; background: #FFFFFF; font-family: sans-serif; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 15px;">
  <div style="font-weight: 700; color: #1E293B; margin-bottom: 12px; font-size: 15px;">Page-by-Page Composition Breakdown</div>
  <!-- Legend -->
  <div style="display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: #475569;">
    {legend_html}
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
                page_html_parts.append(f'<div style="width: {clean:.2f}%; background: {segment_cfg["clean"]["color"]}; height: 100%;" title="Clean Text: {clean:.1f}%"></div>')
            if faded > 0:
                page_html_parts.append(f'<div style="width: {faded:.2f}%; background: {segment_cfg["faded"]["color"]}; height: 100%;" title="Faded Text: {faded:.1f}%"></div>')
            if logo > 0:
                page_html_parts.append(f'<div style="width: {logo:.2f}%; background: {segment_cfg["logo"]["color"]}; height: 100%;" title="Logo: {logo:.1f}%"></div>')
            if stamp > 0:
                page_html_parts.append(f'<div style="width: {stamp:.2f}%; background: {segment_cfg["stamp"]["color"]}; height: 100%;" title="Stamp: {stamp:.1f}%"></div>')
            if handwritten > 0:
                page_html_parts.append(f'<div style="width: {handwritten:.2f}%; background: {segment_cfg["handwritten"]["color"]}; height: 100%;" title="Handwritten: {handwritten:.1f}%"></div>')
            if whitespace > 0:
                ws_border = f" border-left: 1px solid {segment_cfg['whitespace']['border']}; border-right: 1px solid {segment_cfg['whitespace']['border']};"
                page_html_parts.append(f'<div style="width: {whitespace:.2f}%; background: {segment_cfg["whitespace"]["color"]};{ws_border} height: 100%;" title="Whitespace: {whitespace:.1f}%"></div>')
            if noise > 0:
                page_html_parts.append(f'<div style="width: {noise:.2f}%; background: {segment_cfg["noise"]["color"]}; height: 100%;" title="Noise: {noise:.1f}%"></div>')

            page_html_parts.append("""</div>
  <!-- Numeric breakdown tooltip inline -->
  <div style="display: flex; gap: 10px; font-size: 10px; color: #64748B; margin-top: 5px; flex-wrap: wrap;">""")

            metrics = [
                ("clean", clean, "Text"),
                ("faded", faded, "Faded"),
                ("logo", logo, "Logo"),
                ("stamp", stamp, "Stamp"),
                ("handwritten", handwritten, "Hand"),
                ("whitespace", whitespace, "WS"),
                ("noise", noise, "Noise"),
            ]
            for key, val, short_lbl in metrics:
                if val > 0:
                    cfg = segment_cfg[key]
                    border_style = f" border: 1px solid {cfg['border']};" if "border" in cfg else ""
                    pill_html = (
                        f'<span style="display: inline-flex; align-items: center; gap: 4px; white-space: nowrap;">'
                        f'<span style="display: inline-block; width: 8px; height: 8px; background: {cfg["color"]}; border-radius: 2px;{border_style}"></span>'
                        f'{short_lbl}: {val:.1f}%</span>'
                    )
                    page_html_parts.append(pill_html)

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



@st.cache_data(show_spinner=False)
def cached_is_obvious_noise(snippet_path_str: str) -> bool:
    """Check if the snippet at the path is obvious noise (cached)."""
    try:
        arr = np.array(Image.open(snippet_path_str).convert("L"))
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


@st.cache_data(show_spinner=False)
def get_cached_card_thumbnail(snippet_path_str: str, width: int = 480, height: int = 160) -> bytes:
    """Build a fixed-size thumbnail canvas and return as JPEG bytes (cached)."""
    import io
    try:
        with Image.open(snippet_path_str) as img:
            thumb = _build_uniform_thumbnail(img, width=width, height=height)
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return b""


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

    return cached_is_obvious_noise(str(snippet_path))


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
    if not snippet_path.exists():
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
    if not snippet_path.exists():
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

    type_cfg = SNIPPET_TYPE_CONFIG.get(snippet_type, SNIPPET_TYPE_CONFIG["signature"])
    status_cfg = STATUS_BADGES.get(status, STATUS_BADGES["pending"])
    file_path = str(snippet.get("file_path") or "")
    doc_link = _build_document_page_link(file_path=file_path, page_num=int(page_num or 1))

    # Wrap the entire card in a container with a border
    with st.container(border=True):
        # Anchor div for CSS selectors to target container and apply premium hovers and shadows
        st.markdown(f'<div class="snippet-card-anchor {status}"></div>', unsafe_allow_html=True)
        
        # ── Row 1: Header (Type tag, Page Number / Link) ──
        # Render type badge and page link in a single row
        badge_html = f"""
            <div style="margin-top: 4px;">
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
            </div>
        """
        
        col_badge, col_btn = st.columns([1.8, 1.2])
        with col_badge:
            st.markdown(badge_html, unsafe_allow_html=True)
        with col_btn:
            if file_path:
                st.button(
                    f"📄 P. {page_num} 🔗",
                    key=f"open_card_page_{review_id}_{idx}",
                    on_click=_open_source_document,
                    args=(file_path, page_num),
                    use_container_width=True,
                    help=f"Open document to page {page_num}"
                )
            else:
                st.markdown(
                    f'<div style="text-align: right; margin-top: 4px;"><span style="background:#F1F5F9; color:#94A3B8; font-size:0.71rem; padding:0.2rem 0.5rem; border-radius:4px; border:1px solid #E2E8F0; display:inline-block;">📄 P. {page_num}</span></div>',
                    unsafe_allow_html=True
                )


        # ── Row 2: Render Snippet Image ──
        if snippet_path:
            try:
                if compact:
                    # Use cached card thumbnail to avoid opening and resizing on every rerun
                    thumb_bytes = get_cached_card_thumbnail(str(snippet_path), width=480, height=160)
                    if thumb_bytes:
                        st.image(thumb_bytes, use_column_width=True)
                    else:
                        st.error("Failed to generate snippet thumbnail")
                else:
                    st.image(str(snippet_path), use_column_width=True)
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
                <span style="
                    background:{status_cfg['bg']};
                    color:{status_cfg['color']};
                    font-size:{label_font};
                    font-weight:600;
                    padding:0.2rem 0.5rem;
                    border-radius:5px;
                    border: 1px solid {status_cfg['color']}22;
                ">{status_cfg['label']}</span>
            </div>
            <div style="display:flex; gap:1.5rem; align-items:flex-start; flex-wrap:wrap;">
                <div style="flex:0 0 auto;">
                    <div style="font-size:{label_font}; color:#374151; margin-bottom:0.24rem;">
                        <b>Accuracy Impact:</b>
                        <span style="color:#DC2626; font-weight:700; font-size:0.82rem;">
                            −{accuracy_impact:.2f}%
                        </span>
                    </div>
                    <div style="font-size:{label_font}; color:#374151;">
                        <b>Assigned To:</b>
                        <span style="font-weight:500; color:{type_cfg['color']};">{reviewer_role}</span>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if doc_link and file_path:
        # Use native OS file opener via button callback (bypasses all browser restrictions)
        def open_source_file():
            """Open file with system default application to specific page."""
            try:
                page_num_int = int(page_num or 1)
                file_path_str = str(file_path)
                
                if os.name == 'nt':  # Windows
                    # Try Adobe Reader with page parameter first
                    try:
                        # Adobe Reader command: AcroRd32.exe /A "page=X=OpenActions" file.pdf
                        subprocess.run(
                            [r'AcroRd32.exe', f'/A', f'page={page_num_int}', file_path_str],
                            check=False,
                            timeout=5
                        )
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        # Fallback: Try Acrobat
                        try:
                            subprocess.run(
                                [r'Acrobat.exe', f'/A', f'page={page_num_int}', file_path_str],
                                check=False,
                                timeout=5
                            )
                        except (FileNotFoundError, subprocess.TimeoutExpired):
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
        
        col_open, _ = st.columns([2, 3])
        with col_open:
            st.button(
                f"🔗",
                on_click=open_source_file,
                key=f"open_doc_{review_id}",
                help="Opens the source document to the specified page with your default PDF viewer"
            )

    # ── Render image ──
    if snippet_path.exists():
        try:
            img = Image.open(str(snippet_path))
            if compact:
                thumb = _build_uniform_thumbnail(img, width=520, height=280)
                st.image(
                    thumb,
                    use_column_width=True,
                    caption=f"{type_cfg['icon']} Page {page_num} | −{accuracy_impact:.2f}%",
                )
            else:
                st.image(
                    img,
                    use_column_width=True,
                    caption=f"{type_cfg['icon']} {type_cfg['label']} — Page {page_num} | Impact: −{accuracy_impact:.2f}%",
                )
        except Exception as img_err:
            st.error(f"Could not load snippet image: {img_err}")
    else:
        st.warning(f"Snippet file not found: `{snippet_path.name}`")

    # ── Review reason + review metadata for already-reviewed items ──
    if status in ("accepted", "rejected"):
        reason = snippet.get("review_reason", "")
        reviewed_by = snippet.get("reviewed_by", "")
        reviewed_at = snippet.get("reviewed_at", "")
        action_label = "Accepted" if status == "accepted" else "Rejected"
        st.markdown(
            f"""
            <div style="
                background:#F9FAFB; border:1px solid #E5E7EB; border-radius:8px;
                padding:0.6rem 0.8rem; margin-top:0.3rem; font-size:0.75rem; color:#374151;
            ">
                <b>{action_label}</b> by <i>{reviewed_by or 'Unknown'}</i>
                {f'on {reviewed_at[:19]}' if reviewed_at else ''}<br/>
                {f'<b>Reason:</b> {reason}' if reason else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )
        return  # No action buttons for already-reviewed items

    # ── Action buttons for pending items ──
    # Acceptance reason selector
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
        if st.button(
            "✅ Accept & Learn",
            key=f"btn_acc_{review_id}",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["active_review_editor"] = review_id
            st.rerun()

    with btn_col2:
        if st.button(
            "❌ Reject",
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

    if st.session_state.get("active_review_editor") == review_id:
        st.markdown(
            f"""
            <div style="
                margin-top:0.6rem; border:1px solid #BFDBFE; border-radius:10px;
                background:#EFF6FF; padding:0.7rem;
            ">
                <div style="font-size:0.82rem; font-weight:700; color:#1E3A8A; margin-bottom:0.15rem;">
                    📝 {reviewer_role} Verification Window
                </div>
                <div style="font-size:0.74rem; color:#334155;">Type visible content, then submit to accept and auto-tag similar pending snippets.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if snippet_path.exists():
            try:
                preview_img = Image.open(str(snippet_path))
                st.image(_build_uniform_thumbnail(preview_img, width=640, height=220), use_column_width=True)
            except Exception:
                pass

        text_key = f"typed_content_{review_id}"
        typed_content = st.text_area(
            "Content in this snippet",
            key=text_key,
            placeholder=f"{reviewer_role} types here...",
            height=90,
        )

        submit_col, cancel_col = st.columns(2)
        with submit_col:
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
                if "visual_memory" in st.session_state and st.session_state.visual_memory and snippet_path.exists():
                    try:
                        candidate_vector = st.session_state.visual_memory.extract_vector(str(snippet_path))
                        if candidate_vector is not None:
                            vector_dir.mkdir(parents=True, exist_ok=True)
                            vector_path = vector_dir / f"{review_id}.npy"
                            np.save(str(vector_path), candidate_vector)
                            matched_vector_path = str(vector_path)
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
                    )

                    # ── Index reviewed snippet to OpenSearch for searchability ──
                    try:
                        doc_id = snippet["smart_id"]
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
                            # Log but don't fail the review acceptance
                            pass
                    except Exception as review_index_error:
                        # Silent fail for indexing - doesn't block review acceptance
                        pass

                    auto_count = 0
                    if "visual_memory" in st.session_state and st.session_state.visual_memory and vector_dir.exists():
                        siblings = get_all_reviews_for_doc(snippet["smart_id"])
                        for sib in siblings:
                            if sib.get("status") != "pending":
                                continue
                            if sib.get("review_id") == review_id:
                                continue
                            if str(sib.get("snippet_type") or "") != str(snippet_type):
                                continue

                            sib_path = _resolve_snippet_path(Path(str(sib.get("snippet_path") or "")), working_root)
                            if not sib_path.exists():
                                continue

                            try:
                                is_match, matched_path = st.session_state.visual_memory.match_snippet(
                                    candidate_image_path=str(sib_path),
                                    approved_vectors_dir=str(vector_dir),
                                    threshold=0.90,
                                )
                                if not is_match:
                                    continue

                                update_snippet_review_status(
                                    review_id=str(sib.get("review_id")),
                                    status="accepted",
                                    feature_vector_path=matched_path,
                                    review_reason=f"Auto-tagged from {review_id} | Role={reviewer_role} | Verified Content: {typed}",
                                    reviewed_by=reviewer_role,
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

def render_snippet_review_tab(config: Any) -> None:
    """Render the production-grade HITL Visual Verification Portal."""

    # ── Page Header ──
    st.markdown(
        """
        <style>
        /* CSS to style standard Streamlit container with border for premium snippet card */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) {
            border: 1px solid #E2E8F0 !important;
            border-radius: 14px !important;
            background: #FFFFFF !important;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            padding: 1rem !important;
            margin-bottom: 0.5rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor):hover {
            transform: translateY(-3px) !important;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.07) !important;
            border-color: #CBD5E1 !important;
        }

        /* Dim and color-code accepted cards */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor.accepted) {
            border: 1px solid #A7F3D0 !important;
            background-color: #FAFAF9 !important;
            opacity: 0.65 !important;
            box-shadow: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor.accepted):hover {
            opacity: 1.0 !important;
            border-color: #34D399 !important;
        }

        /* Dim and color-code rejected cards */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor.rejected) {
            border: 1px solid #FECACA !important;
            background-color: #FAFAF9 !important;
            opacity: 0.65 !important;
            box-shadow: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor.rejected):hover {
            opacity: 1.0 !important;
            border-color: #F87171 !important;
        }

        /* Crop image framed preview */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) div[data-testid="stImage"] {
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

        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) div[data-testid="stImage"] img {
            width: 100% !important;
            height: auto !important;
            object-fit: contain !important;
            transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        /* Hover zoom micro-animation */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) div[data-testid="stImage"]:hover img {
            transform: scale(1.05) !important;
        }

        /* Hide fullscreen expand button inside card images to prevent Streamlit layout engine crashing/flickering */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) button[title*="fullscreen"],
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) button[data-testid="stImageFullscreenButton"],
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) div[data-testid="stImage"] button {
            display: none !important;
        }

        /* Style selectbox input */
        div[data-testid="stSelectbox"] {
            margin-top: 0.25rem !important;
        }

        /* Style the buttons in card columns */
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):has(div.snippet-card-anchor) button {
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
                ["All Roles", "Contract Auditor", "Operations Manager", "Marketing Reviewer", "Text Specialist"],
                index=0,
                key="snippet_role_filter",
                help="Contract Auditor: Signatures • Operations Manager: Stamps • Marketing Reviewer: Logos • Text Specialist: OCR Anomalies",
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
            ]

        min_impact_by_type = {
            "signature": float(preprocessing_cfg.get("signature_min_impact", 0.0) or 0.0),
            "logo": float(preprocessing_cfg.get("logo_min_impact", 0.0) or 0.0),
            "stamp": float(preprocessing_cfg.get("stamp_min_impact", 0.0) or 0.0),
            "text_anomaly": float(preprocessing_cfg.get("text_anomaly_min_impact", 0.0) or 0.0),
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

        # Auto-hide obvious dot/blob noise, printed-font text, and OCR text from queue.
        hidden_noise_count = 0
        hidden_text_count = 0
        hidden_printed_count = 0
        visible_snippets = []
        for snippet in filtered:
            snippet_type = str((snippet or {}).get("snippet_type") or "").lower()

            if keep_signatures_visible and snippet_type == "signature":
                visible_snippets.append(snippet)
                continue

            if _is_obvious_noise_review_snippet(snippet, working_root):
                hidden_noise_count += 1
                continue
            if _is_printed_font_review_snippet(snippet, working_root):
                hidden_printed_count += 1
                continue
            if _is_text_like_review_snippet(snippet, working_root):
                hidden_text_count += 1
                continue
            visible_snippets.append(snippet)
        filtered = visible_snippets

        # Sort: pending first (urgent), then by page number for readability
        def sort_priority(s):
            status_order = {"pending": 0, "accepted": 1, "rejected": 2}
            return (status_order.get(s.get("status"), 3), s.get("page_num", 0))
        filtered = sorted(filtered, key=sort_priority)

        if hidden_noise_count > 0:
            st.caption(f"Auto-hidden {hidden_noise_count} obvious noise snippets from review queue.")
        if hidden_printed_count > 0:
            st.caption(f"Auto-hidden {hidden_printed_count} printed-font snippets (not handwriting).")
        if hidden_text_count > 0:
            st.caption(f"Auto-hidden {hidden_text_count} text-like snippets (kept in OCR flow).")

        view_tabs = st.tabs(["Waterfall Analysis", "Page Composition"])
        with view_tabs[0]:
            st.markdown("<div style='margin:0.35rem 0 0.5rem 0;'><b>Accuracy Impact Waterfall</b></div>", unsafe_allow_html=True)
            _render_accuracy_waterfall_chart(all_snippets, selected_doc)
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

            # ── Render snippet cards in compact 4-column tile layout ──
            tiles_per_row = 4
            for row_start in range(0, len(filtered), tiles_per_row):
                cols = st.columns(tiles_per_row)
                for col_idx in range(tiles_per_row):
                    snippet_idx = row_start + col_idx
                    if snippet_idx >= len(filtered):
                        continue
                    with cols[col_idx]:
                        _render_snippet_card(filtered[snippet_idx], working_root, snippet_idx, compact=True)

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
