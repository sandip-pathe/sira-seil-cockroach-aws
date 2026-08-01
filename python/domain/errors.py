"""Domain-layer exceptions with no transport-specific behavior."""


class DomainValidationError(ValueError):
    """Raised when an object would violate a domain invariant."""


class InvalidTransitionError(DomainValidationError):
    """Raised when an aggregate state transition is not allowed."""
