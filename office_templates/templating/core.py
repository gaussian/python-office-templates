import re
from .parser import resolve_tag_expression
from .formatting import convert_format
from .permissions import enforce_permissions


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
    Resolve template tags in `text` using the context. Two modes: "normal" or "table".

    - In "normal" mode:
        * If the entire text is exactly one placeholder (pure mode), and the value is a list, join it with `delimiter`.
        * If it's mixed text, each placeholder is replaced inline. If a placeholder resolves to a list, we join it.

    - In "table" mode:
        * If the entire text is exactly one placeholder (pure), and the value is a list, return a list of strings.
        * If it's mixed text, we require exactly one placeholder. If it yields a list, return a list of replaced strings.

    Permission checking is done via enforce_permissions(). Non-Django objects pass automatically.
    """

    pure_text = text.strip()
    # Check if text is a "pure" placeholder: exactly "{{ ... }}"
    is_pure = (
        pure_text.startswith("{{")
        and pure_text.endswith("}}")
        and pure_text.count("{{") == 1
        and pure_text.count("}}") == 1
    )

    if is_pure:
        # Extract raw expression
        raw_expr = pure_text[2:-2].strip()

        # Possibly a pipe for formatting e.g. " now | MMM dd, YYYY "
        if "|" in raw_expr:
            parts = raw_expr.split("|", 1)
            value_expr = parts[0].strip()
            fmt_str = parts[1].strip()
            fmt_str_conv = convert_format(fmt_str)
            value = resolve_tag_expression(value_expr, context)
            # If the resolved value is datetime-like and supports strftime
            if hasattr(value, "strftime"):
                try:
                    value = value.strftime(fmt_str_conv)
                except Exception as e:
                    if errors is not None:
                        errors.append(f"Formatting error for '{raw_expr}': {e}")
                    return ""
        else:
            # No pipe formatting
            value = resolve_tag_expression(raw_expr, context)

        # Enforce permissions
        value = enforce_permissions(
            value, raw_expr, errors, request_user, check_permissions
        )

        # Return based on mode
        if mode == "normal":
            if isinstance(value, list):
                return delimiter.join(str(x) for x in value if x is not None)
            return str(value)
        else:  # mode == "table"
            if isinstance(value, list):
                return [str(x) for x in value if x is not None]
            return str(value)

    else:
        # Mixed text
        if mode == "table":
            # Must have exactly one placeholder
            placeholders = re.findall(r"\{\{(.*?)\}\}", text)
            if len(placeholders) != 1:
                raise ValueError(
                    "Table mode requires exactly one placeholder in mixed text."
                )
            raw_expr = placeholders[0].strip()
            val = resolve_tag_expression(raw_expr, context)
            val = enforce_permissions(
                val, raw_expr, errors, request_user, check_permissions
            )

            if isinstance(val, list):
                # For each item, produce a version of the text
                results = []
                for item in val:

                    def repl(_m):
                        return str(item)

                    results.append(re.sub(r"\{\{.*?\}\}", repl, text))
                return results
            else:

                def repl(_m):
                    return str(val)

                return re.sub(r"\{\{.*?\}\}", repl, text)
        else:
            # "normal" mixed text
            def replacer(match):
                raw_expr = match.group(1).strip()
                v = resolve_tag_expression(raw_expr, context)
                v = enforce_permissions(
                    v, raw_expr, errors, request_user, check_permissions
                )
                if isinstance(v, list):
                    # join the list inline
                    return delimiter.join(str(x) for x in v if x is not None)
                return str(v)

            return re.sub(r"\{\{(.*?)\}\}", replacer, text)
