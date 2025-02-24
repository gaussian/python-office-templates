import unittest
from template_reports.templating.formatting import convert_date_format


class TestFormatting(unittest.TestCase):
    def test_convert_format_basic(self):
        pattern = "MMMM dd, YYYY"
        expected = "%B %d, %Y"
        self.assertEqual(convert_date_format(pattern), expected)

    def test_convert_format_tokens(self):
        pattern = "ddd DD, YY at HH:mm:ss"
        expected = "%a %A, %y at %H:%M:%S"
        self.assertEqual(convert_date_format(pattern), expected)

    def test_convert_format_no_tokens(self):
        pattern = "No tokens here!"
        expected = "No tokens here!"
        self.assertEqual(convert_date_format(pattern), expected)

    def test_convert_format_compatibility(self):
        import datetime

        pattern = "YYYY/MM/dd HH:mm"
        fmt = convert_date_format(pattern)
        dt = datetime.datetime(2025, 12, 31, 23, 59)
        result = dt.strftime(fmt)
        expected = "2025/12/31 23:59"
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
