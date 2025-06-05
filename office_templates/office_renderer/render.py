from io import BytesIO
from typing import IO, Callable, Optional

from .pptx.render import render_pptx
from .xlsx.render import render_xlsx
from .utils import identify_file_type


def render_from_file_stream(
    template_file_stream: IO[bytes],
    context: dict,
    check_permissions: Optional[Callable[[object], bool]],
):
    """
    Render the document template (a path string or a file-like object) using the provided context and save to output.
    'output' can be a path string or a file-like object. If it's a file-like object, it will be rewound after saving.

    We delegate

    Parameters:
        template: Path to the template document file or a file-like object
        context: Dictionary with values to replace placeholders
        output: Path or file-like object where to save the rendered result
        check_permissions: Function to check permissions for objects

    Returns:
        Tuple (output, errors) where errors is None if successful or a list of errors
    """

    # Get the file type
    file_type = identify_file_type(template_file_stream)

    # Prepare an output stream to save to
    output = BytesIO()

    # Render if PPTX
    if file_type == "pptx":
        _, errors = render_pptx(
            template=template_file_stream,
            context=context,
            output=output,
            check_permissions=check_permissions,
        )

    # Render if XLSX
    elif file_type == "xlsx":
        _, errors = render_xlsx(
            template=template_file_stream,
            context=context,
            output=output,
            check_permissions=check_permissions,
        )

    else:
        assert False, f"Unsupported file type: {file_type}"

    return output, errors, file_type
