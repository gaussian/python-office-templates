class UnsupportedFileType(Exception):
    """Raised when the file type is not supported."""

    pass


class UnterminatedTagException(Exception):
    """Raised when a template tag starting with '{{' is not terminated by '}}' in the same paragraph."""

    pass


class UnresolvedTagError(Exception):
    """Raised when one or more template tags could not be resolved."""

    pass


class TableError(Exception):
    """Raised when an error occurs while processing a table."""

    pass


class CellOverwriteError(Exception):
    """Raised when a table/spreadsheet cell would be overwritten with a new value."""

    pass


class ChartError(Exception):
    """Raised when an error occurs while processing a chart."""

    pass


class ImageError(Exception):
    """Raised when an error occurs while processing an image."""

    pass
