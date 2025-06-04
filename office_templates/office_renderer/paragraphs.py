from typing import Callable, Optional
from template_reports.templating import process_text
from .exceptions import UnterminatedTagException


def merge_split_placeholders(paragraph):
    """
    Collapse {{ … }} placeholders that have been split across several runs
    into a single run, preserving all other runs and formatting.
    """
    runs = list(paragraph.runs)  # make a concrete snapshot
    i = 0
    while i < len(runs):
        run = runs[i]
        # running balance: +1 for each '{{', −1 for each '}}'
        balance = run.text.count("{{") - run.text.count("}}")

        if balance > 0:  # we have an unmatched opening
            merged_chunks = [run.text]
            j = i + 1

            while j < len(runs) and balance > 0:
                merged_chunks.append(runs[j].text)
                balance += runs[j].text.count("{{") - runs[j].text.count("}}")
                j += 1

            if balance:  # never saw a matching close
                raise UnterminatedTagException(
                    f"Unterminated tag starting in run {i}: {run.text!r}"
                )

            # update the first run's text
            runs[i].text = "".join(merged_chunks)

            # delete the now-redundant runs *by object reference*
            for doomed in runs[i + 1 : j]:
                paragraph._p.remove(doomed._r)

            # refresh our snapshot because the XML tree changed
            runs = list(paragraph.runs)

        i += 1

    return paragraph


def process_paragraph(paragraph, context, perm_user, mode="normal"):
    """
    Merge placeholders in a paragraph if a single placeholder ({{ ... }}) is split across multiple runs.
    Then process each run's text with process_text.
    """
    # Convert perm_user to check_permissions lambda
    from template_reports.templating.permissions import has_view_permission
    if perm_user is not None:
        check_permissions = lambda obj: has_view_permission(obj, perm_user)
    else:
        check_permissions = None
    
    # Use the helper to merge runs containing split placeholders.
    paragraph = merge_split_placeholders(paragraph)

    for run in paragraph.runs:
        current_text = run.text
        result = process_text(
            text=current_text,
            context=context,
            check_permissions=check_permissions,
            mode=mode,
            fail_if_empty=True,
        )
        if isinstance(result, str):
            run.text = result
        else:
            run.text = ", ".join(str(item) for item in result)
