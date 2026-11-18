"""Conservative Haar Cascade + LBPH attendance recognition.

Recognition is advisory only. Faculty must review the complete class list before
attendance is written. Model files are accepted only when their manifest proves
that trainer.yml and labels.json belong to the same training generation.
"""
import hashlib
import json
import logging
import math
import os
from collections import defaultdict

import cv2
import numpy as np

FACE_SIZE = (200, 200)
DEFAULT_DISTANCE_THRESHOLD = 42.0
DEFAULT_MIN_VOTES = 5
FRAME_SAMPLE_INTERVAL = 5
MIN_FACE_SIZE = 80
MIN_BLUR_VARIANCE = 35.0
MIN_BRIGHTNESS = 35.0
MAX_BRIGHTNESS = 220.0


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_model_bundle(model_path, labels_path, manifest_path):
    """Fail closed if model/label files are missing or from different trainings."""
    if not all(os.path.isfile(path) for path in (model_path, labels_path, manifest_path)):
        return False
    try:
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = json.load(file)
        return (
            manifest.get("format_version") == 1
            and manifest.get("trainer_sha256") == _sha256(model_path)
            and manifest.get("labels_sha256") == _sha256(labels_path)
        )
    except (OSError, ValueError, TypeError, AttributeError):
        logging.exception("Could not validate recognition model manifest")
        return False


def _face_cascade():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        raise RuntimeError("Could not load OpenCV Haar face detector")
    return cascade


def preprocess_face(gray_face):
    """Normalize a raw grayscale face exactly as the training pipeline does."""
    if gray_face is None or gray_face.size == 0:
        return None
    face = cv2.resize(gray_face, FACE_SIZE, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(face)


def _quality_ok(face):
    """Assess brightness and blur on the un-equalized camera crop."""
    if face is None or face.size == 0:
        return False
    brightness = float(np.mean(face))
    blur_variance = float(cv2.Laplacian(face, cv2.CV_64F).var())
    return (
        np.isfinite(brightness)
        and np.isfinite(blur_variance)
        and MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS
        and blur_variance >= MIN_BLUR_VARIANCE
    )


def _positive_env_int(name, default, minimum=1):
    try:
        value = int(os.getenv(name, default))
        return max(minimum, value)
    except (TypeError, ValueError):
        logging.warning("Invalid %s; using default %s", name, default)
        return default


def _positive_env_float(name, default, minimum=1.0):
    try:
        value = float(os.getenv(name, default))
        if not math.isfinite(value) or value < minimum:
            raise ValueError("value must be finite and positive")
        return value
    except (TypeError, ValueError):
        logging.warning("Invalid %s; using default %s", name, default)
        return default


def _aggregate_votes(votes, threshold, min_votes):
    """Accept only identities with enough distinct time windows and a safe median."""
    accepted = []
    for student_id, window_distances in votes.items():
        distances = [
            float(distance) for distance in window_distances.values()
            if np.isfinite(distance) and float(distance) <= threshold
        ]
        if len(distances) < min_votes:
            continue
        median_distance = float(np.median(distances))
        if median_distance <= threshold:
            accepted.append(str(student_id))
        logging.info(
            "Candidate %s: distinct_windows=%d median_distance=%.2f",
            student_id, len(distances), median_distance,
        )
    return sorted(set(accepted))


def recognize_attendance(root, video_path, branch, batch):
    model_dir = os.path.join(root, "models", str(batch), str(branch))
    model_path = os.path.join(model_dir, "trainer.yml")
    labels_path = os.path.join(model_dir, "labels.json")
    manifest_path = os.path.join(model_dir, "manifest.json")

    if not _verify_model_bundle(model_path, labels_path, manifest_path):
        logging.error(
            "Recognition model bundle is missing or inconsistent. "
            "Retrain this batch/branch before taking attendance."
        )
        return None

    try:
        with open(labels_path, "r", encoding="utf-8") as file:
            raw_labels = json.load(file)
        if not isinstance(raw_labels, dict) or not raw_labels:
            raise ValueError("labels map must be a non-empty object")
        label_map = {int(key): str(value) for key, value in raw_labels.items()}
        if len(set(label_map.values())) != len(label_map):
            raise ValueError("labels map contains duplicate student IDs")
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
    except Exception:
        logging.exception("Unable to load trained LBPH model")
        return None

    if not os.path.isfile(video_path):
        logging.error("Video not found: %s", video_path)
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error("Unable to open uploaded video")
        cap.release()
        return None

    try:
        detector = _face_cascade()
    except Exception:
        logging.exception("Unable to initialize face detector")
        cap.release()
        return None

    threshold = _positive_env_float(
        "LBPH_DISTANCE_THRESHOLD", DEFAULT_DISTANCE_THRESHOLD, minimum=1.0
    )
    min_votes = _positive_env_int("LBPH_MIN_VOTES", DEFAULT_MIN_VOTES, minimum=3)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if not np.isfinite(fps) or fps <= 0:
        logging.warning("Video FPS metadata unavailable; using conservative 25 FPS fallback")
        fps = 25.0

    votes = defaultdict(dict)
    frame_index = 0
    sampled_frames = 0
    review_dir = os.path.join(
        root, "detected_faces", str(batch), str(branch), "review"
    )
    os.makedirs(review_dir, exist_ok=True)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % FRAME_SAMPLE_INTERVAL:
                continue
            sampled_frames += 1

            raw_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detection_gray = cv2.equalizeHist(raw_gray)
            faces = detector.detectMultiScale(
                detection_gray,
                scaleFactor=1.1,
                minNeighbors=7,
                minSize=(MIN_FACE_SIZE, MIN_FACE_SIZE),
            )
            time_window = int((frame_index - 1) / fps)

            for face_index, (x, y, width, height) in enumerate(faces):
                raw_face = raw_gray[y:y + height, x:x + width]
                if not _quality_ok(raw_face):
                    continue
                crop = preprocess_face(raw_face)
                if crop is None:
                    continue

                try:
                    label, distance = recognizer.predict(crop)
                except cv2.error:
                    logging.exception("LBPH prediction failed for a sampled face")
                    continue

                student_id = label_map.get(int(label))
                if student_id is None or not np.isfinite(distance):
                    continue
                distance = float(distance)
                if distance > threshold:
                    review_path = os.path.join(
                        review_dir, f"frame_{frame_index}_face_{face_index}.jpg"
                    )
                    if not cv2.imwrite(review_path, crop):
                        logging.warning("Could not save rejected face review crop")
                    continue

                current = votes[student_id].get(time_window)
                if current is None or distance < current:
                    votes[student_id][time_window] = distance
    except Exception:
        logging.exception("Video processing failed; no recognition result will be trusted")
        return None
    finally:
        cap.release()

    accepted = _aggregate_votes(votes, threshold, min_votes)
    logging.info(
        "Recognition complete: sampled_frames=%d accepted_students=%d "
        "threshold=%.2f required_windows=%d",
        sampled_frames, len(accepted), threshold, min_votes,
    )
    return accepted
