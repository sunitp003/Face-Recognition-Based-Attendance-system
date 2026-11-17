"""Optional Haar Cascade dataset-preparation helpers.

The active LBPH training path reads student images from uploads/ directly.
These helpers remain available for older workflows and use the same 200x200
grayscale normalization as modelTrain.py.
"""
import hashlib
import logging
import os

import cv2
import numpy as np

SUPPORTED_IMAGES = (".jpg", ".jpeg", ".png")
FACE_SIZE = (200, 200)


def _detector():
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if detector.empty():
        raise RuntimeError("Could not load OpenCV Haar face detector")
    return detector


def process_image(image_path, padding=30):
    """Return one normalized face and its numeric roll number, if available."""
    try:
        roll_no = os.path.basename(os.path.dirname(image_path)).strip()
        if not roll_no.isdigit():
            return None, None

        image = cv2.imread(image_path)
        if image is None:
            return None, None

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = _detector().detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=6, minSize=(60, 60)
        )
        if len(faces) != 1:
            return None, None

        x, y, width, height = faces[0]
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(gray.shape[1], x + width + padding)
        y2 = min(gray.shape[0], y + height + padding)
        face = gray[y1:y2, x1:x2]
        if face.size == 0:
            return None, None

        face = cv2.resize(face, FACE_SIZE, interpolation=cv2.INTER_AREA)
        return cv2.equalizeHist(face), int(roll_no)
    except (OSError, ValueError, cv2.error) as exc:
        logging.warning("Could not process image %s: %s", image_path, exc)
        return None, None


def face_detect(path, roll, branch, batch, root):
    """Prepare unique face crops for one student; return 1 only if any are saved."""
    if not os.path.isdir(path):
        return 0

    target_dir = os.path.join(root, "dataset", str(batch), str(branch), str(roll))
    os.makedirs(target_dir, exist_ok=True)
    seen = set()
    saved = 0

    for filename in sorted(os.listdir(path)):
        if not filename.lower().endswith(SUPPORTED_IMAGES):
            continue
        face, _ = process_image(os.path.join(path, filename))
        if face is None:
            continue

        digest = hashlib.sha256(face.tobytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        output_path = os.path.join(target_dir, f"{roll}_{saved + 1}.jpg")
        if cv2.imwrite(output_path, face):
            saved += 1

    return 1 if saved else 0
