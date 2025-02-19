class BadTagException(Exception):
    """Raised when a template tag has a bad format."""

    pass


class MissingDataException(Exception):
    """Raised when a template tag's value can't be found."""

    pass


class TagCallableException(Exception):
    """Raised when a callable in a tag throws an exception."""

    pass


class PermissionDeniedException(Exception):
    """Raised when one or more expressions fail the permission check."""

    def __init__(self, errors):
        self.errors = errors
        msg = "Permission denied for the following expressions: " + ", ".join(errors)
        super().__init__(msg)
