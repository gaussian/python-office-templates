import re


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
            obj = obj[part]
        else:
            obj = getattr(obj, part)
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


def parse_callable_args(args_str: str) -> list:
    """
    Split a comma-separated argument string and convert each argument using parse_value.
    Only int, float, or str are allowed.
    """
    if not args_str.strip():
        return []
    args = [arg.strip() for arg in args_str.split(",")]
    return [parse_value(arg) for arg in args]
