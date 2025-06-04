"""
Permissions utility module for the templating system.
"""

from typing import Callable
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


def _check_permissions(item, check_permissions: Callable[[object], bool]):
    """
    Check permission for a single item using the provided check_permissions function.
    Returns a tuple (item, True) if the item passes the permission check.
    Otherwise, raises PermissionDeniedException.
    """
    if not check_permissions(item):
        msg = f"Permission denied on: {item}"
        raise PermissionDeniedException(msg)
    return (item, True)


def enforce_permissions(
    value,
    check_permissions: Callable[[object], bool],
    raise_exception=True,
):
    """
    Enforce permission checks on the resolved value by delegating per-item permission logic to _check_permissions.

    - If check_permissions is None, returns the value unmodified.
    - For list values: iterates once, replaces any item failing _check_permissions (i.e. gets None) by filtering it out.
      If any item fails, the first error message is already appended (via _check_permissions).
    - For a single value: returns "" if _check_permissions returns None.
    """
    if check_permissions is None:
        return value

    # If value is a list, check each item.
    if isinstance(value, list):
        permitted = []
        for item in value:
            res, success = _check_permissions(
                item,
                check_permissions,
            )
            if success:
                permitted.append(res)
        return permitted
    else:
        res, success = _check_permissions(
            value,
            check_permissions,
        )
        return res if success else ""
