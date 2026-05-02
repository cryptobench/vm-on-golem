class DomainError(Exception):
    """Base class for provider domain errors."""


class NotFoundError(DomainError):
    """Requested resource was not found."""


class ConflictError(DomainError):
    """Requested operation conflicts with current state."""


class ValidationError(DomainError):
    """Domain validation failed."""


class ExternalServiceError(DomainError):
    """External boundary call failed."""
