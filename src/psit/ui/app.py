"""Streamlit entry point (replaceable presentation adapter). Run: streamlit run src/psit/ui/app.py"""
import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import PERSONAS, BackendUnavailable
from psit.ui.views import approvals, assistant, audit, dashboard, detail, documents, intake, knowledge, settings

st.set_page_config(page_title="PSIT Agent", page_icon="🧪", layout="wide")
theme.inject()

pages = {
    "dashboard": st.Page(dashboard.render, title="Dashboard", icon="📊", default=True),
    "intake": st.Page(intake.render, title="New Intake", icon="📝", url_path="intake"),
    "detail": st.Page(detail.render, title="Report Detail", icon="🗂️", url_path="detail"),
    "assistant": st.Page(assistant.render, title="Assistant", icon="🤖", url_path="assistant"),
    "knowledge": st.Page(knowledge.render, title="Knowledge Assistant", icon="🔎", url_path="knowledge"),
    "documents": st.Page(documents.render, title="Documents & Index", icon="📚", url_path="documents"),
    "approvals": st.Page(approvals.render, title="Approvals", icon="✅", url_path="approvals"),
    "audit": st.Page(audit.render, title="Audit Trail", icon="🔗", url_path="audit"),
    "settings": st.Page(settings.render, title="Settings", icon="⚙️", url_path="settings"),
}
st.session_state["_pages"] = pages

with st.sidebar:
    st.markdown("### 🧪 PSIT Agent")
    st.caption("Pharma Safety Intake & Triage Knowledge Agent")
    st.selectbox("Sign in as (demo persona)", list(PERSONAS), key="persona")
    st.caption(f"Role: **{session.role()}**")

try:
    health = session.client().health()
    dot = "🟢" if health["database"] == "ok" else "🟠"
    status_txt = f"{dot} API v{health['version']}"
except BackendUnavailable:
    status_txt = "🔴 API offline"

st.markdown(
    f'<div class="psit-banner"><span>⚠️ <b>Fictional training data only.</b> Not a pharmacovigilance system, '
    f'medical device, or regulatory decision engine. It never assesses causality, seriousness, or reportability.</span>'
    f'<span>{status_txt}</span></div>', unsafe_allow_html=True)

if status_txt.startswith("🔴"):
    st.error("Cannot reach the backend. Start it with: `uvicorn psit.api.app:create_app --factory --port 8000`")
    st.stop()

nav = st.navigation(list(pages.values()))
session.show_flash()
nav.run()
