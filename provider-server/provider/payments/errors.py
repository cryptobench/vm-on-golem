from provider.errors import ExternalServiceError, NotFoundError, ValidationError


class PaymentsDisabledError(ValidationError):
    """Streaming payments are not configured for this provider."""


class StreamNotFoundError(NotFoundError):
    """No stream mapping exists for a VM."""


class InvalidStreamError(ValidationError):
    """A stream exists but does not satisfy provider requirements."""


class StreamLookupError(ExternalServiceError):
    """Stream lookup failed at the chain boundary."""
