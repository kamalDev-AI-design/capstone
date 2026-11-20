import pandas as pd
import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError

EXAMPLES = [
    "How quickly must a complaint be acknowledged?",
    "LOT-88392",
    "tablets turning to powder when pressed out of the foil",
    "Can an AI assistant approve a closure?",
    "What does the SOP say about quarantine hold?",
    "Did the drug cause the headache?",
    "What is the capital of France?",
]


def _use_example(q: str) -> None:
    st.session_state["kq"] = q


def _citation_card(c) -> None:
    kind = "SOP" if c.source_type == "SOP" else "REPORT"
    label = "SOP" if kind == "SOP" else "HISTORICAL REPORT"
    bits = []
    if kind == "SOP":
        bits.append(f"v{c.version}" + (" · <b style='color:#fca5a5'>SUPERSEDED</b>" if c.superseded else ""))
        if c.section:
            bits.append(theme.esc(c.section))
        if c.page:
            bits.append(f"page {c.page}")
    else:
        if c.status:
            bits.append(theme.pill(c.status))
        if c.title:
            bits.append(theme.esc(c.title))
    exact = " · 🎯 exact ID match" if c.exact_id_match else ""
    st.markdown(
        f'<div class="psit-card" style="margin-bottom:8px"><span class="pill pill-{kind}">{label}</span> '
        f'<b>[{c.n}]</b> <span class="ref">{theme.esc(c.source_id)}</span> '
        f'<span class="muted">· {theme.esc(c.chunk_id)}{exact}</span>'
        f'<div class="muted" style="margin:4px 0">{" · ".join(bits)}</div>'
        f'<div style="font-size:.88rem;color:#c7d2e5">{theme.esc((c.snippet or "")[:320])}…</div></div>',
        unsafe_allow_html=True)
    st.progress(min(max(c.relevance, 0.0), 1.0), text=f"reranker relevance {c.relevance:.2f}")


def render() -> None:
    api = session.client()
    theme.header("Knowledge Assistant", "Evidence-constrained hybrid retrieval over fictional SOPs and historical reports")
    status = api.index_status()
    if not status.built:
        theme.alert("warn", "The knowledge index has not been built. Open <b>Documents</b>, ingest SOPs and rebuild the index.")
    elif status.stale:
        theme.alert("warn", f"⚠️ {status.pending_reports} report(s) are not in the index yet. Rebuild it on the Documents page.")
    st.caption(f"Model profile **{status.profile}** · embeddings `{status.active_model}` · reranker `{status.reranker}` · "
               "answers are **extractive** (no generative model).")

    st.markdown("**Try an example**")
    cols = st.columns(len(EXAMPLES))
    for col, ex in zip(cols, EXAMPLES):
        col.button(ex if len(ex) < 28 else ex[:26] + "…", key=f"ex_{ex}", on_click=_use_example, args=(ex,), help=ex)

    with st.form("kform", clear_on_submit=False):
        q = st.text_input("Ask a question or enter a REF / LOT / SOP identifier", key="kq")
        with st.expander("Filters"):
            c1, c2, c3 = st.columns(3)
            src = c1.multiselect("Source", ["SOP", "HISTORICAL_REPORT"], format_func=lambda s: "SOPs" if s == "SOP" else "Historical reports")
            rstatus = c2.selectbox("Report status", ["", "NEW", "IN_REVIEW", "CLOSED"], format_func=lambda x: x or "Any")
            old = c3.checkbox("Include superseded SOP versions", value=False)
        go = st.form_submit_button("🔎 Search", type="primary")

    if go and q.strip():
        with st.spinner("BM25 + dense retrieval → RRF → cross-encoder rerank…"):
            try:
                st.session_state["_kresult"] = api.knowledge_search(q.strip(), source_types=src, status=rstatus or None,
                                                                    include_superseded=old)
            except ApiError as e:
                st.session_state.pop("_kresult", None)
                theme.alert("bad", f"[{theme.esc(e.code)}] {theme.esc(e.message)}")
                return
    res = st.session_state.get("_kresult")
    if res:
        show_result(res)


def show_result(res) -> None:
    route_label = res.route.replace("_", " ").title()
    st.markdown(f'<span class="pill pill-type">route: {theme.esc(route_label)}</span>', unsafe_allow_html=True)
    if res.blocked:
        theme.alert("bad", f"🛑 <b>Scope boundary ({theme.esc(res.block_category or '')})</b><br>{theme.esc(res.answer)}")
        return
    if res.abstained:
        theme.alert("warn", f"🤷 <b>Abstained</b> ({theme.esc(res.abstain_reason or '')})<br>{theme.esc(res.answer)}")
    else:
        left, right = st.columns([3, 2])
        with left:
            st.markdown("#### Answer")
            st.markdown(res.answer)
            st.caption("ℹ️ " + res.scope_statement)
        with right:
            st.markdown("#### Citations")
            for c in res.citations:
                _citation_card(c)

    with st.expander("🔬 Retrieval trace (4 stages)"):
        t = res.timings_ms
        st.caption(f"BM25 {t.get('bm25', 0)} ms · dense {t.get('dense', 0)} ms · RRF {t.get('fusion', 0)} ms · "
                   f"rerank {t.get('rerank', 0)} ms · total {t.get('total', 0)} ms · candidates {res.counts}")
        if res.trace:
            df = pd.DataFrame([{"Chunk": r.chunk_id, "Source": r.source_type, "BM25 rank": r.bm25_rank,
                                "Dense rank": r.dense_rank, "RRF rank": r.rrf_rank, "RRF score": r.rrf_score,
                                "Rerank rank": r.rerank_rank, "Rerank score": r.rerank_score,
                                "Exact ID": r.exact_id, "In context": r.selected} for r in res.trace])
            st.dataframe(df, hide_index=True, width="stretch")
