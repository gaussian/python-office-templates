def convert_format(custom_format):
    """
    Convert a custom date format string into a Python strftime format.

    Custom tokens:
      - MMMM : Full month name (e.g., January)  -> %B
      - MMM  : Abbreviated month name (e.g., Jan) -> %b
      - MM   : Zero-padded month number         -> %m
      - YYYY : 4-digit year                     -> %Y
      - YY   : 2-digit year                     -> %y
      - dd   : Zero-padded day of month         -> %d
      - DD   : Full weekday name                -> %A
      - ddd  : Abbreviated weekday name         -> %a
      - HH   : 24-hour clock hour               -> %H
      - hh   : 12-hour clock hour               -> %I
      - mm   : Minute                           -> %M
      - ss   : Second                           -> %S

    You can extend this mapping as needed.
    """
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
    # Replace longer tokens first to avoid partial replacement.
    for token in sorted(mapping.keys(), key=lambda x: -len(x)):
        custom_format = custom_format.replace(token, mapping[token])
    return custom_format
