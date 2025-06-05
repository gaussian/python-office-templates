"""
Permissions utility module for the templating system.
"""

from typing import Callable

from .exceptions import PermissionDeniedException


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
