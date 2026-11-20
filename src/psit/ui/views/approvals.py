import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError


def render() -> None:
    api = session.client()
    theme.header("Closure Approvals", "Closing a report requires explicit human authorization")
    pending = api.list_closure_requests("PENDING")
    st.markdown(f"#### Pending ({len(pending)})")
    if not pending:
        st.caption("Nothing waiting for approval.")
    for a in pending:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f'<span class="ref">{a.reference_id}</span> · approval #{a.approval_id} · requested by '
                        f'<b>{theme.esc(a.requested_by)}</b> at {a.requested_at:%Y-%m-%d %H:%M} · record v{a.report_version_at_request}',
                        unsafe_allow_html=True)
            if a.request_note:
                c1.caption(a.request_note)
            if c2.button("Open", key=f"o{a.approval_id}"):
                session.open_report(a.reference_id)
            if session.role() == "REVIEWER":
                if c2.button("Approve", key=f"a{a.approval_id}", type="primary"):
                    try:
                        api.approve(a.approval_id)
                        session.flash("ok", f"{a.reference_id} closed.")
                    except ApiError as e:
                        session.flash("bad", f"[{e.code}] {e.message}")
                    st.rerun()
            else:
                c2.caption("Reviewer only")

    st.markdown("#### Decided")
    for a in api.list_closure_requests("APPROVED"):
        st.markdown(f'{theme.pill("CLOSED")} <span class="ref">{a.reference_id}</span> approved by '
                    f'<b>{theme.esc(a.decided_by)}</b> at {a.decided_at:%Y-%m-%d %H:%M}', unsafe_allow_html=True)
