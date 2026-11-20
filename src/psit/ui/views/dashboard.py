import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError

STATUS_COLORS = {"NEW": "#3b82f6", "IN_REVIEW": "#f59e0b", "CLOSED": "#10b981"}


def _style(fig: go.Figure) -> go.Figure:
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e6edf7",
                      margin=dict(l=10, r=10, t=30, b=10), height=260, legend=dict(orientation="h", y=-0.1))
    return fig


def render() -> None:
    api = session.client()
    theme.header("Tracker Dashboard", "Fictional safety intake records and their review status")
    try:
        stats = api.stats()
    except ApiError as e:
        st.error(e.message)
        return

    if stats.total == 0:
        theme.alert("warn", "No records yet. Create one on <b>New Intake</b> or load fictional demo data.")
        if st.button("📥 Load fictional demo data", type="primary"):
            n = api.seed_demo()
            session.flash("ok", f"Loaded {n} fictional demo reports.")
            st.rerun()
        return

    cols = st.columns(5)
    cards = [("Total", stats.total, "#e6edf7"), ("New", stats.by_status.get("NEW", 0), "#93c5fd"),
             ("In review", stats.by_status.get("IN_REVIEW", 0), "#fcd34d"),
             ("Closed", stats.by_status.get("CLOSED", 0), "#6ee7b7"),
             ("Pending approvals", stats.pending_approvals, "#f9a8d4")]
    for c, (label, v, color) in zip(cols, cards):
        c.markdown(theme.kpi(label, v, color), unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        labels = list(stats.by_status)
        fig = go.Figure(go.Pie(labels=labels, values=[stats.by_status[k] for k in labels], hole=0.62,
                               marker_colors=[STATUS_COLORS.get(k, "#64748b") for k in labels], textinfo="value"))
        fig.update_layout(title="By status")
        c1.plotly_chart(_style(fig), width="stretch")
    with c2:
        fig = go.Figure(go.Bar(x=[theme.type_label(k) for k in stats.by_type], y=list(stats.by_type.values()),
                               marker_color=["#8b5cf6", "#ec4899"][: len(stats.by_type)]))
        fig.update_layout(title="By report type")
        c2.plotly_chart(_style(fig), width="stretch")

    st.markdown("#### Reports")
    f1, f2, f3, f4 = st.columns([1, 1.3, 1, 1.4])
    status = f1.selectbox("Status", ["", "NEW", "IN_REVIEW", "CLOSED"], format_func=lambda x: x or "All")
    rtype = f2.selectbox("Type", ["", "SUSPECTED_ADVERSE_EVENT", "PRODUCT_QUALITY_COMPLAINT"],
                         format_func=lambda x: theme.type_label(x) if x else "All")
    chan = f3.selectbox("Channel", ["", "EMAIL", "TELEPHONE"], format_func=lambda x: x or "All")
    product = f4.text_input("Product contains")
    d1, d2 = st.columns(2)
    dfrom = d1.date_input("Received from", value=None)
    dto = d2.date_input("Received to", value=None)

    res = api.list_reports(status=status, report_type=rtype, intake_channel=chan, product=product,
                           date_from=dfrom.isoformat() if dfrom else None, date_to=dto.isoformat() if dto else None, limit=200)
    st.caption(f"{res.total} record(s) match. Select a row to open it.")
    if not res.items:
        return
    df = pd.DataFrame([{
        "Reference": r.reference_id, "Status": r.status.value, "Type": theme.type_label(r.report_type.value),
        "Product": r.product_name, "Lot": r.lot_number, "Received": r.date_received, "Channel": r.intake_channel,
        "Reporter": r.reporter_type.value.replace("_", " ").title(),
    } for r in res.items])
    icon = {"NEW": "🔵 NEW", "IN_REVIEW": "🟠 IN_REVIEW", "CLOSED": "🟢 CLOSED"}
    df["Status"] = df["Status"].map(icon)
    ev = st.dataframe(df, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row")
    rows = ev.selection.rows
    if rows:
        ref = df.iloc[rows[0]]["Reference"]
        if st.button(f"Open {ref} →", type="primary"):
            session.open_report(ref)
