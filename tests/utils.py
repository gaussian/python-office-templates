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
