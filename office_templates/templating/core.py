"""
Core templating functions.

This module defines process_text() which resolves template tags (delimited by {{ and }})
from a text string using the provided context.

Two modes are supported:
  • "normal" mode:
      - Pure placeholder (i.e. the entire text is exactly "{{ ... }}"):
          • If the resolved value is a list, join its items using the delimiter.
          • Otherwise, return its string representation.
      - Mixed text:
          • Each placeholder is replaced inline. If a placeholder includes a pipe (for formatting),
            the formatting is applied. If a placeholder resolves to a list, its items are joined.
  • "table" mode:
      - Pure placeholder: if the resolved value is a list, return a list of strings (one per item);
          otherwise, return the string.
      - Mixed text: the text must contain exactly one placeholder; if it resolves to a list,
          return a list of strings (one per item), otherwise return a singleton list.

Permission checking is enforced by calling enforce_permissions() (from permissions.py).
Non‑Django objects (ones without a _meta attribute) bypass permissions.
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
      context (dict): Mapping of variable names to values.
      errors (list, optional): List for error messages.
      request_user: The user object for permission checking.
      check_permissions (bool): Whether to enforce permission checks.
      mode (str): "normal" or "table" (default "normal").
      delimiter (str): Delimiter for joining list values in normal mode.

    Returns:
      In "normal" mode: a string.
      In "table" mode: either a string or a list of strings.
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
        # Check for formatting pipe.
        if "|" in raw_expr:
            parts = raw_expr.split("|", 1)
            value_expr = parts[0].strip()
            fmt_str = parts[1].strip()
            fmt_str_conv = convert_format(fmt_str)
            value = resolve_tag_expression(value_expr, context)
            if hasattr(value, "strftime"):
                try:
                    value = value.strftime(fmt_str_conv)
                except Exception as e:
                    if errors is not None:
                        errors.append(f"Formatting error for '{raw_expr}': {e}")
                    return ""
            else:
                value = str(value)
        else:
            value = resolve_tag_expression(raw_expr, context)
        # Enforce permissions.
        value = enforce_permissions(
            value, raw_expr, errors, request_user, check_permissions
        )
        if mode == "normal":
            if isinstance(value, list):
                return delimiter.join(str(x) for x in value if x is not None)
            return str(value)
        else:  # table mode
            if isinstance(value, list):
                return [str(x) for x in value if x is not None]
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

                    def repl(_m):
                        return str(item)

                    results.append(re.sub(r"\{\{.*?\}\}", repl, text))
                return results
            else:

                def repl(_m):
                    return str(value)

                return re.sub(r"\{\{.*?\}\}", repl, text)
        else:  # Normal mixed text mode

            def repl(match):
                raw_expr = match.group(1).strip()
                # Check for formatting in mixed mode
                if "|" in raw_expr:
                    parts = raw_expr.split("|", 1)
                    value_expr = parts[0].strip()
                    fmt_str = parts[1].strip()
                    fmt_str_conv = convert_format(fmt_str)
                    v = resolve_tag_expression(value_expr, context)
                    if hasattr(v, "strftime"):
                        try:
                            v = v.strftime(fmt_str_conv)
                        except Exception as e:
                            if errors is not None:
                                errors.append(f"Formatting error for '{raw_expr}': {e}")
                            v = ""
                    else:
                        v = str(v)
                else:
                    v = resolve_tag_expression(raw_expr, context)
                v = enforce_permissions(
                    v, raw_expr, errors, request_user, check_permissions
                )
                if isinstance(v, list):
                    return delimiter.join(str(x) for x in v if x is not None)
                return str(v)

            return re.sub(r"\{\{(.*?)\}\}", repl, text)
