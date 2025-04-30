import unittest
from unittest.mock import patch

from template_reports.office_renderer.exceptions import TableError
import template_reports.office_renderer.tables as tables
from template_reports.office_renderer.tables import (
    clone_row_with_value,
    fill_column_with_list,
    process_table_cell,
)


# ——— Dummy helpers ————————————————————————————————————————


class DummyRequestUser:
    def has_perm(self, perm, obj):
        return True


class DummyElement:
    """Bare‑bones XML element stand‑in."""

    def __init__(self, text=""):
        self.text = text
        self.parent = None
        self.text_frame = None

    def getparent(self):
        return self.parent

    # python‑pptx internal helper our *_Cell wrapper expects
    def get_or_add_txBody(self):
        return self

    def __repr__(self):
        return f"DummyElement({self.text!r})"


class DummyRun:
    def __init__(self, text=""):
        self.text = text
        self._r = DummyElement(text)
        self.font = type("Font", (), {})()
        self.font.bold = False
        self.font.size = 12


class DummyParagraph:
    def __init__(self, text=""):
        self._p = DummyElement("")  # underlying XML element placeholder
        self.runs = [DummyRun(text)] if text else []

    def clear(self):
        self.runs = []

    def add_run(self):
        r = DummyRun()
        self.runs.append(r)
        return r


class DummyTextFrame:
    def __init__(self, paragraphs=None):
        self.paragraphs = paragraphs or []
        if not self.paragraphs:
            self.paragraphs.append(DummyParagraph(""))

    def add_paragraph(self):
        p = DummyParagraph("")
        self.paragraphs.append(p)
        return p


class DummyCell:
    """Substitute for pptx.table._Cell used inside the library code."""

    def __init__(self, target, parent):
        self._target = target  # DummyElement
        self._parent = parent  # DummyRow
        if target.text_frame is None:
            target.text_frame = DummyTextFrame([DummyParagraph(target.text)])
        self.text_frame = target.text_frame

    @property
    def text(self):
        # Derive from runs
        return "".join(r.text for p in self.text_frame.paragraphs for r in p.runs)

    @text.setter
    def text(self, value):
        if not self.text_frame.paragraphs:
            self.text_frame.paragraphs.append(DummyParagraph(""))
        p = self.text_frame.paragraphs[0]
        if p.runs:
            p.runs[0].text = value
            for extra in p.runs[1:]:
                extra.text = ""
        else:
            p.runs.append(DummyRun(value))
        self._target.text = value  # sync back


class DummyRow(list):
    def __init__(self, cells, parent=None):
        super().__init__(cells)
        for c in cells:
            c.parent = self
        self.parent = parent

    def getparent(self):
        return self.parent

    def __deepcopy__(self, memo):
        copied_cells = []
        for c in self:
            nc = DummyElement(c.text)
            if getattr(c, "text_frame", None) is not None:
                new_paras = []
                for p in c.text_frame.paragraphs:
                    new_p = DummyParagraph("")
                    new_p.runs = []
                    for r in p.runs:
                        new_r = DummyRun(r.text)
                        new_r.font.bold = r.font.bold
                        new_r.font.size = r.font.size
                        new_p.runs.append(new_r)
                    new_paras.append(new_p)
                nc.text_frame = DummyTextFrame(new_paras)
            copied_cells.append(nc)
        return DummyRow(copied_cells, parent=self.parent)


class DummyTable:
    def __init__(self):
        self.rows = []

    def append(self, row):
        row.parent = self
        self.rows.append(row)

    def __iter__(self):
        return iter(self.rows)

    def __repr__(self):
        return f"DummyTable(rows={self.rows})"


class DummyCellWrapper:
    """What the library receives in real use (shape.table.cell)."""

    def __init__(self, text=""):
        self._tc = DummyElement(text)
        self._tc.text_frame = DummyTextFrame([DummyParagraph(text)])
        self.text_frame = self._tc.text_frame

    @property
    def text(self):
        return "".join(r.text for p in self.text_frame.paragraphs for r in p.runs)

    @text.setter
    def text(self, value):
        p = self.text_frame.paragraphs[0]
        if p.runs:
            p.runs[0].text = value
            for extra in p.runs[1:]:
                extra.text = ""
        else:
            p.runs.append(DummyRun(value))
        self._tc.text = value


