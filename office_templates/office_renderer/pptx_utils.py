"""
Utility functions for PPTX manipulation.
"""

from copy import deepcopy


def duplicate_slide(pres, index):
    """
    Create a duplicate of the slide at the given index and return the new slide.
    
    This function duplicates a slide by:
    1. Getting the source slide
    2. Creating a new blank slide
    3. Copying all shapes from source to destination
    
    Args:
        pres: The Presentation object
        index: Index of the slide to duplicate
        
    Returns:
        The newly created slide object
    """
    source = pres.slides[index]
    blank_slide_layout = pres.slide_layouts[6]  # typically a blank layout
    new_slide = pres.slides.add_slide(blank_slide_layout)

    for shape in source.shapes:
        el = shape.element
        new_el = deepcopy(el)
        new_slide.shapes._spTree.insert_element_before(new_el, 'p:extLst')

    return new_slide