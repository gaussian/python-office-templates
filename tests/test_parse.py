import unittest
from template_reports.templating.parse import (
    get_nested_attr,
    evaluate_condition,
    parse_value,
)


# Dummy classes for testing get_nested_attr.
class Dummy:
    def __init__(self, value):
        self.value = value

    def method(self):
        return self.value


class TestResolver(unittest.TestCase):
    def test_get_nested_attr_object(self):
        # Test getting a simple attribute.
        dummy = Dummy(42)
        self.assertEqual(get_nested_attr(dummy, "value"), 42)

    def test_get_nested_attr_dict(self):
        # Test nested dictionary attribute.
        data = {"a": {"b": {"c": 100}}}
        self.assertEqual(get_nested_attr(data, "a__b__c"), 100)
        # Exception if not found.
        with self.assertRaises(KeyError):
            get_nested_attr(data, "a__x")

    def test_evaluate_condition_true(self):
        # Use a dict.
        data = {"status": "active", "count": 5}
        # Condition with equality (string case).
        self.assertTrue(evaluate_condition(data, "status=active"))
        # Condition with integer.
        self.assertTrue(evaluate_condition(data, "count=5"))

    def test_evaluate_condition_false(self):
        data = {"status": "inactive", "count": 10}
        self.assertFalse(evaluate_condition(data, "status=active"))
        self.assertFalse(evaluate_condition(data, "count=5"))

    def test_parse_value_int(self):
        self.assertEqual(parse_value("123"), 123)

    def test_parse_value_float(self):
        self.assertEqual(parse_value("3.14"), 3.14)

    def test_parse_value_bool(self):
        self.assertTrue(parse_value("true"))
        self.assertFalse(parse_value("False"))

    def test_parse_value_str_quotes(self):
        # Remove surrounding quotes.
        self.assertEqual(parse_value('"hello"'), "hello")
        self.assertEqual(parse_value("'world'"), "world")

    def test_parse_value_str_no_quotes(self):
        # Returns string as is if no conversion applies.
        self.assertEqual(parse_value("example"), "example")


if __name__ == "__main__":
    unittest.main()
