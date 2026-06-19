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
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image
import streamlit as st

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
from ocr.visual_memory import VisualMemoryEngine

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


def _render_snippet_card(
    snippet: Dict[str, Any],
    working_root: Path,
    idx: int,
) -> None:
    """Render a single snippet review card with image, details, and action buttons."""
    review_id = snippet["review_id"]
    snippet_type = snippet["snippet_type"]
    snippet_path = Path(snippet["snippet_path"])
    page_num = snippet["page_num"]
    accuracy_impact = snippet["accuracy_impact"]
    reviewer_role = snippet["reviewer_role"]
    status = snippet.get("status", "pending")

    type_cfg = SNIPPET_TYPE_CONFIG.get(snippet_type, SNIPPET_TYPE_CONFIG["signature"])
    status_cfg = STATUS_BADGES.get(status, STATUS_BADGES["pending"])

    # ── Card container ──
    st.markdown(
        f"""
        <div style="
            border: 1px solid {type_cfg['border']};
            border-radius: 12px;
            padding: 1.2rem;
            background: linear-gradient(135deg, {type_cfg['bg']} 0%, #FFFFFF 100%);
            margin-bottom: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <span style="
                        background:{type_cfg['color']};
                        color:white;
                        font-size:0.75rem;
                        font-weight:700;
                        padding:0.3rem 0.7rem;
                        border-radius:6px;
                        letter-spacing:0.3px;
                    ">{type_cfg['icon']} {type_cfg['label']}</span>
                    <span style="
                        font-size:0.75rem;
                        color:#6B7280;
                        font-weight:500;
                        background:#F3F4F6;
                        padding:0.2rem 0.5rem;
                        border-radius:4px;
                    ">📄 Page {page_num}</span>
                </div>
                <span style="
                    background:{status_cfg['bg']};
                    color:{status_cfg['color']};
                    font-size:0.72rem;
                    font-weight:600;
                    padding:0.25rem 0.6rem;
                    border-radius:5px;
                    border: 1px solid {status_cfg['color']}22;
                ">{status_cfg['label']}</span>
            </div>
            <div style="display:flex; gap:1.5rem; align-items:flex-start; flex-wrap:wrap;">
                <div style="flex:0 0 auto;">
                    <div style="font-size:0.75rem; color:#374151; margin-bottom:0.3rem;">
                        <b>Accuracy Impact:</b>
                        <span style="color:#DC2626; font-weight:700; font-size:0.85rem;">
                            −{accuracy_impact:.2f}%
                        </span>
                    </div>
                    <div style="font-size:0.75rem; color:#374151;">
                        <b>Assigned To:</b>
                        <span style="font-weight:500; color:{type_cfg['color']};">{reviewer_role}</span>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Render image ──
    if snippet_path.exists():
        try:
            img = Image.open(str(snippet_path))
            st.image(
                img,
                use_container_width=True,
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
            if not final_reason or final_reason == "Custom reason...":
                st.warning("⚠️ Please select or enter an acceptance reason before approving.")
                return

            # CNN visual memory learning
            matched_vector_path = None
            if "visual_memory" in st.session_state and st.session_state.visual_memory and snippet_path.exists():
                try:
                    candidate_vector = st.session_state.visual_memory.extract_vector(str(snippet_path))
                    if candidate_vector is not None:
                        vector_dir = working_root / "data" / "visual_memory" / snippet["smart_id"]
                        vector_dir.mkdir(parents=True, exist_ok=True)
                        vector_path = vector_dir / f"{review_id}.npy"
                        np.save(str(vector_path), candidate_vector)
                        matched_vector_path = str(vector_path)
                except Exception:
                    pass  # Graceful fallback — approve without CNN learning

            try:
                update_snippet_review_status(
                    review_id=review_id,
                    status="accepted",
                    feature_vector_path=matched_vector_path,
                    review_reason=final_reason,
                    reviewed_by="Dashboard User",
                )
                st.toast(
                    f"✅ Accepted: {type_cfg['label']} — visual template {'learned' if matched_vector_path else 'saved'}!",
                    icon="✨",
                )
                st.rerun()
            except Exception as e:
                st.error(f"Failed to accept snippet: {e}")

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


def render_snippet_review_tab(config: Any) -> None:
    """Render the production-grade HITL Visual Verification Portal."""

    # ── Page Header ──
    st.markdown(
        """
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
    for doc in docs:
        fname = doc.get("file_name", "Unknown")
        sid = doc.get("smart_id", "")
        pending = doc.get("pending_count", 0)
        label = f"{'🔴 ' if pending > 0 else '🟢 '}{fname}  —  {pending} pending | {doc.get('accepted_count', 0)} accepted | {doc.get('rejected_count', 0)} rejected"
        doc_options[label] = doc

    selected_label = st.selectbox(
        "📂 Select Document to Review",
        options=list(doc_options.keys()),
        index=0,
        help="Documents with pending reviews are marked with 🔴",
    )
    selected_doc = doc_options[selected_label]
    selected_smart_id = selected_doc["smart_id"]

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
                ["All Roles", "Contract Auditor", "Operations Manager", "Marketing Reviewer"],
                index=0,
                key="snippet_role_filter",
                help="Contract Auditor: Signatures • Operations Manager: Stamps • Marketing Reviewer: Logos",
            )

        # Apply filters
        filtered = all_snippets
        if status_filter != "All Statuses":
            status_map = {"Pending": "pending", "Accepted": "accepted", "Rejected": "rejected"}
            filtered = [s for s in filtered if s.get("status") == status_map.get(status_filter, "")]
        if role_filter != "All Roles":
            filtered = [s for s in filtered if s.get("reviewer_role") == role_filter]

        if not filtered:
            st.info(f"No snippets matching filters: Status={status_filter}, Role={role_filter}")
        else:
            st.markdown(
                f"<p style='font-size:0.82rem; color:#64748B; margin:0.5rem 0;'>"
                f"Showing <b>{len(filtered)}</b> of <b>{len(all_snippets)}</b> elements</p>",
                unsafe_allow_html=True,
            )

            # ── Render snippet cards in clean vertical layout ──
            for idx, snippet in enumerate(filtered):
                _render_snippet_card(snippet, working_root, idx)
                if idx < len(filtered) - 1:
                    st.markdown("<hr style='border:none; border-top:1px solid #E5E7EB; margin:0.5rem 0;'/>", unsafe_allow_html=True)

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
