"""
Permissions utility module for the templating system.
"""

from template_reports.pptx_renderer.exceptions import PermissionDeniedException


def is_django_object(obj):
    return hasattr(obj, "_meta")


def has_view_permission(obj, request_user):
    """
    If request_user is None, returns False.
    For Django-like objects (with _meta), returns request_user.has_perm("view", obj).
    For all other objects, returns True.
    """
    if request_user is None:
        return False
    if is_django_object(obj):
        return request_user.has_perm("view", obj)
    return True


def _check_permissions(item, request_user, raw_expr, raise_exception, errors):
    """
    Check permission for a single item.
    Returns a tuple (item, True) if the item passes the permission check.
    Otherwise, returns (None, False). If raise_exception is True, raises PermissionDeniedException immediately.
    """
    if is_django_object(item) and not has_view_permission(item, request_user):
        msg = f"Permission denied for expression '{raw_expr}': {item}"
        if raise_exception:
            raise PermissionDeniedException(msg)
        else:
            errors.append(msg)
            return (None, False)
    return (item, True)


def enforce_permissions(
    value,
    raw_expr,
    request_user,
    check_permissions,
    raise_exception=True,
):
    """
    Enforce permission checks on the resolved value by delegating per-item permission logic to _check_permissions.

    - If check_permissions is False or no request_user is provided, returns the value unmodified.
    - For list values: iterates once, replaces any item failing _check_permissions (i.e. gets None) by filtering it out.
      If any item fails, the first error message is already appended (via _check_permissions).
    - For a single value: returns "" if _check_permissions returns None.
    """
    if not check_permissions or request_user is None:
        return value

    # If value is a list, check each item.
    if isinstance(value, list):
        permitted = []
        for item in value:
            res, success = _check_permissions(
                item, request_user, raw_expr, raise_exception, errors
            )
            if success:
                permitted.append(res)
        return permitted
    else:
        res, success = _check_permissions(
            value, request_user, raw_expr, raise_exception, errors
        )
        return res if success else ""
