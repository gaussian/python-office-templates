import unittest
import datetime
import re
from unittest.mock import patch, Mock

from template_reports.templating.core import process_text
from template_reports.pptx_renderer.exceptions import PermissionDeniedException


# Dummy request user for testing.
class DummyRequestUser:
    def has_perm(self, perm, obj):
        return True


class TestCore(unittest.TestCase):
    """This test class focuses on the 'process_text' function in both normal and table modes.

    Each test is designed to illustrate how placeholders,
    permissions, and formatting are handled using patched dependencies.
    """

    @patch("template_reports.templating.core.enforce_permissions", return_value="Alice")
    @patch(
        "template_reports.templating.core.resolve_tag_expression", return_value="Alice"
    )
    def test_pure_placeholder_normal(self, mock_resolve, mock_enforce):
        """Verifies normal-mode resolution of a simple placeholder.

        Ensures that 'resolve_tag_expression' and 'enforce_permissions'
        are called correctly, returning the expected string value.
        """
        context = {"user": "Alice"}
        text = "{{ user }}"
        result = process_text(
            text,
            context,
            request_user=DummyRequestUser(),
            check_permissions=True,
            mode="normal",
        )
        self.assertEqual(result, "Alice")
        mock_resolve.assert_called_once_with("user", context)

    @patch("template_reports.templating.core.enforce_permissions", return_value="Bob")
    @patch("template_reports.templating.core.resolve_tag_expression", return_value="Bob")
    def test_pure_placeholder_table(self, mock_resolve, mock_enforce):
        context = {"user": "Bob"}
        text = "{{ user }}"
        result = process_text(
            text,
            context,
            request_user=DummyRequestUser(),
            check_permissions=True,
            mode="table",
        )
        self.assertEqual(result, "Bob")

    @patch("template_reports.templating.core.convert_format", return_value="%B %d, %Y")
    @patch("template_reports.templating.core.enforce_permissions")
    @patch("template_reports.templating.core.resolve_tag_expression")
    def test_formatting_pipe(self, mock_resolve, mock_enforce, mock_convert):
        """Ensures that placeholders with a formatting pipe are
        converted correctly into a Python strftime format.
        """
        fake_date = datetime.datetime(2020, 1, 1)
        mock_resolve.return_value = fake_date
        # When enforce_permissions is called, return the value unchanged.
        mock_enforce.side_effect = lambda value, r, e, ru, cp, **kwargs: value
        context = {"date": fake_date}
        text = "{{ date | MMMM dd, YYYY }}"
        result = process_text(
            text,
            context,
            request_user=DummyRequestUser(),
            check_permissions=True,
            mode="normal",
        )
        expected = fake_date.strftime("%B %d, %Y")
        self.assertEqual(result, expected)
        mock_convert.assert_called_once_with("MMMM dd, YYYY")

    @patch(
        "template_reports.templating.core.enforce_permissions", return_value="TestValue"
    )
    @patch(
        "template_reports.templating.core.resolve_tag_expression",
        return_value="TestValue",
    )
    def test_mixed_text(self, mock_resolve, mock_enforce):
        context = {"value": "TestValue"}
        text = "Prefix {{ value }} Suffix"
        result = process_text(
            text,
            context,
            request_user=DummyRequestUser(),
            check_permissions=True,
            mode="normal",
        )
        self.assertEqual(result, "Prefix TestValue Suffix")

    # --- Additional Edge Case Tests with full patching ---
    @patch("template_reports.templating.core.resolve_tag_expression", return_value="")
    def test_empty_placeholder(self, mock_resolve):
        tpl = "Empty: {{    }}."
        # Without a valid resolution, empty placeholders are processed to empty.
        result = process_text(
            tpl,
            {},
            errors=[],
            request_user=DummyRequestUser(),
            check_permissions=False,
            mode="normal",
        )
        self.assertEqual(result, "Empty: .")

    @patch("template_reports.templating.core.resolve_tag_expression", return_value="")
    def test_missing_key(self, mock_resolve):
        tpl = "Missing: {{ non_existent }}."
        errors = []
        result = process_text(
            tpl,
            {},
            errors=errors,
            request_user=DummyRequestUser(),
            check_permissions=False,
            mode="normal",
        )
        self.assertEqual(result, "Missing: .")
        self.assertTrue(any("non_existent" in err for err in errors))

    @patch(
        "template_reports.templating.core.resolve_tag_expression",
        side_effect=lambda expr, ctx: "Alice" if expr == "user.name" else ctx.get("now"),
    )
    @patch("template_reports.templating.core.convert_format", return_value="%B %d, %Y")
    @patch(
        "template_reports.templating.core.enforce_permissions",
        side_effect=lambda value, r, e, ru, cp, **kwargs: value,
    )
    def test_multiple_placeholders_in_mixed_text(
        self, mock_enforce, mock_convert, mock_resolve
    ):
        """Checks that multiple placeholders in a single string
        are each resolved and formatted independently.
        """
        tpl = "User: {{ user.name }}, today: {{ now | MMMM dd, YYYY }}."
        fixed_now = datetime.datetime(2025, 2, 18, 12, 0, 0)
        context = {"user": {"name": "Alice"}, "now": fixed_now}
        result = process_text(
            tpl,
            context,
            errors=[],
            request_user=DummyRequestUser(),
            check_permissions=False,
            mode="normal",
        )
        expected = f"User: Alice, today: {fixed_now.strftime('%B %d, %Y')}."
        self.assertEqual(result, expected)

    @patch(
        "template_reports.templating.core.resolve_tag_expression",
        return_value=lambda: "ALICE",
    )
    @patch("template_reports.templating.core.enforce_permissions", return_value="ALICE")
    def test_nested_lookup_with_function(self, mock_enforce, mock_resolve):
        context = {"user": {"name": "Alice", "get_display": lambda: "ALICE"}}
        tpl = "Display: {{ user.get_display }}"
        result = process_text(
            tpl,
            context,
            errors=[],
            request_user=DummyRequestUser(),
            check_permissions=False,
            mode="normal",
        )
        self.assertEqual(result, "Display: ALICE")

    @patch("template_reports.templating.core.convert_format", return_value="%b %d, %Y")
    @patch("template_reports.templating.core.resolve_tag_expression")
    @patch(
        "template_reports.templating.core.enforce_permissions",
        side_effect=lambda v, r, e, ru, cp: v,
    )
    def test_formatting_with_percent_error(
        self, mock_enforce, mock_resolve, mock_convert
    ):
        # Return a mock datetime object that raises ValueError on strftime.
        mock_dt = Mock(spec=datetime.datetime)
        mock_dt.strftime.side_effect = ValueError("format error")
        mock_resolve.return_value = mock_dt

        tpl = "{{ now | MMM dd, YYYY %Z }}"
        context = {"now": datetime.datetime(2025, 2, 18, 12, 0, 0)}
        errors = []
        result = process_text(
            tpl,
            context,
            errors=errors,
            request_user=DummyRequestUser(),
            check_permissions=False,
            mode="normal",
        )
        self.assertEqual(result, "")
        self.assertTrue(
            any("format error" in err or "Formatting error" in err for err in errors)
        )


if __name__ == "__main__":
    unittest.main()
