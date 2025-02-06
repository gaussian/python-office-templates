import unittest
from template_reports.templating import (
    resolve_tag_expression,
    split_expression,
    get_nested_attr,
    evaluate_condition,
    parse_value,
    process_text,
)


# A simple dummy class to simulate model instances.
class Dummy:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __str__(self):
        # For display in drop-downs or when joining lists.
        if hasattr(self, "email"):
            return self.email
        return super().__str__()


class TestTemplating(unittest.TestCase):

    def test_simple_attribute_lookup(self):
        # Test resolving a simple dot-notation lookup.
        user = Dummy(email="alice@example.com")
        context = {"user": user}
        result = resolve_tag_expression("user.email", context)
        self.assertEqual(result, "alice@example.com")

    def test_nested_attribute_lookup(self):
        # Test lookup through a nested attribute (using dot notation).
        profile = Dummy(phone="123-4567")
        user = Dummy(email="bob@example.com", profile=profile)
        context = {"user": user}
        result = resolve_tag_expression("user.profile.phone", context)
        self.assertEqual(result, "123-4567")

        # Also test using the double-underscore lookup helper.
        result2 = get_nested_attr(user, "profile__phone")
        self.assertEqual(result2, "123-4567")

    def test_collection_mapping(self):
        # When the attribute yields a list, the next lookup should be mapped.
        user1 = Dummy(email="user1@example.com", is_active=True)
        user2 = Dummy(email="user2@example.com", is_active=False)
        program = Dummy(users=[user1, user2])
        context = {"program": program}

        # Without any filtering, we expect a list of emails.
        result = resolve_tag_expression("program.users.email", context)
        self.assertEqual(result, ["user1@example.com", "user2@example.com"])

    def test_filtering_in_collection(self):
        # Test that a filter in the tag works.
        user1 = Dummy(email="user1@example.com", is_active=True)
        user2 = Dummy(email="user2@example.com", is_active=False)
        user3 = Dummy(email="user3@example.com", is_active=True)
        program = Dummy(users=[user1, user2, user3])
        context = {"program": program}

        # Using the filter syntax: only active users.
        result = resolve_tag_expression("program.users[is_active==True].email", context)
        self.assertEqual(result, ["user1@example.com", "user3@example.com"])

    def test_process_text_single_tag(self):
        # Test process_text for a string with one template tag.
        user = Dummy(email="charlie@example.com")
        context = {"user": user}
        input_text = "Email: {{ user.email }}"
        output_text = process_text(input_text, context)
        self.assertEqual(output_text, "Email: charlie@example.com")

    def test_process_text_multiple_tags(self):
        # Test process_text with more than one tag in the text.
        user = Dummy(email="david@example.com")
        program = Dummy(
            users=[
                Dummy(email="david@example.com", is_active=True),
                Dummy(email="eve@example.com", is_active=False),
                Dummy(email="frank@example.com", is_active=True),
            ]
        )
        context = {"user": user, "program": program}
        input_text = "User: {{ user.email }}; Active Participants: {{ program.users[is_active==True].email }}"
        # Expect the list of active participants to be joined by commas.
        expected = "User: david@example.com; Active Participants: david@example.com, frank@example.com"
        self.assertEqual(process_text(input_text, context), expected)

    def test_parse_value(self):
        # Test conversion of string representations to Python types.
        self.assertEqual(parse_value("True"), True)
        self.assertEqual(parse_value("false"), False)
        self.assertEqual(parse_value("42"), 42)
        self.assertEqual(parse_value("3.14"), 3.14)
        self.assertEqual(parse_value("'hello'"), "hello")
        self.assertEqual(parse_value('"world"'), "world")
        self.assertEqual(parse_value("unquoted"), "unquoted")

    def test_evaluate_condition(self):
        # Test that evaluate_condition correctly evaluates an equality condition.
        user_active = Dummy(email="active@example.com", is_active=True)
        user_inactive = Dummy(email="inactive@example.com", is_active=False)
        # Condition: is_active==True should return True only for the active user.
        self.assertTrue(evaluate_condition(user_active, "is_active==True"))
        self.assertFalse(evaluate_condition(user_inactive, "is_active==True"))
        # Also test a chained lookup in the condition using double underscores.
        profile = Dummy(phone="555-1234")
        user = Dummy(email="phone@example.com", profile=profile)
        self.assertTrue(evaluate_condition(user, "profile__phone=='555-1234'"))
        self.assertFalse(evaluate_condition(user, "profile__phone=='000-0000'"))

    def test_split_expression(self):
        # Ensure that split_expression splits correctly and ignores dots inside filter brackets.
        expr = "program.users[is_active==True].email"
        segments = split_expression(expr)
        self.assertEqual(segments, ["program", "users[is_active==True]", "email"])

        # Also test an expression without any filter.
        expr2 = "user.profile.phone"
        segments2 = split_expression(expr2)
        self.assertEqual(segments2, ["user", "profile", "phone"])


if __name__ == "__main__":
    unittest.main()
