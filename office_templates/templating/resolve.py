import re
import datetime
from typing import Callable, Optional

from .exceptions import BadTagException, MissingDataException, TagCallableException
from .formatting import format_value
from .parse import get_nested_attr, evaluate_condition, parse_callable_args
from .permissions import enforce_permissions, is_django_object, has_view_permission

BAD_SEGMENT_PATTERN = re.compile(r"^[#%]*$")


def resolve_formatted_tag(expr: str, context, check_permissions: Optional[Callable[[object], bool]] = None):
    """
    Resolve a template tag expression and return its final value.

    This function supports several features:

      1. Simple replacements of tag expressions with their corresponding values.

      2. Nested attributes and dictionary values, following "." or "__" paths.

      3. Handling of lists, where a tag expression may return a list of values, each
        of which is processed separately.
        For example:
            {{ users.name }}

      4. Callable methods with arguments, eg "user.get_name()" or "team.get_role(mem)".

      5. Filtering expressions for list or queryset-like (eg Django) objects.

      6. Certain keywords, such as "now" to return the current datetime.

      7. Use of mathematical operators (+, -, *, /) to perform arithmetic operations on the resolved value.
         For example:
             {{ user.age + 5 }}          will return the user's age plus 5.

      8. Use of a pipe operator (|) to specify a format string eg for date or datetime or numerical values.
         For example:
             {{ now | %Y-%m-%d }}         will return the current date formatted as specified.
             {{ now | MMMM, dd, YYYY }}   will return the current date formatted as specified.
             {{ value | .2f }}            will return the value formatted to two decimal places.
             {{ value | upper }}          will return the value in upper case.
             {{ value | lower }}          will return the value in lower case.
             {{ value | length }}          will return the length of the value.

      9. [CURRENTLY DISABLED] Use of a pipe operator to retrieve more than one attribute from an object/dictionary
         and return a tuple of values. For example:
             {{ user | email, name }}
             {{ team.users | email, phone }}

      10. "Nested tags" or "tag within a tag" where a portion of the tag expression is enclosed
          within dollar signs ($). These inner sub-tags are resolved first and their result replaces the sub-tag.
          For example:
              {{ user.custom_function($value$) }}
          If value resolves to 45, the expression will first convert to:
              {{ user.custom_function(45) }}

    Parameters:
      expr (str): The complete tag expression (without the double curly braces) to be resolved.
      context (dict): The context dictionary containing variables used during tag resolution.
      check_permissions: The permission checking function that takes an object and returns bool.

    Returns:
      The final resolved value of the tag, which may be a string, numeric value, datetime, or list.

    Raises:
      BadTagException: When the tag contains unexpected curly braces or formatting issues.
    """
    # First, replace sub-tags enclosed in $ with their corresponding resolved values.
    expr = substitute_inner_tags(expr, context, check_permissions)

    if "{" in expr or "}" in expr:
        raise BadTagException(
            f"Bad format in tag '{expr}': unexpected curly brace detected."
        )

    # Split by the pipe operator to separate the tag expression from an optional format string.
    format_parts = expr.split("|")
    if len(format_parts) > 2:
        raise BadTagException(f"Bad format in tag '{expr}': too many pipe operators.")
    value_expr = format_parts[0].strip()

    format_expr = None
    if len(format_parts) == 2:
        format_expr = format_parts[1].strip()
        if (format_expr.startswith('"') and format_expr.endswith('"')) or (
            format_expr.startswith("'") and format_expr.endswith("'")
        ):
            format_expr = format_expr[1:-1]

    # Preparing for mathematical operators:
    # Split at the last closing parenthesis or bracket if present, keeping both parts
    # Determine the last occurrence of ')' or ']' and split accordingly
    last_paren = value_expr.rfind(")")
    last_bracket = value_expr.rfind("]")
    if last_paren != -1 or last_bracket != -1:
        # Choose the splitter that occurs later in the string
        splitter = ")" if last_paren > last_bracket else "]"
        pre_part, _, value_expr_post_brackets = value_expr.rpartition(splitter)
        pre_part += splitter
        value_expr_post_brackets = value_expr_post_brackets.strip()
    else:
        pre_part = ""
        value_expr_post_brackets = value_expr

    # Split by mathematical operators for (add, subtract, multiply, divide)
    math_operator = None
    math_operand = None
    for operator in ["+", "-", "*", "/"]:
        if operator in value_expr_post_brackets:
            math_parts = value_expr_post_brackets.split(operator)
            if len(math_parts) > 2:
                raise BadTagException(
                    f"Bad format in tag '{value_expr}': too many `{operator}` operators."
                )
            value_expr = pre_part + math_parts[0].strip()
            math_operator = operator
            try:
                math_operand = float(math_parts[1].strip())
            except ValueError:
                raise BadTagException(
                    f"Invalid operand for operator '{math_operator}': {math_parts[1].strip()}"
                )
            if operator == "/" and math_operand == 0:
                raise BadTagException("Division by zero error.")
            break

    # Resolve the tag expression (without the formatting part).
    value = resolve_tag(value_expr, context, check_permissions=check_permissions)

    # Perform mathematical operations if applicable.
    if math_operator and math_operand is not None:
        try:
            value = apply_math_operator(value, math_operator, math_operand)
        except ValueError:
            raise BadTagException(
                f"Invalid value for mathematical operation '{value_expr}': '{value}'"
            )

    # If a format string is provided...
    if format_expr:
        value = format_value(value, format_expr)

    return value


