import unittest
from unittest.mock import MagicMock, patch
from template_reports.office_renderer.worksheets import process_worksheet
from template_reports.office_renderer.exceptions import CellOverwriteError


class TestProcessWorksheet(unittest.TestCase):
    def setUp(self):
        # Create a mock worksheet with cells containing placeholder text
        self.context = {
            "user": {"name": "Alice", "email": "alice@example.com"},
            "company": "Example Corp",
            "values": {"0": 10.5, "1": 20.25, "2": 30.75},
            "employees": ["Alice", "Bob", "Carol"],
        }

        # Create mock cell objects
        self.cell1 = MagicMock()
        self.cell1.value = "Hello, {{ user.name }}"
        self.cell1.column_letter = "A"

        self.cell2 = MagicMock()
        self.cell2.value = "{{ company }}"
        self.cell2.column_letter = "A"

        self.cell3 = MagicMock()
        self.cell3.value = "{{ values.0 }}"
        self.cell3.column_letter = "B"

        self.cell4 = MagicMock()
        self.cell4.value = "{{ values.1 }}"
        self.cell4.column_letter = "B"

        self.cell5 = MagicMock()
        self.cell5.value = "{{ values.2 }}"
        self.cell5.column_letter = "B"

        self.col1 = [self.cell1, self.cell2]
        self.col2 = [self.cell3, self.cell4, self.cell5]

        # Create a mock worksheet
        self.worksheet = MagicMock()
        self.worksheet.iter_cols.return_value = [self.col1, self.col2]
        self.worksheet.max_row = 5  # Set max_row for the worksheet

        # Setup worksheet[] access to return empty cells for expansion
        def mock_getitem(key):
            mock_cell = MagicMock()
            mock_cell.value = None
            return mock_cell

        self.worksheet.__getitem__.side_effect = mock_getitem

        # Request user for permission checks
        self.request_user = MagicMock()
        self.request_user.has_perm.return_value = True

    @patch("template_reports.office_renderer.worksheets.process_text_list")
    def test_process_worksheet_basic(self, mock_process_text_list):
        """Test that the process_worksheet function processes all columns."""
        # Set up mock return values for process_text_list - each call returns a single value per cell
        mock_process_text_list.side_effect = [
            ["Hello, Alice"],  # For cell1
            ["Example Corp"],  # For cell2
            [10.5],  # For cell3
            [20.25],  # For cell4
            [30.75],  # For cell5
        ]

        # Call process_worksheet
        process_worksheet(
            worksheet=self.worksheet, context=self.context, perm_user=self.request_user
        )

        # Verify cell values were updated correctly
        self.assertEqual(self.cell1.value, "Hello, Alice")
        self.assertEqual(self.cell2.value, "Example Corp")
        self.assertEqual(self.cell3.value, 10.5)
        self.assertEqual(self.cell4.value, 20.25)
        self.assertEqual(self.cell5.value, 30.75)

    @patch("template_reports.office_renderer.worksheets.process_text_list")
    def test_process_worksheet_preserves_cell_values(self, mock_process_text_list):
        """Test that non-template cell values are preserved."""
        # Cell without template
        plain_cell = MagicMock()
        plain_cell.value = "Plain text"
        plain_cell.column_letter = "A"

        # Column with mixed content
        mixed_col = [plain_cell, self.cell1]
        self.worksheet.iter_cols.return_value = [mixed_col]

        # Return values that don't expand - one value per call
        mock_process_text_list.side_effect = [
            ["Plain text"],  # For plain_cell
            ["Hello, Alice"],  # For cell1
        ]

        # Process the worksheet
        process_worksheet(worksheet=self.worksheet, context=self.context, perm_user=None)

        # Verify plain text is preserved
        self.assertEqual(plain_cell.value, "Plain text")
        self.assertEqual(self.cell1.value, "Hello, Alice")

    @patch("template_reports.office_renderer.worksheets.process_text_list")
    def test_list_expansion(self, mock_process_text_list):
        """Test that a cell with a list placeholder expands to multiple rows."""
        # Create a cell with a list placeholder
        list_cell = MagicMock()
        list_cell.value = "{{ employees }}"
        list_cell.column_letter = "C"

        # Create a column with the list cell
        list_col = [list_cell]
        self.worksheet.iter_cols.return_value = [list_col]

        # Mock process_text_list to return multiple values (expanded list)
        mock_process_text_list.return_value = ["Alice", "Bob", "Carol"]

        # Process the worksheet
        process_worksheet(worksheet=self.worksheet, context=self.context, perm_user=None)

        # Verify the cell was updated with the first value
        self.assertEqual(list_cell.value, "Alice")

        # Verify that the worksheet[] was called to get cells for the additional values
        self.worksheet.__getitem__.assert_any_call("C2")
        self.worksheet.__getitem__.assert_any_call("C3")

    @patch("template_reports.office_renderer.worksheets.process_text_list")
    def test_cell_overwrite_error(self, mock_process_text_list):
        """Test that CellOverwriteError is raised when trying to expand into non-empty cells."""
        # Create a cell with a list placeholder
        list_cell = MagicMock()
        list_cell.value = "{{ employees }}"
        list_cell.column_letter = "C"

        # Column with the list cell
        list_col = [list_cell]
        self.worksheet.iter_cols.return_value = [list_col]

        # Mock process_text_list to return multiple values (expanded list)
        mock_process_text_list.return_value = ["Alice", "Bob", "Carol"]

        # Set up worksheet[] to return a cell with value for C2 (would be overwritten)
        def mock_getitem_with_value(key):
            mock_cell = MagicMock()
            # C2 already has a value, others are empty
            if key == "C2":
                mock_cell.value = "Existing value"
            else:
                mock_cell.value = None
            return mock_cell

        self.worksheet.__getitem__.side_effect = mock_getitem_with_value

        # Process the worksheet - should raise CellOverwriteError
        with self.assertRaises(CellOverwriteError):
            process_worksheet(
                worksheet=self.worksheet, context=self.context, perm_user=None
            )


if __name__ == "__main__":
    unittest.main()
