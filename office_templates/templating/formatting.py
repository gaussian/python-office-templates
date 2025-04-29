"""
Converts custom date format tokens to Python's strftime format.
Supported tokens:
  - MMMM -> %B (full month name)
  - MMM  -> %b (abbreviated month name)
  - MM   -> %m (zero-padded month number)
  - YYYY -> %Y (4-digit year)
  - YY   -> %y (2-digit year)
  - dd   -> %d (zero-padded day)
  - DD   -> %A (full weekday name)
  - ddd  -> %a (abbreviated weekday name)
  - HH   -> %H (24-hour)
  - hh   -> %I (12-hour)
  - mm   -> %M (minute)
  - ss   -> %S (second)
"""

from .exceptions import BadTagException


def convert_date_format(custom_format):
    mapping = {
        "MMMM": "%B",
        "MMM": "%b",
        "MM": "%m",
        "YYYY": "%Y",
        "YY": "%y",
        "dd": "%d",
        "DD": "%A",
        "ddd": "%a",
        "HH": "%H",
        "hh": "%I",
        "mm": "%M",
        "ss": "%S",
    }
    # Replace longer tokens first.
    for token in sorted(mapping.keys(), key=lambda k: -len(k)):
        custom_format = custom_format.replace(token, mapping[token])
    return custom_format


def format_value(value, format_expr):
    """
    Formats a value using a custom format string.

    This function supports:
      - Date formatting with custom tokens (e.g., 'MMMM, dd, YYYY' or '%Y-%m-%d')
      - Numeric formatting (e.g., '.2f' for two decimal places)
      - String case transformations ('upper', 'lower', 'capitalize')

    Options for format_expr:
        Date/time:    %Y, %m, %d, %A, %a, %I, %H, %M, %S, %p, MMMM, MMM, MM, dd, etc.
        Numeric:      .2f, .0f, d, etc.
        String case:  upper, lower, capitalize

    Examples:
       %Y-%m-%d         # Formats current date as '2024-06-01'
       MMMM, dd, YYYY   # Formats as 'June, 01, 2024'
       .2f              # Formats number as '3.14'
       upper            # Converts string to uppercase
       lower            # Converts string to lowercase
       capitalize       # Converts string to uppercase (same as 'upper')
       title            # Converts string to title case (all word initials uppercase)
       %A               # Formats date as full weekday name, e.g., 'Monday'
       %I:%M %p         # Formats time as '01:30 PM'
    """
    try:
        # Handle uppercase/lowercase.
        if format_expr in ("upper", "capitalize"):
            return str(value).upper()
        if format_expr == "lower":
            return str(value).lower()
        if format_expr == "title":
            return str(value).title()

        # Convert the format string to a date format if necessary.
        format_expr = convert_date_format(format_expr)

        # Now use the default python formatting for dates, numbers, etc
        return format(value, format_expr)

    except Exception as e:
        raise BadTagException(
            f"Error formatting value '{value}' with format '{format_expr}': {str(e)}"
        )

    return value

    # If the format string contains a comma, split it to retrieve multiple attributes.
    # elif "," in format_expr:
    #     attrs = [a.strip() for a in format_expr.split(",")]
    #     return tuple(
    #         resolve_tag(f"{value_expr}.{attr}", context, perm_user=perm_user)
    #         for attr in attrs
    #     )
