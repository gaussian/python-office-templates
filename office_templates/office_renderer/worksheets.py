from template_reports.templating.list import process_text_list


def process_worksheet(worksheet, context: dict, perm_user=None):
    process_kwargs = {
        "context": context,
        "perm_user": perm_user,
        "as_float": True,
        "fail_if_not_float": False,
    }

    # Process by rows
    for col in worksheet.iter_cols():
        # Extract values for the entire row
        row_values = [cell.value for cell in col]

        # Process the row values as a list
        processed_values = process_text_list(row_values, **process_kwargs)

        # Update the cells with processed values
        for cell, processed_value in zip(col, processed_values):
            cell.value = processed_value
