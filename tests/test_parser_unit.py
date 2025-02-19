import unittest
import datetime
from unittest.mock import patch

from template_reports.templating.parser import (
    parse_formatted_tag,
    split_expression,
    resolve_segment,
)
from template_reports.templating.resolver import get_nested_attr
from template_reports.templating.exceptions import (
    BadTagException,
    MissingDataException,
    TagCallableException,
)  # Added import


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
        result = parse_formatted_tag(expr, self.context)
        self.assertEqual(result, "Test")

    def test_resolve_tag_expression_nested_underscore(self):
        # Resolves a nested attribute using double underscores.
        expr = "dummy.nested__key"
        result = parse_formatted_tag(expr, self.context)
        self.assertEqual(result, "value")

    def test_resolve_tag_expression_nested_period(self):
        # Resolves a nested attribute using double underscores.
        expr = "dummy.nested.key"
        result = parse_formatted_tag(expr, self.context)
        self.assertEqual(result, "value")

    def test_resolve_tag_expression_now(self):
        # "now" should return a datetime instance (current time)
        expr = "now"
        result = parse_formatted_tag(expr, self.context)
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
        resolved = parse_formatted_tag(expr, context)
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
        resolved = parse_formatted_tag(expr, context)
        self.assertIsInstance(resolved, list)
        # Only users meeting both conditions should remain.
        self.assertEqual(len(resolved), 2)
        self.assertTrue(all(user.name == "Alice" and user.is_active for user in resolved))

    def test_empty_expression(self):
        # Empty expression should yield an empty string.
        self.assertEqual(parse_formatted_tag("", {}), "")

    def test_nonexistent_key(self):
        # Expression with a non-existent key should throw MissingDataException.
        context = {"user": {"name": "Alice"}}
        with self.assertRaises(MissingDataException):
            parse_formatted_tag("nonexistent", context)

    def test_simple_nested_lookup(self):
        # With the context having nested dictionary.
        context = {"user": {"name": "Alice"}}
        self.assertEqual(parse_formatted_tag("user.name", context), "Alice")

    @patch("template_reports.templating.parser.datetime")
    def test_now_expression(self, mock_datetime):
        # For "now", patch datetime.datetime.now to return a fixed value.
        fixed_now = datetime.datetime(2025, 2, 18, 12, 0, 0)
        mock_datetime.datetime.now.return_value = fixed_now
        # Expression "now" should then return fixed_now.
        result = parse_formatted_tag("now", {})
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
        with self.assertRaises(MissingDataException):
            resolve_segment("abc#", "xyz")

    def test_get_nested_attr_with_callable(self):
        # Test that if an attribute is callable, it gets called.
        obj = Dummy(name=lambda: "test", value=123)
        self.assertEqual(get_nested_attr(obj, "name"), "test")
        # If calling raises exception, should convert exception
        obj_bad = Dummy(name=lambda: 1 / 0, value=123)
        with self.assertRaises(TagCallableException):
            get_nested_attr(obj_bad, "name")

    def test_parse_expression_with_nonexistent_nested_attr(self):
        # For nested keys that don't exist, should return empty string.
        context = {"user": {"name": "Alice"}}
        with self.assertRaises(MissingDataException):
            parse_formatted_tag("user.age", context)

    def test_expression_with_opening_brace(self):
        # Expression containing an extra opening brace should fail.
        expr = "dummy.{name}"
        with self.assertRaises(BadTagException):
            parse_formatted_tag(expr, self.context)

    def test_expression_with_closing_brace(self):
        # Expression containing an extra closing brace should fail.
        expr = "dummy.name}"
        with self.assertRaises(BadTagException):
            parse_formatted_tag(expr, self.context)

    def test_expression_with_both_extra_braces(self):
        # Expression containing both extra "{" and "}" should fail.
        expr = "dummy.{name}}"
        with self.assertRaises(BadTagException):
            parse_formatted_tag(expr, self.context)

    def test_expression_with_invalid_characters(self):
        # Expression with unexpected characters (e.g., special symbols) should fail.
        expr = "dummy.na#me"
        with self.assertRaises(BadTagException):
            parse_formatted_tag(expr, self.context)

    def test_user_filter_on_nested_attribute(self):
        # Dummy classes for filtering test.
        class Program:
            def __init__(self, is_active):
                self.is_active = is_active

        class User:
            def __init__(self, name, program):
                self.name = name
                self.program = program
                self.program__is_active = program.is_active

            def __str__(self):
                return self.name

        # Create users with different program is_active values.
        users = [
            User("Alice", Program(True)),
            User("Bob", Program(False)),
            User("Carol", Program(True)),
        ]
        context = {"users": users}
        # Expression: filter users with program.is_active True and get their names.
        result = parse_formatted_tag("users[program__is_active=True].name", context)
        # Expected result is a list of names for Alice and Carol.
        self.assertIsInstance(result, list)
        self.assertEqual(result, ["Alice", "Carol"])


if __name__ == "__main__":
    unittest.main()
