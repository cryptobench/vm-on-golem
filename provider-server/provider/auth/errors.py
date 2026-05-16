from provider.errors import DomainError


class AuthError(DomainError):
    """Base class for provider authorization failures."""


class UnauthorizedError(AuthError):
    """Authentication is missing or invalid."""


class ForbiddenError(AuthError):
    """Authenticated identity is not allowed to access the resource."""
