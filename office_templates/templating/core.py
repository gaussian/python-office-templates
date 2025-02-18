"""
Core templating functions.

This module defines process_text() which resolves template tags (delimited by {{ and }})
in a text string using the provided context.

It supports two modes:
  • "normal" mode:
      - Pure placeholder (i.e. text is exactly "{{ ... }}"):
          • If the resolved value is a list, join its items using the specified delimiter.
          • Otherwise, return the string representation.
      - Mixed text:
          • Each placeholder is substituted inline. If a placeholder resolves to a list,
            its items are automatically joined using the delimiter.
  • "table" mode:
      - Pure placeholder: if the resolved value is a list, return a list of strings (one per item);
          otherwise, return the string.
      - Mixed text: The text must contain exactly one placeholder; if that placeholder resolves
          to a list, the result is a list of strings (one per item), else a singleton list.

Permission checking is performed via enforce_permissions() (imported from permissions.py).
Only objects that appear to be Django model–like (i.e. have a _meta attribute) are checked.
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
    Process text containing template tags.

    Args:
      text (str): The input text (which may contain one or more placeholders).
      context (dict): Mapping from variable names to their values.
      errors (list, optional): List to collect error messages.
      request_user: The user object for permission checking.
      check_permissions (bool): Whether to enforce permission checks.
      mode (str): Either "normal" or "table" (default "normal").
      delimiter (str): Delimiter used to join list values in normal mode.

    Returns:
      In normal mode: a string.
      In table mode: either a string or a list of strings.
    """
    pure_text = text.strip()
    is_pure = (
        pure_text.startswith("{{")
        and pure_text.endswith("}}")
        and pure_text.count("{{") == 1
        and pure_text.count("}}") == 1
    )

    if is_pure:
        raw_expr = pure_text[2:-2].strip()
        if "|" in raw_expr:
            parts = raw_expr.split("|", 1)
            value_expr = parts[0].strip()
            fmt_str = parts[1].strip()
            fmt_str_converted = convert_format(fmt_str)
            value = resolve_tag_expression(value_expr, context)
            if hasattr(value, "strftime"):
                try:
                    value = value.strftime(fmt_str_converted)
                except Exception as e:
                    if errors is not None:
                        errors.append(f"Formatting error for '{raw_expr}': {e}")
                    return ""
        else:
            value = resolve_tag_expression(raw_expr, context)
        # Enforce permissions.
        value = enforce_permissions(
            value, raw_expr, errors, request_user, check_permissions
        )
        if mode == "normal":
            if isinstance(value, list):
                return delimiter.join(str(item) for item in value if item is not None)
            else:
                return str(value)
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
            if isinstance(value, list):
                results = []
                for item in value:

                    def repl(match):
                        return str(item)

                    results.append(re.sub(r"\{\{.*?\}\}", repl, text))
                return results
            else:

                def repl(match):
                    return str(value)

                return re.sub(r"\{\{.*?\}\}", repl, text)
        else:

            def repl(match):
                raw_expr = match.group(1).strip()
                val = resolve_tag_expression(raw_expr, context)
                val = enforce_permissions(
                    val, raw_expr, errors, request_user, check_permissions
                )
                if isinstance(val, list):
                    return delimiter.join(str(item) for item in val if item is not None)
                return str(val)

            return re.sub(r"\{\{(.*?)\}\}", repl, text)
