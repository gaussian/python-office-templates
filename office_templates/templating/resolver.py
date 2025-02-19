import re

from .exceptions import BadTagException


def get_nested_attr(obj, attr):
    """
    Retrieve an attribute from an object or dictionary using a chain of lookups separated by "__".

    Args:
      obj: The object or dict.
      attr (str): The attribute name (or chain, e.g., "profile__name").

    Returns:
      The attribute value, or None if not found.
    """
    parts = attr.split("__")
    for part in parts:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            obj = getattr(obj, part, None)
        if callable(obj):
            try:
                obj = obj()
            except Exception:
                raise BadTagException(f"{attr} failed when calling")
    return obj


def evaluate_condition(item, condition):
    """
    Evaluate a condition in the form "attribute=value".

    Args:
      item: The object to evaluate.
      condition (str): The condition string.

    Returns:
      bool: True if the condition holds.
    """
    m = re.match(r"([\w__]+)\s*=\s*(.+)", condition)
    if not m:
        return False
    attr_chain, value_str = m.groups()
    expected_value = parse_value(value_str)
    actual_value = get_nested_attr(item, attr_chain)
    return str(actual_value) == str(expected_value)


def parse_value(val_str):
    """
    Convert a string to a Python value (int, float, bool, or str).

    Args:
      val_str (str): The value string.

    Returns:
      The converted value.
    """
    val_str = val_str.strip()
    if val_str.lower() == "true":
        return True
    if val_str.lower() == "false":
        return False
    try:
        return int(val_str)
    except ValueError:
        pass
    try:
        return float(val_str)
    except ValueError:
        pass
    if (val_str.startswith('"') and val_str.endswith('"')) or (
        val_str.startswith("'") and val_str.endswith("'")
    ):
        return val_str[1:-1]
    return val_str
