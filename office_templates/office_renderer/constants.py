"""
Constants used in the template reports system.
"""

# Loop directive keywords
LOOP_KEYWORD = "loop"
IN_KEYWORD = "in"
ENDLOOP_KEYWORD = "endloop"

# Image directive keywords
IMAGE_KEYWORD = "image"
IMAGESQUEEZE_KEYWORD = "imagesqueeze"

# Directive markers
DIRECTIVE_START = "%"
DIRECTIVE_END = "%"

# Full directive patterns
LOOP_START_PATTERN_STR = f"{DIRECTIVE_START}\\s*{LOOP_KEYWORD}\\s+(\\w+)\\s+{IN_KEYWORD}\\s+(.+?)\\s*{DIRECTIVE_END}"
LOOP_END_PATTERN_STR = f"{DIRECTIVE_START}\\s*{ENDLOOP_KEYWORD}\\s*{DIRECTIVE_END}"

# Image directive patterns
IMAGE_DIRECTIVES = {
    f"{DIRECTIVE_START}{IMAGE_KEYWORD}{DIRECTIVE_END}": "fit",
    f"{DIRECTIVE_START}{IMAGESQUEEZE_KEYWORD}{DIRECTIVE_END}": "squeeze",
}