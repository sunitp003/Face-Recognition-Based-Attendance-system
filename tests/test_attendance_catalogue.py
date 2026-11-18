import unittest
from services.attendance_catalogue import is_valid_subject


class AttendanceCatalogueTests(unittest.TestCase):
    def test_valid_subject(self):
        self.assertTrue(is_valid_subject("it", "2", "DBMS"))

    def test_rejects_unknown_subject_branch_and_year(self):
        self.assertFalse(is_valid_subject("it", "2", "Invented"))
        self.assertFalse(is_valid_subject("unknown", "2", "DBMS"))
        self.assertFalse(is_valid_subject("it", "5", "DBMS"))

    def test_branch_is_case_insensitive(self):
        self.assertTrue(is_valid_subject("IT", "2", "DBMS"))


if __name__ == "__main__":
    unittest.main()
