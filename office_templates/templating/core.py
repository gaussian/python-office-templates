import re
from .parser import resolve_tag_expression
from .formatting import convert_format


def has_view_permission(obj, request_user):
    """
    Checks if request_user has permission to view obj.
    If obj appears to be a Django model instance (has a _meta attribute),
    returns request_user.has_perm("view", obj); otherwise, returns True.
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
          * If the entire text is a pure placeholder (i.e. the trimmed text starts with "{{" and ends with "}}"
            and contains exactly one pair of braces), then:
              - Resolve the placeholder.
              - If it resolves to a list, join its items with the delimiter.
              - Otherwise, return the resolved value.
          * If the text is mixed, substitute each placeholder. If any placeholder resolves to a list,
            raise a ValueError.
      - mode="table":
          * In pure mode, if the placeholder resolves to a list, return a list of strings (one per item).
            Otherwise, return the string.
          * In mixed mode, require exactly one placeholder and return a list of strings (one per list item).

    Permission checking:
      For each placeholder, if check_permissions is True and request_user is provided,
      then:
        - If the resolved value is a list, filter it with has_view_permission.
          If any items are denied, record an error.
        - If it’s a single object and permission fails, record an error and return an empty string.

    Note: No joining is performed in table mode.
    """
    pure = text.strip()
    # Pure placeholder if it starts with "{{" and ends with "}}" and contains exactly one pair.
    if (
        pure.startswith("{{")
        and pure.endswith("}}")
        and pure.count("{{") == 1
        and pure.count("}}") == 1
    ):
        raw_expr = pure[2:-2].strip()
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
            # else, leave value as is.
        else:
            value = resolve_tag_expression(raw_expr, context)
        # Permission check:
        if check_permissions and request_user is not None:
            if isinstance(value, list):
                permitted = [
                    item for item in value if has_view_permission(item, request_user)
                ]
                not_permitted = [
                    item for item in value if not has_view_permission(item, request_user)
                ]
                if not_permitted:
                    if errors is not None:
                        errors.append(
                            f"Permission denied for expression '{raw_expr}': {not_permitted}"
                        )
                value = permitted
            else:
                if not has_view_permission(value, request_user):
                    if errors is not None:
                        errors.append(
                            f"Permission denied for expression '{raw_expr}': {value}"
                        )
                    value = ""
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
        # Mixed text.
        if mode == "table":
            placeholders = re.findall(r"\{\{(.*?)\}\}", text)
            if len(placeholders) != 1:
                raise ValueError(
                    "Table mode supports mixed text with exactly one placeholder."
                )
            raw_expr = placeholders[0].strip()
            value = resolve_tag_expression(raw_expr, context)
            if check_permissions and request_user is not None:
                if isinstance(value, list):
                    permitted = [
                        item for item in value if has_view_permission(item, request_user)
                    ]
                    not_permitted = [
                        item
                        for item in value
                        if not has_view_permission(item, request_user)
                    ]
                    if not_permitted:
                        if errors is not None:
                            errors.append(
                                f"Permission denied for expression '{raw_expr}': {not_permitted}"
                            )
                    value = permitted
                else:
                    if not has_view_permission(value, request_user):
                        if errors is not None:
                            errors.append(
                                f"Permission denied for expression '{raw_expr}': {value}"
                            )
                        value = ""
            if not isinstance(value, list):

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
                if check_permissions and request_user is not None:
                    if isinstance(val, list):
                        permitted = [
                            item
                            for item in val
                            if has_view_permission(item, request_user)
                        ]
                        not_permitted = [
                            item
                            for item in val
                            if not has_view_permission(item, request_user)
                        ]
                        if not_permitted:
                            if errors is not None:
                                errors.append(
                                    f"Permission denied for expression '{raw_expr}': {not_permitted}"
                                )
                        val = permitted
                    else:
                        if not has_view_permission(val, request_user):
                            if errors is not None:
                                errors.append(
                                    f"Permission denied for expression '{raw_expr}': {val}"
                                )
                            val = ""
                if isinstance(val, list):
                    raise ValueError(
                        f"Cannot render list in mixed text in normal mode: {match.group(0)}"
                    )
                return str(val)

            return re.sub(r"\{\{(.*?)\}\}", replacer, text)
