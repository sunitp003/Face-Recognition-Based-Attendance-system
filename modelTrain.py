import cv2
import os
import numpy as np
from PIL import Image
import re

# Extract roll number from image path (to label images correctly)
def extract_roll_no_from_path(imagePath):
    """
    Extracts the first numeric roll number (6 digits) from the given image path.
    """
    match = re.search(r'\b\d{6}\b', imagePath)  # Extract only 6-digit student roll numbers
    return match.group() if match else None

# Process image for face and eye detection
def process_image(imagePath, padding=60):  # Increased padding from 30 to 60
    roll_no = extract_roll_no_from_path(imagePath)
    if roll_no is None:
        print(f"⚠️ Skipping: {imagePath} (No roll number found)")
        return None, None

    try:
        Id = int(roll_no)
        pilImage = Image.open(imagePath).convert("L")  # Convert image to grayscale
        imageNp = np.array(pilImage, 'uint8')

        # Load Haar Cascade for face and eye detection
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

        # Detect faces in the image
        faces = face_cascade.detectMultiScale(imageNp, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30))

        if len(faces) > 0:
            # Use the first detected face (if multiple faces are found)
            for (x, y, w, h) in faces:
                # Crop the face region
                face_cropped = imageNp[y:y+h, x:x+w]

                # Detect eyes in the face region
                eyes = eye_cascade.detectMultiScale(face_cropped)

                if len(eyes) > 0:
                    # Use the first detected eye to define the region around the face
                    ex, ey, ew, eh = eyes[0]

                    # Adjust the crop to include eyes and some padding around the face
                    x1 = max(x - padding, 0)
                    y1 = max(y - padding, 0)
                    x2 = min(x + w + padding, imageNp.shape[1])
                    y2 = min(y + h + padding, imageNp.shape[0])

                    # Crop the region around the face and eyes with more area
                    face_resized = imageNp[y1:y2, x1:x2]

                    # Resize the cropped face to a fixed size (200x200) for consistency
                    face_resized = cv2.resize(face_resized, (200, 200))
                    
                    return face_resized, Id

        print(f"⚠️ No face detected in: {imagePath}")
        return None, None

    except Exception as e:
        print(f"❌ Error processing {imagePath}: {e}")
        return None, None



# Get all images and labels (face data and roll numbers) from a directory
def getImagesAndLabels(path):
    """
    Extracts face data and numeric IDs from images inside student folders.
    """
    if not os.path.exists(path):
        print(f"❌ Dataset path '{path}' does not exist!")
        return [], []

    imagePaths = [os.path.join(root, file) for root, _, files in os.walk(path) for file in files if file.lower().endswith((".jpg", ".png", ".jpeg"))]

    if len(imagePaths) == 0:
        print(f"⚠️ No images found in '{path}'. Ensure dataset is properly uploaded!")
        return [], []

    print(f"🔍 Found {len(imagePaths)} images in '{path}'")

    faces, Ids = [], []
    for imagePath in imagePaths:
        face, Id = process_image(imagePath)
        if face is not None and Id is not None:
            faces.append(face)
            Ids.append(Id)

    print(f"📋 Unique IDs trained: {sorted(set(Ids))}")
    return faces, Ids


# Example usage for training the model
def TrainImages(root, batch, branch):
    uploads_path = os.path.join(root, "uploads", batch, branch)
    dataset_path = os.path.join(root, "dataset", batch, branch)

    if not os.path.exists(uploads_path):
        print(f"❌ No images found in '{uploads_path}'. Ensure dataset is properly uploaded!")
        return 0

    print(f"🛠 Training data path: {uploads_path}")

    # Ensure dataset directory exists
    os.makedirs(dataset_path, exist_ok=True)

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()  # Older OpenCV versions
    except AttributeError:
        recognizer = cv2.face_LBPHFaceRecognizer.create()  # Newer OpenCV versions

    faces, Ids = getImagesAndLabels(uploads_path)

    if len(faces) > 0 and len(Ids) > 0:
        print(f"🟢 Processing {len(faces)} images for {len(set(Ids))} students...")

        # Save processed images in dataset
        for i, (face, Id) in enumerate(zip(faces, Ids), start=1):
            student_folder = os.path.join(dataset_path, str(Id))
            os.makedirs(student_folder, exist_ok=True)
            face_image_path = os.path.join(student_folder, f"{Id}_{i}.jpg")
            cv2.imwrite(face_image_path, face)
            print(f"✅ Processed face saved: {face_image_path}")

        # Train the recognizer
        recognizer.train(faces, np.array(Ids))

        # Save trained model
        model_path = os.path.join(root, "models", batch, branch)
        os.makedirs(model_path, exist_ok=True)
        recognizer.save(os.path.join(model_path, "trainer.yml"))

        print(f"✅ Model trained successfully! Saved to: {model_path}/trainer.yml")
        return 1
    else:
        print("❌ No valid training data found. Ensure the dataset contains properly labeled images.")
        return 0

# Example usage
if __name__ == "__main__":
    APP_ROOT = "C:/Users/sunit/OneDrive/Desktop/Project_Final_Year/Project_deployment"
    batch = "2025"
    branch = "ce"

    result = TrainImages(APP_ROOT, batch, branch)
    if result == 1:
        print("🎯 Training completed successfully.")
    else:
        print("⚠️ Training failed. Check the dataset for issues.")
