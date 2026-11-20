import pytest
from fastapi.testclient import TestClient

from psit.api.app import create_app
from psit.infra.config import Settings

OP = {"X-Actor-Id": "operator.demo", "X-Actor-Role": "INTAKE_OPERATOR"}
REV = {"X-Actor-Id": "reviewer.demo", "X-Actor-Role": "REVIEWER"}
REV2 = {"X-Actor-Id": "reviewer.two", "X-Actor-Role": "REVIEWER"}
AGENT = {"X-Actor-Id": "agent.psit", "X-Actor-Role": "AGENT"}

PQC = {
    "report_type": "PRODUCT_QUALITY_COMPLAINT", "product_name": "Zentrafen 50mg Tablets", "lot_number": "LOT-88392",
    "date_received": "2026-01-10", "reporter_type": "PHARMACIST", "intake_channel": "EMAIL",
    "description": "Fictional blister pack found with a cracked seal.",
}
AE = {
    **PQC, "report_type": "SUSPECTED_ADVERSE_EVENT", "intake_channel": "TELEPHONE",
    "event_description": "Fictional report of mild headache after dose.", "event_onset_date": "2026-01-09",
}


@pytest.fixture()
def app(tmp_path):
    return create_app(Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", auto_migrate=True))


@pytest.fixture()
def client(app):
    return TestClient(app)
