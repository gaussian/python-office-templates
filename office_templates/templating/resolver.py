import re


def get_nested_attr(obj, attr):
    """
    Retrieve an attribute from an object (or dict).
    Supports chained lookup using double-underscores.
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
                obj = None
    return obj


def evaluate_condition(item, condition):
    """
    Evaluate a condition of the form attribute==value (or attribute=value).
    Only equality is supported.
    """
    m = re.match(r"([\w__]+)\s*(==|=)\s*(.+)", condition)
    if not m:
        return False
    attr_chain, op, value_str = m.groups()
    expected_value = parse_value(value_str)
    actual_value = get_nested_attr(item, attr_chain)
    return actual_value == expected_value


def parse_value(val_str):
    """
    Parse a string value into a Python object.
    Tries booleans, integers, floats; strips quotes from strings.
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
