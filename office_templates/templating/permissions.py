"""
Permissions utility module for the templating system.
"""


def is_django_object(obj):
    """
    Returns True if obj appears to be a Django model instance (has a _meta attribute).
    """
    return hasattr(obj, "_meta")


def has_view_permission(obj, request_user):
    """
    Check if the given request_user has permission to view obj.

    If request_user is None, returns False.
    If obj appears to be a Django model instance (has _meta), returns request_user.has_perm("view", obj).
    Otherwise, returns True.

    Args:
        obj: The object to check.
        request_user: The user performing the check.

    Returns:
        bool: True if permission is granted, False otherwise.
    """
    if request_user is None:
        return False
    if is_django_object(obj):
        return request_user.has_perm("view", obj)
    return True


def enforce_permissions(value, raw_expr, errors, request_user, check_permissions):
    """
    Enforce permission checks on a resolved value.

    - If check_permissions is False or no request_user is provided, returns the value unmodified.
    - If the value is a list, then for each item:
         * If the item is a Django object (i.e. has a _meta attribute), check permission.
         * Non-Django objects bypass permission checks.
      If any Django items are denied, an error message is appended.
    - If the value is a single object and it’s a Django object, check permission.
      If permission is denied, append an error message and return an empty string.
    - Otherwise, return the value.

    Args:
      value: The resolved value (could be a list or a single object).
      raw_expr (str): The raw placeholder expression (without braces).
      errors (list): A list to which error messages will be appended.
      request_user: The user object for permission checking.
      check_permissions (bool): Whether to enforce permission checking.

    Returns:
      The value filtered by permission.
    """
    if not check_permissions or request_user is None:
        return value

    if isinstance(value, list):
        permitted = [
            item
            for item in value
            if (not is_django_object(item)) or has_view_permission(item, request_user)
        ]
        # If any Django items were filtered out, record an error.
        if any(
            is_django_object(item) and not has_view_permission(item, request_user)
            for item in value
        ):
            errors.append(f"Permission denied for expression '{raw_expr}': {value}")
        return permitted
    else:
        if is_django_object(value):
            if not has_view_permission(value, request_user):
                errors.append(f"Permission denied for expression '{raw_expr}': {value}")
                return ""
        return value
