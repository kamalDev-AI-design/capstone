from enum import StrEnum


class ReportType(StrEnum):
    SUSPECTED_ADVERSE_EVENT = "SUSPECTED_ADVERSE_EVENT"
    PRODUCT_QUALITY_COMPLAINT = "PRODUCT_QUALITY_COMPLAINT"


class ReportStatus(StrEnum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    CLOSED = "CLOSED"


class IntakeChannel(StrEnum):
    EMAIL = "EMAIL"
    TELEPHONE = "TELEPHONE"
    # Future: WEB_PORTAL, MANUAL_ENTRY, CHAT (stored as plain strings; no schema change needed)


class ReporterType(StrEnum):
    HEALTHCARE_PROFESSIONAL = "HEALTHCARE_PROFESSIONAL"
    PHARMACIST = "PHARMACIST"
    CONSUMER = "CONSUMER"
    DISTRIBUTOR = "DISTRIBUTOR"
    OTHER = "OTHER"


class ActorRole(StrEnum):
    INTAKE_OPERATOR = "INTAKE_OPERATOR"
    REVIEWER = "REVIEWER"
    AGENT = "AGENT"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
