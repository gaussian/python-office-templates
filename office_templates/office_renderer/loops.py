"""
Functions to handle loop functionality in PPTX templates.
"""

import re

from ..templating import process_text

# Patterns for loop directives
LOOP_START_PATTERN = re.compile(r"%loop\s+(\w+)\s+in\s+(\w+)%")
LOOP_END_PATTERN = re.compile(r"%endloop%")


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
    if not hasattr(shape, "text_frame"):
        return False
    
    variable, collection = extract_loop_directive(shape.text_frame.text)
    return variable is not None and collection is not None


def is_loop_end(shape) -> bool:
    """Return True if the shape text indicates a loop end."""
    if not hasattr(shape, "text_frame"):
        return False
    
    text = shape.text_frame.text
    if not text:
        return False
    
    return LOOP_END_PATTERN.search(text.strip()) is not None