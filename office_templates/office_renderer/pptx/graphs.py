"""
Module for creating node/edge graph visualizations in PowerPoint presentations.

This module provides functionality to generate graph visualizations where:
- Each graph is rendered on a single slide
- Nodes are positioned using x/y coordinates
- Edges connect nodes using elbow connectors
- Nodes can be nested within parent nodes
"""

from typing import Callable, Optional
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_CONNECTOR_TYPE
from pptx.dml.color import RGBColor

from office_templates.templating.core import process_text_recursive
from .render import process_single_slide
from .layouts import build_layout_mapping
from .utils import copy_slide_across_presentations


def compose_graphs_pptx(
    template_files: list,
    graphs: list[dict],
    global_context: dict,
    output,
    check_permissions: Optional[Callable[[object], bool]] = None,
    use_tagged_layouts=False,
    use_all_slides_as_layouts_by_title=False,
    layout_name: str = "graph",
):
    """
    Compose a PPTX with node/edge graphs, each graph on a single slide.
    
    This function creates professional-looking node/edge graph visualizations suitable for
    architecture diagrams, flowcharts, network topologies, and organizational charts.
    
    Args:
        template_files: List of template file paths or file-like objects
        graphs: List of graph dictionaries, each containing 'nodes' and 'edges'
        global_context: Global context dictionary for template variable processing
        output: Output file path or file-like object
        check_permissions: Optional permission checking function
        use_tagged_layouts: If True, include slides with % layout XXX % tags
        use_all_slides_as_layouts_by_title: If True, use all slides as layouts by title
        layout_name: Name of the layout to use for graph slides (default: "graph")
        
    Graph Structure:
        Each graph dictionary should have:
        
        nodes: List of node dicts with:
            - id (str, required): Unique identifier
            - name (str, required): Display name
            - detail (str, optional): Additional detail text shown in smaller font
            - position (dict, required): Dict with 'x' and 'y' keys in inches
            - parent (str, optional): ID of parent node for nesting (placeholder)
            
        edges: List of edge dicts with:
            - from (str, required): Source node ID
            - to (str, required): Target node ID
            - label (str, optional): Edge label text
    
    Example:
        >>> graphs = [
        ...     {
        ...         "nodes": [
        ...             {
        ...                 "id": "frontend",
        ...                 "name": "Frontend",
        ...                 "detail": "React Application",
        ...                 "position": {"x": 1, "y": 2},
        ...             },
        ...             {
        ...                 "id": "backend",
        ...                 "name": "Backend",
        ...                 "detail": "Node.js API",
        ...                 "position": {"x": 4, "y": 2},
        ...             },
        ...         ],
        ...         "edges": [
        ...             {"from": "frontend", "to": "backend", "label": "HTTPS"},
        ...         ],
        ...     }
        ... ]
        >>> result, errors = compose_graphs_pptx(
        ...     template_files=["template.pptx"],
        ...     graphs=graphs,
        ...     global_context={"project": "My Project"},
        ...     output="output.pptx",
        ...     use_tagged_layouts=True,
        ... )
        
    Features:
        - Nodes are rectangular shapes with auto-expanding text
        - Edges use elbow connectors (right angles) for professional appearance
        - Slides automatically expand to fit all nodes
        - Node names and details support template variables like {{ variable }}
        - Edge labels also support template variables
        - Parent nodes are accepted but not yet fully implemented (placeholder)
            
    Returns:
        Tuple of (output, errors):
            - output: The output file object if successful, None otherwise
            - errors: None if successful, list of error strings otherwise
    """
    errors: list[str] = []
    
    try:
        # Validate inputs
        if not template_files:
            errors.append("No template files provided")
            return None, errors
            
        if not graphs:
            errors.append("No graphs specified")
            return None, errors
            
        # Build layout mapping from all template files
        layout_mapping = build_layout_mapping(
            template_files,
            use_tagged_layouts=use_tagged_layouts,
            use_all_slides_as_layouts_by_title=use_all_slides_as_layouts_by_title,
        )
        
        # Use the first template as the base presentation
        if isinstance(template_files[0], str):
            base_prs = Presentation(template_files[0])
        else:
            template_files[0].seek(0)
            base_prs = Presentation(template_files[0])
            
        # Remove all slides from the base presentation
        sld_ids = base_prs.slides._sldIdLst
        while len(sld_ids) > 0:
            slide_id = sld_ids[0]
            sld_ids.remove(slide_id)
            
        # Create a slide for each graph
        for graph_index, graph in enumerate(graphs):
            try:
                # Validate graph structure
                if "nodes" not in graph:
                    errors.append(f"Graph {graph_index + 1}: Missing 'nodes' key")
                    continue
                    
                if "edges" not in graph:
                    errors.append(f"Graph {graph_index + 1}: Missing 'edges' key")
                    continue
                    
                nodes = graph["nodes"]
                edges = graph["edges"]
                
                # Validate nodes
                if not isinstance(nodes, list):
                    errors.append(f"Graph {graph_index + 1}: 'nodes' must be a list")
                    continue
                    
                if not nodes:
                    errors.append(f"Graph {graph_index + 1}: 'nodes' list is empty")
                    continue
                    
                # Validate edges
                if not isinstance(edges, list):
                    errors.append(f"Graph {graph_index + 1}: 'edges' must be a list")
                    continue
                    
                # Get or create the slide
                if layout_name in layout_mapping:
                    # Use the specified layout
                    source_prs, layout_item = layout_mapping[layout_name]
                    if hasattr(layout_item, "slide_layout"):
                        # It's a slide - copy it directly
                        new_slide = copy_slide_across_presentations(base_prs, layout_item)
                    else:
                        # It's a slide layout - use it
                        if len(base_prs.slide_layouts) > 6:
                            layout = base_prs.slide_layouts[6]  # Use blank layout
                        elif len(base_prs.slide_layouts) > 0:
                            layout = base_prs.slide_layouts[0]
                        else:
                            errors.append(f"Graph {graph_index + 1}: No slide layouts available")
                            continue
                        new_slide = base_prs.slides.add_slide(layout)
                else:
                    # Use blank layout
                    if len(base_prs.slide_layouts) > 6:
                        layout = base_prs.slide_layouts[6]
                    elif len(base_prs.slide_layouts) > 0:
                        layout = base_prs.slide_layouts[0]
                    else:
                        errors.append(f"Graph {graph_index + 1}: No slide layouts available")
                        continue
                    new_slide = base_prs.slides.add_slide(layout)
                    
                # Calculate required slide dimensions
                slide_width, slide_height = _calculate_slide_dimensions(nodes, errors, graph_index)
                
                # Resize the slide
                base_prs.slide_width = Inches(slide_width)
                base_prs.slide_height = Inches(slide_height)
                
                # Create node shapes and store them for edge connections
                node_shapes = {}
                for node in nodes:
                    shape = _create_node_shape(
                        new_slide, node, global_context, check_permissions, errors, graph_index
                    )
                    if shape:
                        node_shapes[node["id"]] = shape
                        
                # Create edge connectors
                for edge in edges:
                    _create_edge_connector(
                        new_slide, edge, node_shapes, global_context, check_permissions, errors, graph_index
                    )
                    
                # Process the slide to handle any template variables
                slide_context = {**global_context}
                process_single_slide(
                    slide=new_slide,
                    context=slide_context,
                    slide_number=graph_index + 1,
                    check_permissions=check_permissions,
                    errors=errors,
                )
                
            except Exception as e:
                errors.append(f"Error processing graph {graph_index + 1}: {e}")
                
        # If we have errors, don't save
        if errors:
            print("Composition aborted due to the following errors:")
            for err in set(errors):
                print(f" - {err}")
            print("Output file not saved.")
            return None, errors
            
        # Save to output
        if isinstance(output, str):
            base_prs.save(output)
        else:
            base_prs.save(output)
            output.seek(0)
            
        return output, None
        
    except Exception as e:
        errors.append(f"Unexpected error during graph composition: {e}")
        return None, errors


