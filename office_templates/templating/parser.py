import re
import datetime

from .formatting import convert_format
from .resolver import get_nested_attr, evaluate_condition


def parse_formatted_tag(expr, context, errors=None):
    """
    New helper that checks for the pipe operator '|' in the expression.
    If found, splits the expression into the value expression and format string.
    For date/datetime values, applies formatting using convert_format().
    Otherwise, returns the string representation of the resolved value.
    If no pipe operator is found, delegates to resolve_tag_expression().

    Additional validation:
      - If the value expression or format string contains unexpected curly braces,
        an error is recorded (if errors is provided) and an empty string is returned.
    """
    if "|" in expr:
        parts = expr.split("|", 1)
        value_expr = parts[0].strip()
        fmt_str = parts[1].strip()

        # Validate that neither the value expression nor format string contains '{' or '}'.
        if "{" in value_expr or "}" in value_expr or "{" in fmt_str or "}" in fmt_str:
            if errors is not None:
                errors.append(
                    f"Bad format in tag '{expr}': unexpected curly brace detected."
                )
            return ""

        # Remove surrounding quotes, if present.
        if (fmt_str.startswith('"') and fmt_str.endswith('"')) or (
            fmt_str.startswith("'") and fmt_str.endswith("'")
        ):
            fmt_str = fmt_str[1:-1]
        value = resolve_tag_expression(value_expr, context)

        if hasattr(value, "strftime"):
            try:
                return value.strftime(convert_format(fmt_str))
            except Exception as e:
                if errors is not None:
                    errors.append(f"Formatting error for '{expr}': {e}")
                return ""
        else:
            return str(value)
    else:
        # Also check for stray curly braces in a non-formatted tag.
        if "{" in expr or "}" in expr:
            if errors is not None:
                errors.append(f"Bad tag '{expr}': unexpected curly brace.")
            return ""
        return resolve_tag_expression(expr, context)


def resolve_tag_expression(expr, context):
    """
    Resolve a dotted expression (e.g. "user.name", "program.users[is_active=True].email").

    Special-case: If the first segment is "now", returns the current datetime.
    """
    segments = split_expression(expr)
    if not segments:
        return ""
    # "now" returns a datetime
    if segments[0].strip() == "now":
        return datetime.datetime.now()

    current = context.get(segments[0])
    if current is None:
        return ""

    for seg in segments[1:]:
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
        return None

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
        # Flattened results
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
