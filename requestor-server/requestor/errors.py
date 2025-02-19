class RequestorError(Exception):
    """Base class for requestor errors."""
    pass

class ProviderError(RequestorError):
    """Provider communication error."""
    pass

class DiscoveryError(RequestorError):
    """Discovery service error."""
    pass

class SSHError(RequestorError):
    """SSH-related error."""
    pass

class ConfigError(RequestorError):
    """Configuration error."""
    pass

class DatabaseError(RequestorError):
    """Database operation error."""
    pass

class VMError(RequestorError):
    """VM operation error."""
    def __init__(self, message: str, vm_id: str = None):
        self.vm_id = vm_id
        super().__init__(message)
