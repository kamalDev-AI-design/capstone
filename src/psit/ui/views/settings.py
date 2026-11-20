import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError


def render() -> None:
    api = session.client()
    theme.header("Settings", "Answer generation mode. The default is fully local and extractive.")
    s = api.get_llm_settings()
    theme.alert("ok" if s["provider"] == "EXTRACTIVE" else "warn",
                f"Current mode: <b>{'Local extractive (no generative model)' if s['provider'] == 'EXTRACTIVE' else 'OpenRouter (cloud LLM)'}</b>"
                f" · OPENROUTER_API_KEY {'detected in backend environment ✓' if s['key_configured'] else 'not set ✗'}")
    st.write("")
    st.markdown("##### Optional: OpenRouter answer generation")
    st.caption("Retrieval, embeddings and reranking always stay local. When enabled, only the question and the already-retrieved "
               "**fictional** evidence passages are sent to OpenRouter (temperature 0, ≤450 tokens). Citations are validated and any "
               "failure falls back to the extractive answer. The key is read from the backend environment only and never shown or stored.")
    if not s["key_configured"]:
        st.info("Set `OPENROUTER_API_KEY` in the backend's environment (see `.env.example`) and restart the API to enable this.")
    with st.form("llm"):
        enable = st.toggle("Use OpenRouter for answer generation", value=s["provider"] == "OPENROUTER",
                           disabled=not s["key_configured"])
        model = st.selectbox("Model", s["suggested_models"], index=s["suggested_models"].index(s["model"])
                             if s["model"] in s["suggested_models"] else 0, accept_new_options=True)
        if st.form_submit_button("Save", type="primary"):
            try:
                api.put_llm_settings("OPENROUTER" if enable else "EXTRACTIVE", model)
                session.flash("ok", "Settings saved.")
            except ApiError as e:
                session.flash("bad", f"[{e.code}] {e.message}" + ("" if not e.fields else " " + "; ".join(e.fields)))
            st.rerun()
