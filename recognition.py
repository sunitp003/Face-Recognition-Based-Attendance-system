import os
import cv2
import numpy as np
from datetime import datetime

def recognize_attendance(root, video_path, branch, batch):
    """
    Recognizes faces from a given video using the trained model.

    Args:
        root (str): Root directory of the project.
        video_path (str): Path to the recorded attendance video.
        branch (str): Student's branch.
        batch (str): Student's batch.

    Returns:
        list: List of recognized student IDs.
    """

    # Path to the trained model
    model_path = os.path.join(root, "models", batch, branch, "trainer.yml")

    # Check if model exists
    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        return []

    # Load the model
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"⚠️ Error loading model: {e}")
        return []

    # Load face detection classifier
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return []

    # Open video
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"❌ Failed to open video file: {video_path}")
        return []

    # Get the current date for folder structure
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Set up the base folder path for storing recognized and detected faces
    base_folder = os.path.join(root, "detected_faces", batch, branch, current_date)
    
    # Create necessary directories if they do not exist
    detected_folder = os.path.join(base_folder, "detected")
    recognized_folder = os.path.join(base_folder, "recognized")
    
    os.makedirs(detected_folder, exist_ok=True)
    os.makedirs(recognized_folder, exist_ok=True)

    # Variables for face recognition
    minW = 0.1 * cap.get(3)
    minH = 0.1 * cap.get(4)
    recognized_faces = set()
    recognized_this_session = set()  # Prevent duplicate recognition
    frame_count = 0
    THRESHOLD = 85  # Adjusted threshold for better accuracy (lower for stricter matches)

    while True:
        success, img = cap.read()
        if not success:
            print(f"⚠️ Video ended after {frame_count} frames.")
            break

        frame_count += 1
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Detect faces in the image
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(50, 50))

        for x, y, w, h in faces:
            # Crop face region from the grayscale image
            face_gray = gray[y:y+h, x:x+w]

            # Resize the face region to the fixed size used during training
            face_resized = cv2.resize(face_gray, (200, 200))

            # Predict the ID from the trained model
            try:
                Id, conf = recognizer.predict(face_resized)

                # Save recognized face with ID if confidence is below the threshold
                if conf < THRESHOLD and Id not in recognized_this_session:
                    recognized_faces.add(str(Id))  
                    recognized_this_session.add(Id)  # Prevent duplicate session entries
                    
                    # Save the recognized face in the 'recognized' folder
                    face_filename = os.path.join(recognized_folder, f"recognized_{frame_count}_{Id}.jpg")
                    cv2.imwrite(face_filename, face_resized)
                    print(f"🎯 Recognized Student ID: {Id}, Confidence: {round(conf, 2)} ✅ Accepted")
                else:
                    # Save the face even if not recognized (for later review)
                    face_filename = os.path.join(detected_folder, f"detected_{frame_count}.jpg")
                    cv2.imwrite(face_filename, face_resized)
                    print(f"⚠️ Ignored ID: {Id}, Confidence: {round(conf, 2)} (Above {THRESHOLD})")

            except Exception as e:
                print(f"⚠️ Error during prediction: {e}")

        # Reset the session after every 50 frames to avoid duplicates over long videos
        if frame_count % 50 == 0:
            recognized_this_session.clear()

    cap.release()

    # Return the list of recognized student IDs
    return list(recognized_faces)
