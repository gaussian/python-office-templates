from typing import IO, Callable, Optional
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from ..charts import process_chart
from ..images import (
    replace_shape_with_image,
    should_replace_shape_with_image,
)
from ..paragraphs import process_paragraph
from ..tables import process_table_cell
from .loops import (
    is_loop_end,
    is_loop_start,
    process_loops,
)
from .utils import remove_shape


def render_pptx(
    template: str | IO[bytes],
    context: dict,
    output: str | IO[bytes],
    check_permissions: Optional[Callable[[object], bool]],
):
    """
    Render the PPTX template (a path string or a file-like object) using the provided context and save to output.
    'output' can be a path string or a file-like object. If it's a file-like object, it will be rewound after saving.
    """
    # Support template as a file path or file-like object.
    if isinstance(template, str):
        prs = Presentation(template)
    else:
        template.seek(0)
        prs = Presentation(template)

    errors: list[str] = []

    # Process loops first - identify loop sections and duplicate slides
    slides_to_process = process_loops(
        prs,
        context=context,
        check_permissions=check_permissions,
        errors=errors,
    )

    # Process all slides including duplicated ones from loops
    for slide_info in slides_to_process:
        slide = slide_info["slide"]
        slide_number = slide_info.get("slide_number", 0)
        extra_context = slide_info.get("extra_context", {})

        # Create slide context (include `extra_context`, which is where loop variables are)
        slide_context = {
            **context,
            **extra_context,
            "slide_number": slide_number,
        }

        # Add loop variable to context if present
        if "loop_var" in slide_info and "loop_item" in slide_info:
            slide_context[slide_info["loop_var"]] = slide_info["loop_item"]

        # Process the slide
        process_single_slide(
            slide=slide,
            context=slide_context,
            slide_number=slide_number,
            check_permissions=check_permissions,
            errors=errors,
        )

    if errors:
        print("Rendering aborted due to the following errors:")
        for err in set(errors):
            print(f" - {err}")
        print("Output file not saved.")
        return None, errors

    # Save to output (file path or file-like object)
    if isinstance(output, str):
        prs.save(output)
    else:
        prs.save(output)
        output.seek(0)

    return output, None


def process_single_slide(
    slide,
    context: dict,
    slide_number: int,
    check_permissions: Optional[Callable[[object], bool]],
    errors: list[str],
):
    """Process a single slide with the given context."""
    # Process the slide's shapes
    for shape in slide.shapes:
        # Skip loop directive shapes - we'll clear them later
        if is_loop_start(shape) or is_loop_end(shape):
            continue

        # Process the shape content
        process_shape_content(
            shape,
            slide=slide,
            context=context,
            slide_number=slide_number,
            check_permissions=check_permissions,
            errors=errors,
        )


def process_shape_content(
    shape,
    slide,
    context: dict,
    slide_number: int,
    check_permissions: Optional[Callable[[object], bool]],
    errors: list[str],
):
    """Process the content of a shape based on its type."""
    # 0) Check if this is a grouped shape and process recursively.
    if hasattr(shape, "shape_type") and shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for grouped_shape in shape.shapes:
            process_shape_content(
                shape=grouped_shape,
                slide=slide,
                context=context,
                slide_number=slide_number,
                check_permissions=check_permissions,
                errors=errors,
            )
        return

    # 1) Check if this shape should be replaced with an image.
    if should_replace_shape_with_image(shape):
        try:
            replace_shape_with_image(
                shape,
                slide,
                context=context,
                check_permissions=check_permissions,
            )
        except Exception as e:
            errors.append(f"Error processing image (slide {slide_number}): {e}")
        # Skip further processing for this shape.
        return

    # 2) Check if this shape should be removed (because it's a loop directive).
    if is_loop_start(shape) or is_loop_end(shape):
        remove_shape(shape)
        return

    # 3) Process text frames (non-table).
    if hasattr(shape, "text_frame"):
        for paragraph in shape.text_frame.paragraphs:
            # Merge any placeholders that are split across multiple runs.
            try:
                process_paragraph(
                    paragraph=paragraph,
                    context=context,
                    check_permissions=check_permissions,
                    mode="normal",  # for text frames
                )
            except Exception as e:
                errors.append(f"Error in paragraph (slide {slide_number}): {e}")

    # 4) Process tables.
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                try:
                    process_table_cell(
                        cell=cell,
                        context=context,
                        check_permissions=check_permissions,
                    )
                except Exception as e:
                    errors.append(f"Error in table cell (slide {slide_number}): {e}")

    # 5) Process chart spreadsheets.
    if getattr(shape, "has_chart", False):
        try:
            process_chart(
                chart=shape.chart,
                context=context,
                check_permissions=check_permissions,
            )
        except Exception as e:
            errors.append(f"Error in chart (slide {slide_number}): {e}")
