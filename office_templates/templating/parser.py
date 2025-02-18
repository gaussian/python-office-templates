import re
import datetime
from .resolver import get_nested_attr, evaluate_condition, parse_value


def resolve_tag_expression(expr, context):
    """
    Resolve a dotted expression (e.g. "user.name" or "program.users[is_active=True].email")
    using the given context.

    Special-case: if the first segment is "now", returns the current datetime.
    """
    segments = split_expression(expr)
    if not segments:
        return ""
    if segments[0] == "now":
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
    Split an expression into segments by periods, ignoring periods within square brackets.

    For example, "program.users[is_active=True].email" becomes:
         ["program", "users[is_active=True]", "email"]
    """
    return re.split(r"\.(?![^\[]*\])", expr)


def resolve_segment(current, segment):
    """
    Resolve one segment of a dotted expression.

    The segment can optionally include a filter in square brackets, e.g.
         "users[is_active=True]"
    For Django-like querysets (objects with a filter() method), we call filter(**filter_dict).
    For other objects, if a filter is provided, we apply manual filtering.

    If current is a list, apply resolution to each element (and flatten the result).
    """
    m = re.match(r"(\w+(?:__\w+)*)(\[(.*?)\])?$", segment)
    if not m:
        return None
    attr_name = m.group(1)
    filter_expr = m.group(3)

    # If current is a list, map resolution to each element.
    if isinstance(current, (list, tuple)):
        results = []
        for item in current:
            res = resolve_segment(item, segment)
            if isinstance(res, (list, tuple)):
                results.extend(res)
            else:
                results.append(res)
        return results

    # Get the attribute from the current object.
    value = get_nested_attr(current, attr_name)

    # If the value is a Django-like queryset (has filter method), use it.
    if value is not None and hasattr(value, "filter") and callable(value.filter):
        if filter_expr:
            filter_dict = {}
            conditions = [cond.strip() for cond in filter_expr.split(",")]
            for cond in conditions:
                m2 = re.match(r"([\w__]+)\s*=\s*(.+)", cond)
                if m2:
                    key, val = m2.groups()
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    filter_dict[key] = val
            value = value.filter(**filter_dict)
        return value
    else:
        # For non-queryset objects, if a filter is provided, apply it manually.
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
