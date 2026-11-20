"""Temporary UI state only (selected persona/page/report, flash messages). No business state."""
import streamlit as st

from .api_client import PERSONAS, ApiClient

DEFAULT_PERSONA = next(iter(PERSONAS))


def persona() -> str:
    return st.session_state.setdefault("persona", DEFAULT_PERSONA)


def role() -> str:
    return PERSONAS[persona()][1]


def actor_id() -> str:
    return PERSONAS[persona()][0]


def client() -> ApiClient:
    aid, r = PERSONAS[persona()]
    return ApiClient(aid, r)


def flash(kind: str, text: str) -> None:
    st.session_state["_flash"] = (kind, text)


def show_flash() -> None:
    f = st.session_state.pop("_flash", None)
    if f:
        {"ok": st.success, "bad": st.error, "warn": st.warning}.get(f[0], st.info)(f[1])


def open_report(ref: str) -> None:
    st.session_state["selected_ref"] = ref
    st.switch_page(st.session_state["_pages"]["detail"])
