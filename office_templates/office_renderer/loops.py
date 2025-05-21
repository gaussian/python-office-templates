"""
Functions to handle loop functionality in PPTX templates.
"""

import re
from typing import Dict, List, Optional, Tuple, Any

from ..templating import resolve_tag
from .constants import (
    LOOP_START_PATTERN_STR,
    LOOP_END_PATTERN_STR,
)
from .pptx_utils import duplicate_slide

# Patterns for loop directives
LOOP_START_PATTERN = re.compile(LOOP_START_PATTERN_STR)
LOOP_END_PATTERN = re.compile(LOOP_END_PATTERN_STR)


def extract_loop_directive(text: str | None) -> tuple[str | None, str | None]:
    """Return (variable, collection) if *text* contains a loop directive."""
    if not text:
        return None, None
    
    match = LOOP_START_PATTERN.search(text.strip())
    if match:
        variable = match.group(1)
        collection = match.group(2)
        return variable, collection
    
    return None, None


def is_loop_start(shape) -> bool:
    """Return True if the shape text indicates a loop start."""
    if not hasattr(shape, "text_frame") or not hasattr(shape.text_frame, "text"):
        return False
    
    variable, collection = extract_loop_directive(shape.text_frame.text)
    return variable is not None and collection is not None


def is_loop_end(shape) -> bool:
    """Return True if the shape text indicates a loop end."""
    if not hasattr(shape, "text_frame") or not hasattr(shape.text_frame, "text"):
        return False
    
    text = shape.text_frame.text
    if not text:
        return False
    
    return LOOP_END_PATTERN.search(text.strip()) is not None





def process_loops(prs, context, perm_user, errors):
    """
    Process loops in the presentation:
    - Identify loop sections (slides between %loop var in collection% and %endloop%)
    - For each item in the collection, create a mapping between loop slides and variables
    - Return a list of slides to process with their context info
    """
    # We'll use this to track which original slides each output slide corresponds to
    slide_mapping = {}
    
    # First pass: identify loop sections and collect info about them
    loop_sections = []
    in_loop = False
    loop_start_index = -1
    loop_variable = None
    loop_collection = None
    
    for i, slide in enumerate(prs.slides):
        # Track whether this slide has loop directives
        has_loop_start = False
        has_loop_end = False
        loop_start_var = None
        loop_start_collection = None
        loop_start_shapes = []
        loop_end_shapes = []
        
        for shape in slide.shapes:
            # Check for loop start
            if is_loop_start(shape):
                loop_start_shapes.append(shape)
                variable, collection = extract_loop_directive(shape.text_frame.text)
                if variable and collection:
                    has_loop_start = True
                    loop_start_var = variable
                    loop_start_collection = collection
            
            # Check for loop end
            if is_loop_end(shape):
                loop_end_shapes.append(shape)
                if not in_loop and not has_loop_start:
                    errors.append(f"Error on slide {i + 1}: %endloop% without a matching loop start")
                has_loop_end = True
        
        # Detect multiple loop start directives on the same slide
        if len(loop_start_shapes) > 1:
            errors.append(f"Error on slide {i + 1}: Multiple loop start directives on same slide")
            return []  # Short-circuit when multiple loop starts found

        # Detect multiple loop end directives on the same slide
        if len(loop_end_shapes) > 1:
            errors.append(f"Error on slide {i + 1}: Multiple loop end directives on same slide")
            return []  # Short-circuit when multiple loop ends found
        
        # Check for both start and end on same slide (allowed but warn)
        if has_loop_start and has_loop_end:
            errors.append(f"Note on slide {i + 1}: Both loop start and end on the same slide")
        
        # Handle loop start
        if has_loop_start:
            if in_loop:
                errors.append(f"Error on slide {i + 1}: Nested loops are not supported")
                continue
            
            in_loop = True
            loop_start_index = i
            loop_variable = loop_start_var
            loop_collection = loop_start_collection
        
        # Handle loop end
        if has_loop_end and in_loop:
            # Count how many loop end directives there are on the slide
            loop_end_count = sum(1 for shape in slide.shapes if is_loop_end(shape))
            if loop_end_count > 1:
                errors.append(f"Error on slide {i + 1}: Multiple loop end directives on same slide")
                return []  # Short-circuit when multiple loop ends found
                
            loop_sections.append({
                "start_index": loop_start_index,
                "end_index": i,
                "variable": loop_variable,
                "collection": loop_collection
            })
            
            # Reset loop state
            in_loop = False
            loop_start_index = -1
            loop_variable = None
            loop_collection = None
    
    # Check for unclosed loops
    if in_loop:
        errors.append(f"Error: Loop started but never closed with %endloop%")
        # Don't short circuit, still process non-loop slides
    
    # Prepare slides to process
    slides_to_process = []
    current_slide_number = 1
    
    # Keep track of which slides are part of loops to avoid duplicating them
    loop_slide_indices = set()
    for section in loop_sections:
        for i in range(section["start_index"], section["end_index"] + 1):
            loop_slide_indices.add(i)
    
    # Create the slide structure with correct context
    for i, slide in enumerate(prs.slides):
        # If this slide is part of a loop section
        is_loop_slide = False
        for section in loop_sections:
            if section["start_index"] <= i <= section["end_index"]:
                is_loop_slide = True
                
                # If this is the start of a loop section, process the entire section
                if i == section["start_index"]:
                    # Get the collection from the context using resolve_tag
                    try:
                        collection_value = resolve_tag(section["collection"], context, perm_user)
                    except Exception as e:
                        errors.append(f"Error on slide {i + 1}: Failed to resolve collection '{section['collection']}': {str(e)}")
                        collection_value = None  # Set to None so it will be skipped but non-loop slides still processed
                        
                    if collection_value is None:
                        errors.append(f"Error on slide {i + 1}: Collection '{section['collection']}' not found in context")
                        # Proceed with non-loop slides but skip this loop section
                        continue
                        
                    # Ensure the collection is iterable
                    try:
                        collection_value = list(collection_value)  # Force evaluation of any lazy iterables
                    except TypeError:
                        errors.append(f"Error on slide {i + 1}: '{section['collection']}' is not iterable")
                    
                    # For empty or nonexistent collections, return all non-loop slides
                    if not collection_value:
                        # Proceed with non-loop slides but skip this loop section
                        continue
                    
                    # For each item in the collection, process each slide
                    for loop_item in collection_value:
                        for j in range(section["start_index"], section["end_index"] + 1):
                            # Duplicate the slide for real-world scenarios
                            new_slide = duplicate_slide(prs, j)
                            slides_to_process.append({
                                "slide": new_slide,
                                "slide_number": current_slide_number,
                                "loop_var": section["variable"],
                                "loop_item": loop_item
                            })
                            current_slide_number += 1
                    
                break
        
        # If this slide is not part of a loop, add it for regular processing
        if not is_loop_slide:
            slides_to_process.append({
                "slide": slide,
                "slide_number": current_slide_number
            })
            current_slide_number += 1
    
    return slides_to_process