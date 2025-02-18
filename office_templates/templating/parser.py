import re
import datetime
from .resolver import get_nested_attr, evaluate_condition, parse_value


def resolve_tag_expression(expr, context):
    """
    Resolve an expression (e.g., "user.name" or "program.users[is_active=True].email").
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
    # If current is a Django manager/queryset, call .all() to get a QuerySet.
    if hasattr(current, "all") and callable(current.all):
        current = current.all()
    for seg in segments[1:]:
        current = resolve_segment(current, seg)
        if current is None:
            return ""
    return current


def split_expression(expr):
    """
    Split the expression into segments by periods but ignore periods inside square brackets.
    For example, "program.users[is_active=True].email" becomes:
       ['program', 'users[is_active=True]', 'email']
    """
    return re.split(r"\.(?![^\[]*\])", expr)


def resolve_segment(current, segment):
    """
    Resolve one segment. A segment is of the form:
       attribute_name[optional_filter]
    where attribute_name can use double-underscores for nested lookup.
    If a filter is specified (e.g. [is_active=True]), and if current is a Django QuerySet,
    then perform a .filter() call with the parsed filter conditions.
    Otherwise, if current is a list/tuple or plain object/dict, use get_nested_attr and filter.
    """
    m = re.match(r"(\w+(?:__\w+)*)(\[(.*?)\])?$", segment)
    if not m:
        return None
    attr_name = m.group(1)
    filter_expr = m.group(3)

    # For Django querysets, if current has a "filter" method, we assume we can use it.
    if hasattr(current, "filter") and callable(current.filter):
        # Get the attribute from each object? In a queryset, accessing a related field
        # is handled by Django’s ORM. So first, get the queryset corresponding to attr_name.
        qs = getattr(current, attr_name, None)
        if qs is None:
            # Try treating current as a model instance.
            qs = get_nested_attr(current, attr_name)
        else:
            # If qs is a manager, get the queryset.
            if hasattr(qs, "all") and callable(qs.all):
                qs = qs.all()
        # If a filter is provided, parse it into a dict and apply.
        if filter_expr:
            filter_dict = {}
            conditions = [cond.strip() for cond in filter_expr.split(",")]
            for cond in conditions:
                m2 = re.match(r"([\w__]+)\s*=\s*(.+)", cond)
                if not m2:
                    continue
                key, val = m2.groups()
                # Remove surrounding quotes if present.
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                filter_dict[key] = val
            qs = qs.filter(**filter_dict)
        return qs
    else:
        # For non-queryset objects.
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
