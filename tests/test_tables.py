import unittest
from unittest.mock import patch

from template_reports.office_renderer.exceptions import TableError
from template_reports.office_renderer.tables import (
    process_table_cell,
    clone_row_with_value,
    fill_column_with_list,
)
from template_reports.templating import process_text


# Define a DummyRequestUser for these tests.
class DummyRequestUser:
    def has_perm(self, perm, obj):
        return True


# Define dummy XML element classes to simulate pptx objects.


class DummyElement:
    def __init__(self, text):
        self.text = text
        self.parent = None

    def getparent(self):
        return self.parent

    # Add this method so that _Cell can call it.
    def get_or_add_txBody(self):
        return self

    # Added clear_content to simulate real behavior.
    def clear_content(self):
        self.text = ""

    # Add this to avoid AttributeError when cell.text is assigned:
    def add_p(self):
        # Return a new dummy paragraph element
        return DummyElement("")

    def _append_text(self, txt, p):
        p.text += txt
        return p

    # NEW: append_text method to satisfy the call from pptx.text.text.
    def append_text(self, txt):
        self.text += txt
        return self

    def __repr__(self):
        return f"DummyElement(text={self.text})"


class DummyRow(list):
    """A dummy row element (list of cell XML elements)."""

    def __init__(self, cells, parent=None):
        super().__init__(cells)
        for cell in cells:
            cell.parent = self
        self.parent = parent  # parent table

    def getparent(self):
        return self.parent

    def __deepcopy__(self, memo):
        # For the purpose of testing, we use deepcopy on a new DummyRow with copied cells.
        copied_cells = [DummyElement(cell.text) for cell in self]
        new_row = DummyRow(copied_cells, parent=self.parent)
        return new_row


class DummyTable:
    """A dummy table element that holds rows."""

    def __init__(self):
        self.rows = []

    def append(self, row):
        row.parent = self
        self.rows.append(row)

    def __iter__(self):
        return iter(self.rows)

    def __repr__(self):
        return f"DummyTable(rows={self.rows})"


class DummyCell:
    """
    A patched dummy version of pptx.table._Cell.
    Simply wraps a target DummyElement; setting text updates target.text.
    Avoids calling super() and related issues.
    """

    def __init__(self, target, parent):
        self.target = target
        self.parent = parent

    @property
    def text(self):
        return self.target.text

    @text.setter
    def text(self, value):
        self.target.text = value


# Dummy cell for process_table_cell tests.
class DummyTextFrame:
    def __init__(self, paragraphs):
        self.paragraphs = paragraphs


class DummyParagraph:
    def __init__(self, text):
        self.text = text
        self.runs = [DummyRun(text)]
        self._p = DummyElement("")  # dummy underlying XML

    def clear(self):
        """Clear existing runs."""
        self.runs = []

    def add_run(self):
        """Add a new run and return it."""
        run = DummyRun("")
        self.runs.append(run)
        return run


class DummyRun:
    def __init__(self, text):
        self.text = text
        self._r = DummyElement(text)


# For process_text, use the actual function from templating/core.py


class DummyCellWrapper:
    """
    Dummy cell simulating a table cell.
    Has an attribute _tc representing the underlying XML,
    a text_frame with paragraphs, and a text attribute.
    """

    def __init__(self, text):
        self.text = text
        # For testing, _tc will be a DummyElement.
        self._tc = DummyElement(text)
        self.text_frame = DummyTextFrame([DummyParagraph(text)])

    def __repr__(self):
        return f"DummyCellWrapper(text={self.text})"


