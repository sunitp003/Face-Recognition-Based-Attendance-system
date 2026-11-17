"""Conservative multi-frame attendance recognition using YuNet + SFace."""
import json
import os
from collections import defaultdict
from datetime import datetime

import cv2
import numpy as np

DETECTOR_RELATIVE_PATH = os.path.join("models", "face_detection_yunet_2023mar.onnx")
RECOGNIZER_RELATIVE_PATH = os.path.join("models", "face_recognition_sface_2021dec.onnx")
DEFAULT_COSINE_THRESHOLD = 0.45
DEFAULT_MIN_MARGIN = 0.06
DEFAULT_MIN_VOTES = 3
FRAME_SAMPLE_INTERVAL = 5


def _load_models(root):
    detector_path = os.path.join(root, DETECTOR_RELATIVE_PATH)
    recognizer_path = os.path.join(root, RECOGNIZER_RELATIVE_PATH)
    if not os.path.isfile(detector_path) or not os.path.isfile(recognizer_path):
        raise FileNotFoundError("Run 'python download_models.py' to fetch YuNet and SFace.")
    detector = cv2.FaceDetectorYN.create(
        detector_path, "", (320, 320), 0.85, 0.3, 5000
    )
    recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")
    return detector, recognizer


def _normalized_feature(image, face_row, recognizer):
    aligned = recognizer.alignCrop(image, face_row)
    feature = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(feature))
    if not np.isfinite(norm) or norm == 0:
        return None
    return feature / norm


def _best_identity(feature, gallery):
    scores = []
    for student_id, samples in gallery.items():
        vectors = np.asarray(samples, dtype=np.float32)
        similarities = vectors @ feature
        # Average the best few enrollment samples to reduce one-photo outliers.
        top = np.sort(similarities)[-min(3, len(similarities)):]
        scores.append((float(np.mean(top)), str(student_id)))
    scores.sort(reverse=True)
    if not scores:
        return None, 0.0, 0.0
    best_score, best_id = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else -1.0
    return best_id, best_score, best_score - second_score


def recognize_attendance(root, video_path, branch, batch):
    model_dir = os.path.join(root, "models", str(batch), str(branch))
    gallery_path = os.path.join(model_dir, "face_embeddings.json")
    if not os.path.isfile(gallery_path) or not os.path.isfile(video_path):
        print("SFace gallery or video is missing.")
        return []

    try:
        with open(gallery_path, "r", encoding="utf-8") as file:
            saved = json.load(file)
        if saved.get("model") != "OpenCV-SFace" or saved.get("version") != 1:
            raise ValueError("Unsupported face gallery format; retrain the model.")
        gallery = {
            str(student_id): np.asarray(vectors, dtype=np.float32)
            for student_id, vectors in saved.get("students", {}).items()
        }
        if not gallery:
            return []
        detector, recognizer = _load_models(root)
    except Exception as exc:
        print(f"Unable to load SFace gallery/models: {exc}")
        return []

    threshold = float(os.getenv("SFACE_COSINE_THRESHOLD", DEFAULT_COSINE_THRESHOLD))
    min_margin = float(os.getenv("SFACE_MIN_MARGIN", DEFAULT_MIN_MARGIN))
    min_votes = int(os.getenv("SFACE_MIN_VOTES", DEFAULT_MIN_VOTES))
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Unable to open video: {video_path}")
        return []

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
            height, width = frame.shape[:2]
            detector.setInputSize((width, height))
            _, faces = detector.detect(frame)
            if faces is None:
                continue
            seen_in_frame = set()
            for face_index, face_row in enumerate(faces):
                try:
                    feature = _normalized_feature(frame, face_row, recognizer)
                    if feature is None:
                        continue
                    student_id, score, margin = _best_identity(feature, gallery)
                except cv2.error:
                    continue
                if student_id is None or score < threshold or margin < min_margin:
                    review_path = os.path.join(
                        review_dir, f"frame_{frame_index}_face_{face_index}.jpg"
                    )
                    x, y, w, h = np.asarray(face_row[:4], dtype=int)
                    crop = frame[max(0, y):max(0, y + h), max(0, x):max(0, x + w)]
                    if crop.size:
                        cv2.imwrite(review_path, crop)
                    continue
                if student_id not in seen_in_frame:
                    votes[student_id].append(score)
                    seen_in_frame.add(student_id)
    finally:
        cap.release()

    accepted = []
    for student_id, scores in votes.items():
        median_score = float(np.median(scores))
        if len(scores) >= min_votes and median_score >= threshold:
            accepted.append(student_id)
        print(
            f"Candidate {student_id}: votes={len(scores)}, "
            f"median_cosine={median_score:.3f}"
        )
    return sorted(accepted)
