import pandas as pd
import streamlit as st

from psit.ui import session, theme


def render() -> None:
    api = session.client()
    theme.header("Audit Trail", "Append-only, hash-chained business events (tamper-evident, not absolutely immutable)")
    c1, c2 = st.columns([3, 1])
    entity = c1.text_input("Filter by entity (e.g. REF-2026-0001)")
    if c2.button("🔍 Verify hash chain", type="primary", width="stretch"):
        v = api.verify_audit()
        theme.alert("ok" if v.valid else "bad",
                    f"{'✅' if v.valid else '❌'} {theme.esc(v.message)} · {v.events_checked} events checked")

    res = api.audit_events(entity_id=entity or None)
    st.caption(f"{res.total} event(s); showing newest first.")
    if not res.items:
        return
    df = pd.DataFrame([{
        "Time (UTC)": e.timestamp_utc[:19].replace("T", " "), "Action": e.action_type, "Outcome": e.outcome,
        "Entity": e.entity_id, "Actor": f"{e.actor_id} ({e.actor_role})", "Details": str(e.details),
        "Event hash": e.event_hash[:12] + "…", "Prev hash": e.previous_event_hash[:12] + "…",
    } for e in res.items])
    st.dataframe(df, hide_index=True, width="stretch")
