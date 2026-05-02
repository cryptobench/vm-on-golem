class DomainError(Exception):
    """Base error for port-checker domain failures."""


class ValidationError(DomainError):
    """The request was syntactically valid but violates domain rules."""


class ForbiddenError(DomainError):
    """The request is not allowed by proxy policy."""


class NotFoundError(DomainError):
    """The requested provider or route target was not found."""


class ProxyDisabledError(NotFoundError):
    """Proxy routes are intentionally hidden when disabled."""


class PayloadTooLargeError(DomainError):
    """Request body exceeds configured proxy limits."""


class GatewayTimeoutError(DomainError):
    """A dependency or upstream provider timed out."""


class BadGatewayError(DomainError):
    """A dependency or upstream provider failed."""


class DependencyUnavailableError(DomainError):
    """A configured optional dependency is unavailable."""


class ConfigurationError(DomainError):
    """The service is missing required runtime configuration."""
