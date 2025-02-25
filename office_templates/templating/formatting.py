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
