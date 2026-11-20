class DomainError(Exception):
    code = "DOMAIN_ERROR"
    http_status = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class InvalidTransitionError(DomainError):
    code = "INVALID_TRANSITION"
    http_status = 409


class ApprovalRequiredError(DomainError):
    code = "APPROVAL_REQUIRED"
    http_status = 409


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    http_status = 403


class VersionConflictError(DomainError):
    code = "VERSION_CONFLICT"
    http_status = 409


class ConflictError(DomainError):
    code = "CONFLICT"
    http_status = 409
