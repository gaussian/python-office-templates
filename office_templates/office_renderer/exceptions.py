class UnterminatedTagException(Exception):
    """Raised when a template tag starting with '{{' is not terminated by '}}' in the same paragraph."""

    pass


class UnresolvedTagError(Exception):
    """Raised when one or more template tags could not be resolved."""

    pass


class TableError(Exception):
    """Raised when an error occurs while processing a table."""

    pass


class TableCellOverwriteError(Exception):
    """Raised when a table cell is overwritten with a new value."""

    pass


class ChartError(Exception):
    """Raised when an error occurs while processing a chart."""

    pass


class BadChartDataResultError(Exception):
    """Raised when a processed value is invalid (i.e. result is not a float)."""

    pass