class TestTables(unittest.TestCase):

    # --- Tests for clone_row_with_value ---
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_clone_row_with_value_normal(self):
        # Create a dummy row with three cells.
        cell1 = DummyElement("A")
        cell2 = DummyElement("B")
        cell3 = DummyElement("C")
        original_row = DummyRow([cell1, cell2, cell3])
        # Clone the row updating cell index 1 to "NEW".
        cloned = clone_row_with_value(original_row, 1, "NEW")
        # Verify cloned row cell 1's text.
        self.assertEqual(cloned[1].text, "NEW")
        # Ensure the other cells remain identical to original (copied value, not same reference)
        self.assertEqual(cloned[0].text, "A")
        self.assertEqual(cloned[2].text, "C")
        # Original row remains unchanged.
        self.assertEqual(original_row[1].text, "B")

    def test_clone_row_with_value_out_of_range(self):
        # If cell_index is out of range, row should remain unchanged.
        cell1 = DummyElement("X")
        original_row = DummyRow([cell1])
        with self.assertRaises(TableError):
            clone_row_with_value(original_row, 5, "NEW")

    # --- Tests for fill_column_with_list ---
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_fill_column_with_list_normal(self):
        # Create a dummy table structure with one row and one cell.
        cell_wrapper = DummyCellWrapper("ORIGINAL")
        row = DummyRow([cell_wrapper._tc])
        table = DummyTable()
        table.append(row)
        # Call fill_column_with_list on the cell with a list of items.
        items = ["First", "Second", "Third"]
        fill_column_with_list(cell_wrapper, items)
        # The original cell gets updated with first item.
        self.assertEqual(cell_wrapper.text, "First")
        # The table should now have the original row plus 2 new rows.
        self.assertEqual(
            len(table.rows), 3
        )  # Our dummy rows are appended to the XML table element
        # But our function uses: table_element.append(new_row_element)
        # So we simulate that by checking row.parent appended rows.
        # For this test, we simulate by creating a dummy table and manually setting parent's relationship.
        row.parent = table
        initial_row_count = len(table.rows)
        # Append additional row using clone_row_with_value.
        new_row = clone_row_with_value(row, 0, "Second")
        table.append(new_row)
        self.assertEqual(len(table.rows), initial_row_count + 1)
        # Verify that the cloned row's cell at index 0 has text "Second".
        self.assertEqual(new_row[0].text, "Second")

    def test_fill_column_with_list_empty(self):
        cell_wrapper = DummyCellWrapper("NonEmpty")
        # When items list is empty, cell text should be set to empty string.
        fill_column_with_list(cell_wrapper, [])
        self.assertEqual(cell_wrapper.text, "")

    # --- Tests for process_table_cell ---
    def test_process_table_cell_pure_placeholder(self):
        # For a pure placeholder, process_table_cell should use table mode.
        placeholder = "{{ test }}"
        cell_wrapper = DummyCellWrapper(placeholder)

        # Set up a dummy table structure:
        # Create a dummy row containing the cell's XML element.
        row = DummyRow([cell_wrapper._tc])
        # Create a dummy table and append the new row.
        dummy_table = DummyTable()
        dummy_table.append(row)

        # Now, cell_wrapper._tc.getparent() returns row and row.getparent() returns dummy_table.

        # Define a dummy process_text that returns a list.
        def dummy_process_text(text, context, perm_user, mode):
            if mode == "table":
                return ["Row1", "Row2"]
            return "Row1"

        original_process_text = process_text
        try:
            from template_reports.office_renderer import tables

            tables.process_text = dummy_process_text
            context = {"test": "ignored"}
            process_table_cell(cell_wrapper, context, None)
            # Since dummy_process_text returned a list, the original cell should be updated to first item.
            self.assertEqual(cell_wrapper.text, "Row1")
        finally:
            tables.process_text = original_process_text

    def test_process_table_cell_mixed_text(self):
        # For a cell that is not a pure placeholder, process_table_cell should call
        # process_paragraph and update the paragraph's runs.
        non_pure = "Prefix {{ test }} Suffix {{ test }}"
        cell_wrapper = DummyCellWrapper(non_pure)
        import template_reports.office_renderer.tables as tables_module

        # Save the original local binding for process_paragraph in tables module.
        original_para_processor = tables_module.__dict__.get("process_paragraph")
        try:

            def dummy_para_process(paragraph, context, perm_user, mode):
                # Get full text from paragraph runs.
                full_text = "".join(run.text for run in paragraph.runs)
                # Replace the placeholder with VALUE.
                new_text = full_text.replace("{{ test }}", "VALUE")
                # Clear runs and add a new run with new text.
                paragraph.clear()
                paragraph.add_run().text = new_text

            # Override the local process_paragraph reference in tables module.
            tables_module.__dict__["process_paragraph"] = dummy_para_process

            context = {"test": "VALUE"}
            # Call process_table_cell (which will use our dummy process_paragraph).
            from template_reports.office_renderer.tables import process_table_cell

            process_table_cell(cell_wrapper, context, perm_user=None)

            # Retrieve updated text from the first paragraph's first run.
            updated_text = cell_wrapper.text_frame.paragraphs[0].runs[0].text
            self.assertIn("VALUE", updated_text)
        finally:
            # Restore the original process_paragraph.
            tables_module.__dict__["process_paragraph"] = original_para_processor


if __name__ == "__main__":
    unittest.main()
