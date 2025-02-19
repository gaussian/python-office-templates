"""
Permissions utility module for the templating system.
"""


def is_django_object(obj):
    return hasattr(obj, "_meta")


def has_view_permission(obj, request_user):
    """
    If request_user is None, return False.
    For Django-like objects (with _meta), return request_user.has_perm("view", obj).
    For all other objects, return True.
    """
    if request_user is None:
        return False
    if is_django_object(obj):
        return request_user.has_perm("view", obj)
    return True


def enforce_permissions(value, raw_expr, errors, request_user, check_permissions):
    """
    Enforce permission checks on the resolved value.

    - If check_permissions is False or no request_user, return value unmodified.
    - If value is a list, filter out any Django-like objects for which request_user.has_perm("view", obj) is False.
      Append an error message if any items are removed.
    - For a single value, if it is Django-like and permission is denied, record an error and return an empty string.
    """
    if not check_permissions or request_user is None:
        return value
    if isinstance(value, list):
        permitted = [
            item
            for item in value
            if (not is_django_object(item)) or has_view_permission(item, request_user)
        ]
        if any(
            is_django_object(item) and not has_view_permission(item, request_user)
            for item in value
        ):
            errors.append(f"Permission denied for expression '{raw_expr}': {value}")
        return permitted
    else:
        if is_django_object(value) and not has_view_permission(value, request_user):
            errors.append(f"Permission denied for expression '{raw_expr}': {value}")
            return ""
        return value
