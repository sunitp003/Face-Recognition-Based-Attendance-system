"""Upload staging and rollback tests for student image ZIPs."""
import os
import tempfile
import unittest
import zipfile

from services.file_storage import unzip_file


class FileStorageValidationTests(unittest.TestCase):
    def make_zip(self, path):
        with zipfile.ZipFile(path, "w") as archive:
            for index in range(5):
                archive.writestr(f"photo_{index}.jpg", b"fake-image-data")

    def test_failed_sample_validation_preserves_previous_upload(self):
        with tempfile.TemporaryDirectory() as root:
            archive_path = os.path.join(root, "samples.zip")
            target = os.path.join(root, "uploads")
            self.make_zip(archive_path)
            student_dir = os.path.join(target, "ROLL1")
            os.makedirs(student_dir)
            previous = os.path.join(student_dir, "previous.jpg")
            with open(previous, "wb") as output:
                output.write(b"previous samples")

            result = unzip_file(archive_path, target, "ROLL1", validator=lambda _path: False)

            self.assertIsNone(result)
            self.assertTrue(os.path.exists(previous))
            with open(previous, "rb") as source:
                self.assertEqual(source.read(), b"previous samples")

    def test_validated_staging_replaces_previous_upload(self):
        with tempfile.TemporaryDirectory() as root:
            archive_path = os.path.join(root, "samples.zip")
            target = os.path.join(root, "uploads")
            self.make_zip(archive_path)
            student_dir = os.path.join(target, "ROLL1")
            os.makedirs(student_dir)
            with open(os.path.join(student_dir, "old.jpg"), "wb") as output:
                output.write(b"old")

            result = unzip_file(archive_path, target, "ROLL1", validator=lambda _path: True)

            self.assertEqual(result, student_dir)
            self.assertFalse(os.path.exists(os.path.join(student_dir, "old.jpg")))
            self.assertEqual(len(os.listdir(student_dir)), 5)


if __name__ == "__main__":
    unittest.main()
