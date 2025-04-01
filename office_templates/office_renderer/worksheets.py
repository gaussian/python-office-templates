from template_reports.templating.list import process_text_list

from .exceptions import CellOverwriteError


def process_worksheet(worksheet, context: dict, perm_user=None):
    """
    Process a worksheet, replacing placeholders with values from the context.
    When a placeholder resolves to a list, it expands into multiple rows in the column.
    """
    process_kwargs = {
        "context": context,
        "perm_user": perm_user,
        "as_float": True,
        "fail_if_not_float": False,
    }

    # Process column by column, THEN each element (row) of the column.
    for col in worksheet.iter_cols():
        for cell_idx, cell in enumerate(col):
            # Process the cell value (with placeholders or otherwise)
            processed_value_list = process_text_list([cell.value], **process_kwargs)

            # If the cell was a straightforward value (with no expanded placeholders),
            # we can just set the cell value directly.
            if len(processed_value_list) == 1:
                processed_value = processed_value_list[0]
                cell.value = processed_value
                continue

            # Otherwise, we have a list of values (with expanded placeholders) and
            # we need to fill the rest of the column with these values.

            # First, set the current cell to the first value
            cell.value = processed_value_list[0]

            # Get the maximum row in the worksheet to ensure we have enough rows
            max_row = worksheet.max_row

            # Then fill the subsequent cells in the column with the remaining values
            for i, value in enumerate(processed_value_list[1:], start=1):
                row_idx = cell_idx + i + 1  # +1 because Excel is 1-based

                # Check if we're beyond the current max rows - if so, append rows
                if row_idx > max_row:
                    # Excel doesn't actually need explicit row creation since openpyxl
                    # will create them on demand, but we'll update max_row to track it
                    max_row = row_idx

                # Get the cell in the right column at the right row
                col_letter = cell.column_letter
                target_cell = worksheet[f"{col_letter}{row_idx}"]

                # Check if the target cell already has content
                if target_cell.value:
                    raise CellOverwriteError(
                        f"Cannot expand list into non-empty cell at {col_letter}{row_idx}"
                    )

                # Set the value
                target_cell.value = value
