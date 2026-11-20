import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError
from psit.ui.views.knowledge import show_result

SUGGESTIONS = [
    "hello",
    "list new reports",
    "show REF-2026-0004",
    "What does the SOP say about acknowledging a complaint?",
    "similar complaints about cracked seals",
    "move REF-2026-0004 to in review",
    "request closure for REF-2026-0004",
    "approve approval #1",
    "verify the audit chain",
    "Did the drug cause the headache?",
]
OUTCOME_KIND = {"OK": "ok", "NEEDS_INPUT": "warn", "ABSTAINED": "warn", "NEEDS_HUMAN_CONFIRMATION": "warn",
                "BLOCKED": "bad", "REJECTED": "bad", "CIRCUIT_BREAKER_TRIGGERED": "bad"}


def _send(text: str) -> None:
    st.session_state["_pending_msg"] = text


def _render_agent(msg: dict, idx: int) -> None:
    r = msg["resp"]
    st.markdown(f'<span class="pill pill-type">route: {theme.esc(r.route)}</span> &nbsp; '
                f'<span class="muted">outcome: {theme.esc(r.outcome)}</span>', unsafe_allow_html=True)
    if r.circuit_breaker:
        theme.alert("bad", f"⛔ <b>CIRCUIT_BREAKER_TRIGGERED</b><br>{theme.esc(r.message)}")
    elif r.outcome == "BLOCKED":
        theme.alert("bad", f"🛑 <b>Scope boundary</b><br>{theme.esc(r.message)}")
    elif not r.knowledge:
        st.markdown(r.message)
    if r.knowledge and not r.knowledge.blocked:
        show_result(r.knowledge)
    if r.reports:
        st.dataframe([{"Reference": x.reference_id, "Status": x.status.value, "Product": x.product_name, "Lot": x.lot_number}
                      for x in r.reports], hide_index=True, width="stretch")
    if r.pending_confirmation:
        pc = r.pending_confirmation
        if session.role() == "REVIEWER":
            if st.button(f"✅ I confirm: approve closure of {pc.reference_id} (approval #{pc.approval_id})",
                         key=f"confirm_{idx}", type="primary"):
                try:
                    session.client().approve(pc.approval_id)
                    session.flash("ok", f"{pc.reference_id} closed with your human approval.")
                except ApiError as e:
                    session.flash("bad", f"[{e.code}] {e.message}")
                st.rerun()
    if r.tool_calls:
        st.caption("🔧 tools: " + " → ".join(f"`{t.tool}` {'✓' if t.status == 'OK' else '✗ ' + (t.error_code or '')}" for t in r.tool_calls))


def render() -> None:
    api = session.client()
    theme.header("Assistant", "Bounded agent: policy check → routing → typed tools → backend rules. It retrieves and routes; it never decides.")
    chat = st.session_state.setdefault("chat", [])
    with st.expander("💡 Suggested prompts", expanded=not chat):
        cols = st.columns(2)
        for i, s in enumerate(SUGGESTIONS):
            cols[i % 2].button(s, key=f"sg{i}", on_click=_send, args=(s,))
    if st.button("🗑️ Clear conversation", disabled=not chat):
        st.session_state["chat"] = []
        st.rerun()

    for i, m in enumerate(chat):
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m["content"])
            else:
                _render_agent(m, i)

    text = st.chat_input("Ask about reports, SOPs, or request an action…") or st.session_state.pop("_pending_msg", None)
    if text:
        chat.append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        with st.chat_message("assistant"):
            with st.spinner("Routing and running approved tools…"):
                try:
                    resp = api.agent_message(text)
                    chat.append({"role": "assistant", "resp": resp})
                except ApiError as e:
                    chat.append({"role": "assistant", "resp": _err(e)})
        st.rerun()


def _err(e: ApiError):
    from psit.contracts.agent import AgentResponse
    return AgentResponse(route="ERROR", outcome="REJECTED", message=f"[{e.code}] {e.message}")
