"""Flask security regression tests."""
import unittest

import app as application


class CsrfProtectionTests(unittest.TestCase):
    def setUp(self):
        application.app.config.update(TESTING=True)
        self.client = application.app.test_client()

    def test_post_without_csrf_token_is_rejected_before_database_access(self):
        response = self.client.post("/", data={"loginAs": "Admin"})
        self.assertEqual(response.status_code, 400)

    def test_login_page_renders_csrf_token(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="_csrf_token"', response.data)


if __name__ == "__main__":
    unittest.main()
