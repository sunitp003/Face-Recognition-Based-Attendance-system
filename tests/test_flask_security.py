"""Flask security regression tests."""
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash

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

    def test_first_login_password_reset_stores_a_hash(self):
        class FakeCursor:
            rowcount = 1
            def execute(self, query, params):
                self.query = query
                self.params = params

        class FakeConnection:
            def __init__(self):
                self.fake_cursor = FakeCursor()
            def cursor(self):
                return self.fake_cursor
            def commit(self):
                pass

        fake_connection = FakeConnection()
        with self.client.session_transaction() as session:
            session["user"] = "admin-user"
            session["role"] = "Admin"
            session["must_change_password"] = True
            session["_csrf_token"] = "test-csrf-token"
        with patch("routes.auth.conn", fake_connection):
            response = self.client.post(
                "/change-password",
                data={
                    "_csrf_token": "test-csrf-token",
                    "new_password": "LongSecurePass123",
                    "confirm_password": "LongSecurePass123",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(check_password_hash(fake_connection.fake_cursor.params[0], "LongSecurePass123"))
        with self.client.session_transaction() as session:
            self.assertNotIn("must_change_password", session)

if __name__ == "__main__":
    unittest.main()
