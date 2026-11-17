"""Conservative video face recognition for attendance.

LBPH is a distance-based recognizer (lower is better). A single frame is never
sufficient to mark a student present: predictions are aggregated over sampled
frames and uncertain identities are rejected.
"""
import json
import os
from collections import defaultdict
from datetime import datetime

import cv2
import numpy as np

FACE_SIZE = (200, 200)
DEFAULT_DISTANCE_THRESHOLD = 55.0
DEFAULT_MIN_VOTES = 3
DEFAULT_MIN_VOTE_RATIO = 0.60
FRAME_SAMPLE_INTERVAL = 5


def _face_cascade():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        raise RuntimeError("Could not load OpenCV Haar face detector")
    return cascade


def preprocess_face(gray_face):
    """Use the exact same grayscale/equalization/size pipeline at train and test."""
    if gray_face is None or gray_face.size == 0:
        return None
    face = cv2.resize(gray_face, FACE_SIZE, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(face)


def recognize_attendance(root, video_path, branch, batch):
    model_dir = os.path.join(root, "models", str(batch), str(branch))
    model_path = os.path.join(model_dir, "trainer.yml")
    labels_path = os.path.join(model_dir, "labels.json")
    if not os.path.isfile(model_path) or not os.path.isfile(labels_path):
        print("Recognition model or labels map missing. Retrain the model.")
        return []

    try:
        with open(labels_path, "r", encoding="utf-8") as file:
            label_map = {int(k): str(v) for k, v in json.load(file).items()}
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
        return []

    detector = _face_cascade()
    threshold = float(os.getenv("LBPH_DISTANCE_THRESHOLD", DEFAULT_DISTANCE_THRESHOLD))
    min_votes = int(os.getenv("LBPH_MIN_VOTES", DEFAULT_MIN_VOTES))
    min_ratio = float(os.getenv("LBPH_MIN_VOTE_RATIO", DEFAULT_MIN_VOTE_RATIO))
    votes = defaultdict(list)
    frame_index = 0
    today = datetime.now().strftime("%Y-%m-%d")
    review_dir = os.path.join(root, "detected_faces", str(batch), str(branch), today, "review")
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
                gray, scaleFactor=1.1, minNeighbors=6, minSize=(80, 80)
            )
            seen_in_frame = set()
            for face_index, (x, y, w, h) in enumerate(faces):
                crop = preprocess_face(gray[y:y + h, x:x + w])
                if crop is None:
                    continue
                try:
                    label, distance = recognizer.predict(crop)
                except cv2.error:
                    continue
                student_id = label_map.get(int(label))
                if student_id is None or not np.isfinite(distance):
                    continue
                # Keep evidence for human review; do not treat it as a positive match.
                if distance > threshold:
                    review_path = os.path.join(
                        review_dir, f"frame_{frame_index}_face_{face_index}.jpg"
                    )
                    cv2.imwrite(review_path, crop)
                    continue
                if student_id not in seen_in_frame:
                    votes[student_id].append(float(distance))
                    seen_in_frame.add(student_id)
    finally:
        cap.release()

    accepted = []
    for student_id, distances in votes.items():
        # Require repeated independent observations, not one lucky frame.
        if len(distances) < min_votes:
            continue
        vote_ratio = len(distances) / max(1, sum(len(v) for v in votes.values()))
        median_distance = float(np.median(distances))
        if median_distance <= threshold and vote_ratio >= min_ratio:
            accepted.append(student_id)
        print(
            f"Candidate {student_id}: votes={len(distances)}, "
            f"median_distance={median_distance:.1f}, ratio={vote_ratio:.2f}"
        )

    return sorted(accepted)
