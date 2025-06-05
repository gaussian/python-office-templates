import unittest
from template_reports.templating.list import process_text_list, make_float
from template_reports.templating.exceptions import BadFloatDataResultError


# Dummy user for permission testing
class DummyRequestUser:
    def has_perm(self, perm, obj):
        # Deny permission if object's name contains "deny"
        if hasattr(obj, "name") and "deny" in obj.name.lower():
            return False
        return True


class TestProcessTextList(unittest.TestCase):
    def setUp(self):
        self.context = {
            "user": {
                "name": "Alice",
                "email": "alice@example.com",
            },
            "users": [
                {"name": "Bob", "email": "bob@example.com"},
                {"name": "Carol", "email": "carol@example.com"},
            ],
            "numbers": {
                "0": 1,
                "1": 2,
                "2": 3,
            },
            "float_values": {
                "0": "1.5",
                "1": "2.5",
                "2": "not_a_number",
            },
            "none_value": None,
            "blank_value": "",
        }
        self.request_user = DummyRequestUser()

    def test_simple_text_list(self):
        """Test processing a list of simple text items."""
        items = ["Hello, {{ user.name }}", "Email: {{ user.email }}"]
        result = process_text_list(
            items=items, context=self.context, check_permissions=None, as_float=False
        )
        self.assertEqual(result, ["Hello, Alice", "Email: alice@example.com"])

    def test_table_mode_expansion(self):
        """Test table mode expansion for a single item with a list-resolving placeholder."""
        items = ["User: {{ users.name }}"]
        result = process_text_list(
            items=items, context=self.context, check_permissions=None, as_float=False
        )
        self.assertEqual(result, ["User: Bob", "User: Carol"])

    def test_as_float_conversion(self):
        """Test that items are converted to float when as_float is True."""
        items = ["{{ numbers.0 }}", "{{ numbers.1 }}", "{{ numbers.2 }}"]
        result = process_text_list(
            items=items, context=self.context, check_permissions=None, as_float=True
        )
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_as_float_with_non_convertible(self):
        """Test behavior when as_float is True but some values can't be converted."""
        items = ["{{ float_values.0 }}", "{{ float_values.1 }}", "{{ float_values.2 }}"]
        result = process_text_list(
            items=items,
            context=self.context,
            check_permissions=None,
            as_float=True,
            fail_if_not_float=False,
        )
        self.assertEqual(result, [1.5, 2.5, "not_a_number"])

    def test_fail_if_not_float(self):
        """Test that BadFloatDataResultError is raised when fail_if_not_float is True."""
        items = ["{{ float_values.2 }}"]
        with self.assertRaises(BadFloatDataResultError):
            process_text_list(
                items=items,
                context=self.context,
                check_permissions=None,
                as_float=True,
                fail_if_not_float=True,
            )

    def test_as_float_with_none_value(self):
        """Test that an empty placeholder with as_float=True results in None or ''."""
        items = ["{{ none_value }}"]
        # Value is None, should resolve to empty string
        result = process_text_list(
            items=items,
            context=self.context,
            check_permissions=None,
            as_float=True,
            fail_if_not_float=False,
        )
        self.assertEqual(result[0], "")
        result = process_text_list(
            items=items,
            context=self.context,
            check_permissions=None,
            as_float=True,
            fail_if_not_float=True,
        )
        self.assertEqual(result[0], 0.0)

    def test_as_float_with_empty_value(self):
        """Test that an empty placeholder with as_float=True results in None or ''."""
        items = ["{{ blank_value }}"]
        # Value is None, should resolve to empty string
        result = process_text_list(
            items=items,
            context=self.context,
            check_permissions=None,
            as_float=True,
            fail_if_not_float=False,
        )
        self.assertEqual(result[0], "")
        result = process_text_list(
            items=items,
            context=self.context,
            check_permissions=None,
            as_float=True,
            fail_if_not_float=True,
        )
        self.assertEqual(result[0], 0.0)

    def test_make_float_function(self):
        """Test the make_float utility function."""
        self.assertEqual(make_float("1.5", False), 1.5)
        self.assertEqual(make_float("not_a_number", False), "not_a_number")
        with self.assertRaises(BadFloatDataResultError):
            make_float("not_a_number", True)


if __name__ == "__main__":
    unittest.main()
