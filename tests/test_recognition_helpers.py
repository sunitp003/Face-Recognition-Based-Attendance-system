"""Regression tests for conservative face-recognition helpers."""
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import modelTrain
import recognition


class RecognitionHelperTests(unittest.TestCase):
    def test_vote_aggregation_requires_distinct_windows(self):
        votes = {
            "STU001": {0: 20.0, 1: 25.0, 2: 30.0, 3: 35.0, 4: 40.0},
            "STU002": {0: 20.0, 1: 25.0, 2: 30.0, 3: 35.0},
            "STU003": {0: 45.0, 1: 46.0, 2: 47.0, 3: 48.0, 4: 49.0},
        }
        self.assertEqual(
            recognition._aggregate_votes(votes, threshold=42.0, min_votes=5),
            ["STU001"],
        )

    def test_invalid_threshold_uses_safe_default(self):
        with patch.dict(os.environ, {"TEST_LBPH_THRESHOLD": "nan"}):
            self.assertEqual(
                recognition._positive_env_float("TEST_LBPH_THRESHOLD", 42.0),
                42.0,
            )

    def test_invalid_vote_setting_uses_default(self):
        with patch.dict(os.environ, {"TEST_LBPH_VOTES": "not-an-int"}):
            self.assertEqual(
                recognition._positive_env_int("TEST_LBPH_VOTES", 5, minimum=3),
                5,
            )

    def test_quality_check_uses_raw_image_characteristics(self):
        rng = np.random.default_rng(7)
        textured = rng.integers(50, 200, size=(120, 120), dtype=np.uint8)
        dark = np.zeros((120, 120), dtype=np.uint8)
        self.assertTrue(recognition._quality_ok(textured))
        self.assertFalse(recognition._quality_ok(dark))
        self.assertFalse(recognition._quality_ok(None))

    def test_preprocessing_returns_expected_face_size(self):
        face = np.arange(120 * 100, dtype=np.uint8).reshape(120, 100)
        processed = recognition.preprocess_face(face)
        self.assertEqual(processed.shape, (200, 200))
        self.assertEqual(processed.dtype, np.uint8)

    def test_missing_model_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = recognition.recognize_attendance(directory, "missing.mp4", "it", "2024")
            self.assertIsNone(result)
    def test_model_bundle_manifest_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            model = os.path.join(directory, "trainer.yml")
            labels = os.path.join(directory, "labels.json")
            manifest = os.path.join(directory, "manifest.json")
            with open(model, "wb") as file:
                file.write(b"model-data")
            with open(labels, "wb") as file:
                file.write(b'{"0":"STU001"}')

            def digest(path):
                with open(path, "rb") as file:
                    return hashlib.sha256(file.read()).hexdigest()

            with open(manifest, "w", encoding="utf-8") as file:
                json.dump({
                    "format_version": 1,
                    "trainer_sha256": digest(model),
                    "labels_sha256": digest(labels),
                }, file)
            self.assertTrue(recognition._verify_model_bundle(model, labels, manifest))

            with open(labels, "wb") as file:
                file.write(b'{"0":"WRONG"}')
            self.assertFalse(recognition._verify_model_bundle(model, labels, manifest))

    def test_training_rejects_multiple_faces(self):
        image = np.full((240, 240, 3), 120, dtype=np.uint8)

        class TwoFaceDetector:
            def detectMultiScale(self, *args, **kwargs):
                return [(10, 10, 100, 100), (120, 10, 100, 100)]

        with patch("modelTrain.cv2.imread", return_value=image):
            self.assertIsNone(modelTrain.process_image("unused.jpg", TwoFaceDetector()))

    def test_training_uses_raw_brightness_before_equalization(self):
        image = np.zeros((240, 240, 3), dtype=np.uint8)

        class OneFaceDetector:
            def detectMultiScale(self, *args, **kwargs):
                return [(20, 20, 180, 180)]

        with patch("modelTrain.cv2.imread", return_value=image):
            self.assertIsNone(modelTrain.process_image("unused.jpg", OneFaceDetector()))

    def test_photo_recognition_returns_suggestion_from_group_photo(self):
        class FakeRecognizer:
            def predict(self, image):
                return 0, 20.0

        class OneFaceDetector:
            def detectMultiScale(self, *args, **kwargs):
                return [(10, 10, 100, 100)]

        fake_image = np.zeros((140, 140, 3), dtype=np.uint8)
        fake_gray = np.full((140, 140), 100, dtype=np.uint8)
        fake_face = np.full((200, 200), 100, dtype=np.uint8)
        with patch.object(recognition, "_load_recognizer", return_value=(FakeRecognizer(), {0: "STU001"})):
            with patch.object(recognition, "_face_cascade", return_value=OneFaceDetector()):
                with patch("recognition.cv2.imread", return_value=fake_image):
                    with patch("recognition.cv2.cvtColor", return_value=fake_gray):
                        with patch("recognition.cv2.equalizeHist", return_value=fake_gray):
                            with patch.object(recognition, "_quality_ok", return_value=True):
                                with patch.object(recognition, "preprocess_face", return_value=fake_face):
                                    result = recognition.recognize_attendance_images(
                                        "/unused", ["photo1.jpg", "photo2.jpg"], "it", "2024"
                                    )
        self.assertEqual(result, ["STU001"])

    def test_live_camera_requires_a_bounded_capture_duration(self):
        with patch.object(recognition, "_load_recognizer", return_value=(object(), {0: "STU001"})):
            with patch("recognition.cv2.VideoCapture") as capture:
                result = recognition.recognize_attendance(
                    "/unused", "rtsp://camera.local/stream", "it", "2024"
                )
        self.assertIsNone(result)
        capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
