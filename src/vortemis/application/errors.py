class ApplicationError(Exception):
    """Base class for application failures that adapters translate."""


class InvalidQueryError(ValueError):
    """The supplied query is out of range or malformed."""


class NotFoundError(ApplicationError):
    """The requested resource does not exist."""


class PermissionDeniedError(ApplicationError):
    """The operator lacks the role required for the operation."""
