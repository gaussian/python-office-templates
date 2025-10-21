"""
Functions for processing graph slides with nodes and edges.

This module provides functionality to create node/edge graph visualizations
on PowerPoint slides, including validation, positioning, and rendering.
"""

from typing import Callable, Optional

from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_CONNECTOR_TYPE
from pptx.dml.color import RGBColor

from office_templates.templating.core import process_text_recursive


def process_graph_slide(
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
