"""Train a balanced LBPH model using Haar Cascade face detection."""
import hashlib
import json
import os

import cv2
import numpy as np

FACE_SIZE = (200, 200)
SUPPORTED_IMAGES = (".jpg", ".jpeg", ".png")
MIN_IMAGES_PER_STUDENT = 5
MAX_IMAGES_PER_STUDENT = 30
MIN_FACE_SIZE = 80
MIN_BLUR_VARIANCE = 35.0
MIN_BRIGHTNESS = 35.0
MAX_BRIGHTNESS = 220.0


def _detector():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        raise RuntimeError("Could not load OpenCV Haar face detector")
    return cascade


def process_image(image_path, detector=None):
    """Return one normalized face, rejecting ambiguous or poor-quality images."""
    image = cv2.imread(image_path)
    if image is None:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    detector = detector or _detector()
    faces = detector.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=6, minSize=(MIN_FACE_SIZE, MIN_FACE_SIZE)
    )

    # Never assign a training image containing multiple faces to one student.
    if len(faces) != 1:
        return None

    x, y, width, height = faces[0]
    face = gray[y:y + height, x:x + width]
    if face.size == 0:
        return None

    brightness = float(np.mean(face))
    blur_variance = float(cv2.Laplacian(face, cv2.CV_64F).var())
    if not (MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS):
        return None
    if blur_variance < MIN_BLUR_VARIANCE:
        return None

    face = cv2.resize(face, FACE_SIZE, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(face)


def getImagesAndLabels(path):
    """Return balanced face arrays, numeric labels and label-to-roll mapping."""
    if not os.path.isdir(path):
        return [], [], {}

    detector = _detector()
    faces, labels, label_map = [], [], {}
    student_dirs = sorted(
        (entry for entry in os.scandir(path) if entry.is_dir()),
        key=lambda entry: entry.name,
    )
    next_label = 0

    for student_dir in student_dirs:
        roll_no = student_dir.name.strip()
        if not roll_no:
            continue

        student_faces = []
        seen_hashes = set()
        for filename in sorted(os.listdir(student_dir.path)):
            if not filename.lower().endswith(SUPPORTED_IMAGES):
                continue
            face = process_image(
                os.path.join(student_dir.path, filename), detector
            )
            if face is None:
                continue

            digest = hashlib.sha256(face.tobytes()).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            student_faces.append(face)

            # Limit per-student samples so one student's larger ZIP does not
            # dominate the model's nearest-histogram matching.
            if len(student_faces) >= MAX_IMAGES_PER_STUDENT:
                break

        if len(student_faces) < MIN_IMAGES_PER_STUDENT:
            print(
                f"Skipping {roll_no}: {len(student_faces)} usable unique images; "
                f"{MIN_IMAGES_PER_STUDENT} required."
            )
            continue

        label_map[str(next_label)] = roll_no
        faces.extend(student_faces)
        labels.extend([next_label] * len(student_faces))
        print(f"Training {roll_no}: {len(student_faces)} usable images.")
        next_label += 1

    return faces, labels, label_map


def TrainImages(root, batch, branch):
    """Train and safely replace the model only after successful training."""
    uploads_path = os.path.join(root, "uploads", str(batch), str(branch))
    model_dir = os.path.join(root, "models", str(batch), str(branch))
    if not os.path.isdir(uploads_path):
        print(f"Training folder not found: {uploads_path}")
        return 0

    try:
        faces, labels, label_map = getImagesAndLabels(uploads_path)
        if not faces or not label_map:
            print("No students have enough valid, unique, single-face images.")
            return 0

        recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        recognizer.train(faces, np.asarray(labels, dtype=np.int32))

        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "trainer.yml")
        labels_path = os.path.join(model_dir, "labels.json")
        temporary_model = os.path.join(model_dir, "trainer.tmp.yml")
        temporary_labels = os.path.join(model_dir, "labels.tmp.json")

        recognizer.save(temporary_model)
        with open(temporary_labels, "w", encoding="utf-8") as file:
            json.dump(label_map, file, indent=2)

        # Keep the previous trained model intact if preprocessing/training fails.
        os.replace(temporary_model, model_path)
        os.replace(temporary_labels, labels_path)

        print(
            f"Model trained: {len(faces)} images, {len(label_map)} students. "
            f"Saved to {model_dir}"
        )
        return 1
    except Exception as exc:
        print(f"Training failed: {exc}")
        for filename in ("trainer.tmp.yml", "labels.tmp.json"):
            temporary_path = os.path.join(model_dir, filename)
            if os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass
        return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train attendance face model")
    parser.add_argument("root")
    parser.add_argument("batch")
    parser.add_argument("branch")
    args = parser.parse_args()
    raise SystemExit(0 if TrainImages(args.root, args.batch, args.branch) else 1)
