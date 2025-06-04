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


def enforce_permissions(
    value,
    check_permissions: Callable[[object], bool],
    raise_exception=True,
):
    """
    Enforce permission checks on the resolved value.

    - If check_permissions is None, returns the value unmodified.
    - For list values: iterates once, filters out any item failing permission check.
      If any item fails, raises PermissionDeniedException.
    - For a single value: returns "" if permission check fails, raises PermissionDeniedException otherwise.
    """
    if check_permissions is None:
        return value

    # If value is a list, check each item.
    if isinstance(value, list):
        permitted = []
        for item in value:
            if not check_permissions(item):
                msg = f"Permission denied on: {item}"
                raise PermissionDeniedException(msg)
            permitted.append(item)
        return permitted
    else:
        if not check_permissions(value):
            msg = f"Permission denied on: {value}"
            raise PermissionDeniedException(msg)
        return value
