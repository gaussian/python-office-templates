class BadTagException(Exception):
    """Raised when a template tag has a bad format."""

    pass


class MissingDataException(Exception):
    """Raised when a template tag's value can't be found."""

    pass
