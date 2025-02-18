"""
Permissions utility module for the templating system.
"""


def enforce_permissions(value, raw_expr, errors, request_user, check_permissions):
    """
    Enforce permission checks on a resolved value.

    Args:
      value: The value resolved from a placeholder.
      raw_expr (str): The raw expression string (without braces).
      errors (list): List to which error messages are appended.
      request_user: The user object for permission checking.
      check_permissions (bool): Whether to enforce permission checking.

    Returns:
      The value filtered by permission:
        - For a list, only permitted items are kept.
        - For a single object, returns the object if permitted, otherwise returns an empty string.
    """
    if not check_permissions or request_user is None:
        return value
    if isinstance(value, list):
        permitted = [item for item in value if has_view_permission(item, request_user)]
        if len(permitted) < len(value):
            errors.append(f"Permission denied for expression '{raw_expr}': {value}")
        return permitted
    else:
        if not has_view_permission(value, request_user):
            errors.append(f"Permission denied for expression '{raw_expr}': {value}")
            return ""
        return value


def has_view_permission(obj, request_user):
    """
    Check if the given request_user has permission to view obj.

    If request_user is None, return False.
    If the object appears to be a Django model instance (i.e. has a _meta attribute),
    return request_user.has_perm("view", obj).
    Otherwise, return False.

    Args:
        obj: The object to check.
        request_user: The user object performing the check.

    Returns:
        bool: True if permission is granted, False otherwise.
    """
    if request_user is None:
        return False
    if hasattr(obj, "_meta"):
        return request_user.has_perm("view", obj)
    return False
