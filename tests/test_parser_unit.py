import unittest
import datetime
from unittest.mock import patch

from template_reports.templating.parser import (
    resolve_tag_expression,
    split_expression,
    resolve_segment,
)
from template_reports.templating.resolver import get_nested_attr


# Dummy class for testing nested attribute and filtering.
class Dummy:
    def __init__(self, name, value, nested=None):
        self.name = name
        self.value = value
        self.nested = nested or {}

    def __str__(self):
        return f"Dummy({self.name})"


class TestParser(unittest.TestCase):
    def setUp(self):
        self.dummy = Dummy("Test", 123, nested={"key": "value"})
        self.context = {
            "dummy": self.dummy,
            "now": datetime.datetime(2020, 1, 1, 12, 0, 0),
        }

    def test_split_expression(self):
        expr = "program.users[is_active=True].email"
        result = split_expression(expr)
        expected = ["program", "users[is_active=True]", "email"]
        self.assertEqual(result, expected)

    def test_resolve_tag_expression_simple(self):
        # Resolves a simple attribute.
        expr = "dummy.name"
        result = resolve_tag_expression(expr, self.context)
        self.assertEqual(result, "Test")

    def test_resolve_tag_expression_nested(self):
        # Resolves a nested attribute using double underscores.
        expr = "dummy.nested__key"
        result = resolve_tag_expression(expr, self.context)
        self.assertEqual(result, "value")

    def test_resolve_tag_expression_now(self):
        # "now" should return a datetime instance (current time)
        expr = "now"
        result = resolve_tag_expression(expr, self.context)
        self.assertIsInstance(result, datetime.datetime)

    def test_resolve_segment_with_filter(self):
        # Create a dummy User class with an 'is_active' attribute.
        class User:
            def __init__(self, name, is_active):
                self.name = name
                self.is_active = is_active

            def __str__(self):
                return self.name

        # Setup a dummy list for filtering.
        users = [User("Alice", True), User("Bob", False), User("Charlie", True)]

        # Create a dummy container with a 'users' attribute.
        class Container:
            def __init__(self, users):
                self.users = users

        container = Container(users)
        context = {"container": container}

        # Expression: container.users[is_active=True]
        expr = "container.users[is_active=True]"
        resolved = resolve_tag_expression(expr, context)
        # Expect list of users with is_active True.
        self.assertIsInstance(resolved, list)
        self.assertEqual([user.name for user in resolved], ["Alice", "Charlie"])

    def test_resolve_segment_multiple_conditions(self):
        # Dummy user for multiple conditions
        class User:
            def __init__(self, name, is_active, age):
                self.name = name
                self.is_active = is_active
                self.age = age

            def __str__(self):
                return self.name

        # Create a list with diverse users.
        users = [
            User("Alice", True, 30),
            User("Alice", False, 30),
            User("Bob", True, 25),
            User("Alice", True, 25),
        ]

        # Container holds the list.
        class Container:
            def __init__(self, users):
                self.users = users

        container = Container(users)
        context = {"container": container}

        # Expression with multiple conditions separated by ", "
        # Expect to filter users with name "Alice" and is_active True.
        expr = "container.users[is_active=True, name=Alice]"
        resolved = resolve_tag_expression(expr, context)
        self.assertIsInstance(resolved, list)
        # Only users meeting both conditions should remain.
        self.assertEqual(len(resolved), 2)
        self.assertTrue(all(user.name == "Alice" and user.is_active for user in resolved))

    def test_empty_expression(self):
        # Empty expression should yield an empty string.
        self.assertEqual(resolve_tag_expression("", {}), "")

    def test_invalid_percentage_expression(self):
        # Expression containing "%" which is not a valid key
        # (context doesn't have "%" as key) should return "".
        self.assertEqual(resolve_tag_expression("%", {"%": "value"}), "value")
        # But if context lacks "%", returns "".
        self.assertEqual(resolve_tag_expression("%", {}), "")

    def test_nonexistent_key(self):
        # Expression with a non-existent key returns empty string.
        context = {"user": {"name": "Alice"}}
        self.assertEqual(resolve_tag_expression("nonexistent", context), "")

    def test_simple_nested_lookup(self):
        # With the context having nested dictionary.
        context = {"user": {"name": "Alice"}}
        self.assertEqual(resolve_tag_expression("user.name", context), "Alice")

    @patch("template_reports.templating.parser.datetime")
    def test_now_expression(self, mock_datetime):
        # For "now", patch datetime.datetime.now to return a fixed value.
        fixed_now = datetime.datetime(2025, 2, 18, 12, 0, 0)
        mock_datetime.datetime.now.return_value = fixed_now
        # Expression "now" should then return fixed_now.
        result = resolve_tag_expression("now", {})
        self.assertEqual(result, fixed_now)

    def test_resolve_segment_with_filter_non_queryset(self):
        # Test resolve_segment when filtering a non-queryset.
        # For simplicity, assume no complex filtering; we simulate by passing a list.
        # Context: list of dicts. Filter on is_active=True.
        items = [{"name": "A", "is_active": True}, {"name": "B", "is_active": False}]

        # For segment "users[is_active=True]", our resolve_segment applies filtering.
        # Here, get_nested_attr returns dict value.
        # We must mimic get_nested_attr behavior: for each item, item.get('users') is None.
        # Instead, we test by wrapping items in a dummy object.
        class DummyObj:
            def __init__(self, users):
                self.users = users

        obj = DummyObj(users=items)
        # Without filter, resolve_segment simply returns attribute.
        self.assertEqual(resolve_segment(obj, "users"), items)
        # With filter, we expect only one item (True).
        # Note: evaluate_condition and parse_value are used for filtering.
        filtered = resolve_segment(obj, "users[is_active=True]")
        self.assertEqual(filtered, [items[0]])

    def test_split_expression_with_brackets(self):
        # Test that periods inside square brackets are not split.
        expr = "program.users[active=True].email"
        segments = split_expression(expr)
        # Expect three segments.
        self.assertEqual(segments, ["program", "users[active=True]", "email"])

    def test_resolve_segment_invalid_segment(self):
        # Segment that does not match the expected pattern should return None.
        self.assertIsNone(resolve_segment("abc#", "xyz"))

    def test_get_nested_attr_with_callable(self):
        # Test that if an attribute is callable, it gets called.
        obj = Dummy(name=lambda: "test", value=123)
        self.assertEqual(get_nested_attr(obj, "name"), "test")
        # If calling raises exception, returns None.
        obj_bad = Dummy(name=lambda: 1 / 0, value=123)
        self.assertIsNone(get_nested_attr(obj_bad, "name"))

    def test_parse_expression_with_nonexistent_nested_attr(self):
        # For nested keys that don't exist, should return empty string.
        context = {"user": {"name": "Alice"}}
        self.assertEqual(resolve_tag_expression("user.age", context), "")

    def test_expression_with_opening_brace(self):
        # Expression containing an extra opening brace should return empty string.
        expr = "dummy.{name}"
        result = resolve_tag_expression(expr, self.context)
        self.assertEqual(result, "", "Expression with stray '{' should not resolve.")

    def test_expression_with_closing_brace(self):
        # Expression containing an extra closing brace should return empty string.
        expr = "dummy.name}"
        result = resolve_tag_expression(expr, self.context)
        self.assertEqual(result, "", "Expression with stray '}' should not resolve.")

    def test_expression_with_both_extra_braces(self):
        # Expression containing both extra "{" and "}" should return empty string.
        expr = "dummy.{name}}"
        result = resolve_tag_expression(expr, self.context)
        self.assertEqual(result, "", "Expression with extra braces should not resolve.")

    def test_expression_with_invalid_characters(self):
        # Expression with unexpected characters (e.g., special symbols) should return empty string.
        expr = "dummy.na#me"
        result = resolve_tag_expression(expr, self.context)
        self.assertEqual(
            result, "", "Expression with invalid characters should not resolve."
        )


if __name__ == "__main__":
    unittest.main()
