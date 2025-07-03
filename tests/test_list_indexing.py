import unittest
from office_templates.templating.resolve import resolve_formatted_tag
from office_templates.templating.exceptions import MissingDataException


class TestListIndexing(unittest.TestCase):
    def setUp(self):
        """Set up test context with various data structures."""
        
        class MockProgram:
            def __init__(self):
                self.users = ['Alice', 'Bob', 'Carol']
                self.user_count = 3
                
            def get_figures(self):
                return [10.5, 20.3, 30.7]
                
            def get_some_dict(self):
                return {'some_key': 'some_value', 'other_key': 'other_value'}
                
            def get_nested_list(self):
                return [
                    {'name': 'Item1', 'value': 100},
                    {'name': 'Item2', 'value': 200}
                ]
        
        self.context = {
            'team': {
                'users': ['Alice', 'Bob', 'Carol'],
                'metadata': {'count': 3}
            },
            'program': MockProgram(),
            'simple_list': [1, 2, 3, 4, 5],
            'empty_list': [],
            'nested_lists': [
                [1, 2, 3],
                [4, 5, 6],
                [7, 8, 9]
            ]
        }

    def test_basic_list_indexing(self):
        """Test basic list indexing: {{ team.users.0 }}"""
        result = resolve_formatted_tag('team.users.0', self.context)
        self.assertEqual(result, 'Alice')
        
        result = resolve_formatted_tag('team.users.1', self.context)
        self.assertEqual(result, 'Bob')
        
        result = resolve_formatted_tag('team.users.2', self.context)
        self.assertEqual(result, 'Carol')

    def test_function_returning_list_indexing(self):
        """Test function returning list with indexing: {{ program.get_figures().0 }}"""
        result = resolve_formatted_tag('program.get_figures().0', self.context)
        self.assertEqual(result, 10.5)
        
        result = resolve_formatted_tag('program.get_figures().1', self.context)
        self.assertEqual(result, 20.3)
        
        result = resolve_formatted_tag('program.get_figures().2', self.context)
        self.assertEqual(result, 30.7)

    def test_function_returning_dict_access(self):
        """Test function returning dict with attribute access: {{ program.get_some_dict().some_key }}"""
        # This should already work
        result = resolve_formatted_tag('program.get_some_dict().some_key', self.context)
        self.assertEqual(result, 'some_value')

    def test_direct_list_indexing(self):
        """Test direct list indexing: {{ simple_list.0 }}"""
        result = resolve_formatted_tag('simple_list.0', self.context)
        self.assertEqual(result, 1)
        
        result = resolve_formatted_tag('simple_list.4', self.context)
        self.assertEqual(result, 5)

    def test_nested_list_indexing(self):
        """Test nested list indexing: {{ nested_lists.0.1 }}"""
        result = resolve_formatted_tag('nested_lists.0.1', self.context)
        self.assertEqual(result, 2)
        
        result = resolve_formatted_tag('nested_lists.2.0', self.context)
        self.assertEqual(result, 7)

    def test_invalid_index_on_non_list(self):
        """Test that numeric access on non-list should fail appropriately: {{ program.user_count.0 }}"""
        with self.assertRaises(MissingDataException):
            resolve_formatted_tag('program.user_count.0', self.context)

    def test_out_of_bounds_index(self):
        """Test out of bounds index should fail appropriately: {{ simple_list.10 }}"""
        with self.assertRaises(MissingDataException) as cm:
            resolve_formatted_tag('simple_list.10', self.context)
        self.assertIn("Index 10 out of bounds", str(cm.exception))

    def test_negative_index(self):
        """Test negative indexing: {{ simple_list.-1 }}"""
        # Current implementation won't match negative numbers in regex
        with self.assertRaises(Exception):  # Malformed segment
            resolve_formatted_tag('simple_list.-1', self.context)

    def test_empty_list_indexing(self):
        """Test indexing into empty list: {{ empty_list.0 }}"""
        with self.assertRaises(MissingDataException) as cm:
            resolve_formatted_tag('empty_list.0', self.context)
        self.assertIn("Index 0 out of bounds for list of length 0", str(cm.exception))

    def test_list_indexing_with_filters_and_calls(self):
        """Test that numeric indexing only works when there are no filters or calls"""
        
        class MockObj:
            def __init__(self):
                self.items = [
                    {'name': 'A', 'active': True}, 
                    {'name': 'B', 'active': False}
                ]
        
        context = {'obj': MockObj()}
        
        # This should use filter behavior, not numeric indexing
        result = resolve_formatted_tag('obj.items[active=True].name', context)
        self.assertEqual(result, ['A'])
        
    def test_list_indexing_with_mathematical_operations(self):
        """Test that list indexing works with mathematical operations"""
        result = resolve_formatted_tag('simple_list.0 + 10', self.context)
        self.assertEqual(result, 11.0)  # 1 + 10
        
        result = resolve_formatted_tag('program.get_figures().1 * 2', self.context)
        self.assertEqual(result, 40.6)  # 20.3 * 2

    def test_list_indexing_with_formatting(self):
        """Test that list indexing works with formatting"""
        result = resolve_formatted_tag('program.get_figures().0 | .1f', self.context)
        self.assertEqual(result, '10.5')

    def test_mixed_indexing_and_attributes(self):
        """Test mixed indexing and attribute access"""
        result = resolve_formatted_tag('program.get_nested_list().0.name', self.context)
        self.assertEqual(result, 'Item1')
        
        result = resolve_formatted_tag('program.get_nested_list().1.value', self.context)
        self.assertEqual(result, 200)

    def test_indexing_preserves_existing_list_behavior(self):
        """Test that existing list behavior is preserved for non-numeric attributes"""
        # This should still apply the attribute to each element
        result = resolve_formatted_tag('program.get_nested_list().name', self.context)
        self.assertEqual(result, ['Item1', 'Item2'])

    def test_dict_with_numeric_keys_vs_list_indexing(self):
        """Test that dicts with numeric keys work correctly"""
        context = {
            'numeric_dict': {'0': 'dict_value_0', '1': 'dict_value_1'},
            'actual_list': ['list_value_0', 'list_value_1']
        }
        
        # Dict should use key access
        result = resolve_formatted_tag('numeric_dict.0', context)
        self.assertEqual(result, 'dict_value_0')
        
        # List should use index access
        result = resolve_formatted_tag('actual_list.0', context)
        self.assertEqual(result, 'list_value_0')


if __name__ == '__main__':
    unittest.main()