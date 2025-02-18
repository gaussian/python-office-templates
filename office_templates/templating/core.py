import re
from .parser import resolve_tag_expression
from .formatting import convert_format


def has_view_permission(obj, request_user):
    """
    Checks if the request_user has permission to view obj.
    If obj appears to be a Django model instance (has a _meta attribute),
    then returns request_user.has_perm("view", obj). Otherwise, returns False.
    """
    if request_user is None:
        return False
    if hasattr(obj, "_meta"):
        return request_user.has_perm("view", obj)
    return False


def process_text(
    text,
    context,
    errors=None,
    request_user=None,
    check_permissions=True,
    mode="normal",
    delimiter=", ",
):
    """
    Process text containing template tags.

    Modes:
      - mode="normal":
          * If the entire text is exactly a pure placeholder (e.g. "{{ ... }}"):
              - If it resolves to a list, join the items with the delimiter.
              - Otherwise, return the value.
          * If the text is mixed, substitute each placeholder. If any placeholder resolves
            to a list, a ValueError is raised.
      - mode="table":
          * If the text is pure (only one placeholder), and it resolves to a list,
            return a list of strings—each with the placeholder replaced by one item.
          * If the text is mixed, require that there is exactly one placeholder; then produce a list.

    Permission checking:
      For each placeholder, if check_permissions is True and a request_user is provided,
      then for the resolved value (or each value in a list) we check has_view_permission.
      If the check fails, the placeholder is treated as unresolved (an empty string or omitted from a list).

    No joining is performed in table mode.
    """
    pure_pattern = r"^\s*\{\{(.*?)\}\}\s*$"
    m = re.match(pure_pattern, text)
    if m:
        raw_expr = m.group(1).strip()
        # Handle formatting pipe operator.
        if "|" in raw_expr:
            parts = raw_expr.split("|", 1)
            value_expr = parts[0].strip()
            fmt_str = parts[1].strip()
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
                # For non-date values, just use str()
                value = str(value)
        else:
            value = resolve_tag_expression(raw_expr, context)
        # Permission check:
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
        # Return based on mode.
        if mode == "normal":
            if isinstance(value, list):
                return delimiter.join(str(item) for item in value if item is not None)
            else:
                return value
        elif mode == "table":
            if isinstance(value, list):
                return [str(item) for item in value if item is not None]
            else:
                return str(value)
    else:
        # Mixed text mode.
        placeholders = re.findall(r"\{\{(.*?)\}\}", text)
        if mode == "table":
            if len(placeholders) != 1:
                raise ValueError(
                    "Table mode supports mixed text with exactly one placeholder."
                )
            raw_expr = placeholders[0].strip()
            value = resolve_tag_expression(raw_expr, context)
            # Permission check for table mode:
            if check_permissions and request_user is not None:
                if isinstance(value, list):
                    value = [
                        item for item in value if has_view_permission(item, request_user)
                    ]
                else:
                    if not has_view_permission(value, request_user):
                        value = ""
            if not isinstance(value, list):
                # Substitute normally.
                def replacer(match):
                    return str(resolve_tag_expression(match.group(1).strip(), context))

                return re.sub(r"\{\{(.*?)\}\}", replacer, text)
            else:
                results = []
                for item in value:

                    def replacer(match):
                        return str(item)

                    results.append(re.sub(r"\{\{(.*?)\}\}", replacer, text))
                return results
        else:

            def replacer(match):
                raw_expr = match.group(1).strip()
                val = resolve_tag_expression(raw_expr, context)
                # Permission check for each placeholder.
                if check_permissions and request_user is not None:
                    if isinstance(val, list):
                        permitted = [
                            item
                            for item in val
                            if has_view_permission(item, request_user)
                        ]
                        val = permitted
                    else:
                        if not has_view_permission(val, request_user):
                            val = ""
                if isinstance(val, list):
                    raise ValueError(
                        f"Cannot render list in mixed text in normal mode: {match.group(0)}"
                    )
                return str(val)

            return re.sub(r"\{\{(.*?)\}\}", replacer, text)
