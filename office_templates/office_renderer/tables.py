from copy import deepcopy

from pptx.table import _Cell

from template_reports.templating import process_text, get_matching_tags

from .exceptions import TableCellOverwriteError, TableError
from .paragraphs import process_paragraph


def process_table_cell(cell, context, perm_user=None):
    """
    Process the text in a table cell.

    If the cell's text contains exactly one placeholder, process in "table" mode.
    If the result is a list, fill the column with the list items (and expand table if not enough room).
    Otherwise, process each paragraph in "normal" mode.
    """
    cell_text = cell.text.strip()

    matches = get_matching_tags(cell_text)

    # Process in "table" mode if exactly one tag is found.
    if len(matches) == 1:
        result = process_text(
            cell_text,
            context,
            perm_user=perm_user,
            mode="table",
        )
        if isinstance(result, list):
            fill_column_with_list(cell, result)
        else:
            cell.text = result

    # Otherwise, process each paragraph in "normal" mode.
    else:
        for paragraph in cell.text_frame.paragraphs:
            process_paragraph(
                paragraph,
                context,
                perm_user,
                mode="normal",
            )


def fill_column_with_list(cell, items):
    """
    Fill the table column corresponding to the given cell with values from `items`.

    (1) Update the original cell with the first item.
    (2) For subsequent items, try to fill existing cells in later rows in the same column
        if they are empty (after stripping whitespace).
    (3) If there are not enough existing rows with empty cells, clone the current row
        for the remaining items.

    If the cell's underlying XML does not have a parent (row or table not found), simply update the cell.
    """
    if not items:
        cell.text = ""
        return

    # Set first item in original cell.
    cell.text = str(items[0])

    # Attempt to get the row element (<a:tr>) from the cell's XML.
    row_element = cell._tc.getparent()
    if row_element is None:
        raise TableError(f"Row element not found while replacing {items}.")
    table_element = row_element.getparent()
    if table_element is None:
        raise TableError(f"Table element not found while replacing {items}.")

    # Determine the cell's index in the row.
    row_cells = list(row_element)
    cell_index = row_cells.index(cell._tc)

    # Get all rows from the table element.
    table_rows = list(table_element)

    try:
        current_row_index = table_rows.index(row_element)
    except Exception:
        raise TableError(f"Row element not found in table while replacing {items}.")

    remaining_items = items[1:]

    # Fill existing rows that follow if their cell is empty.
    for r in table_rows[current_row_index + 1 :]:
        if len(r) > cell_index:
            cell_element = r[cell_index]
            cell_text = cell_element.text if hasattr(cell_element, "text") else ""
            if cell_text.strip():
                raise TableCellOverwriteError(
                    f"Cell in table would be overwritten: {cell_text}"
                )
            set_cell_text(remaining_items.pop(0), cell_element, r)
            # Stop if no more items to fill.
            if not remaining_items:
                return

    # If still items remaining, clone the current row for each item.
    for item in remaining_items:
        new_row_element = clone_row_with_value(row_element, cell_index, item)
        table_element.append(new_row_element)


def clone_row_with_value(original_row, cell_index, new_text):
    """
    Helper function to create a new row from an existing row.

    - Deep-copies the original row.
    - Finds the cell at the given cell_index.
    - Updates that cell's text with new_text.
    - Returns the new row element.

    Uses _Cell to update the text properly.
    """

    new_row = deepcopy(original_row)
    new_row_cells = list(new_row)

    if cell_index < 0 or cell_index >= len(new_row_cells):
        raise TableError(
            f"Cell index {cell_index} out of bounds for row {new_row_cells}."
        )

    # Process text cells in the new row.
    for i, cell_element in enumerate(new_row_cells):
        # Cell is already empty, so skip if not the target cell.
        if not cell_element.text and i != cell_index:
            continue

        # Update the cell at the given index with the new text.
        if "{{" in cell_element.text:
            set_cell_text("", cell_element, new_row)
            # cell.text = ""

        # Clear cells that contain a template placeholder.
        elif i == cell_index:
            # cell.text = str(new_text)
            set_cell_text(str(new_text), cell_element, new_row)

    return new_row


def set_cell_text(text: str, cell_element, parent_row):
    """
    Set the text of a cell in a table.

    If the cell is not found in the parent, raise a TableError.
    """
    # Add wrapper so we can set the cell text
    cell = _Cell(cell_element, parent=parent_row)

    # Update the cell text
    cell.text = text
