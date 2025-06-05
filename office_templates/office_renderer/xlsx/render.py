from typing import Callable, Optional
from ..utils import get_load_workbook
from .worksheets import process_worksheet


def render_xlsx(
    template,
    context: dict,
    output,
    check_permissions: Optional[Callable[[object], bool]],
):
    """
    Render the XLSX template (a path string or a file-like object) using the provided context and save to output.
    'output' can be a path string or a file-like object. If it's a file-like object, it will be rewound after saving.

    Parameters:
        template: Path to the template XLSX file or a file-like object
        context: Dictionary with values to replace placeholders
        output: Path or file-like object where to save the rendered result
        check_permissions: Function to check permissions for objects

    Returns:
        Tuple (output, errors) where errors is None if successful or a list of errors
    """

    load_workbook = get_load_workbook()

    # Load the workbook (support template as a file path or file-like object)
    if isinstance(template, str):
        workbook = load_workbook(template)
    else:
        template.seek(0)
        workbook = load_workbook(template)

    errors = []

    # Process each worksheet in the workbook
    for sheet_name in workbook.sheetnames:
        worksheet = workbook[sheet_name]

        # Add extra context per sheet
        sheet_context = {
            **context,
            "sheet_name": sheet_name,
        }

        try:
            process_worksheet(
                worksheet=worksheet,
                context=sheet_context,
                check_permissions=check_permissions,
            )

        except Exception as e:
            errors.append(f"Error in sheet '{sheet_name}': {e}")

    if errors:
        print("Rendering aborted due to the following errors:")
        for err in set(errors):
            print(f" - {err}")
        print("Output file not saved.")
        return None, errors

    # Save to output (file path or file-like object)
    if isinstance(output, str):
        workbook.save(output)
    else:
        workbook.save(output)
        output.seek(0)

    return output, None
