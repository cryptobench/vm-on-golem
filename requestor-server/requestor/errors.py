class RequestorError(Exception):
    """Base class for requestor errors."""


class DomainError(RequestorError):
    """Base class for requestor domain errors."""


class NotFoundError(DomainError):
    """Requested resource was not found."""


class ConflictError(DomainError):
    """Requested operation conflicts with current state."""


class ValidationError(DomainError):
    """Domain validation failed."""


class ExternalServiceError(DomainError):
    """External boundary call failed."""


class ConfigurationError(DomainError):
    """Configuration is invalid or incomplete."""


class ProviderError(ExternalServiceError):
    """Provider communication error."""


class DiscoveryError(ExternalServiceError):
    """Discovery service error."""


class SSHError(ExternalServiceError):
    """SSH-related error."""


class ConfigError(ConfigurationError):
    """Configuration error."""


class DatabaseError(ExternalServiceError):
    """Database operation error."""


class VMError(DomainError):
    """VM operation error."""

    def __init__(self, message: str, vm_id: str = None):
        self.vm_id = vm_id
        super().__init__(message)
