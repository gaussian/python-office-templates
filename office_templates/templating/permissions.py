"""
Permissions utility module for the templating system.
"""

from .exceptions import PermissionDeniedException


def is_django_object(obj):
    return hasattr(obj, "_meta")


def has_view_permission(obj, perm_user):
    """
    If perm_user is None, returns False.
    For Django-like objects (with _meta), returns perm_user.has_perm("view", obj).
    For all other objects, returns True.
    """
    if perm_user is None:
        return False
    if is_django_object(obj):
        return perm_user.has_perm("view", obj)
    return True


def _check_permissions(item, perm_user):
    """
    Check permission for a single item.
    Returns a tuple (item, True) if the item passes the permission check.
    Otherwise, returns (None, False). If raise_exception is True, raises PermissionDeniedException immediately.
    """
    if is_django_object(item) and not has_view_permission(item, perm_user):
        msg = f"Permission denied on: {item}"
        raise PermissionDeniedException(msg)
    return (item, True)


def enforce_permissions(
    value,
    perm_user,
    raise_exception=True,
):
    """
    Enforce permission checks on the resolved value by delegating per-item permission logic to _check_permissions.

    - If check_permissions is False or no perm_user is provided, returns the value unmodified.
    - For list values: iterates once, replaces any item failing _check_permissions (i.e. gets None) by filtering it out.
      If any item fails, the first error message is already appended (via _check_permissions).
    - For a single value: returns "" if _check_permissions returns None.
    """
    if perm_user is None:
        return value

    # If value is a list, check each item.
    if isinstance(value, list):
        permitted = []
        for item in value:
            res, success = _check_permissions(
                item,
                perm_user,
            )
            if success:
                permitted.append(res)
        return permitted
    else:
        res, success = _check_permissions(
            value,
            perm_user,
        )
        return res if success else ""
