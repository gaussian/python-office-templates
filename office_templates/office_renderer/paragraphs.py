from ..templating import process_text
from .exceptions import UnterminatedTagException


def merge_split_placeholders(paragraph):
    runs = paragraph.runs
    i = 0
    while i < len(runs):
        current_text = runs[i].text
        if "{{" in current_text and "}}" not in current_text:
            merged_text = current_text
            j = i + 1
            while j < len(runs):
                merged_text += runs[j].text
                if "}}" in runs[j].text:
                    for k in range(i + 1, j + 1):
                        paragraph._p.remove(runs[k]._r)
                    runs[i].text = merged_text
                    break
                j += 1
            else:
                raise UnterminatedTagException(
                    f"Unterminated tag starting in run {i}: {current_text}"
                )
            runs = paragraph.runs  # refresh runs list
        i += 1
    return paragraph


def process_paragraph(paragraph, context, perm_user, mode="normal"):
    """
    Merge placeholders in a paragraph if a single placeholder ({{ ... }}) is split across multiple runs.
    Then process each run's text with process_text.
    """
    # Use the helper to merge runs containing split placeholders.
    paragraph = merge_split_placeholders(paragraph)

    for run in paragraph.runs:
        current_text = run.text
        processed = process_text(
            current_text,
            context,
            perm_user=perm_user,
            mode=mode,
        )
        if isinstance(processed, str):
            run.text = processed
        else:
            run.text = ", ".join(str(item) for item in processed)