def apply_math_operator(value, math_operator, operand):
    # If the value is a list, apply the operation to each element.
    if isinstance(value, list):
        return [apply_math_operator(v, math_operator, operand) for v in value]

    value = float(value if value else 0)

    if math_operator == "+":
        value += operand
    elif math_operator == "-":
        value -= operand
    elif math_operator == "*":
        value *= operand
    elif math_operator == "/":
        value /= operand

    return value


def substitute_inner_tags(expr: str, context, check_permissions: Optional[Callable[[object], bool]] = None) -> str:
    """
    Replace any sub-tags embedded within a tag expression. A sub-tag is any substring
    within a tag that is enclosed between dollar signs ($). For example, in a tag like:

        {{ user.custom_function($value$) }}

    this function will locate "$value$" and replace it with the resolved value (as computed
    by the main tag resolution process), so that the final expression becomes something like:

        {{ user.custom_function(45) }}

    Parameters:
      expr (str): The original tag expression possibly containing inner sub-tags.
      context (dict): A dictionary holding variable names and their values used while resolving tags.
      check_permissions: The permission checking function for enforcement during tag resolution.

    Returns:
      A new string where all inner sub-tags have been replaced with their corresponding values.
    """
    pattern = re.compile(r"\$(.*?)\$")

    def replace_func(match):
        inner_expr = match.group(1).strip()
        # Resolve the inner expression using the same tag parser.
        resolved = resolve_formatted_tag(inner_expr, context, check_permissions)
        return str(resolved)

    return pattern.sub(replace_func, expr)


def resolve_tag(expr, context, check_permissions: Optional[Callable[[object], bool]] = None):
    """
    Resolve a dotted tag expression using the provided context. The expression can consist
    of multiple segments separated by periods. Each segment may represent:

      - A standard attribute lookup (e.g., "user.name").
      - A nested attribute using either dots or double underscores (e.g., "user.profile__email" or "user.profile.email").
      - A callable method, optionally with arguments, where the arguments must be convertible to int, float, or str.
        For example: "user.get_greeting('Hello')" or "user.compute_total(10, 20)".
      - A filtered lookup using square brackets to filter list or queryset results (e.g., "users[is_active=True]").

    Special case:
      - If the first segment is "now", the current datetime is returned.

    Parameters:
      expr (str): The dotted expression to be resolved.
      context (dict): The dictionary with variables available for resolution.
      check_permissions: The permission checking function for enforcing permissions.

    Returns:
      The resolved value after processing all segments. If any segment returns None, an empty string is returned.

    Raises:
      BadTagException: For malformed expressions or invalid characters.
    """
    segments = split_expression(expr)
    if not segments:
        return ""
    first_segment = segments[0]
    if not first_segment:
        return ""

    if any(bool(BAD_SEGMENT_PATTERN.fullmatch(s)) for s in segments):
        raise BadTagException(f"Bad characters in tag segments: {segments}")

    if first_segment.strip() == "now":
        return datetime.datetime.now()

    current = context
    for seg in segments:
        current = resolve_segment(current, seg, check_permissions=check_permissions)
        if current is None:
            return ""
    return current


