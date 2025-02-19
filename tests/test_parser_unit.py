import unittest
import datetime
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


if __name__ == "__main__":
    unittest.main()
