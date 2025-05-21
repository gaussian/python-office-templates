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
)
from .paragraphs import process_paragraph
from .tables import process_table_cell


def process_loops(prs, context, perm_user, errors):
    """
    Process loops in the presentation:
    - Identify loop sections (slides between %loop var in collection% and %endloop%)
    - Duplicate those slides for each item in the collection
    - Return a list of slides to process with their context info
    """
    slides_to_process = []
    in_loop = False
    loop_start_index = -1
    loop_variable = None
    loop_collection = None
    
    # First, extract loop information from the slides
    for i, slide in enumerate(prs.slides):
        slide_number = i + 1
        # Track whether this slide has loop directives
        has_loop_start = False
        has_loop_end = False
        
        for shape in slide.shapes:
            # Check for loop start
            if is_loop_start(shape):
                if in_loop:
                    errors.append(f"Error on slide {slide_number}: Nested loops are not supported")
                    continue
                    
                variable, collection = extract_loop_directive(shape.text_frame.text)
                if variable and collection:
                    in_loop = True
                    loop_start_index = i
                    loop_variable = variable
                    loop_collection = collection
                    has_loop_start = True
            
            # Check for loop end
            if is_loop_end(shape):
                if not in_loop:
                    errors.append(f"Error on slide {slide_number}: %endloop% without a matching loop start")
                    continue
                    
                has_loop_end = True
        
        # Cannot have both loop start and end on the same slide
        if has_loop_start and has_loop_end:
            errors.append(f"Error on slide {slide_number}: Cannot have both loop start and end on the same slide")
            in_loop = False
            loop_start_index = -1
            loop_variable = None
            loop_collection = None
        
        # If we found the end of a loop, process it
        if has_loop_end and in_loop:
            loop_end_index = i
            
            # Get the collection from the context
            collection_value = context.get(loop_collection)
            if collection_value is None:
                errors.append(f"Error on slide {slide_number}: Collection '{loop_collection}' not found in context")
                in_loop = False
                continue
                
            # Ensure the collection is iterable
            try:
                iter(collection_value)
            except TypeError:
                errors.append(f"Error on slide {slide_number}: '{loop_collection}' is not iterable")
                in_loop = False
                continue
            
            # For each item in the collection, duplicate the loop slides
            loop_slides = []
            for loop_item in collection_value:
                for j in range(loop_start_index, loop_end_index + 1):
                    slide_info = {
                        "slide": prs.slides[j],
                        "slide_number": j + 1,
                        "loop_var": loop_variable,
                        "loop_item": loop_item
                    }
                    loop_slides.append(slide_info)
            
            # Mark these slides for processing
            slides_to_process.extend(loop_slides)
            
            # Reset loop state
            in_loop = False
            loop_start_index = -1
            loop_variable = None
            loop_collection = None
    
    # If we're still in a loop at the end, that's an error
    if in_loop:
        errors.append(f"Error: Loop started but never closed with %endloop%")
    
    # Add all non-loop slides to the processing list
    for i, slide in enumerate(prs.slides):
        # Check if this slide is part of a loop
        is_in_loop = False
        for shape in slide.shapes:
            if is_loop_start(shape) or is_loop_end(shape):
                is_in_loop = True
                break
        
        # If not in a loop, add it for regular processing
        if not is_in_loop:
            slides_to_process.append({
                "slide": slide,
                "slide_number": i + 1
            })
    
    return slides_to_process


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
            slide_context[slide_info["loop_var"]] = slide_info["loop_item"]
        
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
