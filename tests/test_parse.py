import unittest
from office_templates.templating.parse import (
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

    def test_get_nested_attr_list_indexing(self):
        """Test numeric indexing on lists in get_nested_attr"""
        test_list = ['a', 'b', 'c']
        self.assertEqual(get_nested_attr(test_list, "0"), 'a')
        self.assertEqual(get_nested_attr(test_list, "1"), 'b')
        self.assertEqual(get_nested_attr(test_list, "2"), 'c')
        
        # Test out of bounds
        with self.assertRaises(AttributeError):
            get_nested_attr(test_list, "5")

    def test_get_nested_attr_list_vs_dict_numeric_keys(self):
        """Test that numeric keys work for both lists and dicts"""
        test_list = ['list_val_0', 'list_val_1']
        test_dict = {'0': 'dict_val_0', '1': 'dict_val_1'}
        
        # List should use indexing
        self.assertEqual(get_nested_attr(test_list, "0"), 'list_val_0')
        
        # Dict should use key access
        self.assertEqual(get_nested_attr(test_dict, "0"), 'dict_val_0')

    def test_get_nested_attr_nested_with_indexing(self):
        """Test nested access with list indexing"""
        data = {
            'items': [
                {'name': 'item0'},
                {'name': 'item1'}
            ]
        }
        self.assertEqual(get_nested_attr(data, "items__0__name"), 'item0')
        self.assertEqual(get_nested_attr(data, "items__1__name"), 'item1')


if __name__ == "__main__":
    unittest.main()
