"""Ensure attendance review actions do not create invalid nested HTML forms."""
import os
import unittest
from html.parser import HTMLParser


class FormNestingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.max_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)

    def handle_endtag(self, tag):
        if tag == "form":
            self.depth -= 1


class AttendanceReviewTemplateTests(unittest.TestCase):
    def test_review_template_has_no_nested_forms_and_cancel_overrides_action(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "templates", "attendance_review.html")
        with open(path, encoding="utf-8") as source:
            template = source.read()
        parser = FormNestingParser()
        parser.feed(template)
        self.assertEqual(parser.max_depth, 1)
        self.assertIn('formaction="{{ url_for(\'cancel_attendance_review\') }}"', template)
        self.assertIn('name="_csrf_token"', template)


if __name__ == "__main__":
    unittest.main()
