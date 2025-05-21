from copy import deepcopy
from pptx import Presentation

from .charts import process_chart
from .images import (
    replace_shape_with_image,
    should_replace_shape_with_image,
)
from .loops import (
    extract_loop_directive,
    is_loop_end,
    is_loop_start,
    process_loops,
)
from .paragraphs import process_paragraph
from .tables import process_table_cell


def render_pptx(template, context: dict, output, perm_user):
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

    errors = []
    
    # Process loops first - identify loop sections and duplicate slides
    slides_to_process = process_loops(prs, context, perm_user, errors)
    
    # Track which slides and shapes have been processed to avoid processing the same data multiple times
    processed_content = set()
    
    # Process all slides including duplicated ones from loops
    for slide_info in slides_to_process:
        slide = slide_info["slide"]
        slide_number = slide_info.get("slide_number", 0)
        
        # Create slide context - add loop variable if this is a loop iteration
        slide_context = {
            **context,
            "slide_number": slide_number,
        }
        
        # Add loop variable to context if present
        if "loop_var" in slide_info and "loop_item" in slide_info:
            loop_id = id(slide_info["loop_item"])  # Use object id to distinguish between iterations
            slide_context[slide_info["loop_var"]] = slide_info["loop_item"]
        else:
            loop_id = None
        
        # Create a unique ID for this slide in this context
        slide_context_id = f"{id(slide)}_{loop_id}"
        
        # Skip if we've already processed this exact slide with this exact context
        if slide_context_id in processed_content:
            continue
            
        processed_content.add(slide_context_id)
        
        # Process the slide's shapes
        for shape in slide.shapes:
            # Skip shapes that are loop directives - they've already been processed
            if is_loop_start(shape) or is_loop_end(shape):
                continue
                
            # Check if this shape should be replaced with an image.
            if should_replace_shape_with_image(shape):
                try:
                    replace_shape_with_image(
                        shape,
                        slide,
                        context=slide_context,
                        perm_user=perm_user,
                    )
                except Exception as e:
                    errors.append(
                        f"Error processing image (slide {slide_number}): {e}"
                    )
                # Skip further processing for this shape
                continue

            # 1) Process text frames (non-table).
            if hasattr(shape, "text_frame"):
                for paragraph in shape.text_frame.paragraphs:
                    # Merge any placeholders that are split across multiple runs.
                    try:
                        process_paragraph(
                            paragraph=paragraph,
                            context=slide_context,
                            perm_user=perm_user,
                            mode="normal",  # for text frames
                        )
                    except Exception as e:
                        errors.append(f"Error in paragraph (slide {slide_number}): {e}")
            # 2) Process tables.
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    for cell in row.cells:
                        try:
                            process_table_cell(
                                cell=cell,
                                context=slide_context,
                                perm_user=perm_user,
                            )
                        except Exception as e:
                            errors.append(
                                f"Error in table cell (slide {slide_number}): {e}"
                            )
            # 3) Process chart spreadsheets.
            if getattr(shape, "has_chart", False):
                try:
                    process_chart(
                        chart=shape.chart,
                        context=slide_context,
                        perm_user=perm_user,
                    )
                except Exception as e:
                    errors.append(f"Error in chart (slide {slide_number}): {e}")


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