def split_expression(expr):
    """
    Split a dotted expression into its individual segments.

    This function splits the expression by periods, except when the period is within
    square brackets. This is important because filtering expressions inside square brackets
    (e.g., "users[is_active=True].email") should not be split on the period inside the brackets.

    Parameters:
      expr (str): The dotted expression string.

    Returns:
      A list of segments (strings).
    """
    return re.split(r"\.(?![^\[]*\])", expr)


def resolve_segment(current, segment, check_permissions: Optional[Callable[[object], bool]] = None):
    """
    Resolve a single segment of a dotted tag expression.

    A segment may comprise various elements:

      - A simple attribute name, e.g., "name".
      - A callable function, indicated by the presence of parentheses "()", which may optionally include arguments.
        For example, "custom_function()" or "compute_sum(3,4)".
      - A filter expression indicated by square brackets, e.g., "users[is_active=True]" to filter a list or queryset.

    The function supports callable resolution; if a segment contains parentheses with arguments,
    those arguments are parsed (only int, float, and str values are allowed) and the attribute is called.

    Additionally, before parsing the segment with regular expressions, it checks for unmatched round or square brackets.

    Parameters:
      current: The current object (or list of objects) being resolved.
      segment (str): The individual segment to resolve.
      check_permissions: The permission checking function for enforcement.

    Returns:
      The value obtained after resolving the segment. If the segment leads to a list and further resolution is required,
      the function flattens the list.

    Raises:
      BadTagException: If the segment is malformed or has unmatched brackets.
      TagCallableException: If an attribute is expected to be callable but is not.
      MissingDataException: If an attribute is not found in the current context.
    """
    # Check for unmatched round or square brackets.
    if segment.count("(") != segment.count(")"):
        raise BadTagException(f"Unmatched round brackets in segment: '{segment}'")
    if segment.count("[") != segment.count("]"):
        raise BadTagException(f"Unmatched square brackets in segment: '{segment}'")

    # Regular expression that captures:
    #  - The attribute name (with possible double-underscores).
    #  - Optional callable arguments inside parentheses.
    #  - Optional filtering expression inside square brackets.
    m = re.match(r"^(\w+(?:__\w+)*)(?:\((.*?)\))?(?:\[(.*?)\])?$", segment)
    if not m:
        raise BadTagException(f"Segment '{segment}' is malformed")
    attr_name = m.group(1)
    call_args_str = m.group(2)  # String of comma-separated arguments (may be None)
    filter_expr = m.group(3)  # Filtering expression (may be None)

    # If the current object is a list, apply the segment resolution to each element.
    if isinstance(current, list):
        results = []
        for item in current:
            res = resolve_segment(item, segment, check_permissions=check_permissions)
            if isinstance(res, list):
                results.extend(res)
            else:
                results.append(res)
        return results

    # Retrieve the attribute using a helper function that supports nested lookups.
    try:
        value = get_nested_attr(current, attr_name)
    except (AttributeError, KeyError) as e:
        raise MissingDataException(f"{segment} not found in {current}")

    # If the segment indicates that this attribute is callable (with optional arguments), call it.
    if call_args_str is not None:
        if not callable(value):
            raise TagCallableException(f"Attribute '{attr_name}' is not callable.")
        args = parse_callable_args(call_args_str)
        try:
            value = value(*args)
        except Exception as e:
            raise TagCallableException(
                f"Error calling '{attr_name}' with arguments {args}: {e}"
            )

    # If the value supports filtering (e.g. a queryset-like object), apply any filter expression.
    if value is not None and hasattr(value, "filter") and callable(value.filter):
        if filter_expr:
            conditions = [c.strip() for c in filter_expr.split(",")]
            filter_dict = {}
            for cond in conditions:
                m2 = re.match(r"([\w__]+)\s*=\s*(.+)", cond)
                if m2:
                    key, val = m2.groups()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    filter_dict[key] = val
            value = value.filter(**filter_dict)
        else:
            if hasattr(value, "all") and callable(value.all):
                value = value.all()
        value = list(value)
    else:
        # For non-queryset values that are lists or single objects, apply filtering if provided.
        value_list = value if isinstance(value, list) else [value]
        if filter_expr:
            conditions = [cond.strip() for cond in filter_expr.split(",")]
            value = [
                item
                for item in value_list
                if all(evaluate_condition(item, cond) for cond in conditions)
            ]
    # Enforce permissions on the filtered result.
    value = enforce_permissions(value, check_permissions)
    return value