def _calculate_slide_dimensions(nodes: list[dict], errors: list[str], graph_index: int) -> tuple[float, float]:
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
            errors.append(f"Graph {graph_index + 1}: Node '{node.get('id', 'unknown')}' missing 'position'")
            continue
            
        position = node["position"]
        if "x" not in position or "y" not in position:
            errors.append(
                f"Graph {graph_index + 1}: Node '{node.get('id', 'unknown')}' position missing 'x' or 'y'"
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
    graph_index: int,
):
    """
    Create a node shape on the slide.
    
    Returns:
        The created shape or None if creation failed
    """
    try:
        # Validate required fields
        if "id" not in node:
            errors.append(f"Graph {graph_index + 1}: Node missing 'id' field")
            return None
            
        if "name" not in node:
            errors.append(f"Graph {graph_index + 1}: Node '{node['id']}' missing 'name' field")
            return None
            
        if "position" not in node:
            errors.append(f"Graph {graph_index + 1}: Node '{node['id']}' missing 'position' field")
            return None
            
        position = node["position"]
        if "x" not in position or "y" not in position:
            errors.append(f"Graph {graph_index + 1}: Node '{node['id']}' position missing 'x' or 'y'")
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
        errors.append(f"Graph {graph_index + 1}: Error creating node '{node.get('id', 'unknown')}': {e}")
        return None


def _create_edge_connector(
    slide,
    edge: dict,
    node_shapes: dict,
    global_context: dict,
    check_permissions: Optional[Callable[[object], bool]],
    errors: list[str],
    graph_index: int,
):
    """
    Create an edge connector between two nodes.
    
    Returns:
        The created connector or None if creation failed
    """
    try:
        # Validate required fields
        if "from" not in edge:
            errors.append(f"Graph {graph_index + 1}: Edge missing 'from' field")
            return None
            
        if "to" not in edge:
            errors.append(f"Graph {graph_index + 1}: Edge missing 'to' field")
            return None
            
        from_id = edge["from"]
        to_id = edge["to"]
        
        # Check if nodes exist
        if from_id not in node_shapes:
            errors.append(f"Graph {graph_index + 1}: Edge references unknown source node '{from_id}'")
            return None
            
        if to_id not in node_shapes:
            errors.append(f"Graph {graph_index + 1}: Edge references unknown target node '{to_id}'")
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
        errors.append(f"Graph {graph_index + 1}: Error creating edge: {e}")
        return None
