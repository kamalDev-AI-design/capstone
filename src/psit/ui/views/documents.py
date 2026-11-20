import pandas as pd
import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError

KIND = {"INGESTED": "ok", "DUPLICATE": "warn", "QUARANTINED": "warn", "REJECTED": "bad"}


def render() -> None:
    api = session.client()
    theme.header("Documents & Index", "Local-only ingestion (PDF, DOCX, Markdown, TXT) and derived search-index status")
    can_write = session.role() in ("INTAKE_OPERATOR", "REVIEWER")

    s = api.index_status()
    m = s.manifest
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(theme.kpi("Index status", (m.status if m else "NOT BUILT"), "#6ee7b7" if s.built and not s.stale else "#fcd34d"),
                unsafe_allow_html=True)
    c2.markdown(theme.kpi("Chunks", m.chunk_count if m else 0), unsafe_allow_html=True)
    c3.markdown(theme.kpi("Sources", m.document_count if m else 0), unsafe_allow_html=True)
    c4.markdown(theme.kpi("Vector dim", m.embedding_dimension if m else "-"), unsafe_allow_html=True)
    if m:
        st.caption(f"v{m.index_version} · `{m.embedding_model}` · built {m.last_successful_build} · sha256 `{(m.checksum or '')[:16]}…` "
                   "· SQLite is the authority; FAISS is a derived artifact.")
    if s.stale:
        theme.alert("warn", f"Index is stale ({s.pending_reports} report(s) not indexed or documents changed).")
    if st.button("🔁 Rebuild index", disabled=not can_write, type="primary"):
        with st.spinner("Projecting reports, embedding chunks, swapping index atomically…"):
            try:
                api.rebuild_index()
                session.flash("ok", "Index rebuilt.")
            except ApiError as e:
                session.flash("bad", f"[{e.code}] {e.message}")
        st.rerun()

    st.markdown("#### Ingest documents")
    st.caption("Fictional SOPs need a header with `SOP-XXX-000`, `Version:` and `Effective Date:`. "
               "Image-only PDFs are quarantined; unsupported files are rejected.")
    files = st.file_uploader("Select files", accept_multiple_files=True, disabled=not can_write)
    if files and st.button("⬆️ Ingest selected files", disabled=not can_write):
        any_ok = False
        for f in files:
            try:
                r = api.upload_document(f.name, f.getvalue(), rebuild=False)
                theme.alert(KIND.get(r.status, "warn"), f"<b>{theme.esc(r.status)}</b> · {theme.esc(r.filename)} — {theme.esc(r.message)}")
                any_ok |= r.status == "INGESTED"
            except ApiError as e:
                theme.alert("bad", f"{theme.esc(f.name)}: {theme.esc(e.message)}")
        if any_ok:
            with st.spinner("Rebuilding index…"):
                api.rebuild_index()
            st.success("Index rebuilt with the new documents.")

    ov = api.documents()
    st.markdown("#### SOP versions")
    if ov.versions:
        st.dataframe(pd.DataFrame([{
            "SOP": v.doc_key, "Title": v.title, "Version": v.version, "State": "ACTIVE" if v.active else "SUPERSEDED",
            "Effective": v.effective_date, "File": v.filename, "Pages": v.page_count, "Chunks": v.chunk_count,
            "SHA-256": v.sha256[:12] + "…"} for v in ov.versions]), hide_index=True, width="stretch")
    else:
        st.caption("No SOPs ingested yet.")
    st.markdown("#### Ingestion runs")
    if ov.runs:
        st.dataframe(pd.DataFrame([{"Time": r.started_at, "File": r.filename, "Status": r.status, "Chunks": r.chunk_count,
                                    "Message": r.message} for r in ov.runs]), hide_index=True, width="stretch")
