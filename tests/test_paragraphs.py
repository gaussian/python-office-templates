import unittest
from template_reports.office_renderer.paragraphs import (
    merge_split_placeholders,
    UnterminatedTagException,
)


class DummyRun:
    def __init__(self, text=""):
        self.text = text
        self._r = self  # minimal stub for removal


class DummyParagraph:
    def __init__(self, runs=None):
        self.runs = runs or []
        self._p = self  # minimal stub for removal

    @property
    def text(self):
        return "".join(run.text for run in self.runs)

    def remove(self, run):
        self.runs.remove(run)


class TestMergeSplitPlaceholders(unittest.TestCase):
    def test_merge_placeholder_across_runs(self):
        # {{ in one run, }} in another
        para = DummyParagraph(
            [
                DummyRun("Hello "),
                DummyRun("{{ name"),
                DummyRun(" }}!"),
            ]
        )
        # Patch _p.remove to DummyParagraph.remove
        para._p = para
        for run in para.runs:
            run._r = run
        merge_split_placeholders(para)
        self.assertEqual(para.text, "Hello {{ name }}!")
        self.assertEqual(len(para.runs), 2)  # merged into one, plus 'Hello '
        self.assertEqual(para.runs[1].text, "{{ name }}!")

    def test_merge_multiple_placeholders_across_runs(self):
        para = DummyParagraph(
            [
                DummyRun("{{ foo"),
                DummyRun(" }} and "),
                DummyRun("{{ bar"),
                DummyRun(" }}"),
            ]
        )
        para._p = para
        for run in para.runs:
            run._r = run
        merge_split_placeholders(para)
        self.assertEqual(para.text, "{{ foo }} and {{ bar }}")
        self.assertEqual(len(para.runs), 2)
        self.assertEqual(para.runs[0].text, "{{ foo }} and ")
        self.assertEqual(para.runs[1].text, "{{ bar }}")

    def test_merge_multiple_placeholders_per_run(self):
        para = DummyParagraph(
            [
                DummyRun("{{ foo }} and {{ "),
                DummyRun("bar"),
                DummyRun(" }}"),
            ]
        )
        para._p = para
        for run in para.runs:
            run._r = run
        merge_split_placeholders(para)
        self.assertEqual(para.text, "{{ foo }} and {{ bar }}")
        self.assertEqual(len(para.runs), 1)
        self.assertEqual(para.runs[0].text, "{{ foo }} and {{ bar }}")

    def test_unterminated_tag_raises(self):
        para = DummyParagraph(
            [
                DummyRun("Hello {{ name"),
                DummyRun(" is here"),
            ]
        )
        para._p = para
        for run in para.runs:
            run._r = run
        with self.assertRaises(UnterminatedTagException):
            merge_split_placeholders(para)


if __name__ == "__main__":
    unittest.main()
