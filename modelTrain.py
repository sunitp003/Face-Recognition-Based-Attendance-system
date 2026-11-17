"""Build a student face-embedding gallery with OpenCV YuNet + SFace.

Unlike the legacy LBPH model, SFace produces normalized embeddings and compares
them with cosine similarity. Every enrollment photo must contain exactly one face.
"""
import json
import os

import cv2
import numpy as np

FACE_DETECTOR_PATH = os.path.join("models", "face_detection_yunet_2023mar.onnx")
FACE_RECOGNIZER_PATH = os.path.join("models", "face_recognition_sface_2021dec.onnx")
MIN_IMAGES_PER_STUDENT = 3


def _load_models(root):
    detector_path = os.path.join(root, FACE_DETECTOR_PATH)
    recognizer_path = os.path.join(root, FACE_RECOGNIZER_PATH)
    missing = [p for p in (detector_path, recognizer_path) if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError(
            "Face models missing. Run 'python download_models.py'. Missing: "
            + ", ".join(missing)
        )
    detector = cv2.FaceDetectorYN.create(
        detector_path, "", (320, 320), 0.85, 0.3, 5000
    )
    recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")
    return detector, recognizer


def _extract_embedding(image, detector, recognizer):
    if image is None or image.size == 0:
        return None
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    if faces is None or len(faces) != 1:
        return None
    aligned = recognizer.alignCrop(image, faces[0])
    feature = recognizer.feature(aligned)
    vector = np.asarray(feature, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0:
        return None
    return (vector / norm).tolist()


def getImagesAndLabels(path, detector, recognizer):
    """Return a mapping of exact roll numbers to normalized face embeddings."""
    gallery = {}
    if not os.path.isdir(path):
        return gallery

    for student_dir in sorted(os.scandir(path), key=lambda item: item.name):
        if not student_dir.is_dir():
            continue
        roll_no = student_dir.name.strip()
        if not roll_no:
            continue
        embeddings = []
        for filename in sorted(os.listdir(student_dir.path)):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            image = cv2.imread(os.path.join(student_dir.path, filename))
            embedding = _extract_embedding(image, detector, recognizer)
            if embedding is not None:
                embeddings.append(embedding)
        if len(embeddings) >= MIN_IMAGES_PER_STUDENT:
            gallery[roll_no] = embeddings
        else:
            print(
                f"Skipping {roll_no}: {len(embeddings)} valid single-face images; "
                f"need at least {MIN_IMAGES_PER_STUDENT}."
            )
    return gallery


def TrainImages(root, batch, branch):
    uploads_path = os.path.join(root, "uploads", str(batch), str(branch))
    if not os.path.isdir(uploads_path):
        print(f"Training folder not found: {uploads_path}")
        return 0
    try:
        detector, recognizer = _load_models(root)
        gallery = getImagesAndLabels(uploads_path, detector, recognizer)
        if not gallery:
            print("No students have enough valid enrollment images.")
            return 0
        model_dir = os.path.join(root, "models", str(batch), str(branch))
        os.makedirs(model_dir, exist_ok=True)
        output_path = os.path.join(model_dir, "face_embeddings.json")
        temporary_path = output_path + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(
                {"model": "OpenCV-SFace", "version": 1, "students": gallery},
                file,
                separators=(",", ":"),
            )
        os.replace(temporary_path, output_path)
        print(
            f"Created SFace gallery for {len(gallery)} students at {output_path}"
        )
        return 1
    except Exception as exc:
        print(f"Training failed: {exc}")
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build an SFace attendance gallery")
    parser.add_argument("root")
    parser.add_argument("batch")
    parser.add_argument("branch")
    args = parser.parse_args()
    raise SystemExit(0 if TrainImages(args.root, args.batch, args.branch) else 1)
