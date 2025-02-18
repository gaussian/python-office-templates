import re
from .parser import resolve_tag_expression
from .formatting import convert_format


def has_view_permission(obj, request_user):
    """
    Check if the request_user has permission to view obj.
    (Instead of importing Django's Model, we check for a _meta attribute.)
    """
    if not hasattr(obj, "_meta"):
        return True
    return request_user.has_perm("view", obj)


def process_text(text, context, errors=None, request_user=None, check_permissions=True):
    """
    Process text containing template tags. Each occurrence of {{ ... }} is replaced by its evaluated value.

    Special features:
      - Pipe operator for formatting: e.g. {{ now|MMM dd, YYYY }} (no quotes needed)
      - Special tag "now": if the expression starts with "now", returns timezone.now()
      - Supports filtering and nested lookups as before.

    :param text: The input text with tags.
    :param context: The context dictionary.
    :param errors: List to accumulate unresolved tag expressions.
    :param request_user: User for permission checking.
    :param check_permissions: Whether to check permissions (default True).
    """
    pattern = r"\{\{(.*?)\}\}"

    def replacer(match):
        raw_expr = match.group(1).strip()
        # Check for a pipe operator to indicate formatting.
        if "|" in raw_expr:
            parts = raw_expr.split("|", 1)
            value_expr = parts[0].strip()
            fmt_str = parts[1].strip()  # now, no quotes are expected.
            fmt_str_converted = convert_format(fmt_str)
            value = resolve_tag_expression(value_expr, context)
            if hasattr(value, "strftime"):
                try:
                    value = value.strftime(fmt_str_converted)
                except Exception:
                    if errors is not None:
                        errors.append(raw_expr)
                    return ""
            else:
                value = str(value)
        else:
            value = resolve_tag_expression(raw_expr, context)

        if check_permissions and request_user is not None:
            if isinstance(value, list):
                permitted = [
                    item for item in value if has_view_permission(item, request_user)
                ]
                if not permitted:
                    if errors is not None:
                        errors.append(raw_expr)
                    return ""
                value = permitted
            else:
                if not has_view_permission(value, request_user):
                    if errors is not None:
                        errors.append(raw_expr)
                    return ""
        if value == "" or value is None:
            if errors is not None:
                errors.append(raw_expr)
            return ""
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item is not None)
        return str(value)

    return re.sub(pattern, replacer, text)
