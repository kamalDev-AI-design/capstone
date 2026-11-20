import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError


def _act(fn, ok_msg: str) -> None:
    try:
        fn()
    except ApiError as e:
        session.flash("bad", f"Rejected by backend [{e.code}]: {e.message}")
    else:
        session.flash("ok", ok_msg)
    st.rerun()


def render() -> None:
    api = session.client()
    theme.header("Report Detail", "Workflow state is owned by the backend; this page only requests actions")
    refs = [r.reference_id for r in api.list_reports(limit=200).items]
    if not refs:
        st.info("No reports yet.")
        return
    sel = st.session_state.get("selected_ref")
    ref = st.selectbox("Report", refs, index=refs.index(sel) if sel in refs else 0)
    st.session_state["selected_ref"] = ref
    r = api.get_report(ref)

    st.markdown(
        f'<div class="psit-card"><span class="ref" style="font-size:1.3rem">{r.reference_id}</span> &nbsp; '
        f'{theme.pill(r.status.value)} &nbsp; <span class="pill pill-type">{theme.type_label(r.report_type.value)}</span>'
        f'<div class="muted" style="margin-top:6px">Record v{r.record_version} · created by {theme.esc(r.created_by)} · '
        f'synthetic: {r.synthetic}</div></div>', unsafe_allow_html=True)
    st.markdown(theme.stepper(r.status.value), unsafe_allow_html=True)

    left, right = st.columns([3, 2])
    with left:
        a, b, c = st.columns(3)
        a.metric("Product", r.product_name)
        b.metric("Lot", r.lot_number)
        c.metric("Received", str(r.date_received))
        d, e = st.columns(2)
        d.metric("Channel", r.intake_channel)
        e.metric("Reporter", r.reporter_type.value.replace("_", " ").title())
        st.markdown("**Description**")
        st.write(r.description)
        if r.event_description:
            st.markdown(f"**Event description** (onset {r.event_onset_date})")
            st.write(r.event_description)

    with right:
        st.markdown("##### Actions")
        role = session.role()
        if r.status.value == "NEW":
            if st.button("▶ Move to IN_REVIEW", type="primary"):
                _act(lambda: api.transition(ref, "IN_REVIEW"), f"{ref} moved to IN_REVIEW.")
        elif r.status.value == "IN_REVIEW":
            if r.pending_approval_id:
                theme.alert("warn", f"⏳ Closure approval <b>#{r.pending_approval_id}</b> is pending a human reviewer.")
                if role == "REVIEWER":
                    note = st.text_input("Approval note (optional)")
                    if st.button("✅ Approve closure", type="primary"):
                        _act(lambda: api.approve(r.pending_approval_id, note or None), f"{ref} closed with human approval.")
                else:
                    st.caption("Switch persona to a human REVIEWER to approve.")
                    if st.button("🤖 Try to approve anyway (demo)"):
                        _act(lambda: api.approve(r.pending_approval_id), "approved")
            else:
                note = st.text_input("Closure request note (optional)")
                if st.button("📨 Request closure", type="primary"):
                    _act(lambda: api.request_closure(ref, note or None), "Closure requested; awaiting human approval.")
        else:
            theme.alert("ok", "🔒 Closed. Re-opening is not permitted in this prototype.")

        with st.expander("🧪 Demo: attempt prohibited transitions"):
            st.caption("The backend, not the UI, decides validity.")
            if st.button("Force → CLOSED directly"):
                _act(lambda: api.transition(ref, "CLOSED"), "closed?!")
            if st.button("Force → NEW"):
                _act(lambda: api.transition(ref, "NEW"), "No-op or accepted per backend rules.")

    st.markdown("##### Status history")
    html = ['<div class="tl">']
    for h in r.history:
        frm = h.from_status or "—"
        ap = f" · approval #{h.approval_id}" if h.approval_id else ""
        html.append(f'<div class="tl-item"><b>{frm} → {h.to_status}</b>{ap}<div class="muted">'
                    f'{h.changed_at:%Y-%m-%d %H:%M:%S} · {theme.esc(h.actor_id)} ({h.actor_role})</div></div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
