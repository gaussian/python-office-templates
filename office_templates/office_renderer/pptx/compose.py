from pptx import Presentation

from template_reports.templating.core import process_text

from .render import process_single_slide
from .layout_utils import build_layout_mapping
from .slide_utils import copy_slide_across_presentations


def process_placeholders(
    slide,
    placeholders: list[str],
    context: dict,
    slide_number: int,
    perm_user,
    errors: list[str],
):
    """Process placeholder shapes on a slide."""

    placeholder_index = 0
    for shape in slide.shapes:
        # Check if this shape is a placeholder
        if (
            hasattr(shape, "is_placeholder")
            and shape.is_placeholder
            and placeholder_index < len(placeholders)
        ):
            try:
                placeholder_text = placeholders[placeholder_index]
                processed_text = process_text(placeholder_text, context, perm_user)

                # Set the processed text to the shape
                if hasattr(shape, "text_frame"):
                    shape.text_frame.text = processed_text
                elif hasattr(shape, "text"):
                    shape.text = processed_text

                placeholder_index += 1
            except Exception as e:
                errors.append(
                    f"Error processing placeholder {placeholder_index} (slide {slide_number}): {e}"
                )


def compose_pptx(
    template_files: list,
    slide_specs: list[dict],
    global_context: dict,
    output,
    perm_user=None,
    use_tagged_layouts=False,
    use_all_slides_as_layouts_by_title=False,
):
    """
    Compose a PPTX deck using layout slides from multiple template files.

    Args:
        template_files: List of template file paths or file-like objects
        slide_specs: List of slide dictionaries, each containing 'layout' key and context data
        global_context: Global context dictionary
        output: Output file path or file-like object
        perm_user: Permission user object
        use_tagged_layouts: If True, include slides with % layout XXX % tags
        use_all_slides_as_layouts_by_title: If True, use all slides as layouts by title

    Returns:
        Tuple of (output, errors) - errors is None if successful, list of errors otherwise
    """
    errors = []

    try:
        # Validate inputs
        if not template_files:
            errors.append("No template files provided")
            return None, errors

        if not slide_specs:
            errors.append("No slides specified")
            return None, errors

        # Build layout mapping from all template files
        layout_mapping = build_layout_mapping(
            template_files,
            use_tagged_layouts=use_tagged_layouts,
            use_all_slides_as_layouts_by_title=use_all_slides_as_layouts_by_title,
        )

        if not layout_mapping:
            errors.append("No layout slides found in template files")
            return None, errors

        # Use the first template as the base presentation
        if isinstance(template_files[0], str):
            base_prs = Presentation(template_files[0])
        else:
            template_files[0].seek(0)
            base_prs = Presentation(template_files[0])

        # Remove all slides from the base presentation to create a blank deck
        sld_ids = base_prs.slides._sldIdLst
        while len(sld_ids) > 0:
            slide_id = sld_ids[0]
            sld_ids.remove(slide_id)

        # Create slides from the slide specifications
        for slide_index, slide_spec in enumerate(slide_specs):
            try:
                # Validate slide specification
                if "layout" not in slide_spec:
                    errors.append(f"Slide {slide_index + 1}: Missing 'layout' key")
                    continue

                layout_id = slide_spec["layout"]
                if layout_id not in layout_mapping:
                    errors.append(
                        f"Slide {slide_index + 1}: Layout '{layout_id}' not found"
                    )
                    continue

                # Get the layout slide or layout
                source_prs, layout_item = layout_mapping[layout_id]

                # Handle both slide layouts and actual slides
                if hasattr(layout_item, "slide_layout"):
                    # It's a slide - copy it directly
                    new_slide = copy_slide_across_presentations(base_prs, layout_item)
                else:
                    # It's a slide layout - find equivalent layout in base presentation or use blank
                    if len(base_prs.slide_layouts) > 6:
                        layout = base_prs.slide_layouts[6]  # Use blank layout
                    elif len(base_prs.slide_layouts) > 0:
                        layout = base_prs.slide_layouts[0]  # Use first available layout
                    else:
                        errors.append(
                            f"Slide {slide_index + 1}: No slide layouts available in base presentation"
                        )
                        continue
                    new_slide = base_prs.slides.add_slide(layout)

                # Prepare slide context
                slide_context = {**global_context, **slide_spec}
                
                # Pre-process any template variables in slide context values
                # This handles cases where slide context contains template strings
                for key, value in slide_context.items():
                    if isinstance(value, str) and '{{' in value and '}}' in value:
                        try:
                            slide_context[key] = process_text(value, slide_context, perm_user)
                        except Exception as e:
                            errors.append(f"Error processing template in slide context '{key}': {e}")
                
                slide_number = slide_index + 1

                # Get placeholders if specified
                placeholders = slide_spec.get("placeholders", None)
                
                # Handle placeholders first if provided
                if placeholders:
                    process_placeholders(
                        new_slide, placeholders, slide_context, slide_number, perm_user, errors
                    )

                # Process the slide
                process_single_slide(
                    new_slide,
                    slide_context,
                    slide_number,
                    perm_user,
                    errors,
                )

            except Exception as e:
                errors.append(f"Error processing slide {slide_index + 1}: {e}")

        # If we have errors, don't save
        if errors:
            print("Composition aborted due to the following errors:")
            for err in set(errors):
                print(f" - {err}")
            print("Output file not saved.")
            return None, errors

        # Save to output (file path or file-like object)
        if isinstance(output, str):
            base_prs.save(output)
        else:
            base_prs.save(output)
            output.seek(0)

        return output, None

    except Exception as e:
        errors.append(f"Unexpected error during composition: {e}")
        return None, errors
