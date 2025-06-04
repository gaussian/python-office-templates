from pptx import Presentation
from .slide_utils import remove_shape
from .loops import is_loop_start, is_loop_end


def build_layout_mapping(
    template_files,
    use_tagged_layouts=False,
    use_all_slides_as_layouts_by_title=False,
):
    """
    Build a mapping of layout IDs to slide objects from multiple template files.

    Args:
        template_files: List of template file paths or file-like objects
        use_tagged_layouts: If True, include slides with % layout XXX % tags
        use_all_slides_as_layouts_by_title: If True, use all slides as layouts by title

    Returns:
        dict: Mapping of layout ID (str) to (presentation, slide) tuple
    """
    layout_mapping = {}

    for template_file in template_files:
        # Load presentation
        if isinstance(template_file, str):
            prs = Presentation(template_file)
        else:
            template_file.seek(0)
            prs = Presentation(template_file)

        # Get master layouts
        master_layouts = get_master_layouts(prs)
        for layout_id, layout in master_layouts.items():
            layout_mapping[layout_id] = (prs, layout)

        # Get tagged layouts if enabled
        if use_tagged_layouts:
            try:
                tagged_layouts = get_tagged_layouts(prs)
                for layout_id, slide in tagged_layouts.items():
                    layout_mapping[layout_id] = (prs, slide)
            except ValueError as e:
                # Re-raise validation errors to let the caller handle them
                raise e

        # Get title layouts if enabled
        if use_all_slides_as_layouts_by_title:
            title_layouts = get_title_layouts(prs)
            for layout_id, slide in title_layouts.items():
                layout_mapping[layout_id] = (prs, slide)

    return layout_mapping


def get_master_layouts(prs):
    """Get master layout slides where ID is the layout name."""
    layouts = {}
    for slide_layout in prs.slide_layouts:
        # Use the layout name as the ID
        layout_id = slide_layout.name
        # For master layouts, we'll store the layout itself
        # and create slides from it when needed
        layouts[layout_id] = slide_layout

    return layouts


def get_tagged_layouts(prs):
    """Get slides that have shapes with % layout XXX % tags."""
    import re

    layouts = {}
    pattern = re.compile(r"%\s*layout\s+(\w+)\s*%", re.IGNORECASE)

    for slide in prs.slides:
        layout_shapes = []
        layout_id = None
        
        # First pass: find all %layout% shapes and check for conflicts
        for shape in slide.shapes:
            if hasattr(shape, "text_frame") and hasattr(shape.text_frame, "text"):
                text = shape.text_frame.text.strip()
                match = pattern.search(text)
                if match:
                    layout_shapes.append(shape)
                    if layout_id is None:
                        layout_id = match.group(1)
                    elif layout_id != match.group(1):
                        raise ValueError(f"Multiple different layout IDs found on same slide: '{layout_id}' and '{match.group(1)}'")
        
        # Validate: only one %layout% shape per slide
        if len(layout_shapes) > 1:
            raise ValueError(f"Multiple %layout% shapes found on same slide")
        
        # If we found a layout, validate no loop directives on this slide
        if layout_id is not None:
            for shape in slide.shapes:
                if is_loop_start(shape) or is_loop_end(shape):
                    raise ValueError(f"Slide with %layout% cannot contain %loop% or %endloop% directives")
            
            # Remove the %layout% shape
            for shape in layout_shapes:
                remove_shape(shape)
            
            layouts[layout_id] = slide

    return layouts


def get_title_layouts(prs):
    """Get all slides as layouts where ID is the slide title."""
    layouts = {}

    for slide in prs.slides:
        # Find the title shape (usually the first shape or a shape with specific placeholder type)
        title = None
        for shape in slide.shapes:
            if hasattr(shape, "text_frame") and hasattr(shape.text_frame, "text"):
                # Use the first text shape as title
                title = shape.text_frame.text.strip()
                break

        if title:
            layouts[title] = slide

    return layouts
