"""
Core templating functions.

This module provides the `process_text()` function that resolves template tags in a text string.
It supports two modes:
  - "normal": In pure placeholder mode, if the resolved value is a list, it is joined using a delimiter.
             In mixed text mode, placeholders must resolve to non-list values.
  - "table": In pure placeholder mode, if the resolved value is a list, a list of strings is returned
             (one for each item). In mixed mode, the text must contain exactly one placeholder, and the result
             will be a list of strings (one per list element).

Permission checking is performed on every resolved placeholder via the helper function
`enforce_permissions()`. In this design, permission is enforced only if `check_permissions` is True and a
`request_user` is provided. If permission fails, an error is recorded and the value is replaced by an empty string.

The module delegates expression resolution to `resolve_tag_expression()` from the parser module and
date formatting conversion to `convert_format()` from the formatting module.
"""

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
    Process text containing template tags delimited by {{ and }}.

    The function distinguishes between "pure" placeholders (where the trimmed text is exactly one placeholder)
    and mixed text (where the placeholder is embedded in other text). Two modes are supported:

    - mode "normal":
        * In pure mode, if the resolved value is a list, its items are joined with `delimiter`.
          Otherwise, the value is returned.
        * In mixed text mode, if any placeholder resolves to a list, a ValueError is raised.
    - mode "table":
        * In pure mode, if the resolved value is a list, a list of strings is returned.
          Otherwise, the string representation is returned.
        * In mixed mode, the text must contain exactly one placeholder; the result is a list of strings,
          one for each element if the placeholder resolves to a list, or a singleton list otherwise.

    Permission Checking:
      For each placeholder, if check_permissions is True and request_user is provided, the resolved value
      is filtered using `enforce_permissions()`. If permission fails, an error message is added to `errors`
      and the value is replaced by an empty string.

    Args:
      text (str): The input text to process.
      context (dict): Mapping of variable names to values.
      errors (list, optional): List for collecting error messages.
      request_user: The user object for permission checking.
      check_permissions (bool): Whether to enforce permission checks.
      mode (str): Either "normal" or "table" (default "normal").
      delimiter (str): Delimiter for joining list values in "normal" pure mode.

    Returns:
      Processed text (str) in normal mode, or a list of strings in table mode (if applicable).

    Raises:
      ValueError: In mixed text mode if a placeholder resolves to a list (in normal mode) or if table mode mixed text
                  does not contain exactly one placeholder.
    """
    pure_text = text.strip()
    # Determine if the entire text is a pure placeholder.
    is_pure = (
        pure_text.startswith("{{")
        and pure_text.endswith("}}")
        and pure_text.count("{{") == 1
        and pure_text.count("}}") == 1
    )

    if is_pure:
        # Extract the expression inside the braces.
        raw_expr = pure_text[2:-2].strip()
        # Handle formatting with a pipe (e.g., "{{ now|MMM dd, YYYY }}").
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
            # If not a date, leave value as is.
        else:
            value = resolve_tag_expression(raw_expr, context)
        # Apply permission checking.
        value = enforce_permissions(
            value, raw_expr, errors, request_user, check_permissions
        )
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
        if mode == "table":
            placeholders = re.findall(r"\{\{(.*?)\}\}", text)
            if len(placeholders) != 1:
                raise ValueError(
                    "Table mode supports mixed text with exactly one placeholder."
                )
            raw_expr = placeholders[0].strip()
            value = resolve_tag_expression(raw_expr, context)
            value = enforce_permissions(
                value, raw_expr, errors, request_user, check_permissions
            )
            if not isinstance(value, list):
                # Replace the placeholder inline.
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
        else:  # Normal mixed text mode.

            def replacer(match):
                raw_expr = match.group(1).strip()
                val = resolve_tag_expression(raw_expr, context)
                val = enforce_permissions(
                    val, raw_expr, errors, request_user, check_permissions
                )
                if isinstance(val, list):
                    raise ValueError(
                        f"Cannot render list in mixed text in normal mode: {match.group(0)}"
                    )
                return str(val)

            return re.sub(r"\{\{(.*?)\}\}", replacer, text)