# ——— Test cases ——————————————————————————————————————————


class TestTables(unittest.TestCase):

    # --- clone_row_with_value ---
    @patch("pptx.table._Cell", new=DummyCell)
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_clone_row_with_value_normal(self):
        row = DummyRow([DummyElement("A"), DummyElement("B"), DummyElement("C")])
        cloned = clone_row_with_value(row, 1, "NEW")
        vals = [DummyCell(c, cloned).text for c in cloned]
        self.assertEqual(vals, ["A", "NEW", "C"])
        self.assertEqual(row[1].text, "B")

    @patch("pptx.table._Cell", new=DummyCell)
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_clone_row_with_value_out_of_range(self):
        with self.assertRaises(TableError):
            clone_row_with_value(DummyRow([DummyElement("X")]), 5, "NOPE")

    # --- fill_column_with_list ---
    @patch("pptx.table._Cell", new=DummyCell)
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_fill_column_with_list_normal(self):
        cw = DummyCellWrapper("ORIGINAL")
        row = DummyRow([cw._tc])
        tbl = DummyTable()
        tbl.append(row)
        fill_column_with_list(cw, ["First", "Second", "Third"])
        self.assertEqual(cw.text, "First")
        self.assertEqual(len(tbl.rows), 3)
        self.assertEqual(DummyCell(tbl.rows[1][0], tbl.rows[1]).text, "Second")
        self.assertEqual(DummyCell(tbl.rows[2][0], tbl.rows[2]).text, "Third")

    @patch("pptx.table._Cell", new=DummyCell)
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_fill_column_with_list_empty(self):
        cw = DummyCellWrapper("NonEmpty")
        row = DummyRow([cw._tc])
        tbl = DummyTable()
        tbl.append(row)
        fill_column_with_list(cw, [])
        self.assertEqual(cw.text, "")

    @patch("pptx.table._Cell", new=DummyCell)
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    def test_fill_column_with_list_preserves_formatting(self):
        class BR(DummyRun):
            def __init__(self, text):
                super().__init__(text)
                self.font.bold = True
                self.font.size = 22

        p = DummyParagraph("")
        p.runs = [BR("X")]
        cw = DummyCellWrapper("X")
        cw.text_frame = DummyTextFrame([p])
        cw._tc.text_frame = cw.text_frame
        tbl = DummyTable()
        tbl.append(DummyRow([cw._tc]))
        fill_column_with_list(cw, ["A", "B"])
        run0 = cw.text_frame.paragraphs[0].runs[0]
        self.assertTrue(run0.font.bold)
        self.assertEqual(run0.font.size, 22)

    # --- process_table_cell (mixed) ---
    @patch(
        "template_reports.office_renderer.tables.get_matching_tags",
        return_value=["x", "y"],
    )
    def test_process_table_cell_mixed_text(self, *_):
        cw = DummyCellWrapper("Pre {{ x }} Post")
        orig = tables.process_paragraph
        try:

            def dummy_pp(paragraph, context, perm_user, mode):
                paragraph.clear()
                paragraph.add_run().text = "Repl"

            tables.process_paragraph = dummy_pp
            process_table_cell(cw, {}, None)
            self.assertEqual(cw.text, "Repl")
        finally:
            tables.process_paragraph = orig

    # --- process_table_cell (pure) ---
    @patch("pptx.table._Cell", new=DummyCell)
    @patch("template_reports.office_renderer.tables._Cell", new=DummyCell)
    @patch(
        "template_reports.office_renderer.tables.process_text", return_value=["R1", "R2"]
    )
    @patch(
        "template_reports.office_renderer.tables.get_matching_tags", return_value=["only"]
    )
    def test_process_table_cell_pure_placeholder(self, *_):
        cw = DummyCellWrapper("{{ only }}")
        r = DummyRow([cw._tc])
        tbl = DummyTable()
        tbl.append(r)
        cw._tc.parent = r
        r.parent = tbl
        process_table_cell(cw, {}, DummyRequestUser())
        self.assertEqual(cw.text, "R1")
        # second row exists but is cleared, not set
        self.assertEqual(DummyCell(tbl.rows[1][0], tbl.rows[1]).text, "")


if __name__ == "__main__":
    unittest.main()
