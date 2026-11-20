from datetime import date

import streamlit as st

from psit.ui import session, theme
from psit.ui.api_client import ApiError

REPORTERS = ["HEALTHCARE_PROFESSIONAL", "PHARMACIST", "CONSUMER", "DISTRIBUTOR", "OTHER"]


def _sample(kind: str) -> None:
    ss = st.session_state
    ss.update(in_product="Zentrafen 50mg Tablets", in_lot="LOT-88392", in_date=date.today(),
              in_reporter="PHARMACIST", in_channel="EMAIL")
    if kind == "PQC":
        ss["in_desc"] = "Fictional blister pack found with a cracked seal on several tablets."
    else:
        ss.update(in_desc="Fictional pharmacist relays a customer report of mild headache after dosing.",
                  in_evdesc="Mild headache reported within hours of a dose.", in_onset=date.today(), in_channel="TELEPHONE")


def render() -> None:
    theme.header("New Intake", "Manually enter a fictional report received by email or telephone")
    theme.alert("warn", "🔒 <b>Do not enter real patient data.</b> No names, addresses, emails or phone numbers. "
                "Server-side validation rejects them.")
    st.write("")
    kind = st.radio("Report type", ["PQC", "AE"], horizontal=True,
                    format_func=lambda k: "Product Quality Complaint" if k == "PQC" else "Suspected Adverse Event")
    st.session_state.setdefault("in_date", date.today())
    st.session_state.setdefault("in_onset", date.today())
    st.button("✨ Fill sample (fictional) data", on_click=_sample, args=(kind,))

    with st.form("intake_form"):
        c1, c2 = st.columns(2)
        product = c1.text_input("Product name *", key="in_product")
        lot = c2.text_input("Lot number * (LOT-12345)", key="in_lot")
        c3, c4, c5 = st.columns(3)
        received = c3.date_input("Date received *", key="in_date")
        reporter = c4.selectbox("Reporter type *", REPORTERS, key="in_reporter", format_func=lambda x: x.replace("_", " ").title())
        channel = c5.selectbox("Intake channel *", ["EMAIL", "TELEPHONE"], key="in_channel")
        desc = st.text_area("Description *", key="in_desc", height=100)
        payload = {"report_type": "PRODUCT_QUALITY_COMPLAINT" if kind == "PQC" else "SUSPECTED_ADVERSE_EVENT",
                   "product_name": product, "lot_number": lot, "date_received": received.isoformat(),
                   "reporter_type": reporter, "intake_channel": channel, "description": desc}
        if kind == "AE":
            st.markdown("**Adverse event details**")
            ev = st.text_area("Event description *", key="in_evdesc", height=80)
            onset = st.date_input("Event onset date *", key="in_onset")
            payload.update(event_description=ev, event_onset_date=onset.isoformat())
        submitted = st.form_submit_button("Submit report", type="primary")

    if submitted:
        try:
            r = session.client().create_report(payload)
        except ApiError as e:
            theme.alert("bad", f"<b>Rejected by server validation</b> ({e.code})<br>" +
                        "<br>".join(theme.esc(f) for f in (e.fields or [e.message])))
            return
        ref = r["reference_id"]
        theme.alert("ok", f"✅ Report created: <span class='ref'>{ref}</span> · status NEW")
        if st.button(f"Open {ref} →"):
            session.open_report(ref)
