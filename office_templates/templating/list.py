from .core import get_matching_tags, process_text
from .exceptions import BadFloatDataResultError


def process_text_list(
    items: list,
    context: dict,
    perm_user,
    as_float: bool,
    fail_if_not_float: bool = False,
):
    """
    Process a list of items, each of which may be a string with placeholders
    or a list of strings with placeholders. Return a list of processed items.
    """

    def _process_text(t, m):
        r = process_text(
            text=str(t),
            mode=m,
            context=context,
            perm_user=perm_user,
        )

        if as_float:
            if not isinstance(r, list):
                return make_float(r, fail_if_not_float)
            return [make_float(ri, fail_if_not_float) for ri in r]
        return r

    items = list(items)
    results = None

    # If there is only 1 item, use "table" mode, and if the return value
    # is a LIST, then use that list as the results.
    if len(items) == 1:
        only_item = items[0]
        if isinstance(only_item, str):
            placeholder_matches = get_matching_tags(only_item)

            # Table mode only supports exactly one placeholder, obviously,
            # otherwise we would not know how to expand the table.
            if len(placeholder_matches) == 1:
                result = _process_text(only_item, "table")
                if isinstance(result, list):
                    results = result
                else:
                    results = [result]

    # Otherwise, process each category individually.
    if results is None:
        results = [
            (_process_text(item, "normal") if isinstance(item, str) else item)
            for item in items
        ]

    return results


def make_float(value: str | float, throw_if_fail: bool):
    try:
        return float(value)
    except ValueError:
        if not throw_if_fail:
            return value
        raise BadFloatDataResultError(f"Could not convert {value} to float.")
