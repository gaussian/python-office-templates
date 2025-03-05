from __future__ import annotations

from io import BytesIO
from itertools import zip_longest
from typing import TYPE_CHECKING

from pptx.chart.data import ChartData

from template_reports.templating.core import get_matching_tags, process_text

from .exceptions import BadChartDataResultError, ChartError, TableError

if TYPE_CHECKING:
    from pptx.chart.chart import Chart


def process_chart(chart: Chart, context: dict, perm_user):
    """
    Read the current chart data, format text fields using the provided context,
    then update the chart with the new data.

    Parameters:
        chart: a pptx.chart.chart.Chart object.
        context: a dict used for formatting placeholders in text values.
        perm_user: passed along for consistency (not used in this example).
    """

    # Common kwargs
    process_kwargs = dict(
        context=context,
        perm_user=perm_user,
    )

    # (1) Process series DATA in the chart (excluding series names and categories).
    all_processed_series_data = process_series_data(chart, context, perm_user)
    # Transpose the data if the chart's axes are swapped.
    if chart_axes_are_swapped(chart):
        all_processed_series_data = list(zip(*all_processed_series_data))

    # (2) Process series names, and attach to the series data from before.
    raw_series_names = [series.name for series in chart.series]
    series_names = process_chart_list(raw_series_names, **process_kwargs, as_float=False)
    series_names_values = [
        (series_name, series_data)
        for series_name, series_data in zip_longest(
            series_names,
            all_processed_series_data,
            fillvalue=None,
        )
    ]

    # (3) Process the placeholders in the categories from the first plot.
    if len(chart.plots) != 1:
        raise ChartError("Chart must have exactly one plot.")
    plot = chart.plots[0]
    raw_categories = [str(cat) for cat in plot.categories]
    categories = process_chart_list(raw_categories, **process_kwargs, as_float=False)

    # (4) Create a new ChartData object and populate it.
    chart_data = ChartData()
    chart_data.categories = categories
    for name, values in series_names_values:
        chart_data.add_series(name, values)

    # (5) Replace the chart's data with the new ChartData.
    chart.replace_data(chart_data)


def process_series_data(chart, context, perm_user):
    """
    Process the data in a chart, excluding the series names and categories.
    This is because if we put text values into the series data, the pptx
    library will not be able to retrieve it (because it will be left out of
    the XML) and so we need to go to the underlying Excel workbook to update
    the data.
    """

    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ChartError("Chart found, but required package (openpyxl) is not installed.")

    # Access the embedded Excel workbook via the chart's part.
    chart_part = chart.part
    chart_workbook = chart_part.chart_workbook
    xlsx_part = chart_workbook.xlsx_part

    # Load the workbook from the blob.
    wb_stream = BytesIO(xlsx_part.blob)
    workbook = load_workbook(wb_stream)
    if workbook is None or not workbook.worksheets:
        raise TableError("Attached Excel workbook is empty or has no worksheets.")
    worksheet = workbook.worksheets[0]

    # Process the DATA in the workbook (excluding the the first row and column
    # which correspond to series/categories, which are handled more directly
    # instead of reading the Excel data).
    all_series_data = []
    for i, col in enumerate(worksheet.iter_cols()):
        # Skip the first column, which is handled by the ChartData series/categories.
        if i == 0:
            continue
        # Skip the first row, which is handled by the ChartData series/categories.
        rows = [row.value for row in col][1:]
        # Process placeholders in the list data.
        all_series_data.append(
            process_chart_list(
                rows,
                context,
                perm_user,
                as_float=True,
            )
        )

    return all_series_data


def process_chart_list(items: list, context: dict, perm_user, as_float: bool):
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
                return make_float(r)
            return [make_float(ri) for ri in r]
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


def make_float(value):
    try:
        return float(value)
    except ValueError:
        raise BadChartDataResultError(f"Could not convert {value} to float.")


def chart_axes_are_swapped(chart: Chart):
    """
    Return True if the X and Y axes are swapped in the chart.
    Check if the first series name is in the first column, which is the default.
    """

    # Look at the first series
    if not chart.series:
        return False
    series = chart.series[0]

    # Look at the cell range reference ("<c:f>") - but NOT for categories
    if not series._element:
        return False
    range_references = series._element.xpath("./c:tx//c:f/text()")
    if not range_references:
        return False
    range_reference = range_references[0]

    # Normally, series names are in row 1, and if the row/column are
    # swapped, the series names are in column 1 (i.e. column "A"), so
    # if the range reference contains "$A$" then the axes ARE swapped.
    return "$A$" in range_reference
