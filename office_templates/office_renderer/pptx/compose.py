from typing import Callable, Optional

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_CONNECTOR_TYPE
from pptx.dml.color import RGBColor

from office_templates.templating.core import process_text_recursive

from .render import process_single_slide
from .layouts import build_layout_mapping
from .utils import copy_slide_across_presentations


def compose_pptx(
    template_files: list,
    slide_specs: list[dict],
    global_context: dict,
    output,
    check_permissions: Optional[Callable[[object], bool]] = None,
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
        check_permissions: Permission checking function
        use_tagged_layouts: If True, include slides with % layout XXX % tags
        use_all_slides_as_layouts_by_title: If True, use all slides as layouts by title

    Slide Specification:
        Each slide_spec can be a regular slide or a graph slide:
        
        Regular slide:
            - layout: Layout name (required)
            - placeholders: List of placeholder texts (optional)
            - Any other context data for template processing
            
        Graph slide:
            - layout: Layout name (required)
            - graph: Dict containing 'nodes' and 'edges' (optional)
                - nodes: List of node dicts with:
                    - id (str, required): Unique identifier
                    - name (str, required): Display name
                    - detail (str, optional): Additional detail text
                    - position (dict, required): {"x": inches, "y": inches}
                    - parent (str, optional): Parent node ID (placeholder)
                - edges: List of edge dicts with:
                    - from (str, required): Source node ID
                    - to (str, required): Target node ID
                    - label (str, optional): Edge label text

    Returns:
        Tuple of (output, errors) - errors is None if successful, list of errors otherwise
    """
    errors: list[str] = []

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

                # Process the slide spec in case there are any template variables
                for key, value in slide_spec.items():
                    slide_spec[key] = process_text_recursive(
                        value, global_context, check_permissions
                    )

                # Prepare slide context
                slide_context = {**global_context, **slide_spec}
                slide_number = slide_index + 1

                # Get placeholders if specified
                placeholders = slide_spec.get("placeholders", None)

                # Handle placeholders first if provided
                if placeholders:
                    process_placeholders(
                        slide=new_slide,
                        placeholders=placeholders,
                        slide_number=slide_number,
                        errors=errors,
                    )

                # Check if this is a graph slide
                if "graph" in slide_spec:
                    _process_graph_slide(
                        slide=new_slide,
                        graph=slide_spec["graph"],
                        base_prs=base_prs,
                        global_context=global_context,
                        check_permissions=check_permissions,
                        slide_number=slide_number,
                        errors=errors,
                    )
                
                # Process the slide for template variables
                process_single_slide(
                    slide=new_slide,
                    context=slide_context,
                    slide_number=slide_number,
                    check_permissions=check_permissions,
                    errors=errors,
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


def process_placeholders(
    slide,
    placeholders: list[str],
    slide_number: int,
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
                # Set the processed text to the shape
                placeholder_text = placeholders[placeholder_index]
                if hasattr(shape, "text_frame"):
                    shape.text_frame.text = placeholder_text
                elif hasattr(shape, "text"):
                    shape.text = placeholder_text

                placeholder_index += 1
            except Exception as e:
                errors.append(
                    f"Error processing placeholder {placeholder_index} (slide {slide_number}): {e}"
                )


def _process_graph_slide(
    slide,
    graph: dict,
    base_prs,
    global_context: dict,
    check_permissions: Optional[Callable[[object], bool]],
    slide_number: int,
    errors: list[str],
):
    """
    Process a graph slide by creating nodes and edges.
    
    Args:
        slide: The slide to add graph elements to
        graph: Dict containing 'nodes' and 'edges'
        base_prs: The presentation object (for slide resizing)
        global_context: Global context for template processing
        check_permissions: Permission checking function
        slide_number: Slide number for error reporting
        errors: List to append errors to
    """
    try:
        # Validate graph structure
        if "nodes" not in graph:
            errors.append(f"Slide {slide_number}: Graph missing 'nodes' key")
            return
            
        if "edges" not in graph:
            errors.append(f"Slide {slide_number}: Graph missing 'edges' key")
            return
            
        nodes = graph["nodes"]
        edges = graph["edges"]
        
        # Validate nodes
        if not isinstance(nodes, list):
            errors.append(f"Slide {slide_number}: 'nodes' must be a list")
            return
            
        if not nodes:
            errors.append(f"Slide {slide_number}: 'nodes' list is empty")
            return
            
        # Validate edges
        if not isinstance(edges, list):
            errors.append(f"Slide {slide_number}: 'edges' must be a list")
            return
        
        # Calculate required slide dimensions
        slide_width, slide_height = _calculate_slide_dimensions(nodes, errors, slide_number)
        
        # Resize the slide
        base_prs.slide_width = Inches(slide_width)
        base_prs.slide_height = Inches(slide_height)
        
        # Create node shapes and store them for edge connections
        node_shapes = {}
        for node in nodes:
            shape = _create_node_shape(
                slide, node, global_context, check_permissions, errors, slide_number
            )
            if shape:
                node_shapes[node["id"]] = shape
                
        # Create edge connectors
        for edge in edges:
            _create_edge_connector(
                slide, edge, node_shapes, global_context, check_permissions, errors, slide_number
            )
            
    except Exception as e:
        errors.append(f"Slide {slide_number}: Error processing graph: {e}")


def _calculate_slide_dimensions(nodes: list[dict], errors: list[str], slide_number: int) -> tuple[float, float]:
    """
    Calculate the required slide dimensions to fit all nodes.
    
    Returns:
        Tuple of (width, height) in inches
    """
    # Default minimum slide size (standard 16:9)
    min_width = 10
    min_height = 7.5
    
    # Calculate bounds from node positions
    max_x = min_width
    max_y = min_height
    
    # Default node size (will be auto-expanded)
    node_width = 2.5
    node_height = 1.5
    
    for node in nodes:
        if "position" not in node:
            errors.append(f"Slide {slide_number}: Node '{node.get('id', 'unknown')}' missing 'position'")
            continue
            
        position = node["position"]
        if "x" not in position or "y" not in position:
            errors.append(
                f"Slide {slide_number}: Node '{node.get('id', 'unknown')}' position missing 'x' or 'y'"
            )
            continue
            
        # Calculate right and bottom edges of this node
        node_right = position["x"] + node_width
        node_bottom = position["y"] + node_height
        
        max_x = max(max_x, node_right + 1)  # Add 1 inch margin
        max_y = max(max_y, node_bottom + 1)
        
    return max_x, max_y


def _create_node_shape(
    slide,
    node: dict,
    global_context: dict,
    check_permissions: Optional[Callable[[object], bool]],
    errors: list[str],
    slide_number: int,
):
    """
    Create a node shape on the slide.
    
    Returns:
        The created shape or None if creation failed
    """
    try:
        # Validate required fields
        if "id" not in node:
            errors.append(f"Slide {slide_number}: Node missing 'id' field")
            return None
            
        if "name" not in node:
            errors.append(f"Slide {slide_number}: Node '{node['id']}' missing 'name' field")
            return None
            
        if "position" not in node:
            errors.append(f"Slide {slide_number}: Node '{node['id']}' missing 'position' field")
            return None
            
        position = node["position"]
        if "x" not in position or "y" not in position:
            errors.append(f"Slide {slide_number}: Node '{node['id']}' position missing 'x' or 'y'")
            return None
            
        # Process template variables in node name and detail
        name = process_text_recursive(node["name"], global_context, check_permissions)
        detail = ""
        if "detail" in node:
            detail = process_text_recursive(node["detail"], global_context, check_permissions)
            
        # Create rectangle shape at specified position
        left = Inches(position["x"])
        top = Inches(position["y"])
        width = Inches(2.5)  # Default width
        height = Inches(1.5)  # Default height, will auto-expand
        
        shape = slide.shapes.add_shape(
            1,  # MSO_SHAPE.RECTANGLE
            left, top, width, height
        )
        
        # Configure shape appearance
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(173, 216, 230)  # Light blue
        shape.line.color.rgb = RGBColor(0, 0, 0)  # Black border
        shape.line.width = Pt(1)
        
        # Add text to shape
        text_frame = shape.text_frame
        text_frame.clear()  # Clear default paragraph
        text_frame.word_wrap = True
        
        # Add name (larger font)
        p = text_frame.paragraphs[0]
        p.text = name
        p.font.size = Pt(14)
        p.font.bold = True
        
        # Add detail if present (smaller font)
        if detail:
            p = text_frame.add_paragraph()
            p.text = detail
            p.font.size = Pt(10)
            
        # Enable auto-fit
        text_frame.auto_size = 1  # MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        
        # Note: Parent functionality is placeholder for now
        # Will be implemented later to resize parent nodes
        if "parent" in node:
            # TODO: Implement parent node resizing logic
            pass
            
        return shape
        
    except Exception as e:
        errors.append(f"Slide {slide_number}: Error creating node '{node.get('id', 'unknown')}': {e}")
        return None


def _create_edge_connector(
    slide,
    edge: dict,
    node_shapes: dict,
    global_context: dict,
    check_permissions: Optional[Callable[[object], bool]],
    errors: list[str],
    slide_number: int,
):
    """
    Create an edge connector between two nodes.
    
    Returns:
        The created connector or None if creation failed
    """
    try:
        # Validate required fields
        if "from" not in edge:
            errors.append(f"Slide {slide_number}: Edge missing 'from' field")
            return None
            
        if "to" not in edge:
            errors.append(f"Slide {slide_number}: Edge missing 'to' field")
            return None
            
        from_id = edge["from"]
        to_id = edge["to"]
        
        # Check if nodes exist
        if from_id not in node_shapes:
            errors.append(f"Slide {slide_number}: Edge references unknown source node '{from_id}'")
            return None
            
        if to_id not in node_shapes:
            errors.append(f"Slide {slide_number}: Edge references unknown target node '{to_id}'")
            return None
            
        from_shape = node_shapes[from_id]
        to_shape = node_shapes[to_id]
        
        # Create elbow connector (right angles)
        connector = slide.shapes.add_connector(
            MSO_CONNECTOR_TYPE.ELBOW,
            from_shape.left + from_shape.width,  # Right edge of source
            from_shape.top + from_shape.height // 2,  # Middle of source
            to_shape.left,  # Left edge of target
            to_shape.top + to_shape.height // 2,  # Middle of target
        )
        
        # Connect to shapes
        connector.begin_connect(from_shape, 3)  # Right connection point
        connector.end_connect(to_shape, 1)  # Left connection point
        
        # Style the connector
        connector.line.color.rgb = RGBColor(0, 0, 0)  # Black line
        connector.line.width = Pt(1.5)
        
        # Add label if present
        if "label" in edge and edge["label"]:
            label_text = process_text_recursive(edge["label"], global_context, check_permissions)
            
            # Add text box for label near the middle of the connector
            mid_x = (connector.begin_x + connector.end_x) // 2
            mid_y = (connector.begin_y + connector.end_y) // 2
            
            label_box = slide.shapes.add_textbox(
                mid_x - Inches(0.5),
                mid_y - Inches(0.25),
                Inches(1),
                Inches(0.5)
            )
            
            label_box.text_frame.text = label_text
            label_box.text_frame.paragraphs[0].font.size = Pt(9)
            label_box.fill.solid()
            label_box.fill.fore_color.rgb = RGBColor(255, 255, 255)  # White background
            
        return connector
        
    except Exception as e:
        errors.append(f"Slide {slide_number}: Error creating edge: {e}")
        return None
