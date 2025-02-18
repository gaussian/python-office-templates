import re
import datetime

from .resolver import get_nested_attr, evaluate_condition


def resolve_tag_expression(expr, context):
    """
    Resolve an expression (e.g., "user.name" or "program.users[is_active==True].email").
    Special-case: if the first segment is "now", return datetime.datetime.now().
    """
    segments = split_expression(expr)
    if not segments:
        return ""
    if segments[0] == "now":
        current = datetime.datetime.now()
    else:
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
    Split the expression into segments by periods but ignore periods inside square brackets.
    Example: "program.users[is_active==True].email" becomes:
       ['program', 'users[is_active==True]', 'email']
    """
    return re.split(r"\.(?![^\[]*\])", expr)


def resolve_segment(current, segment):
    """
    Resolve one segment of the expression.
    A segment is of the form: attribute_name[optional_filter]
    where attribute_name can use double-underscores for nested lookup.
    """
    m = re.match(r"(\w+(?:__\w+)*)(\[(.*?)\])?$", segment)
    if not m:
        return None
    attr_name = m.group(1)
    filter_expr = m.group(3)

    if isinstance(current, (list, tuple)):
        values = [get_nested_attr(item, attr_name) for item in current]
    else:
        values = get_nested_attr(current, attr_name)

    if filter_expr:
        if not isinstance(values, list):
            values = [values]
        conditions = [cond.strip() for cond in filter_expr.split(",")]
        values = [
            item
            for item in values
            if all(evaluate_condition(item, cond) for cond in conditions)
        ]
    return values
