"""Architecture and storage regression tests for the modular service layer."""
import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from flask import Flask

import database
import modelTrain
import recognition
from services import face_recognition, file_storage, model_training


class DatabaseServiceTests(unittest.TestCase):
    def test_connection_is_cached_per_application_context_and_closed(self):
        class FakeConnection:
            def __init__(self):
                self.closed = 0
                self.autocommit_value = None
            def autocommit(self, value):
                self.autocommit_value = value
            def close(self):
                self.closed += 1

        fake = FakeConnection()
        app = Flask(__name__)
        with patch.object(database.MySQLdb, "connect", return_value=fake) as connect:
            with app.app_context():
                first = database.get_db()
                second = database.get_db()
                self.assertIs(first, second)
                self.assertEqual(connect.call_count, 1)
                self.assertTrue(fake.autocommit_value)
                database.close_db()
                self.assertEqual(fake.closed, 1)


class StorageServiceTests(unittest.TestCase):
    def test_zip_paths_cannot_escape_student_directory(self):
        with tempfile.TemporaryDirectory() as root:
            archive_path = os.path.join(root, "images.zip")
            destination = os.path.join(root, "uploads")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../../outside.jpg", b"image-bytes")
            extracted = file_storage.unzip_file(archive_path, destination, "STU001")
            self.assertEqual(extracted, os.path.join(destination, "STU001"))
            self.assertTrue(os.path.isfile(os.path.join(extracted, "1_outside.jpg")))
            self.assertFalse(os.path.exists(os.path.join(root, "outside.jpg")))


class CompatibilityTests(unittest.TestCase):
    def test_legacy_face_module_paths_export_service_implementations(self):
        self.assertIs(modelTrain.TrainImages, model_training.TrainImages)
        self.assertIs(recognition.recognize_attendance, face_recognition.recognize_attendance)

    def test_existing_route_paths_and_endpoint_names_remain_registered(self):
        import app as application
        expected = {
            ("/", "index"),
            ("/change-password", "change_password"),
            ("/logout", "logout"),
            ("/admin/", "admin"),
            ("/admin/delete", "deleteStudent"),
            ("/admin/addRecord", "addRecord"),
            ("/studentReg", "studentReg"),
            ("/studentDashboard", "studentDashboard"),
            ("/student/view_attendance", "student_view_attendance"),
            ("/faculty", "faculty"),
            ("/faculty/confirm_attendance", "confirm_attendance"),
            ("/faculty/view_attendance", "faculty_view"),
            ("/faculty/edit_attendance", "edit_attendance"),
            ("/faculty/download_attendance", "download_attendance"),
            ("/about", "about"),
        }
        actual = {(rule.rule, rule.endpoint) for rule in application.app.url_map.iter_rules()}
        self.assertTrue(expected.issubset(actual))


if __name__ == "__main__":
    unittest.main()
