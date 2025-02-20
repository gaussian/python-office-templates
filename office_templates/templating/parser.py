import re
import datetime


from .exceptions import BadTagException, MissingDataException, TagCallableException
from .formatting import convert_format
from .permissions import enforce_permissions
from .resolver import get_nested_attr, evaluate_condition, parse_callable_args

BAD_SEGMENT_PATTERN = re.compile(r"^[#%]*$")


def parse_formatted_tag(expr: str, context, perm_user=None):
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
    value = resolve_tag_expression(
        value_expr,
        context,
        perm_user=perm_user,
    )

    if fmt_str and hasattr(value, "strftime"):
        try:
            return value.strftime(convert_format(fmt_str))
        except Exception as e:
            raise BadTagException(f"Bad format in tag '{expr}': {e}.")
    else:
        return value


def resolve_tag_expression(expr, context, perm_user=None):
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
    if any(bool(BAD_SEGMENT_PATTERN.fullmatch(s)) for s in segments):
        raise BadTagException(f"Bad characters in tag segments: {segments}")

    # Special case: "now" returns a datetime
    if first_segment.strip() == "now":
        return datetime.datetime.now()

    # Iterate over the segments
    current = context
    for seg in segments:
        current = resolve_segment(
            current,
            seg,
            perm_user=perm_user,
        )
        if current is None:
            return ""

    return current


def split_expression(expr):
    """
    Split an expression into segments by periods, ignoring periods inside [ ].
    e.g. "program.users[is_active=True].email" -> ["program", "users[is_active=True]", "email"]
    """
    return re.split(r"\.(?![^\[]*\])", expr)


def resolve_segment(current, segment, perm_user=None):
    """
    Resolve one segment of a dotted expression. Supports an optional callable part.
    For example: "custom_function()" or "custom_function(arg1,123)"
    and an optional filter in brackets.
    """
    # Edge case handling: Check for unmatched round or square brackets.
    if segment.count("(") != segment.count(")"):
        raise BadTagException(f"Unmatched round brackets in segment: '{segment}'")
    if segment.count("[") != segment.count("]"):
        raise BadTagException(f"Unmatched square brackets in segment: '{segment}'")

    # Updated regex captures optional callable arguments in parentheses and an optional filter.
    m = re.match(r"^(\w+(?:__\w+)*)(?:\((.*?)\))?(?:\[(.*?)\])?$", segment)
    if not m:
        raise BadTagException(f"Segment '{segment}' is malformed")
    attr_name = m.group(1)
    call_args_str = m.group(2)  # may be None
    filter_expr = m.group(3)  # may be None

    # If current is a list, apply resolution for each item.
    if isinstance(current, list):
        results = []
        for item in current:
            res = resolve_segment(item, segment, perm_user=perm_user)
            if isinstance(res, list):
                results.extend(res)
            else:
                results.append(res)
        return results

    # Retrieve the attribute.
    try:
        value = get_nested_attr(current, attr_name)
    except (AttributeError, KeyError) as e:
        raise MissingDataException(f"{segment} not found in {current}")

    # If a callable part is provided, call the function.
    if call_args_str is not None:
        if not callable(value):
            raise TagCallableException(f"Attribute '{attr_name}' is not callable.")
        # Parse the comma-separated arguments; only int, float, and str are allowed.
        args = parse_callable_args(call_args_str)
        try:
            value = value(*args)
        except Exception as e:
            raise TagCallableException(
                f"Error calling '{attr_name}' with arguments {args}: {e}"
            )

    # ...existing code to handle QuerySet-like filtering and permissions...
    if value is not None and hasattr(value, "filter") and callable(value.filter):
        if filter_expr:
            conditions = [c.strip() for c in filter_expr.split(",")]
            filter_dict = {}
            for cond in conditions:
                m2 = re.match(r"([\w__]+)\s*=\s*(.+)", cond)
                if m2:
                    key, val = m2.groups()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    filter_dict[key] = val
            value = value.filter(**filter_dict)
        else:
            if hasattr(value, "all") and callable(value.all):
                value = value.all()
        return list(value)

    else:
        value_list = value if isinstance(value, list) else [value]
        if filter_expr:
            conditions = [cond.strip() for cond in filter_expr.split(",")]
            value = [
                item
                for item in value_list
                if all(evaluate_condition(item, cond) for cond in conditions)
            ]
        for value_item in value_list:
            enforce_permissions(value_item, perm_user)
        return value
