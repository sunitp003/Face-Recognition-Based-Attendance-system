"""Train an LBPH model using a consistent, deterministic face pipeline."""
import json
import os
import shutil

import cv2
import numpy as np

FACE_SIZE = (200, 200)
SUPPORTED_IMAGES = (".jpg", ".jpeg", ".png")


def _detector():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        raise RuntimeError("Could not load OpenCV Haar face detector")
    return cascade


def process_image(image_path, detector=None):
    image = cv2.imread(image_path)
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    detector = detector or _detector()
    faces = detector.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    # Multiple people in a registration photo make its label ambiguous.
    if len(faces) != 1:
        return None
    x, y, w, h = faces[0]
    face = gray[y:y + h, x:x + w]
    face = cv2.resize(face, FACE_SIZE, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(face)


def getImagesAndLabels(path):
    """Return face arrays, numeric model labels, and an index-to-roll mapping."""
    if not os.path.isdir(path):
        return [], [], {}

    detector = _detector()
    faces, labels, label_map = [], [], {}
    student_dirs = sorted(
        (entry for entry in os.scandir(path) if entry.is_dir()),
        key=lambda entry: entry.name
    )
    next_label = 0
    for student_dir in student_dirs:
        roll_no = student_dir.name.strip()
        if not roll_no:
            continue
        student_faces = []
        for filename in sorted(os.listdir(student_dir.path)):
            if not filename.lower().endswith(SUPPORTED_IMAGES):
                continue
            face = process_image(os.path.join(student_dir.path, filename), detector)
            if face is not None:
                student_faces.append(face)
        # Do not create a model class from one or two accidental detections.
        if len(student_faces) < 3:
            print(f"Skipping {roll_no}: only {len(student_faces)} usable images (need 3).")
            continue
        label_map[str(next_label)] = roll_no
        faces.extend(student_faces)
        labels.extend([next_label] * len(student_faces))
        next_label += 1

    return faces, labels, label_map


def TrainImages(root, batch, branch):
    uploads_path = os.path.join(root, "uploads", str(batch), str(branch))
    model_dir = os.path.join(root, "models", str(batch), str(branch))
    if not os.path.isdir(uploads_path):
        print(f"Training folder not found: {uploads_path}")
        return 0

    try:
        faces, labels, label_map = getImagesAndLabels(uploads_path)
        if not faces or not label_map:
            print("No student has at least 3 valid, single-face training images.")
            return 0

        recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        recognizer.train(faces, np.asarray(labels, dtype=np.int32))
        os.makedirs(model_dir, exist_ok=True)
        recognizer.save(os.path.join(model_dir, "trainer.yml"))
        with open(os.path.join(model_dir, "labels.json"), "w", encoding="utf-8") as file:
            json.dump(label_map, file, indent=2)
        print(
            f"Model trained: {len(faces)} images, {len(label_map)} students. "
            f"Saved to {model_dir}"
        )
        return 1
    except Exception as exc:
        print(f"Training failed: {exc}")
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train attendance face model")
    parser.add_argument("root")
    parser.add_argument("batch")
    parser.add_argument("branch")
    args = parser.parse_args()
    raise SystemExit(0 if TrainImages(args.root, args.batch, args.branch) else 1)
