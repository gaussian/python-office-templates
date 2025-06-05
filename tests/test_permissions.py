import unittest
from office_templates.templating.permissions import (
    enforce_permissions,
)
from office_templates.templating.exceptions import PermissionDeniedException

from tests.utils import has_view_permission, is_django_object


# Dummy request user for permission testing.
class DummyRequestUser:
    def __init__(self, deny_pattern=None):
        self.deny_pattern = deny_pattern

    def has_perm(self, perm, obj):
        # Deny if the object's 'name' contains the deny pattern.
        if hasattr(obj, "name") and self.deny_pattern and self.deny_pattern in obj.name:
            return False
        return True


# Dummy non-Django object.
class NonDjangoObject:
    def __init__(self, name):
        self.name = name


# Dummy Django-like object (has _meta attribute).
class DjangoObject:
    def __init__(self, name):
        self.name = name
        self._meta = True

    def __str__(self):
        return self.name


class TestPermissions(unittest.TestCase):
    def setUp(self):
        self.non_django = NonDjangoObject("NonDjango")
        self.django_allowed = DjangoObject("AllowedObject")
        self.django_denied = DjangoObject("deny_object")
        # Deny any object whose name contains "deny".
        self.request_user = DummyRequestUser(deny_pattern="deny")

    # def test_is_django_object(self):
    #     self.assertFalse(is_django_object(self.non_django))
    #     self.assertTrue(is_django_object(self.django_allowed))

    # def test_has_view_permission(self):
    #     # Non-Django objects always return True.
    #     self.assertTrue(has_view_permission(self.non_django, self.request_user))
    #     # Allowed Django-like object.
    #     self.assertTrue(has_view_permission(self.django_allowed, self.request_user))
    #     # Denied Django-like object.
    #     self.assertFalse(has_view_permission(self.django_denied, self.request_user))
    #     # With no request_user, should return False on Django objects.
    #     self.assertFalse(has_view_permission(self.django_allowed, None))

    def test_enforce_permissions_single_value(self):
        # Create check_permissions lambda
        check_permissions = lambda o: has_view_permission(o, self.request_user)

        # For a non-Django object, value is returned unchanged.
        val = "test value"
        res = enforce_permissions(val, check_permissions, True)
        self.assertEqual(res, val)

        # For allowed Django-like object.
        res_allowed = enforce_permissions(self.django_allowed, check_permissions, True)
        self.assertEqual(res_allowed, self.django_allowed)

        # For denied Django-like object, expect an exception instead of empty string.
        with self.assertRaises(PermissionDeniedException):
            enforce_permissions(self.django_denied, check_permissions, True)

    def test_enforce_permissions_list(self):
        # Create check_permissions lambda
        check_permissions = lambda o: has_view_permission(o, self.request_user)

        # Test on a list containing an allowed object and a denied object.
        values = [self.django_allowed, self.django_denied, self.non_django]
        with self.assertRaises(PermissionDeniedException):
            enforce_permissions(values, check_permissions, True)

    def test_enforce_permissions_single_value_exception(self):
        # Create check_permissions lambda
        check_permissions = lambda o: has_view_permission(o, self.request_user)

        # When permission is denied and raise_exception is True.
        with self.assertRaises(PermissionDeniedException):
            enforce_permissions(
                self.django_denied,
                check_permissions,
            )

    def test_enforce_permissions_list_exception(self):
        # Create check_permissions lambda
        check_permissions = lambda o: has_view_permission(o, self.request_user)

        values = [self.django_allowed, self.django_denied, self.non_django]
        with self.assertRaises(PermissionDeniedException):
            enforce_permissions(values, check_permissions)


if __name__ == "__main__":
    unittest.main()
