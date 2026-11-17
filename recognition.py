"""Conservative Haar Cascade + LBPH attendance recognition.

A student is accepted only after repeated, quality-checked observations in
separate time windows. LBPH distance is a distance (lower is better).
"""
import json
import os
from collections import defaultdict

import cv2
import numpy as np

FACE_SIZE = (200, 200)
DEFAULT_DISTANCE_THRESHOLD = 45.0
DEFAULT_MIN_VOTES = 5
FRAME_SAMPLE_INTERVAL = 5
MIN_FACE_SIZE = 80
MIN_BLUR_VARIANCE = 35.0
MIN_BRIGHTNESS = 35.0
MAX_BRIGHTNESS = 220.0


def _face_cascade():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        raise RuntimeError("Could not load OpenCV Haar face detector")
    return cascade


def preprocess_face(gray_face):
    """Match the training pipeline: grayscale, equalize, resize, equalize."""
    if gray_face is None or gray_face.size == 0:
        return None
    face = cv2.resize(gray_face, FACE_SIZE, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(face)


def _quality_ok(face):
    if face is None or face.size == 0:
        return False
    brightness = float(np.mean(face))
    blur_variance = float(cv2.Laplacian(face, cv2.CV_64F).var())
    return (
        MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS
        and blur_variance >= MIN_BLUR_VARIANCE
    )


def _positive_env_int(name, default, minimum=1):
    try:
        return max(minimum, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def recognize_attendance(root, video_path, branch, batch):
    model_dir = os.path.join(root, "models", str(batch), str(branch))
    model_path = os.path.join(model_dir, "trainer.yml")
    labels_path = os.path.join(model_dir, "labels.json")
    if not os.path.isfile(model_path) or not os.path.isfile(labels_path):
        print("Recognition model or labels map missing. Retrain the model.")
        return []

    try:
        with open(labels_path, "r", encoding="utf-8") as file:
            label_map = {int(key): str(value) for key, value in json.load(file).items()}
        if not label_map:
            print("Labels map is empty. Retrain the model.")
            return []
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
    except Exception as exc:
        print(f"Unable to load trained model: {exc}")
        return []

    if not os.path.isfile(video_path):
        print(f"Video not found: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Unable to open video: {video_path}")
        cap.release()
        return []

    try:
        detector = _face_cascade()
    except Exception as exc:
        print(f"Unable to initialize face detector: {exc}")
        cap.release()
        return []

    threshold = float(os.getenv("LBPH_DISTANCE_THRESHOLD", DEFAULT_DISTANCE_THRESHOLD))
    min_votes = _positive_env_int("LBPH_MIN_VOTES", DEFAULT_MIN_VOTES, 3)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if not np.isfinite(fps) or fps <= 0:
        fps = 25.0

    # One vote per identity per one-second window prevents adjacent frames
    # from being counted as independent evidence.
    votes = defaultdict(dict)
    frame_index = 0
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

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=7,
                minSize=(MIN_FACE_SIZE, MIN_FACE_SIZE),
            )
            time_window = int(frame_index / fps)

            for face_index, (x, y, width, height) in enumerate(faces):
                raw_face = gray[y:y + height, x:x + width]
                if not _quality_ok(raw_face):
                    continue

                crop = preprocess_face(raw_face)
                if crop is None:
                    continue

                try:
                    label, distance = recognizer.predict(crop)
                except cv2.error:
                    continue

                student_id = label_map.get(int(label))
                if student_id is None or not np.isfinite(distance):
                    continue

                if float(distance) > threshold:
                    review_path = os.path.join(
                        review_dir,
                        f"frame_{frame_index}_face_{face_index}.jpg",
                    )
                    cv2.imwrite(review_path, crop)
                    continue

                current = votes[student_id].get(time_window)
                if current is None or float(distance) < current:
                    votes[student_id][time_window] = float(distance)
    finally:
        cap.release()

    accepted = []
    for student_id, window_distances in votes.items():
        distances = list(window_distances.values())
        if len(distances) < min_votes:
            continue
        median_distance = float(np.median(distances))
        if median_distance <= threshold:
            accepted.append(student_id)
        print(
            f"Candidate {student_id}: distinct_windows={len(distances)}, "
            f"median_distance={median_distance:.1f}"
        )

    print(
        f"Recognition complete: sampled_frames={frame_index // FRAME_SAMPLE_INTERVAL}, "
        f"accepted_students={len(accepted)}, threshold={threshold}, "
        f"required_windows={min_votes}"
    )
    return sorted(accepted)
