# Office Templates

Office Templates is a Python library turns PowerPoint (PPTX) and Excel (XLSX) files into reusable templates.  Placeholders inside those templates are resolved using provided context so that you can generate templated documents without hard‑coding content.

## Key Features

* **PowerPoint and Excel rendering** – supply a PPTX or XLSX file and a context dictionary to produce a finished document.
* **Placeholder expressions** using ``{{ }}`` to access attributes, call methods, filter lists and perform math.
* **Formatting helpers** for dates, numbers and string casing (``upper``, ``lower``, ``title``).
* **Arithmetic operators** in expressions (``+``, ``-``, ``*``, ``/``).
* **Dynamic table and worksheet expansion** when a placeholder resolves to a list.
* **Chart support** where spreadsheet values inside charts contain placeholders.
* **Permission enforcement** – data is filtered based on ``check_permissions`` function.
* **Global context** injection for values that should always be available.
* **Context extraction** to inspect templates and determine which context keys are required.
* **Image placeholders** – shapes or cells starting with ``%imagesqueeze%`` or ``%image%`` are replaced by an image downloaded from the provided URL.
* **Node/edge graph generation** – programmatically create graph visualizations with positioned nodes and connecting edges on PPTX slides.

## Codebase Overview

``office_templates/`` contains the library:

* ``office_renderer/`` – logic for rendering PPTX and XLSX files.  This handles text boxes, tables, charts, worksheets and the `%image%`/`%imagesqueeze%` directives.
* ``templating/`` – the template engine responsible for parsing and evaluating expressions.
* ``tests/`` – the test suite.

Start by looking at the functions in ``office_renderer`` to see how a file is rendered.  The templating package is standalone and can be read independently if you want to learn how placeholders are parsed.

## Writing Templates

Template files are just normal PowerPoint or Excel documents.  No coding or macros are required—just type plain text placeholders where you want dynamic information to appear.

1. **Design your layout.** Build the slides or workbook exactly as you would for a static report.
2. **Insert placeholders.** Anywhere you would type text you can instead type a placeholder wrapped in `{{` and `}}`:
   * `{{ user.name }}` – insert a simple value from the context.
   * `{{ user.profile__email }}` – read nested attributes using `.` or `__`.
   * `{{ users[is_active=True].email }}` – pick a specific item from a list.
   * `{{ amount * 1.15 }}` – perform calculations.
   * `{{ price | .2f }}` or `{{ name | upper }}` – apply formatting filters.
3. **Repeat rows or slides for lists.** If a placeholder by itself resolves to a list, extra rows (or slides) will be created so that each item appears separately.  This is how you build tables from querysets.
4. **Add images.** To include an image from a URL, create a text box or cell that starts with `%image%` or `%imagesqueeze%` followed by the address:
   `%image% https://example.com/logo.png`
   `%imagesqueeze% https://example.com/logo.png`
   The former keeps the image's aspect ratio while fitting it inside the shape. The latter squeezes the image to exactly fill the shape.
5. **Save the file** and register it in the Django admin as a report template.

You can experiment with the example files in `office_templates/raw_templates` to see common patterns.  Remember that all placeholders are plain text—avoid formulas or punctuation that might confuse the parser.

Chart data sheets can also contain placeholders so your graphs update automatically.

## Creating Node/Edge Graphs

The library can programmatically generate node/edge graph visualizations in PowerPoint presentations. This is useful for creating architecture diagrams, flowcharts, network topologies, and organizational charts.

### Basic Usage

```python
from office_templates.office_renderer import compose_graphs_pptx

graphs = [
    {
        "nodes": [
            {
                "id": "frontend",
                "name": "Frontend",
                "detail": "React.js Application",
                "position": {"x": 1, "y": 2},
            },
            {
                "id": "backend",
                "name": "Backend API",
                "detail": "Node.js Server",
                "position": {"x": 4, "y": 2},
            },
            {
                "id": "database",
                "name": "Database",
                "detail": "PostgreSQL",
                "position": {"x": 7, "y": 2},
            },
        ],
        "edges": [
            {"from": "frontend", "to": "backend", "label": "HTTPS"},
            {"from": "backend", "to": "database", "label": "SQL"},
        ],
    }
]

result, errors = compose_graphs_pptx(
    template_files=["template.pptx"],
    graphs=graphs,
    global_context={},
    output="output.pptx",
    use_tagged_layouts=True,
)
```

### Graph Structure

Each graph dictionary should contain:

* **nodes** (list, required): List of node dictionaries with:
  * `id` (string, required): Unique identifier for the node
  * `name` (string, required): Display name shown in the node shape
  * `detail` (string, optional): Additional details shown below the name in smaller font
  * `position` (dict, required): Position on the slide with `x` and `y` keys (in inches)
  * `parent` (string, optional): ID of parent node for nesting (placeholder functionality)

* **edges** (list, required): List of edge dictionaries with:
  * `from` (string, required): Source node ID
  * `to` (string, required): Target node ID
  * `label` (string, optional): Text label for the edge

### Features

* **Automatic slide expansion**: Slides automatically resize to fit all nodes
* **Elbow connectors**: Edges use right-angle connectors for professional appearance
* **Template variables**: Node names, details, and edge labels support `{{ }}` placeholders
* **Multiple graphs**: Each graph in the list creates a separate slide
* **Template layouts**: Use `% layout graph %` in template slides to define custom layouts

### Node Positioning

Node positions are specified in inches from the top-left corner of the slide:

```python
"position": {"x": 3.5, "y": 2.0}  # 3.5 inches right, 2 inches down
```

Nodes are automatically sized to fit their content, and slides expand to accommodate all nodes plus margins.

## Learning More

After trying the example templates in ``raw_templates/`` explore the ``tests/`` directory to see many usage patterns.  The test files demonstrate complex placeholders, permission checks and the new image replacement behaviour.

## Development

Use `uv sync --all-extras` to set up the python environment.