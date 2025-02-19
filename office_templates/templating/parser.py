import re
import datetime

from .exceptions import BadTagException, MissingDataException
from .formatting import convert_format
from .resolver import get_nested_attr, evaluate_condition

ALLOWED_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9,\s\[\]\'\"_\-=]*$")


def parse_formatted_tag(expr: str, context):
    """
    New helper that checks for the pipe operator '|' in the expression.
    If found, splits the expression into the value expression and format string.
    For date/datetime values, applies formatting using convert_format().
    Otherwise, returns the string representation of the resolved value.
    If no pipe operator is found, delegates to resolve_tag_expression().
    """

    # Validate that expression does not contain '{' or '}'.
    if "{" in expr or "}" in expr:
        raise BadTagException(
            f"Bad format in tag '{expr}': unexpected curly brace detected."
        )

    # Split the expression by the pipe operator ("|").
    parts = expr.split("|", 1)
    value_expr = parts[0].strip()

    # Pipe operator found
    fmt_str = None
    if len(parts) == 2:
        fmt_str = parts[1].strip()

        # Remove surrounding quotes, if present.
        if (fmt_str.startswith('"') and fmt_str.endswith('"')) or (
            fmt_str.startswith("'") and fmt_str.endswith("'")
        ):
            fmt_str = fmt_str[1:-1]

    # Resolve the tag value itself, excluding any pipe operator.
    value = resolve_tag_expression(value_expr, context)

    if fmt_str and hasattr(value, "strftime"):
        try:
            return value.strftime(convert_format(fmt_str))
        except Exception as e:
            raise BadTagException(f"Bad format in tag '{expr}': {e}.")
    else:
        return value


def resolve_tag_expression(expr, context):
    """
    Resolve a dotted expression (e.g. "user.name", "program.users[is_active=True].email").

    Special-case: If the first segment is "now", returns the current datetime.
    """
    segments = split_expression(expr)
    if not segments:
        return ""
    first_segment = segments[0]
    if not first_segment:
        return ""

    # Validate all segments are valid
    if not all(bool(ALLOWED_SEGMENT_PATTERN.fullmatch(s)) for s in segments):
        raise BadTagException(f"Bad characters in tag segments: {segments}")

    # Special case: "now" returns a datetime
    if first_segment.strip() == "now":
        return datetime.datetime.now()

    # Iterate over the segments
    current = context
    for seg in segments:
        current = resolve_segment(current, seg)
        if current is None:
            return ""

    return current


def split_expression(expr):
    """
    Split an expression into segments by periods, ignoring periods inside [ ].
    e.g. "program.users[is_active=True].email" -> ["program", "users[is_active=True]", "email"]
    """
    return re.split(r"\.(?![^\[]*\])", expr)


def resolve_segment(current, segment):
    """
    Resolve one segment of a dotted expression. A segment may include an optional filter in brackets,
    e.g. "users[is_active=True]".

    - If current is a list, we apply resolution to each item and flatten the results.
    - If the value is a "QuerySet-like" object (has filter method), we either:
        * apply filter(**filter_dict) if bracket expression is given
        * or call .all() if available, then convert it to a list
      and then we continue resolution if there are more segments (by returning that list).
    - If filter_expr is present for a non-queryset, we manually filter items in a list.

    """
    m = re.match(r"(\w+(?:__\w+)*)(\[(.*?)\])?$", segment)
    if not m:
        raise MissingDataException(f"{segment} not in {current}")

    attr_name = m.group(1)
    filter_expr = m.group(3)

    # 1) If current is a list, apply resolution to each item
    if isinstance(current, list):
        results = []
        for item in current:
            res = resolve_segment(item, segment)
            if isinstance(res, list):
                results.extend(res)
            else:
                results.append(res)
        # List results
        return results

    # 2) Get the attribute from the current object
    value = get_nested_attr(current, attr_name)

    # 3) If it's a "Django-like" QuerySet that has .filter(...)
    if value is not None and hasattr(value, "filter") and callable(value.filter):
        # If we have a filter expression in brackets, parse it
        if filter_expr:
            conditions = [c.strip() for c in filter_expr.split(",")]
            filter_dict = {}
            for cond in conditions:
                # e.g. is_active=True
                m2 = re.match(r"([\w__]+)\s*=\s*(.+)", cond)
                if m2:
                    key, val = m2.groups()
                    val = val.strip()
                    # strip quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    filter_dict[key] = val
            value = value.filter(**filter_dict)
        else:
            # No filter expression - treat it like .all()
            if hasattr(value, "all") and callable(value.all):
                value = value.all()
        # Convert the QuerySet to a list for further resolution if there's another segment
        return list(value)

    else:
        # 4) If there's a filter expression on a non-queryset, treat 'value' as a list and filter it
        if filter_expr:
            if not isinstance(value, list):
                value = [value]
            conditions = [cond.strip() for cond in filter_expr.split(",")]
            value = [
                item
                for item in value
                if all(evaluate_condition(item, cond) for cond in conditions)
            ]
        return value
