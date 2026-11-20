"""Synthetic demo data loader. All records are fictional."""
from psit.domain.enums import ReportStatus
from psit.domain.models import Actor

OP = Actor("operator.demo", "INTAKE_OPERATOR")
REV = Actor("reviewer.demo", "REVIEWER")

_PRODUCTS = ["Zentrafen 50mg Tablets", "Lumivex 10mg/mL Injection", "Cardiolan 20mg Capsules", "Nebuprox Oral Solution"]

_ROWS = [
    # type, product idx, lot, date, reporter, channel, description, (event_desc, onset), final status
    ("PQC", 0, "LOT-88392", "2026-01-10", "PHARMACIST", "EMAIL", "Fictional blister pack found with a cracked seal on several tablets.", None, "CLOSED"),
    ("PQC", 0, "LOT-88392", "2026-01-14", "CONSUMER", "TELEPHONE", "Fictional caller reports tablets crumbling when removed from the blister.", None, "IN_REVIEW"),
    ("PQC", 1, "LOT-45107", "2026-02-02", "HEALTHCARE_PROFESSIONAL", "EMAIL", "Vial contained visible particulate matter after reconstitution in a fictional ward.", None, "IN_REVIEW"),
    ("PQC", 2, "LOT-12654", "2026-02-11", "DISTRIBUTOR", "EMAIL", "Outer carton label printed with a smudged expiry date.", None, "NEW"),
    ("PQC", 3, "LOT-70018", "2026-03-03", "CONSUMER", "TELEPHONE", "Bottle cap did not seal properly; liquid leaked in transit.", None, "NEW"),
    ("PQC", 1, "LOT-45107", "2026-03-09", "PHARMACIST", "EMAIL", "Second fictional complaint of cloudy solution in the same lot.", None, "NEW"),
    ("AE", 0, "LOT-88392", "2026-01-20", "HEALTHCARE_PROFESSIONAL", "TELEPHONE", "Fictional clinician reports a patient experienced mild nausea after dosing.", ("Mild nausea reported within hours of a dose.", "2026-01-18"), "IN_REVIEW"),
    ("AE", 2, "LOT-12654", "2026-02-15", "CONSUMER", "EMAIL", "Fictional consumer reports dizziness after starting the product.", ("Dizziness on standing, resolved the same day.", "2026-02-13"), "NEW"),
    ("AE", 3, "LOT-70018", "2026-03-12", "PHARMACIST", "TELEPHONE", "Fictional pharmacist relays a customer report of skin rash.", ("Localized rash noted two days after first use.", "2026-03-08"), "NEW"),
    ("AE", 1, "LOT-45107", "2026-03-20", "HEALTHCARE_PROFESSIONAL", "EMAIL", "Fictional nurse reports injection-site redness.", ("Redness and mild swelling at injection site.", "2026-03-19"), "NEW"),
]


_PQC_TEXT = [
    "Fictional blister pack with a cracked seal; several units exposed to air.",
    "Caller says the tablets crumble to powder when pressed out of the foil.",
    "Visible floating particles in the solution after the vial was shaken.",
    "Carton label has a smudged expiry date that is hard to read.",
    "The bottle cap does not close tightly and liquid leaked out during delivery.",
    "Tablets inside one strip appear discoloured with brown spots.",
    "Patient information leaflet was missing from the sealed carton.",
    "The dosing cup supplied in the box has no measurement markings.",
]
_AE_TEXT = [
    ("Fictional report of a mild headache after the first dose.", "Mild headache starting a few hours after dosing."),
    ("Reporter mentions feeling queasy and nauseous following administration.", "Nausea the same evening, lasting several hours."),
    ("A fictional consumer describes an itchy red rash on the forearm.", "Itchy rash on the forearm appearing two days after use."),
    ("Caller reports lightheadedness when standing up after taking the capsule.", "Brief dizziness on standing, resolved by sitting."),
    ("Nurse reports redness and swelling around the injection site.", "Localised redness and swelling at the injection site."),
    ("Fictional caller reports unusual tiredness during the week of treatment.", "Persistent fatigue for several days."),
]
_LOTS = ["LOT-88392", "LOT-45107", "LOT-12654", "LOT-70018", "LOT-33821", "LOT-90514"]


def _extra_rows():
    import itertools
    from datetime import date, timedelta
    rows, d0 = [], date(2025, 3, 1)
    for i in range(26):
        p = i % 4
        lot = _LOTS[(i * 5 + p) % 6]
        when = (d0 + timedelta(days=17 * i)).isoformat()
        rep = ["PHARMACIST", "CONSUMER", "HEALTHCARE_PROFESSIONAL", "DISTRIBUTOR"][i % 4]
        ch = ["EMAIL", "TELEPHONE"][i % 2]
        final = ["CLOSED", "CLOSED", "IN_REVIEW", "NEW"][i % 4]
        if i % 3 == 2:
            a = _AE_TEXT[i % len(_AE_TEXT)]
            rows.append(("AE", p, lot, when, rep, ch, a[0], (a[1], (date.fromisoformat(when) - timedelta(days=2)).isoformat()), final))
        else:
            rows.append(("PQC", p, lot, when, rep, ch, _PQC_TEXT[i % len(_PQC_TEXT)], None, final))
    return rows


def load_demo_data(intake, workflow, approvals) -> int:
    if intake.stats()["total"] > 0:
        return 0
    n = 0
    for typ, p, lot, d, rep, ch, desc, ae, final in _extra_rows() + _ROWS:
        data = {"report_type": "PRODUCT_QUALITY_COMPLAINT" if typ == "PQC" else "SUSPECTED_ADVERSE_EVENT",
                "product_name": _PRODUCTS[p], "lot_number": lot, "date_received": __import__("datetime").date.fromisoformat(d),
                "reporter_type": rep, "intake_channel": ch, "description": desc}
        if ae:
            data["event_description"] = ae[0]
            data["event_onset_date"] = __import__("datetime").date.fromisoformat(ae[1])
        ref = intake.create(data, OP, "seed").reference_id
        n += 1
        if final in ("IN_REVIEW", "CLOSED"):
            workflow.transition(ref, ReportStatus.IN_REVIEW, OP, "seed")
        if final == "CLOSED":
            a = approvals.request_closure(ref, "Fictional demo closure", OP, "seed")
            approvals.approve(a.id, "Reviewed (demo)", REV, "seed")
    return n
