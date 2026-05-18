"""
main.py — IncidentIQ Streamlit UI.
Premium dark-mode dashboard with 3-panel layout, animated metrics,
incident history, and real-time learning feedback.
"""

import streamlit as st
import json
import time
from datetime import datetime, timezone

# ─── Must be first Streamlit call ────────────────────────────────────────────
st.set_page_config(
    page_title="IncidentIQ — AI Incident Response Agent",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Lazy imports after set_page_config
from agent import analyze_incident
from memory import log_incident_resolution, get_bank_stats

# ─── Premium CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-primary: #0f1117;
    --bg-card: #1a1d27;
    --bg-card-hover: #22263a;
    --border: #2a2e3e;
    --text-primary: #e8eaed;
    --text-secondary: #9aa0b0;
    --accent-red: #ff4757;
    --accent-green: #00d2a0;
    --accent-blue: #4c6ef5;
    --accent-orange: #ff9f43;
    --accent-purple: #a855f7;
    --gradient-hot: linear-gradient(135deg, #ff4757, #ff6b81);
    --gradient-cool: linear-gradient(135deg, #4c6ef5, #748ffc);
    --gradient-success: linear-gradient(135deg, #00d2a0, #00e6b0);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

.stApp { background-color: var(--bg-primary); }
.block-container { padding: 1.5rem 2rem 3rem; max-width: 1400px; }
section[data-testid="stSidebar"] { background: var(--bg-card); }

/* Header */
.iq-header {
    display: flex; align-items: center; gap: 16px;
    padding: 20px 28px; margin-bottom: 24px;
    background: linear-gradient(135deg, rgba(255,71,87,0.08), rgba(76,110,245,0.08));
    border: 1px solid rgba(255,71,87,0.15);
    border-radius: 16px;
}
.iq-header .logo { font-size: 2.2rem; }
.iq-header .title {
    font-size: 1.8rem; font-weight: 800; letter-spacing: -0.03em;
    background: linear-gradient(135deg, #ff4757, #ff6b81, #ff9f43);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0; line-height: 1.1;
}
.iq-header .subtitle {
    font-size: 0.85rem; color: var(--text-secondary); margin: 4px 0 0;
    font-weight: 400;
}
.iq-header .status-pill {
    margin-left: auto; padding: 6px 14px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
    background: rgba(0,210,160,0.12); color: #00d2a0;
    border: 1px solid rgba(0,210,160,0.2);
}

/* Section headers */
.section-header {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--text-secondary);
    padding: 0 0 8px; margin-bottom: 12px;
    border-bottom: 1px solid var(--border);
}
.section-header .icon { margin-right: 6px; }

/* Metric cards */
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.m-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 14px;
    transition: border-color 0.2s;
}
.m-card:hover { border-color: var(--accent-blue); }
.m-card .m-label {
    font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--text-secondary); margin-bottom: 4px;
}
.m-card .m-value { font-size: 1.1rem; font-weight: 700; color: var(--text-primary); }
.m-card .m-value.blue { color: var(--accent-blue); }
.m-card .m-value.green { color: var(--accent-green); }
.m-card .m-value.orange { color: var(--accent-orange); }
.m-card .m-value.red { color: var(--accent-red); }
.m-card .m-value.purple { color: var(--accent-purple); }
.m-card.full { grid-column: 1 / -1; }

/* Badges */
.badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 14px; border-radius: 8px;
    font-size: 0.78rem; font-weight: 600; margin-bottom: 12px;
}
.badge-memory {
    background: rgba(0,210,160,0.12); color: #00d2a0;
    border: 1px solid rgba(0,210,160,0.25);
}
.badge-general {
    background: rgba(168,85,247,0.12); color: #a855f7;
    border: 1px solid rgba(168,85,247,0.25);
}
.badge-sev {
    font-size: 0.7rem; padding: 3px 10px; border-radius: 6px; font-weight: 700;
}
.sev-p1 { background: rgba(255,71,87,0.15); color: #ff4757; border: 1px solid rgba(255,71,87,0.3); }
.sev-p2 { background: rgba(255,159,67,0.15); color: #ff9f43; border: 1px solid rgba(255,159,67,0.3); }
.sev-p3 { background: rgba(76,110,245,0.15); color: #4c6ef5; border: 1px solid rgba(76,110,245,0.3); }

/* Response card */
.response-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px 24px;
}

/* Routing tag */
.route-tag {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 6px;
    font-size: 0.7rem; font-weight: 600; font-family: 'JetBrains Mono', monospace;
}
.route-drafter { background: rgba(0,210,160,0.1); color: #00d2a0; border: 1px solid rgba(0,210,160,0.2); }
.route-verifier { background: rgba(255,159,67,0.1); color: #ff9f43; border: 1px solid rgba(255,159,67,0.2); }

/* Trace entry */
.trace-entry {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px 14px; margin-bottom: 6px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
    color: var(--text-secondary);
}

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─── Session State ───────────────────────────────────────────────────────────
defaults = {
    "active_incident": None,
    "agent_response": None,
    "audit_data": None,
    "past_incidents": None,
    "history": [],           # List of past interactions this session
    "total_queries": 0,
    "total_cost": 0.0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Header ──────────────────────────────────────────────────────────────────
stats = get_bank_stats()
mem_count = stats.get("memory_count", stats.get("total_memories", "—"))

st.markdown(f"""
<div class="iq-header">
    <span class="logo">🚨</span>
    <div>
        <div class="title">IncidentIQ</div>
        <div class="subtitle">AI-Powered Incident Response — learns from every fix via <b>Hindsight</b> memory, routes intelligently via <b>cascadeflow</b></div>
    </div>
    <span class="status-pill">● {mem_count} memories loaded</span>
</div>
""", unsafe_allow_html=True)


# ─── Tabs ────────────────────────────────────────────────────────────────────
tab_main, tab_history = st.tabs(["🎯  Incident Response", "📋  Session History"])

with tab_main:
    col_left, col_center, col_right = st.columns([1.1, 2.2, 1.1])

    # ── LEFT PANEL: Alert Form ───────────────────────────────────────────────
    with col_left:
        st.markdown('<div class="section-header"><span class="icon">⚠️</span>NEW ALERT</div>', unsafe_allow_html=True)

        with st.form("incident_form", clear_on_submit=False):
            service_name = st.selectbox(
                "Service",
                [
                    "payment-service", "auth-api", "nginx-gateway", "user-db",
                    "cache-redis", "inventory-api", "search-service",
                    "notification-service", "report-worker", "image-processing",
                    "frontend-web",
                ],
                help="Select the affected service",
            )
            error_message = st.text_area(
                "Error Message",
                placeholder="e.g. DB connection pool exhausted\ne.g. OOM kill on pod nginx-7x\ne.g. 502 Bad Gateway",
                height=110,
            )
            severity = st.selectbox(
                "Severity",
                ["P1 — Critical", "P2 — High", "P3 — Medium"],
                help="P1 → escalates to stronger model, P3 → fast cheap model",
            )
            submitted = st.form_submit_button(
                "🔍 Analyze Incident", type="primary", use_container_width=True
            )

            if submitted:
                if not error_message.strip():
                    st.error("Enter an error message.")
                else:
                    sev_code = severity.split(" ")[0]
                    with st.spinner("🧠 Searching memory & analyzing..."):
                        t_start = time.time()
                        session_data, past_incidents = analyze_incident(
                            service_name, error_message, sev_code
                        )
                        total_time = (time.time() - t_start) * 1000

                    st.session_state.active_incident = {
                        "service_name": service_name,
                        "error_message": error_message,
                        "severity": sev_code,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    st.session_state.agent_response = session_data.get("response", "Error — see logs.")
                    st.session_state.audit_data = session_data
                    st.session_state.past_incidents = past_incidents
                    st.session_state.total_queries += 1
                    st.session_state.total_cost += session_data.get("total_cost", 0.0)

                    # Add to history
                    st.session_state.history.append({
                        "service": service_name,
                        "error": error_message[:80],
                        "severity": sev_code,
                        "had_memory": bool(past_incidents),
                        "model": session_data.get("model_used", "—"),
                        "cost": session_data.get("total_cost", 0.0),
                        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    })
                    st.rerun()

        # Session stats
        if st.session_state.total_queries > 0:
            st.markdown("---")
            st.caption(f"**Session:** {st.session_state.total_queries} queries · ${st.session_state.total_cost:.5f} total")

    # ── CENTER PANEL: Agent Response ─────────────────────────────────────────
    with col_center:
        st.markdown('<div class="section-header"><span class="icon">🧠</span>AGENT INTELLIGENCE</div>', unsafe_allow_html=True)

        if st.session_state.agent_response:
            inc = st.session_state.active_incident or {}
            has_memory = bool(st.session_state.past_incidents)
            sev = inc.get("severity", "P2")

            # Status bar: severity + memory badge
            sev_class = {"P1": "sev-p1", "P2": "sev-p2", "P3": "sev-p3"}.get(sev, "sev-p2")
            mem_badge = (
                '<span class="badge badge-memory">✓ MEMORY MATCH</span>'
                if has_memory
                else '<span class="badge badge-general">ℹ NEW ERROR TYPE</span>'
            )
            st.markdown(
                f'<span class="badge-sev {sev_class}">{sev}</span> '
                f'{mem_badge} '
                f'<span style="color:#9aa0b0;font-size:0.8rem;">{inc.get("service_name","")} · {inc.get("error_message","")[:60]}</span>',
                unsafe_allow_html=True,
            )

            # Memory expander
            if has_memory:
                with st.expander(f"📂 {len(st.session_state.past_incidents)} recalled memories from Hindsight", expanded=False):
                    for idx, mem in enumerate(st.session_state.past_incidents[:5], 1):
                        text = mem["text"] if isinstance(mem, dict) else str(mem)
                        st.info(f"**Memory #{idx}**\n\n{text}")

            # Agent response
            st.markdown('<div class="response-card">', unsafe_allow_html=True)
            st.markdown(st.session_state.agent_response)
            st.markdown('</div>', unsafe_allow_html=True)

            # Resolve section
            st.markdown("---")
            st.markdown("##### ✅ Resolve & Teach")
            st.caption("Log the fix → agent learns it instantly for next time")
            with st.form("resolve_form"):
                r1, r2 = st.columns(2)
                with r1:
                    rc = st.text_input("Root Cause", placeholder="e.g. Connection leak in reporting service")
                with r2:
                    fix = st.text_input("Fix Applied", placeholder="e.g. Increased pool size from 10→20")
                resolved_by = st.text_input("Resolved By", placeholder="@your-handle")
                res_time = st.number_input("Resolution Time (minutes)", min_value=0, value=15, step=5)
                log_btn = st.form_submit_button("💾 Log to Hindsight Memory", type="primary", use_container_width=True)

                if log_btn:
                    if rc and fix and resolved_by:
                        with st.spinner("Writing to Hindsight..."):
                            success = log_incident_resolution(
                                inc.get("service_name", ""),
                                inc.get("error_message", ""),
                                inc.get("severity", "P2"),
                                rc, fix, resolved_by, res_time,
                            )
                        if success:
                            st.success("✅ Memory updated! Run the same error again to see the agent recall this fix.")
                            for key in ("active_incident", "agent_response", "audit_data", "past_incidents"):
                                st.session_state[key] = None
                            st.rerun()
                        else:
                            st.error("Failed to write to Hindsight. Check API key.")
                    else:
                        st.warning("Fill in root cause, fix, and resolver.")
        else:
            st.markdown("""
<div style="text-align:center; padding:60px 20px; color:#9aa0b0;">
    <div style="font-size:3rem; margin-bottom:16px;">🔍</div>
    <div style="font-size:1.1rem; font-weight:600; color:#e8eaed; margin-bottom:8px;">Ready to Respond</div>
    <div style="font-size:0.85rem;">Submit an alert on the left. The agent will search its Hindsight memory<br>for similar past incidents and suggest a proven fix.</div>
</div>
""", unsafe_allow_html=True)

    # ── RIGHT PANEL: Audit Trail ─────────────────────────────────────────────
    with col_right:
        st.markdown('<div class="section-header"><span class="icon">📊</span>CASCADEFLOW AUDIT</div>', unsafe_allow_html=True)

        audit = st.session_state.audit_data
        if audit and audit.get("model_used"):
            model_used = audit.get("model_used", "—")
            cost = audit.get("total_cost", 0.0)
            latency = audit.get("latency_ms", 0.0)
            savings = audit.get("cost_saved_percentage", 0.0)
            budget = audit.get("severity_budget", 0.25)
            draft_cost = audit.get("draft_cost", 0.0)
            verifier_cost = audit.get("verifier_cost", 0.0)

            # Determine if drafter or verifier was used
            is_drafter = "8b" in model_used.lower()
            route_class = "route-drafter" if is_drafter else "route-verifier"
            route_label = "⚡ DRAFTER" if is_drafter else "🔬 VERIFIER"

            st.markdown(f'<span class="{route_class} route-tag">{route_label}</span>', unsafe_allow_html=True)

            # Metrics grid
            st.markdown(f"""
<div class="metric-grid">
    <div class="m-card full">
        <div class="m-label">Model</div>
        <div class="m-value blue" style="font-size:0.85rem;">{model_used}</div>
    </div>
    <div class="m-card">
        <div class="m-label">Cost</div>
        <div class="m-value green">${cost:.6f}</div>
    </div>
    <div class="m-card">
        <div class="m-label">Latency</div>
        <div class="m-value orange">{latency:.0f}ms</div>
    </div>
    <div class="m-card">
        <div class="m-label">Budget</div>
        <div class="m-value">${budget:.2f}</div>
    </div>
    <div class="m-card">
        <div class="m-label">Savings</div>
        <div class="m-value {'green' if savings > 0 else ''}">{savings:.1f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

            # Why this model?
            sev = (st.session_state.active_incident or {}).get("severity", "P2")
            if sev == "P1":
                rationale = "🔴 P1 Critical → Escalated to stronger model with higher budget ($0.50)"
            elif sev == "P3":
                rationale = "🟢 P3 Medium → Routed to fast/cheap drafter with minimal budget ($0.10)"
            else:
                rationale = "🟡 P2 High → Standard budget ($0.25), drafter attempted first"

            st.caption(f"**Routing:** {rationale}")

            # Trace expander
            traces = audit.get("trace", [])
            summary = audit.get("summary", {})
            if traces or summary:
                with st.expander("🔍 Full Decision Trace"):
                    if traces:
                        for t in traces:
                            action = t.get("action", "—")
                            reason = t.get("reason", "—")
                            st.markdown(
                                f'<div class="trace-entry">step {t.get("step","?")} → '
                                f'<b>{action}</b> · {reason}</div>',
                                unsafe_allow_html=True,
                            )
                    if summary:
                        st.json(summary)
        else:
            st.markdown("""
<div style="text-align:center; padding:40px 10px; color:#9aa0b0;">
    <div style="font-size:2rem; margin-bottom:8px;">📊</div>
    <div style="font-size:0.8rem;">Audit trail appears here after analysis.<br>Shows model routing, cost, latency, and savings.</div>
</div>
""", unsafe_allow_html=True)


# ─── History Tab ─────────────────────────────────────────────────────────────
with tab_history:
    st.markdown('<div class="section-header"><span class="icon">📋</span>SESSION HISTORY</div>', unsafe_allow_html=True)

    if st.session_state.history:
        # Summary metrics
        h = st.session_state.history
        mem_hits = sum(1 for x in h if x["had_memory"])
        total = len(h)
        total_cost = sum(x["cost"] for x in h)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Queries", total)
        c2.metric("Memory Hits", f"{mem_hits}/{total}", delta=f"{mem_hits/total*100:.0f}%" if total else "0%")
        c3.metric("Total Cost", f"${total_cost:.5f}")
        c4.metric("Avg Cost/Query", f"${total_cost/total:.6f}" if total else "$0")

        st.markdown("---")

        # Table
        for i, entry in enumerate(reversed(h)):
            mem_icon = "🟢" if entry["had_memory"] else "🔴"
            st.markdown(
                f"`{entry['time']}` {mem_icon} **{entry['severity']}** "
                f"`{entry['service']}` — {entry['error']} "
                f"· Model: `{entry['model']}` · ${entry['cost']:.6f}"
            )
    else:
        st.info("No queries yet this session. Submit an alert to get started.")
